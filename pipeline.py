import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List as TList, Optional
from audio_utils import duration_seconds
from subtitle_utils import group_words_by_count, extract_audio_for_transcription, transcribe_audio, generate_ass_file
from video_utils import list_videos, pick_segments_to_cover, list_images, pick_image_segments_to_cover
import random
import hashlib
import time
import tempfile
import os
import glob
from ffmpeg_utils import run, get_ffmpeg_path


def get_cache_dir() -> Path:
    """Retorna o diretório de cache na raiz do projeto.

    Returns:
        Path: Caminho para o diretório cache/ na raiz do projeto.
    """
    # Obtém a raiz do projeto (mesmo nível deste arquivo: pipeline.py)
    project_root = Path(__file__).parent
    cache_dir = project_root / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


class FilterBuilder:
    """Centraliza a construção de filtros complexos do FFmpeg."""

    def __init__(self) -> None:
        self.filters: TList[str] = []
        self.current_output: Optional[str] = None
        self.video_duration: float = 0
        self.audio_duration: float = 0
        self.used_labels: set = set()

    def add_filter(self, filter_str: str) -> None:
        self.filters.append(filter_str)

    def set_output(self, output_label: str) -> str:
        if output_label in self.used_labels:
            base_label = output_label.strip('[]')
            counter = 1
            while f"[{base_label}_{counter}]" in self.used_labels:
                counter += 1
            output_label = f"[{base_label}_{counter}]"
        self.current_output = output_label
        self.used_labels.add(output_label)
        return output_label

    def get_filter_complex(self) -> str:
        return ";".join(self.filters) if self.filters else ""

    def save_to_file(self) -> str:
        filter_complex = self.get_filter_complex()
        with tempfile.NamedTemporaryFile(mode='w', suffix='_filter.txt', delete=False, encoding='utf-8') as f:
            f.write(filter_complex)
            return f.name

    def clear(self) -> None:
        self.filters = []
        self.current_output = None
        self.used_labels.clear()


class PipelineStage(ABC):
    @abstractmethod
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        pass


class VideoBaseStage(PipelineStage):
    """Estágio base: seleciona segmentos, chama o cache apropriado e gera concat."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        narration_path = ctx["narration_path"]
        videos_folder = ctx["videos_folder"]
        seed = ctx["seed"]
        shuffle = ctx["shuffle"]
        fps = ctx["fps"]
        width = ctx["width"]
        height = ctx["height"]
        video_mode = ctx["video_mode"]
        image_segment_duration = ctx.get("image_segment_duration", 10.0)

        narration = Path(narration_path)
        folder = Path(videos_folder)
        if not narration.exists():
            raise FileNotFoundError(f"Narração não encontrada: {narration}")
        if not folder.is_dir():
            raise FileNotFoundError(f"Pasta inválida: {folder}")

        audio_dur = duration_seconds(narration)
        ctx["audio_duration"] = audio_dur

        safety_margin = 2.0
        transition = ctx.get("transition_type", "none")
        transition_duration = 1.0

        # --- INÍCIO DA CORREÇÃO LÓGICA ---
        # A seleção de segmentos já está correta, mas vamos garantir que a duração total
        # seja calculada de forma precisa para o modo de imagens.

        if video_mode == "videos":
            vids = list_videos(folder)
            if not vids:
                raise FileNotFoundError(f"Nenhum vídeo em: {folder}")
            num_transitions = max(0, int(audio_dur / 10) - 1) if transition != "none" else 0
            extra_duration = num_transitions * transition_duration
            total_duration = audio_dur + extra_duration + safety_margin
            segments = pick_segments_to_cover(total_duration, vids, seed=seed, shuffle=shuffle)
        else:  # images
            imgs = list_images(folder)
            if not imgs:
                raise FileNotFoundError(f"Nenhuma imagem em: {folder}")

            # Calcula quantos segmentos de imagem são necessários para cobrir a duração do áudio.
            # A função `pick_image_segments_to_cover` já faz isso, então podemos confiar nela.
            extra = max(0, int(audio_dur / image_segment_duration) - 1) * 1.5 if transition != "none" else 0
            total_duration_needed = audio_dur + extra + safety_margin
            segments = pick_image_segments_to_cover(total_duration_needed, imgs, image_segment_duration, seed=seed,
                                                    shuffle=shuffle)

        segments = [s for s in segments if s[1] > 0.01]
        if not segments:
            raise ValueError("Nenhum segmento válido encontrado após a seleção.")
        ctx["segments"] = segments

        # A chamada de cache está correta
        cache_ctx = ctx.copy()
        if video_mode == "videos":
            cache_ctx = MediaCacheStage()(cache_ctx)
        else:
            cache_ctx = ImageCacheStage()(cache_ctx)

        ctx["cached_media"] = cache_ctx["cached_media"]
        cached = ctx["cached_media"]

        # Monta inputs e o arquivo concat.txt CORRETAMENTE
        inputs = ["-y", "-hide_banner", "-loglevel", "error", "-fflags", "+genpts", "-i", str(narration)]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding='utf-8') as f:
            concat_file = f.name
            print("--- Gerando arquivo de concatenação (concat.txt) ---")

            # AQUI ESTÁ A CORREÇÃO: Iteramos sobre a lista 'segments' que contém
            # a sequência correta de imagens/vídeos.
            for src, take in segments:
                path = cached.get(src)
                if not path:
                    raise ValueError(f"Mídia não encontrada no cache: {src}")

                path_str = str(Path(path).resolve()).replace("\\", "/")
                f.write(f"file '{path_str}'\n")
                print(f"Adicionado ao concat: {Path(path).name}")

                # A diretiva 'duration' só é necessária para clipes de vídeo,
                # pois os clipes de imagem já são criados com a duração exata.
                if video_mode == "videos":
                    f.write(f"duration {take:.3f}\n")
            print("----------------------------------------------------")

        # --- FIM DA CORREÇÃO LÓGICA ---

        inputs += ["-f", "concat", "-safe", "0", "-i", concat_file]
        ctx["concat_file"] = concat_file

        ctx.update({
            "inputs": inputs,
            "filter_builder": FilterBuilder(),
            "video_input_idx": 1,
            "audio_idx": 0
        })
        return ctx


class TransitionStage(PipelineStage):
    """Estágio de transições corrigido para usar 'trim' em vez de 'split'."""

    SUPPORTED_TRANSITIONS = [
        "fade", "wipeleft", "wiperight", "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
        "dissolve", "pixelize", "hblur", "fadegrays"
    ]

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        transition = ctx.get("transition_type", "none")
        fb = ctx["filter_builder"]
        segments = ctx["segments"]
        audio_dur = ctx["audio_duration"]
        fps = ctx.get("fps", 30)
        video_input_idx = ctx["video_input_idx"]

        num_segments = len(segments)

        # --- INÍCIO DA CORREÇÃO LÓGICA ---

        # Abandona o filtro 'split'. Em vez disso, vamos usar 'trim' para cortar
        # cada segmento do vídeo principal concatenado.

        labels = []
        current_time = 0.0
        for i, (src, take) in enumerate(segments):
            start = current_time
            end = current_time + take
            segment_label = f"v{i + 1}"

            # Pega o fluxo de vídeo principal [1:v] e corta o segmento correto.
            fb.add_filter(
                f"[{video_input_idx}:v]trim=start={start:.4f}:end={end:.4f},setpts=PTS-STARTPTS[{segment_label}]")

            labels.append(segment_label)
            current_time = end

        # --- FIM DA CORREÇÃO LÓGICA ---

        # Se só um segmento ou sem transição
        if transition == "none" or num_segments < 2:
            # Neste caso, não precisamos dos trims individuais. Apenas pegamos o vídeo principal.
            # Limpa os filtros de trim que acabamos de adicionar.
            fb.filters = []
            # E apenas faz um trim final para a duração do áudio.
            fb.add_filter(f"[{video_input_idx}:v]trim=duration={audio_dur}[vout]")
            fb.set_output("[vout]")
            ctx["map_out"] = "[vout]"
            return ctx

        # Prepara uniformização (settb, fps, format) para cada segmento CORTADO
        clean = []
        for idx, l in enumerate(labels, start=1):
            cl = f"vc{idx}"
            fb.add_filter(f"[{l}]settb=AVTB,fps={fps},format=yuv420p[{cl}]")
            clean.append(cl)

        # Lógica de transição xfade (permanece a mesma e agora funcionará corretamente)
        prev, prev_dur = clean[0], segments[0][1]
        for i in range(1, len(clean)):
            ttype = transition if transition != "random" else random.choice(self.SUPPORTED_TRANSITIONS)
            curr, curr_dur = clean[i], segments[i][1]
            offset = max(0, prev_dur - 1.0)
            out = f"trans{i}"
            fb.add_filter(f"[{prev}][{curr}]xfade=transition={ttype}:duration=1:offset={offset}[{out}]")
            prev, prev_dur = out, prev_dur + curr_dur - 1.0

        # Garante a duração exata e formata o fluxo final
        final_video_out = "[vout]"
        fb.add_filter(f"[{prev}]trim=duration={audio_dur},format=yuv420p,setsar=1{final_video_out}")

        fb.set_output(final_video_out)
        ctx["map_out"] = final_video_out

        return ctx


class OverlayStage(PipelineStage):
    """Overlay melhorado com duração garantida e resolução dinâmica."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not ctx.get("overlay"):
            return ctx
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        overlay = ctx["overlay"]
        overlay_opacity = ctx["overlay_opacity"]
        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]

        # --- INÍCIO DA CORREÇÃO DEFINITIVA ---
        # Pega a largura e altura DIRETAMENTE do contexto.
        # Se não estiverem lá, algo está errado no início do pipeline e deve falhar.
        width = ctx["width"]
        height = ctx["height"]
        # --- FIM DA CORREÇÃO DEFINITIVA ---

        map_out = ctx["map_out"]
        audio_duration = ctx["audio_duration"]

        overlay_idx = sum(1 for x in inputs if x == "-i")
        inputs += ["-stream_loop", "-1", "-t", str(audio_duration), "-i", str(overlay)]

        # O filtro de overlay agora usa a resolução correta do projeto.
        overlay_filter = (
            f"[{overlay_idx}:v]format=rgba,scale={width}:{height}:flags=lanczos,"
            f"colorchannelmixer=aa={overlay_opacity}[ol];"
            f"{map_out}[ol]overlay=0:0:format=auto[vfinal]"
        )

        filter_builder.add_filter(overlay_filter)
        filter_builder.set_output("[vfinal]")
        ctx["inputs"] = inputs
        ctx["map_out"] = "[vfinal]"
        return ctx


class LogoStage(PipelineStage):
    """Estágio de logo adaptado para FilterBuilder, respeitando a resolução."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not ctx.get("logo"):
            return ctx
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        logo = ctx["logo"]
        logo_scale = ctx.get("logo_scale", 0.15)
        logo_position = ctx.get("logo_position", "top_right")
        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        map_out = ctx["map_out"]

        # --- INÍCIO DA CORREÇÃO ---
        # Pega a largura e altura do contexto para garantir consistência.
        width = ctx["width"]
        height = ctx["height"]
        # --- FIM DA CORREÇÃO ---

        logo_idx = sum(1 for x in inputs if x == "-i")
        inputs += ["-i", str(logo)]

        pos_map = {
            "top_left": (20, 20),
            "top_center": (f"(main_w-overlay_w)/2", 20),
            "top_right": (f"main_w-overlay_w-20", 20),
            "bottom_left": (20, f"main_h-overlay_h-20"),
            "bottom_center": (f"(main_w-overlay_w)/2", f"main_h-overlay_h-20"),
            "bottom_right": (f"main_w-overlay_w-20", f"main_h-overlay_h-20"),
            "center": (f"(main_w-overlay_w)/2", f"(main_h-overlay_h)/2"),
        }
        logo_x, logo_y = pos_map.get(logo_position, (20, 20))

        # O filtro agora está ciente da resolução do projeto, embora não a defina diretamente.
        # Isso ajuda na negociação de filtros do FFmpeg.
        logo_filter = (
            f"[{logo_idx}:v]scale=iw*{logo_scale}:ih*{logo_scale}:flags=lanczos[logo];"
            f"{map_out}[logo]overlay=x={logo_x}:y={logo_y}:format=auto[vlogo]"
        )

        filter_builder.add_filter(logo_filter)
        filter_builder.set_output("[vlogo]")
        ctx["inputs"] = inputs
        ctx["map_out"] = "[vlogo]"
        return ctx


class ChromaStage(PipelineStage):
    """Estágio de chroma key adaptado para FilterBuilder"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        chroma_list = ctx.get("chroma_list")
        if not chroma_list and ctx.get("chroma"):
            chroma_list = [{"path": ctx["chroma"], "scale": ctx.get("chroma_scale", 0.5),
                            "position": ctx.get("chroma_position", "bottom_right"),
                            "start": ctx.get("chroma_start", 0)}]
        if not chroma_list:
            return ctx
        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        map_out = ctx["map_out"]
        pos_map = {
            "top_left": (20, 20), "top_center": (f"(main_w-overlay_w)/2", 20),
            "top_right": (f"main_w-overlay_w-20", 20),
            "bottom_left": (20, f"main_h-overlay_h-20"),
            "bottom_center": (f"(main_w-overlay_w)/2", f"main_h-overlay_h-20"),
            "bottom_right": (f"main_w-overlay_w-20", f"main_h-overlay_h-20"),
            "center": (f"(main_w-overlay_w)/2", f"(main_h-overlay_h)/2"),
        }
        last_map = map_out
        for chroma in chroma_list:
            chroma_path = chroma["path"]
            chroma_scale = chroma.get("scale", 0.5)
            chroma_position = chroma.get("position", "bottom_right")
            chroma_start = chroma.get("start", 0)
            chroma_duration = duration_seconds(Path(chroma_path))
            chroma_end = chroma_start + chroma_duration
            chroma_idx = sum(1 for x in inputs if x == "-i")
            inputs += ["-i", str(chroma_path)]
            chroma_x, chroma_y = pos_map.get(chroma_position, (20, 20))
            chroma_filter = (
                f"[{chroma_idx}:v]trim=start=0:end={chroma_duration},setpts=PTS+{chroma_start}/TB,"
                f"colorkey=0x00FF00:0.3:0.2,scale=iw*{chroma_scale}:ih*{chroma_scale}:flags=lanczos[chroma{chroma_idx}];"
                f"{last_map}[chroma{chroma_idx}]overlay=x={chroma_x}:y={chroma_y}:"
                f"enable='between(t,{chroma_start},{chroma_end})':format=auto[vchroma{chroma_idx}]"
            )
            filter_builder.add_filter(chroma_filter)
            last_map = f"[vchroma{chroma_idx}]"
        filter_builder.set_output(last_map)
        ctx["inputs"] = inputs
        ctx["map_out"] = last_map
        return ctx


class CinematicStage(PipelineStage):
    """Aplica efeitos cinematográficos adaptado para FilterBuilder"""
    CINEMATIC_PRESETS = {
        "warm": {"lut": "warm_lut"}, "cold": {"lut": "cold_lut"}, "vintage": {"lut": "vintage_lut"},
        "cinematic": {"lut": "cinematic_lut"}
    }

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        cinematic_preset = ctx.get("cinematic_preset")
        if not cinematic_preset:
            return ctx
        filter_builder = ctx["filter_builder"]
        map_out = ctx["map_out"]
        cinematic_filters = []
        if cinematic_preset in self.CINEMATIC_PRESETS:
            preset = self.CINEMATIC_PRESETS[cinematic_preset]
            if preset.get("lut") == "warm_lut":
                cinematic_filters.append("colortemperature=temperature=3200")
            elif preset.get("lut") == "cold_lut":
                cinematic_filters.append("colortemperature=temperature=7000")
            elif preset.get("lut") == "vintage_lut":
                cinematic_filters.append(
                    "colorchannelmixer=rr=0.393:rg=0.769:rb=0.189:gr=0.349:gg=0.686:gb=0.168:br=0.272:bg=0.534:bb=0.131")
            elif preset.get("lut") == "cinematic_lut":
                cinematic_filters.append("eq=contrast=1.2:brightness=0.05:saturation=0.9")
        if cinematic_filters:
            cinematic_chain = ",".join(cinematic_filters)
            cinematic_out = "[vcinematic]"
            cinematic_filter = f"{map_out}{cinematic_chain}{cinematic_out}"
            filter_builder.add_filter(cinematic_filter)
            filter_builder.set_output(cinematic_out)
            ctx["map_out"] = cinematic_out
        return ctx


class VignetteStage(PipelineStage):
    """
    Domain-driven implementation of vignette effect stage.

    This stage applies a vignette effect (edge darkening) using proper FFmpeg syntax
    and domain validation through the VignetteEffect value object.
    """

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # Domain rule: Only execute if vignette is enabled
        if not ctx.get("enable_vignette"):
            return ctx

        print("Aplicando efeito de vinheta...")

        filter_builder = ctx["filter_builder"]
        map_out = ctx["map_out"]

        try:
            # Create domain object with validation
            from models import VignetteEffect

            intensity = ctx.get("vignette_intensity", 0.3)
            vignette_effect = VignetteEffect(intensity=intensity)

            # Generate valid FFmpeg filter using domain object
            vignette_filter = vignette_effect.to_ffmpeg_filter(map_out, "[vvignette]")

            filter_builder.add_filter(vignette_filter)

            # Update pipeline context
            new_map_out = "[vvignette]"
            filter_builder.set_output(new_map_out)
            ctx["map_out"] = new_map_out

        except ValueError as e:
            print(f"Erro na configuração do vinheta: {e}")
            # Skip vignette if configuration is invalid
            pass
        except Exception as e:
            print(f"Erro inesperado ao aplicar vinheta: {e}")
            # Skip vignette on any other error
            pass

        return ctx


class SubtitleStage(PipelineStage):
    """Estágio de legendas adaptado para FilterBuilder"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not ctx.get("enable_subtitles"):
            return ctx
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        narration_path = ctx["narration_path"]
        subtitle_font_size = ctx.get("subtitle_font_size", 24)
        subtitle_color = ctx.get("subtitle_color", "white")
        subtitle_position = ctx.get("subtitle_position", "bottom_center")
        subtitle_font = ctx.get("subtitle_font", "Noto Sans")
        words_per_subtitle = ctx.get("words_per_subtitle", 1)
        vosk_model_path = ctx.get("vosk_model_path", "_internal/vosk_models/vosk-model-pt")
        filter_builder = ctx["filter_builder"]
        map_out = ctx["map_out"]

        width = ctx.get("width")
        height = ctx.get("height")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio, \
                tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as temp_ass:
            temp_audio_path = temp_audio.name
            ass_file_path = temp_ass.name
        try:
            extract_audio_for_transcription(narration_path, temp_audio_path)
            segments = transcribe_audio(temp_audio_path, vosk_model_path)
            if segments:
                alignment_map = {"bottom_center": 2, "bottom_left": 1, "bottom_right": 3, "center": 5, "top_left": 7,
                                 "top_center": 8, "top_right": 9}
                alignment = alignment_map.get(subtitle_position, 2)
                color_ass_map = {"white": "&H00FFFFFF&", "yellow": "&H0000FFFF&", "red": "&H000000FF&",
                                 "blue": "&H00FF0000&", "green": "&H0000FF00&", "black": "&H00000000&"}
                color_ass = color_ass_map.get(subtitle_color, "&H00FFFFFF&")
                grouped = group_words_by_count(segments, words_per_subtitle)
                outline_color_ass = color_ass_map.get(ctx.get("subtitle_outline_color", "black"), "&H00000000&")
                generate_ass_file(grouped, ass_file_path, font=subtitle_font, size=subtitle_font_size, color=color_ass,
                                  outline_color=outline_color_ass, outline=ctx.get("subtitle_outline_width", 2),
                                  shadow=ctx.get("subtitle_shadow_x", 2), alignment=alignment,
                                  playres_x=width, playres_y=height)
                ass_path_escaped = str(Path(ass_file_path)).replace('\\', '\\\\').replace(':', '\\:')
                subtitle_filter = f"{map_out}subtitles=filename='{ass_path_escaped}'[vsubtitles]"
                filter_builder.add_filter(subtitle_filter)
                ctx["map_out"] = "[vsubtitles]"
                ctx["subtitle_file"] = ass_file_path
        finally:
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
        return ctx


class ImageCacheStage(PipelineStage):
    """Pré-renderiza imagens em vídeos curtos para cache com efeito Ken Burns CONFIÁVEL."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        segments = ctx.get("segments", [])
        if not segments:
            ctx["cached_media"] = {}
            return ctx

        unique_sources = sorted(list(set(s[0] for s in segments)))

        print(f"Iniciando pré-renderização de cache para imagens com efeito Ken Burns (Método Confiável)...")
        start_time = time.time()

        # Usa o diretório de cache na raiz do projeto
        cache_dir = get_cache_dir()

        image_segment_duration = ctx["image_segment_duration"]
        fps = ctx["fps"]
        width = ctx["width"]
        height = ctx["height"]
        encoder_config = ctx.get("encoder_config", {})

        cached_media = {}
        total_images = len(unique_sources)

        for i, src_path_str in enumerate(unique_sources):
            img_path = Path(src_path_str)

            # Verifica se Ken Burns está habilitado no contexto
            enable_ken_burns = ctx.get("enable_ken_burns", True)

            # Inclui o status do Ken Burns no hash para gerar caches diferentes
            img_config = f"{src_path_str}_{width}x{height}_{fps}fps_{image_segment_duration}s_kenburns_{enable_ken_burns}_v4"
            img_hash = hashlib.md5(img_config.encode()).hexdigest()[:12]
            cached_video_path = cache_dir / f"img_{img_hash}.mp4"

            cached_media[src_path_str] = str(cached_video_path)

            if cached_video_path.exists():
                status = "com Ken Burns" if enable_ken_burns else "estática"
                print(f"Cache encontrado ({i + 1}/{total_images}) - {status}: {img_path.name}")
                continue

            status = "com Ken Burns" if enable_ken_burns else "estática"
            print(f"Pré-renderizando imagem ({i + 1}/{total_images}) - {status}: {img_path.name}")
            img_start = time.time()

            self._prerender_image(img_path, cached_video_path, image_segment_duration, fps, width, height,
                                  encoder_config, enable_ken_burns)

            img_time = time.time() - img_start
            print(f"Concluído em {img_time:.1f}s")

        total_time = time.time() - start_time
        print(f"Cache Ken Burns finalizado em {total_time:.1f}s - {total_images} imagens processadas")

        ctx["cached_media"] = cached_media
        return ctx

    def _prerender_image(self, img_path, output_path, duration, fps, width, height, encoder_config, enable_ken_burns=True):
        """Renderiza uma imagem em vídeo com ou sem efeito Ken Burns."""

        if enable_ken_burns:
            # --- EFEITO KEN BURNS HABILITADO ---
            zoom_level = 1.20  # Zoom de 120%

            # Dimensões da imagem após o zoom
            scaled_w = int(width * zoom_level)
            scaled_h = int(height * zoom_level)

            # 't' é o tempo em segundos, 'duration' é a duração total do clipe.
            # A expressão t/duration vai de 0.0 a 1.0 ao longo do clipe.
            effects = [
                # Esquerda -> Direita: A posição X do corte move-se de 0 até a borda direita.
                {'x': f'(iw-ow)*(t/{duration})', 'y': '(ih-oh)/2'},

                # Direita -> Esquerda: A posição X do corte move-se da borda direita para 0.
                {'x': f'(iw-ow)*(1-(t/{duration}))', 'y': '(ih-oh)/2'},

                # Cima -> Baixo: A posição Y do corte move-se de 0 até a borda inferior.
                {'x': '(iw-ow)/2', 'y': f'(ih-oh)*(t/{duration})'},

                # Baixo -> Cima: A posição Y do corte move-se da borda inferior para 0.
                {'x': '(iw-ow)/2', 'y': f'(ih-oh)*(1-(t/{duration}))'},
            ]

            effect = random.choice(effects)
            pan_x = effect['x']
            pan_y = effect['y']

            # Filtro de vídeo usando a técnica scale/crop
            video_filter = (
                # 1. Aplica um zoom inicial na imagem.
                f"scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase,"
                # 2. Corta uma janela que se move sobre a imagem ampliada.
                f"crop=w={width}:h={height}:x='{pan_x}':y='{pan_y}'"
            )
        else:
            # --- EFEITO KEN BURNS DESABILITADO - IMAGEM ESTÁTICA ---
            video_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"

        cmd = [
            get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", f"{duration:.3f}", "-i", str(img_path),
            "-vf", video_filter
        ]

        codec = encoder_config.get("codec", "libx264")
        cmd.extend(["-c:v", codec])

        gop = max(int(fps * 2), 2)
        cmd += ["-pix_fmt", "yuv420p", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"]

        if "nvenc" in codec:
            if "cq" in encoder_config: cmd.extend(["-cq", encoder_config["cq"]])
            if "preset" in encoder_config: cmd.extend(["-preset", encoder_config["preset"]])
            if "tune" in encoder_config: cmd.extend(["-tune", encoder_config["tune"]])
        else:
            if "preset" in encoder_config: cmd.extend(["-preset", encoder_config["preset"]])
            if "crf" in encoder_config: cmd.extend(["-crf", encoder_config["crf"]])

        if "threads" in encoder_config:
            cmd.extend(["-threads", encoder_config["threads"]])

        cmd.extend(["-r", str(fps), "-an", str(output_path)])
        run(cmd)


class MediaCacheStage(PipelineStage):
    """Pré-renderiza mídias (vídeos) em cache para resolução uniforme."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # --- INÍCIO DA CORREÇÃO ---
        # Pega a largura e altura DIRETAMENTE do contexto, sem valores padrão.
        width = ctx["width"]
        height = ctx["height"]
        print(f"  - Resolução lida pelo MediaCacheStage: {width}x{height}")
        # --- FIM DA CORREÇÃO ---

        segments = ctx.get("segments", [])
        if not segments:
            ctx["cached_media"] = {}
            return ctx

        # Usa o diretório de cache na raiz do projeto
        cache_dir = get_cache_dir()

        fps = ctx["fps"]
        encoder_config = ctx.get("encoder_config", {})
        cached = {}

        unique_sources = sorted(list(set(s[0] for s in segments)))

        for src in unique_sources:
            stem = Path(src).stem
            out = cache_dir / f"{stem}_{width}x{height}.mp4"
            cached[src] = str(out)

            if not out.exists():
                print(f"Criando cache para: {Path(src).name} em {width}x{height}")
                vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
                      f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1")
                cmd = [get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vf", vf, "-an"]
                cmd += ["-r", str(fps)]
                codec = encoder_config.get("codec", "libx264")
                cmd += ["-c:v", codec]
                gop = max(int(fps * 2), 2)
                cmd += ["-pix_fmt", "yuv420p", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"]
                if "nvenc" in codec:
                    if "cq" in encoder_config: cmd += ["-cq", encoder_config["cq"]]
                    if "preset" in encoder_config: cmd += ["-preset", encoder_config["preset"]]
                    if "tune" in encoder_config: cmd += ["-tune", encoder_config["tune"]]
                else:
                    if "preset" in encoder_config: cmd += ["-preset", encoder_config["preset"]]
                    if "crf" in encoder_config: cmd += ["-crf", encoder_config["crf"]]
                if "threads" in encoder_config:
                    cmd += ["-threads", encoder_config["threads"]]
                cmd += [str(out)]
                run(cmd)

        ctx["cached_media"] = cached
        return ctx


class EncoderStage(PipelineStage):
    """Configura encoder, resolução e parâmetros de qualidade"""
    RESOLUTION_PRESETS = {
        "horizontal_1080p": (1920, 1080),
        "horizontal_720p": (1280, 720),
        "vertical_1080p": (1080, 1920),
    }

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        resolution_preset = ctx.get("resolution_preset", "horizontal_1080p")

        # Only override resolution if preset is not "custom" and exists in presets
        if resolution_preset != "custom" and resolution_preset in self.RESOLUTION_PRESETS:
            ctx["width"], ctx["height"] = self.RESOLUTION_PRESETS[resolution_preset]
            print(f"  - Resolução ajustada pelo preset '{resolution_preset}': {ctx['width']}x{ctx['height']}")
        else:
            print(f"  - Usando resolução personalizada: {ctx['width']}x{ctx['height']}")

        encoder = ctx.get("encoder", "libx264")
        performance_profile = ctx.get("performance_profile", "quality")
        threads = ctx.get("threads", 0)
        gpu_quality = ctx.get("gpu_quality", 18)
        ctx["encoder_config"] = self._get_encoder_config(encoder, performance_profile, threads, gpu_quality)
        return ctx

    def _get_encoder_config(self, encoder, performance_profile, threads, gpu_quality):
        config = {}
        if encoder == "libx264":
            config.update({"codec": "libx264", "preset": "slow" if performance_profile == "quality" else "ultrafast",
                           "crf": "18" if performance_profile == "quality" else "23"})
        elif encoder == "h264_nvenc":
            config.update({"codec": "h264_nvenc", "cq": str(gpu_quality),
                           "preset": "p7" if performance_profile == "quality" else "p1",
                           "tune": "hq" if performance_profile == "quality" else "ll"})
        if threads > 0:
            config["threads"] = str(threads)
        return config


class BackgroundMusicStage(PipelineStage):
    """Estágio que adiciona trilha de fundo ao áudio"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        background_music = ctx.get("background_music")
        if not background_music:
            return ctx
        music_path = Path(background_music)
        if not music_path.exists():
            print(f"Aviso: Arquivo de música de fundo não encontrado: {background_music}")
            return ctx
        print(f"Adicionando trilha de fundo: {background_music}")
        inputs = ctx["inputs"]
        music_idx = sum(1 for x in inputs if x == "-i")
        inputs.extend(["-i", str(music_path)])
        ctx["background_music_idx"] = music_idx
        ctx["inputs"] = inputs
        return ctx


class OutputStage(PipelineStage):
    """Estágio de saída com filter_complex centralizado"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        print("Iniciando renderização final...")
        start_time = time.time()

        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        map_out = ctx["map_out"]
        audio_idx = ctx["audio_idx"]
        out_path = ctx["out_path"]
        encoder_config = ctx.get("encoder_config", {})
        audio_duration = ctx["audio_duration"]

        # Determina o mapeamento de áudio correto
        audio_map = f"[{audio_idx}]" if isinstance(audio_idx, str) else f"[{audio_idx}:a]"

        # Processamento de áudio com música de fundo, se houver
        background_music_idx = ctx.get("background_music_idx")
        background_music_volume = ctx.get("background_music_volume", 0.2)

        if background_music_idx is not None:
            main_audio_ref = audio_map
            out_audio_label = "[aout_bg]"
            audio_filter = (
                f"[{background_music_idx}:a]aloop=loop=-1:size=2e+09,"
                f"volume={background_music_volume}[bg];"
                f"{main_audio_ref}[bg]amix=inputs=2:duration=first:"
                f"dropout_transition=2{out_audio_label}"
            )
            filter_builder.add_filter(audio_filter)
            audio_map = out_audio_label

        # Salva filter_complex em arquivo temporário
        filter_file = filter_builder.save_to_file()
        print(f"Filter complex salvo em: {filter_file}")

        # Monta comando FFmpeg
        cmd = [get_ffmpeg_path()] + inputs
        cmd += ["-filter_complex_script", filter_file]
        cmd += ["-map", map_out]
        cmd += ["-map", audio_map]

        # Configurações de vídeo
        codec = encoder_config.get("codec", "libx264")
        cmd += ["-c:v", codec]
        if "nvenc" in codec:
            if "cq" in encoder_config: cmd += ["-cq", encoder_config["cq"]]
            if "preset" in encoder_config: cmd += ["-preset", encoder_config["preset"]]
            if "tune" in encoder_config: cmd += ["-tune", encoder_config["tune"]]
        else:
            if "preset" in encoder_config: cmd += ["-preset", encoder_config["preset"]]
            if "crf" in encoder_config: cmd += ["-crf", encoder_config["crf"]]
        if "threads" in encoder_config:
            cmd += ["-threads", encoder_config["threads"]]

        fps = ctx.get("fps", 30)
        gop = max(int(fps * 2), 2)
        cmd += [
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-avoid_negative_ts", "make_zero",
            "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"
        ]

        # Configurações de áudio e saída
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100"]
        cmd += ["-t", str(audio_duration)]
        cmd += [str(out_path)]

        # Executa renderização
        try:
            print("Executando renderização...")
            run(cmd)
        finally:
            # Limpeza de arquivos temporários
            if os.path.exists(filter_file):
                os.unlink(filter_file)
                print(f"Arquivo de filtro removido: {filter_file}")
            if ctx.get("subtitle_file") and os.path.exists(ctx["subtitle_file"]):
                os.unlink(ctx["subtitle_file"])
            if ctx.get("concat_file") and os.path.exists(ctx["concat_file"]):
                os.unlink(ctx["concat_file"])

        total_time = time.time() - start_time
        print(f"Renderização final concluída em {total_time:.1f}s")
        ctx["render_time"] = total_time

        return ctx


class EndingStage(PipelineStage):
    """Adiciona vídeo de encerramento, usando a MediaCacheStage para garantir a resolução correta."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        ending_video_path = ctx.get("ending_video_path")
        if not ending_video_path:
            return ctx

        print(f"Adicionando vídeo de encerramento: {ending_video_path}")

        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        map_out = ctx["map_out"]
        audio_idx = ctx["audio_idx"]

        ending_duration = duration_seconds(ending_video_path)

        # Prepara um contexto temporário para a MediaCacheStage
        cache_ctx = ctx.copy()
        cache_ctx["segments"] = [(ending_video_path, ending_duration)]
        cache_ctx["video_mode"] = "videos"

        # Chama a MediaCacheStage para processar APENAS o vídeo de encerramento.
        cached_ctx = MediaCacheStage()(cache_ctx)
        cached_ending_video_path = cached_ctx["cached_media"].get(ending_video_path)

        if not cached_ending_video_path or not Path(cached_ending_video_path).exists():
            raise RuntimeError(f"Falha ao criar o cache para o vídeo de encerramento: {ending_video_path}")

        # Adiciona os inputs necessários
        original_ending_idx = sum(1 for x in inputs if x == "-i")
        inputs.extend(["-i", str(ending_video_path)])

        cached_ending_idx = sum(1 for x in inputs if x == "-i")
        inputs.extend(["-i", str(cached_ending_video_path)])

        # Define os labels para os filtros
        main_video_ref = map_out
        ending_video_ref = f"[{cached_ending_idx}:v]"
        ending_audio_ref = f"[{original_ending_idx}:a]"

        # Concatena os fluxos corretos
        video_concat = f"{main_video_ref}{ending_video_ref}concat=n=2:v=1:a=0[vfinal_ending]"

        main_audio_ref = f"[{audio_idx}]" if isinstance(audio_idx, str) else f"[{audio_idx}:a]"
        audio_concat = f"{main_audio_ref}{ending_audio_ref}concat=n=2:v=0:a=1[afinal_ending]"

        filter_builder.add_filter(video_concat)
        filter_builder.add_filter(audio_concat)

        # Atualiza o contexto
        ctx["inputs"] = inputs
        ctx["map_out"] = "[vfinal_ending]"
        ctx["audio_idx"] = "afinal_ending"
        ctx["audio_duration"] += ending_duration

        return ctx


class OpeningStage(PipelineStage):
    """Estágio que adiciona vídeos de abertura, respeitando a resolução do projeto."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        print(f"  - Resolução: {ctx['width']}x{ctx['height']}")
        opening_video_paths = ctx.get("opening_video_paths", [])
        if not opening_video_paths:
            return ctx

        print(f"Adicionando {len(opening_video_paths)} vídeo(s) de abertura")

        fb = ctx["filter_builder"]
        map_out = ctx.get("map_out", "[vout]")
        audio_duration = ctx["audio_duration"]

        # --- INÍCIO DA CORREÇÃO ---
        # Pega a largura e altura do contexto para usar no redimensionamento.
        width = ctx["width"]
        height = ctx["height"]
        # --- FIM DA CORREÇÃO ---

        opening_total_duration = 0
        opening_labels = []
        inputs = ctx["inputs"]

        for i, path in enumerate(opening_video_paths):
            if not os.path.exists(path):
                print(f"Aviso: Arquivo de abertura não encontrado: {path}")
                continue

            video_idx = sum(1 for x in inputs if x == "-i")
            inputs.extend(["-i", str(path)])

            try:
                duration = duration_seconds(path)
            except Exception as e:
                print(f"Aviso: Não foi possível obter a duração de {path}. Usando 5 segundos. Erro: {e}")
                duration = 5.0

            opening_total_duration += duration
            in_lbl = f"{video_idx}:v"
            out_lbl = f"opening_{i}"

            # --- INÍCIO DA CORREÇÃO ---
            # Usa as variáveis width e height para redimensionar o vídeo de abertura.
            fb.add_filter(
                f"[{in_lbl}]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[{out_lbl}]"
            )
            # --- FIM DA CORREÇÃO ---

            opening_labels.append(out_lbl)

        ctx["inputs"] = inputs

        if not opening_labels:
            return ctx

        if len(opening_labels) > 1:
            concat_lbls = "".join(f"[{l}]" for l in opening_labels)
            fb.add_filter(f"{concat_lbls}concat=n={len(opening_labels)}:v=1:a=0[opening_concat]")
            opening_output = "opening_concat"
        else:
            opening_output = opening_labels[0]

        map_out_clean = map_out.strip("[]")

        # Ajusta a duração do vídeo principal para dar espaço à abertura
        adjusted_duration = max(0.1, audio_duration)  # O vídeo principal deve ter a duração da narração

        # O vídeo principal já tem a duração correta, não precisa de trim aqui.
        # Apenas concatenamos a abertura com o vídeo principal.
        fb.add_filter(f"[{opening_output}][{map_out_clean}]concat=n=2:v=1:a=0[vout_with_opening]")

        # A duração total do vídeo agora é a abertura + narração.
        ctx["audio_duration"] += opening_total_duration
        ctx["map_out"] = "[vout_with_opening]"

        return ctx


class MediaPipeline:
    """Pipeline principal para processamento de mídia"""

    def __init__(self, stages: TList[PipelineStage]):
        self.stages = stages

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        total_stages = len(self.stages)
        progress_callback = ctx.get("progress_callback")
        for i, stage in enumerate(self.stages):
            stage_name = stage.__class__.__name__
            print(f"--- Executando estágio: {stage_name} ---")
            ctx = stage(ctx)
            if progress_callback:
                progress = int((i + 1) / total_stages * 100)
                progress_callback(progress)
        return ctx
