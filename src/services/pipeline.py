from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List as TList, Optional

import random
import hashlib
import time
import tempfile
import os
import glob

# Local (relative) imports
from .audio_utils import duration_seconds
from .subtitle_utils import (
    group_words_by_count,
    extract_audio_for_transcription,
    transcribe_audio,
    generate_ass_file,
)
from .video_utils import (
    list_videos,
    pick_segments_to_cover,
    list_images,
    pick_image_segments_to_cover,
)
from .ffmpeg_utils import run, get_ffmpeg_path


class FilterBuilder:
    """Centraliza a construção de filtros complexos do FFmpeg.

    Atributos:
        filters (list[str]): Lista de strings de filtro.
        current_output (Optional[str]): Rótulo de saída atual.
        video_duration (float): Duração do vídeo.
        audio_duration (float): Duração do áudio.
        used_labels (set): Conjunto de rótulos de saída usados.
    """

    def __init__(self) -> None:
        self.filters: TList[str] = []
        self.current_output: Optional[str] = None
        self.video_duration: float = 0
        self.audio_duration: float = 0
        self.used_labels: set = set()

    def add_filter(self, filter_str: str) -> None:
        """Adiciona um filtro à cadeia.

        Args:
            filter_str (str): String de filtro do FFmpeg.
        """
        self.filters.append(filter_str)

    def set_output(self, output_label: str) -> str:
        """Define um rótulo de saída único e registra seu uso.

        Args:
            output_label (str): Rótulo de saída desejado.

        Returns:
            str: Rótulo de saída único.
        """
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
        """Obtém a string filter_complex completa.

        Returns:
            str: String filter_complex concatenada.
        """
        return ";".join(self.filters) if self.filters else ""

    def save_to_file(self) -> str:
        """Salva o filter_complex em um arquivo temporário e retorna seu caminho.

        Returns:
            str: Caminho para o arquivo filter_complex temporário.
        """
        filter_complex = self.get_filter_complex()
        with tempfile.NamedTemporaryFile(mode='w', suffix='_filter.txt', delete=False, encoding='utf-8') as f:
            f.write(filter_complex)
            return f.name

    def clear(self) -> None:
        """Limpa todos os filtros e redefine o estado."""
        self.filters = []
        self.current_output = None
        self.used_labels.clear()


class PipelineStage(ABC):
    @abstractmethod
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        pass


class VideoBaseStage(PipelineStage):
    """Estágio base: seleciona segmentos, chama cache e gera concat + trim/scale+pad."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # Contexto
        narration_path = ctx["narration_path"]
        videos_folder = ctx["videos_folder"]
        seed = ctx["seed"]
        shuffle = ctx["shuffle"]
        fps = ctx["fps"]
        width = ctx["width"]
        height = ctx["height"]
        video_mode = ctx["video_mode"]
        image_segment_duration = ctx["image_segment_duration"]

        # Validação
        narration = Path(narration_path)
        folder = Path(videos_folder)
        if not narration.exists():
            raise FileNotFoundError(f"Narração não encontrada: {narration}")
        if not folder.is_dir():
            raise FileNotFoundError(f"Pasta inválida: {folder}")

        # Duração do áudio
        audio_dur = duration_seconds(narration)
        ctx["audio_duration"] = audio_dur

        # Seleção de segmentos
        safety_margin = 2.0
        transition = ctx.get("transition_type", "none")
        if video_mode == "videos":
            vids = list_videos(folder)
            if not vids:
                raise FileNotFoundError(f"Nenhum vídeo em: {folder}")
            extra = (len(vids)-1)*1.5 if transition!="none" and len(vids)>1 else 0
            total = audio_dur + extra + safety_margin
            segments = pick_segments_to_cover(total, vids, seed=seed, shuffle=shuffle)
        else:
            imgs = list_images(folder)
            if not imgs:
                raise FileNotFoundError(f"Nenhuma imagem em: {folder}")
            extra = max(0, int(audio_dur/image_segment_duration)-1)*1.5 if transition!="none" else 0
            total = audio_dur + extra + safety_margin
            segments = pick_image_segments_to_cover(total, imgs, image_segment_duration, seed=seed, shuffle=shuffle)

        # Filtra segmentos curtos
        segments = [s for s in segments if s[1] > 0.01]
        if not segments:
            raise ValueError("Todos os segmentos são muito curtos")
        ctx["segments"] = segments

        # Gera cache para imagens ou vídeos
        ctx = MediaCacheStage()(ctx)
        cached = ctx["cached_media"]

        # Monta inputs e concat file
        # ALTERAÇÃO: adicionar -fflags +genpts ANTES do primeiro -i para garantir PTS válidos
        inputs = ["-y", "-hide_banner", "-loglevel", "error", "-fflags", "+genpts", "-i", str(narration)]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            concat_file = f.name
            for src, take in segments:
                path = cached.get(src, src)
                # Usa o caminho absoluto do arquivo cached diretamente
                path = str(Path(path).resolve()).replace("\\", "/")
                f.write(f"file '{path}'\n")
                f.write(f"duration {take:.3f}\n")
        inputs += ["-f", "concat", "-safe", "0", "-i", concat_file]
        ctx["concat_file"] = concat_file

        # Trim + scale+pad
        fb = FilterBuilder()
        fb.audio_duration = audio_dur
        labels = []
        t = 0.0
        for i, (_, take) in enumerate(segments, start=1):
            in_lbl, out_lbl, seg_lbl = "1:v", f"v{i}", f"v{i}s"
            labels.append(seg_lbl)
            fb.add_filter(f"[{in_lbl}]trim=start={t:.3f}:end={t+take:.3f},setpts=PTS-STARTPTS[{out_lbl}]")
            fb.add_filter(
                f"[{out_lbl}]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[{seg_lbl}]"
            )
            t += take

        # Atualiza contexto
        ctx.update({
            "inputs": inputs,
            "filter_builder": fb,
            "segment_labels": labels,
            "video_input_idx": 1,
            "audio_idx": 0
        })
        return ctx


class TransitionStage(PipelineStage):
    """Estágio de transições melhorado com correção de duração"""

    SUPPORTED_TRANSITIONS = [
        "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
        "slideleft", "slideright", "slideup", "slidedown",
        "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite",
        "radial", "smoothleft", "smoothright", "smoothup", "smoothdown",
        "circleopen", "circleclose", "vertopen", "vertclose",
        "horzopen", "horzclose", "dissolve", "pixelize",
        "diagtl", "diagtr", "diagbl", "diagbr", "hlslice", "hrslice",
        "vuslice", "vdslice", "hblur", "fadegrays", "wipetl", "wipetr",
        "wipebl", "wipebr", "squeezeh", "squeezev", "zoomin", "fadefast",
        "fadeslow", "hlwind", "hrwind", "vuwind", "vdwind", "coverleft",
        "coverright", "coverup", "coverdown", "revealleft", "revealright",
        "revealup", "revealdown"
    ]

    LIGHT_TRANSITIONS = [
        "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
        "slideleft", "slideright", "slideup", "slidedown", "dissolve"
    ]

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        transition = ctx.get("transition_type", "none")
        fb = ctx["filter_builder"]
        labels = ctx["segment_labels"]
        audio_dur = ctx["audio_duration"]
        fps = ctx.get("fps", 30)

        # Se só um segmento ou sem transição
        if transition == "none" or len(labels) < 2:
            concat_lbls = "".join(f"[{l}]" for l in labels)
            # Adiciona um trim para garantir a duração exata mesmo sem transições
            fb.add_filter(f"{concat_lbls}concat=n={len(labels)}:v=1:a=0,trim=duration={audio_dur}[vout]")
            fb.set_output("[vout]")
            ctx["map_out"] = "[vout]"
            return ctx

        # Prepara uniformização
        clean = []
        for idx, l in enumerate(labels, start=1):
            cl = f"vc{idx}"
            fb.add_filter(f"[{l}]settb=AVTB,fps={fps},format=yuv420p[{cl}]")
            clean.append(cl)

        prev, prev_dur = clean[0], ctx["segments"][0][1]
        for i in range(1, len(clean)):
            ttype = transition if transition != "random" else random.choice(self.SUPPORTED_TRANSITIONS)
            curr, curr_dur = clean[i], ctx["segments"][i][1]
            offset = max(prev_dur - 1, 0)
            out = f"trans{i}"
            fb.add_filter(f"[{prev}][{curr}]xfade=transition={ttype}:duration=1:offset={offset}[{out}]")
            prev, prev_dur = out, prev_dur + curr_dur - 1

        # Garante a duração exata e formata o fluxo final
        final_video_out = "[vout]"
        fb.add_filter(f"[{prev}]trim=duration={audio_dur},format=yuv420p,setsar=1{final_video_out}")

        fb.set_output(final_video_out)
        ctx["map_out"] = final_video_out

        return ctx


class OverlayStage(PipelineStage):
    """Overlay melhorado com duração garantida"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not ctx.get("overlay"):
            return ctx

        overlay = ctx["overlay"]
        overlay_opacity = ctx["overlay_opacity"]
        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        width = ctx.get("width", 1920)
        height = ctx.get("height", 1080)
        map_out = ctx["map_out"]
        audio_duration = ctx["audio_duration"]

        # Calcula o índice ANTES de adicionar o novo input
        overlay_idx = sum(1 for x in inputs if x == "-i")
        inputs += ["-stream_loop", "-1", "-t", str(audio_duration), "-i", str(overlay)]

        overlay_filter = (
            f"[{overlay_idx}:v]format=rgba,scale={width}:{height},"
            f"colorchannelmixer=aa={overlay_opacity}[ol];"
            f"{map_out}[ol]overlay=0:0:format=auto[vfinal]"
        )
        filter_builder.add_filter(overlay_filter)
        filter_builder.set_output("[vfinal]")

        ctx["inputs"] = inputs
        ctx["map_out"] = "[vfinal]"

        return ctx


class LogoStage(PipelineStage):
    """Estágio de logo adaptado para FilterBuilder"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not ctx.get("logo"):
            return ctx

        logo = ctx["logo"]
        logo_scale = ctx.get("logo_scale", 0.15)
        logo_position = ctx.get("logo_position", "top_right")
        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        map_out = ctx["map_out"]

        # Calcula o índice ANTES de adicionar o novo input
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

        logo_filter = (
            f"[{logo_idx}:v]scale=iw*{logo_scale}:ih*{logo_scale}[logo];"
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
        chroma_list = ctx.get("chroma_list")
        # Compatibilidade: se não houver chroma_list, usa o chroma único
        if not chroma_list and ctx.get("chroma"):
            chroma_list = [{
                "path": ctx["chroma"],
                "scale": ctx.get("chroma_scale", 0.5),
                "position": ctx.get("chroma_position", "bottom_right"),
                "start": ctx.get("chroma_start", 0)
            }]

        if not chroma_list:
            return ctx

        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        map_out = ctx["map_out"]

        pos_map = {
            "top_left": (20, 20),
            "top_center": (f"(main_w-overlay_w)/2", 20),
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

            # Calcula o índice ANTES de adicionar o novo input
            chroma_idx = sum(1 for x in inputs if x == "-i")
            inputs += ["-i", str(chroma_path)]

            chroma_x, chroma_y = pos_map.get(chroma_position, (20, 20))

            chroma_filter = (
                f"[{chroma_idx}:v]trim=start=0:end={chroma_duration},setpts=PTS+{chroma_start}/TB,"
                f"colorkey=0x00FF00:0.3:0.2,scale=iw*{chroma_scale}:ih*{chroma_scale}[chroma{chroma_idx}];"
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
        "warm": {
            "lut": "warm_lut",
            "curves": "r=0.5/(1+(exp(10*(0.5-x)))):g=0.3/(1+(exp(10*(0.3-x)))):b=0.1/(1+(exp(10*(0.1-x))))",
            "vignette": "PI/4+random(1)*PI/50':x0=W/2:y0=H/2"
        },
        "cold": {
            "lut": "cold_lut",
            "curves": "r=0.1/(1+(exp(10*(0.1-x)))):g=0.3/(1+(exp(10*(0.3-x)))):b=0.7/(1+(exp(10*(0.7-x))))",
            "vignette": "PI/4+random(1)*PI/50':x0=W/2:y0=H/2"
        },
        "vintage": {
            "lut": "vintage_lut",
            "curves": "r=0.393*r+0.769*g+0.189*b:g=0.349*r+0.686*g+0.168*b:b=0.272*r+0.534*g+0.131*b",
            "vignette": "PI/3+random(1)*PI/30':x0=W/2:y0=H/2"
        },
        "cinematic": {
            "lut": "cinematic_lut",
            "curves": "master=0.00392*val:shadows=0.5:midtones=1.0:highlights=0.8",
            "vignette": "PI/5+random(1)*PI/40':x0=W/2:y0=H/2"
        }
    }

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        cinematic_preset = ctx.get("cinematic_preset")
        custom_lut = ctx.get("custom_lut_path")
        enable_vignette = ctx.get("enable_vignette", False)
        vignette_intensity = ctx.get("vignette_intensity", 0.3)
        enable_curves = ctx.get("enable_curves", False)
        custom_curves = ctx.get("custom_curves")

        if not any([cinematic_preset, custom_lut, enable_vignette, enable_curves]):
            return ctx

        filter_builder = ctx["filter_builder"]
        map_out = ctx["map_out"]

        cinematic_filters = []

        # Aplicar LUT
        if custom_lut and Path(custom_lut).exists():
            cinematic_filters.append(f"lut3d='{custom_lut}'")
        elif cinematic_preset and cinematic_preset in self.CINEMATIC_PRESETS:
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

        # Aplicar curves
        curves_filter = None
        if custom_curves:
            curves_filter = f"curves={custom_curves}"
        elif cinematic_preset and cinematic_preset in self.CINEMATIC_PRESETS:
            preset_curves = self.CINEMATIC_PRESETS[cinematic_preset].get("curves")
            if preset_curves and enable_curves:
                if "master=" in preset_curves:
                    curves_filter = f"eq=gamma={preset_curves.split('master=')[1].split(':')[0]}"
                else:
                    curves_filter = f"curves={preset_curves}"

        if curves_filter:
            cinematic_filters.append(curves_filter)

        # Aplicar vignette
        if enable_vignette:
            angle_value = vignette_intensity * 3.14159 / 4
            cinematic_filters.append(f"vignette=angle={angle_value}")

        if cinematic_filters:
            cinematic_chain = ",".join(cinematic_filters)
            cinematic_out = "[vcinematic]"
            cinematic_filter = f"{map_out}{cinematic_chain}{cinematic_out}"
            filter_builder.add_filter(cinematic_filter)
            filter_builder.set_output(cinematic_out)
            ctx["map_out"] = cinematic_out

        return ctx


class SubtitleStage(PipelineStage):
    """Estágio de legendas adaptado para FilterBuilder"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if not ctx.get("enable_subtitles"):
            return ctx

        narration_path = ctx["narration_path"]
        subtitle_font_size = ctx.get("subtitle_font_size", 24)
        subtitle_color = ctx.get("subtitle_color", "white")
        subtitle_position = ctx.get("subtitle_position", "bottom_center")
        subtitle_font = ctx.get("subtitle_font", "Noto Sans")
        words_per_subtitle = ctx.get("words_per_subtitle", 1)
        vosk_model_path = ctx.get("vosk_model_path", "_internal/vosk_models/vosk-model-pt")

        filter_builder = ctx["filter_builder"]
        map_out = ctx["map_out"]

        # Extrai áudio temporário para transcrição
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_audio_path = temp_audio.name

        # Arquivo ASS temporário
        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False) as temp_ass:
            ass_file_path = temp_ass.name

        try:
            extract_audio_for_transcription(narration_path, temp_audio_path)
            segments = transcribe_audio(temp_audio_path, vosk_model_path)

            if segments:
                # Converte posição para alignment ASS
                alignment_map = {
                    "bottom_center": 2,
                    "bottom_left": 1,
                    "bottom_right": 3,
                    "center": 5,
                    "top_left": 7,
                    "top_center": 8,
                    "top_right": 9
                }
                alignment = alignment_map.get(subtitle_position, 2)

                # Converte cor para formato ASS (BGR)
                color_ass_map = {
                    "white": "&H00FFFFFF&",
                    "yellow": "&H0000FFFF&",
                    "red": "&H000000FF&",
                    "blue": "&H00FF0000&",
                    "green": "&H0000FF00&",
                    "black": "&H00000000&",
                    "cyan": "&H00FFFF00&",
                    "magenta": "&H00FF00FF&",
                    "gray": "&H00808080&",
                    "orange": "&H0000A5FF&"
                }
                color_ass = color_ass_map.get(subtitle_color, "&H00FFFFFF&")

                grouped = group_words_by_count(segments, words_per_subtitle)

                # Converte cores de contorno e sombra para formato ASS
                outline_color_ass = color_ass_map.get(ctx.get("subtitle_outline_color", "black"), "&H00000000&")

                # Gera arquivo ASS
                generate_ass_file(
                    grouped,
                    ass_file_path,
                    font=subtitle_font,
                    size=subtitle_font_size,
                    color=color_ass,
                    outline_color=outline_color_ass,
                    outline=ctx.get("subtitle_outline_width", 2),
                    shadow=ctx.get("subtitle_shadow_x", 2),
                    alignment=alignment,
                    playres_x=ctx.get("width", 1920),
                    playres_y=ctx.get("height", 1080),
                    subtitle_effect=ctx.get("subtitle_effect", "none")
                )

                # Aplica filtro subtitles no vídeo
                ass_path_escaped = str(Path(ass_file_path)).replace('\\', '\\\\').replace(':', '\\:')
                subtitle_effect = ctx.get("subtitle_effect", "none")

                # Calcula y da barra conforme a posição da legenda
                bar_h = 80
                margin_v = 40
                height = ctx.get("height", 1080)
                y_map = {
                    "bottom_center": f"ih-{bar_h + margin_v}",
                    "bottom_left": f"ih-{bar_h + margin_v}",
                    "bottom_right": f"ih-{bar_h + margin_v}",
                    "top_center": f"{margin_v}",
                    "top_left": f"{margin_v}",
                    "top_right": f"{margin_v}",
                    "center": f"(ih-{bar_h})/2"
                }
                bar_y = y_map.get(subtitle_position, f"ih-{bar_h + margin_v}")

                if subtitle_effect == "fade_in":
                    # Efeito de fade-in na legenda
                    subtitle_filter = f"{map_out}subtitles=filename='{ass_path_escaped}',fade=t=in:st=0:d=1[vsubtitles]"
                    filter_builder.add_filter(subtitle_filter)
                    ctx["map_out"] = "[vsubtitles]"
                elif subtitle_effect == "fill_bar":
                    # Barra atrás do texto, alinhada com a legenda
                    bar_filter = f"{map_out}drawbox=x=0:y={bar_y}:w='min(t*iw/2,iw)':h={bar_h}:color=yellow@0.95:t=fill[vbar]"
                    subtitle_filter = f"[vbar]subtitles=filename='{ass_path_escaped}'[vsubtitles]"
                    filter_builder.add_filter(bar_filter)
                    filter_builder.add_filter(subtitle_filter)
                    ctx["map_out"] = "[vsubtitles]"
                else:
                    # Sem efeito
                    subtitle_filter = f"{map_out}subtitles=filename='{ass_path_escaped}'[vsubtitles]"
                    filter_builder.add_filter(subtitle_filter)
                    ctx["map_out"] = "[vsubtitles]"

                ctx["subtitle_file"] = ass_file_path  # Salva para limpeza posterior

        finally:
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)

        return ctx


class ImageCacheStage(PipelineStage):
    """Pré-renderiza imagens em vídeos curtos para cache"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        video_mode = ctx.get("video_mode")
        if video_mode != "images":
            return ctx

        print("Iniciando pré-renderização de cache para imagens...")
        start_time = time.time()

        # Configurações
        out_path = ctx["out_path"]
        parent = Path(out_path).parent
        # Evita duplicação se já estamos dentro de cache
        if parent.name == "cache":
            cache_dir = parent
        else:
            cache_dir = parent / "cache"
        cache_dir.mkdir(exist_ok=True)

        videos_folder = ctx["videos_folder"]
        image_segment_duration = ctx["image_segment_duration"]
        fps = ctx["fps"]
        width = ctx["width"]
        height = ctx["height"]

        # Configurações de encoder do contexto
        encoder_config = ctx.get("encoder_config", {})

        # Lista imagens disponíveis
        folder = Path(videos_folder)
        images = list_images(folder)
        if not images:
            return ctx

        # Salva lista de imagens em arquivo para processamento batch
        images_list_file = cache_dir / "images_list.txt"
        with open(images_list_file, 'w', encoding='utf-8') as f:
            for img_path in images:
                f.write(f"{img_path}\n")

        # Processa cada imagem única
        cached_videos = {}
        processed_count = 0
        total_images = len(images)

        for img_path in images:
            # Gera hash único baseado no caminho da imagem e configurações
            img_config = f"{img_path}_{width}x{height}_{fps}fps_{image_segment_duration}s"
            img_hash = hashlib.md5(img_config.encode()).hexdigest()[:12]
            cached_video_path = cache_dir / f"img_{img_hash}.mp4"

            # Se já existe no cache, pula
            if cached_video_path.exists():
                cached_videos[str(img_path)] = str(cached_video_path)
                processed_count += 1
                print(f"Cache encontrado ({processed_count}/{total_images}): {img_path.name}")
                continue

            # Pré-renderiza a imagem
            print(f"Pré-renderizando ({processed_count + 1}/{total_images}): {img_path.name}")
            img_start = time.time()

            self._prerender_image(
                img_path,
                cached_video_path,
                image_segment_duration,
                fps,
                width,
                height,
                encoder_config,
                cache_dir
            )

            img_time = time.time() - img_start
            print(f"Concluído em {img_time:.1f}s")

            cached_videos[str(img_path)] = str(cached_video_path)
            processed_count += 1

        total_time = time.time() - start_time
        print(f"Cache finalizado em {total_time:.1f}s - {processed_count} imagens processadas")

        # Adiciona mapeamento ao contexto
        ctx["cached_images"] = cached_videos
        return ctx

    def _prerender_image(self, img_path, output_path, duration, fps, width, height, encoder_config, cache_dir):
        """Renderiza uma imagem em vídeo curto sem efeitos."""

        # Salva comando em arquivo para reuso
        cmd_file = cache_dir / f"cmd_{output_path.stem}.txt"

        # Pré-renderização simples sem efeitos - apenas escala e padding
        video_filter = (
            f"fps={fps},"
            f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1"
        )

        # Comando base
        cmd = [
            get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-t", f"{duration:.3f}", "-i", str(img_path),
            "-vf", video_filter
        ]

        # Adiciona configurações do encoder
        codec = encoder_config.get("codec", "libx264")
        cmd.extend(["-c:v", codec])

        # Força compatibilidade e GOP estável
        gop = max(int(fps * 2), 2)
        cmd += ["-pix_fmt", "yuv420p", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"]

        # Configurações específicas por codec
        if "nvenc" in codec:
            if "cq" in encoder_config:
                cmd.extend(["-cq", encoder_config["cq"]])
            if "preset" in encoder_config:
                cmd.extend(["-preset", encoder_config["preset"]])
            if "tune" in encoder_config:
                cmd.extend(["-tune", encoder_config["tune"]])
        else:
            if "preset" in encoder_config:
                cmd.extend(["-preset", encoder_config["preset"]])
            if "crf" in encoder_config:
                cmd.extend(["-crf", encoder_config["crf"]])

        # Threads
        if "threads" in encoder_config:
            cmd.extend(["-threads", encoder_config["threads"]])

        # Parâmetros finais
        cmd.extend(["-r", str(fps), "-an", str(output_path)])

        # Salva comando no arquivo cache
        with open(cmd_file, 'w', encoding='utf-8') as f:
            f.write(" ".join([str(c) for c in cmd]))
            f.write("\n")

        run(cmd)


class MediaCacheStage(PipelineStage):
    """Pré-renderiza imagens e vídeos em cache para resolução uniforme."""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        mode = ctx.get("video_mode")
        segments = ctx.get("segments", [])
        if not segments:
            return ctx

        cache_dir = Path(ctx["out_path"]).parent / "cache"
        cache_dir.mkdir(exist_ok=True)

        width, height = ctx["width"], ctx["height"]
        fps = ctx["fps"]
        duration_img = ctx.get("image_segment_duration", 0)
        encoder_config = ctx.get("encoder_config", {})

        cached = {}
        for src, _ in segments:
            stem = Path(src).stem
            out = cache_dir / f"{stem}_{width}x{height}.mp4"
            cmd_file = cache_dir / f"cmd_{stem}_{width}x{height}.txt"

            # Se ainda não existe, gera o vídeo escalado
            if not out.exists():
                # Monta o filtro de vídeo (scale+pad)
                vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                      f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                      f"setsar=1")

                # Base do comando
                if mode == "images":
                    cmd = [
                        get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error",
                        "-loop", "1", "-t", f"{duration_img:.3f}", "-i", str(src),
                        "-vf", vf
                    ]
                else:  # vídeos
                    cmd = [
                        get_ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(src),
                        "-vf", vf
                    ]

                # Framerate
                cmd += ["-r", str(fps)]

                # Codec e encoder_config
                codec = encoder_config.get("codec", "libx264")
                cmd += ["-c:v", codec]

                # Força compat e GOP estável também no cache
                gop = max(int(fps * 2), 2)
                cmd += ["-pix_fmt", "yuv420p", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"]

                # NVENC ou libx264 presets
                if "nvenc" in codec:
                    if "cq" in encoder_config:
                        cmd += ["-cq", encoder_config["cq"]]
                    if "preset" in encoder_config:
                        cmd += ["-preset", encoder_config["preset"]]
                    if "tune" in encoder_config:
                        cmd += ["-tune", encoder_config["tune"]]
                else:
                    if "preset" in encoder_config:
                        cmd += ["-preset", encoder_config["preset"]]
                    if "crf" in encoder_config:
                        cmd += ["-crf", encoder_config["crf"]]

                # Threads
                if "threads" in encoder_config:
                    cmd += ["-threads", encoder_config["threads"]]

                # Saída
                cmd += [str(out)]

                # Salva o comando num arquivo de texto
                with open(cmd_file, "w", encoding="utf-8") as f:
                    f.write(" ".join(cmd) + "\n")

                # Executa o FFmpeg
                run(cmd)

            cached[src] = str(out)

        ctx["cached_media"] = cached
        return ctx


class EncoderStage(PipelineStage):
    """Configura encoder, resolução e parâmetros de qualidade"""

    RESOLUTION_PRESETS = {
        "horizontal_480p": (854, 480),
        "horizontal_720p": (1280, 720),
        "horizontal_1080p": (1920, 1080),
        "horizontal_2k": (2560, 1440),
        "vertical_480p": (480, 854),
        "vertical_720p": (720, 1280),
        "vertical_1080p": (1080, 1920),
        "vertical_2k": (1440, 2560),
    }

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # Aplica preset de resolução
        resolution_preset = ctx.get("resolution_preset", "horizontal_1080p")
        if resolution_preset in self.RESOLUTION_PRESETS:
            width, height = self.RESOLUTION_PRESETS[resolution_preset]
            ctx["width"] = width
            ctx["height"] = height

        # Configura encoder
        encoder = ctx.get("encoder", "libx264")
        performance_profile = ctx.get("performance_profile", "quality")
        threads = ctx.get("threads", 0)
        gpu_quality = ctx.get("gpu_quality", 18)

        # Configurações de encoder
        encoder_config = self._get_encoder_config(encoder, performance_profile, threads, gpu_quality)
        ctx["encoder_config"] = encoder_config

        return ctx

    def _get_encoder_config(self, encoder, performance_profile, threads, gpu_quality):
        """Gera configuração do encoder baseada nos parâmetros"""
        config = {}

        # Configurações base por encoder
        if encoder == "libx264":
            config["codec"] = "libx264"
            if performance_profile == "quality":
                config["preset"] = "slow"
                config["crf"] = "18"
            else:  # speed
                config["preset"] = "ultrafast"
                config["crf"] = "23"

        elif encoder == "libx265":
            config["codec"] = "libx265"
            if performance_profile == "quality":
                config["preset"] = "medium"
                config["crf"] = "20"
            else:  # speed
                config["preset"] = "ultrafast"
                config["crf"] = "25"

        elif encoder == "h264_nvenc":
            config["codec"] = "h264_nvenc"
            config["cq"] = str(gpu_quality)
            if performance_profile == "quality":
                config["preset"] = "p7"
                config["tune"] = "hq"
            else:  # speed
                config["preset"] = "p1"
                config["tune"] = "ll"

        elif encoder == "h265_nvenc":
            config["codec"] = "hevc_nvenc"
            config["cq"] = str(gpu_quality)
            if performance_profile == "quality":
                config["preset"] = "p7"
                config["tune"] = "hq"
            else:  # speed
                config["preset"] = "p1"
                config["tune"] = "ll"

        # Configurações de threads
        if threads > 0:
            config["threads"] = str(threads)

        return config


class BackgroundMusicStage(PipelineStage):
    """Estágio que adiciona trilha de fundo ao áudio"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        background_music = ctx.get("background_music")
        background_music_volume = ctx.get("background_music_volume", 0.2)

        if not background_music:
            return ctx

        music_path = Path(background_music)
        if not music_path.exists():
            print(f"Aviso: Arquivo de música de fundo não encontrado: {background_music}")
            return ctx

        print(f"Adicionando trilha de fundo: {background_music} (volume: {background_music_volume})")

        # Adiciona a música de fundo aos inputs
        inputs = ctx["inputs"]

        # Calcula o índice ANTES de adicionar o novo input
        music_idx = sum(1 for x in inputs if x == "-i")
        inputs.extend(["-i", str(music_path)])

        ctx["background_music_idx"] = music_idx
        ctx["background_music_volume"] = background_music_volume
        ctx["inputs"] = inputs

        return ctx


class OutputStage(PipelineStage):
    """Estágio de saída com filter_complex centralizado"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
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
        if audio_idx == "aout":
            audio_map = "[aout]"
        elif audio_idx == "afinal_ending":
            audio_map = "[afinal_ending]"
        else:
            audio_map = f"[{audio_idx}:a]"

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
            if "cq" in encoder_config:
                cmd += ["-cq", encoder_config["cq"]]
            if "preset" in encoder_config:
                cmd += ["-preset", encoder_config["preset"]]
            if "tune" in encoder_config:
                cmd += ["-tune", encoder_config["tune"]]
        else:
            if "preset" in encoder_config:
                cmd += ["-preset", encoder_config["preset"]]
            if "crf" in encoder_config:
                cmd += ["-crf", encoder_config["crf"]]
        if "threads" in encoder_config:
            cmd += ["-threads", encoder_config["threads"]]

        # ALTERAÇÕES: compatibilidade, seek e GOP estável
        fps = ctx.get("fps", 30)
        gop = max(int(fps * 2), 2)
        cmd += [
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
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
            cache_dir = Path(out_path).parent / "cache"
            if cache_dir.exists():
                for cmd_file in glob.glob(str(cache_dir / "cmd_*.txt")):
                    try:
                        os.unlink(cmd_file)
                    except OSError:
                        pass

        total_time = time.time() - start_time
        print(f"Renderização final concluída em {total_time:.1f}s")
        ctx["render_time"] = total_time

        return ctx


class EndingStage(PipelineStage):
    """Adiciona vídeo de encerramento ao final, com áudio próprio, sem overlay."""
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        ending_video_path = ctx.get("ending_video_path")
        if not ending_video_path:
            return ctx

        # Gera cache do vídeo de encerramento com a resolução correta
        ending_segments = [(ending_video_path, duration_seconds(ending_video_path))]
        cache_ctx = ctx.copy()
        cache_ctx["segments"] = ending_segments
        cache_ctx["video_mode"] = "videos"
        cached_ctx = MediaCacheStage()(cache_ctx)
        cached_ending = cached_ctx["cached_media"].get(ending_video_path, ending_video_path)

        filter_builder = ctx["filter_builder"]
        inputs = ctx["inputs"]
        map_out = ctx["map_out"]
        audio_idx = ctx["audio_idx"]

        # Calcula índice correto do próximo input baseado em quantos "-i" já existem
        ending_idx = sum(1 for x in inputs if x == "-i")
        inputs.extend(["-i", str(cached_ending)])

        # Duração do encerramento
        ending_duration = duration_seconds(ending_video_path)

        # Labels de vídeo e áudio
        main_video_ref = map_out                             # ex: "[vsubtitles]" ou "[vfinal]"
        ending_video_ref = f"[{ending_idx}:v]"               # usa index correto
        ending_audio_ref = f"[{ending_idx}:a]"

        # Concatena vídeo principal + encerramento em labels únicos
        video_concat = f"{main_video_ref}{ending_video_ref}concat=n=2:v=1:a=0[vfinal_ending]"
        audio_concat = f"[{audio_idx}:a]{ending_audio_ref}concat=n=2:v=0:a=1[afinal_ending]"

        filter_builder.add_filter(video_concat)
        filter_builder.add_filter(audio_concat)

        # Atualiza contexto para os próximos estágios
        ctx["map_out"] = "[vfinal_ending]"
        ctx["audio_idx"] = "afinal_ending"
        ctx["audio_duration"] += ending_duration

        return ctx


class OpeningStage(PipelineStage):
    """Estágio que adiciona vídeos de abertura no início do vídeo principal"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        opening_video_paths = ctx.get("opening_video_paths", [])
        if not opening_video_paths:
            return ctx

        print(f"Adicionando {len(opening_video_paths)} vídeo(s) de abertura")

        # Obter o filter builder e outros parâmetros do contexto
        fb = ctx["filter_builder"]
        map_out = ctx.get("map_out", "[vout]")
        audio_duration = ctx["audio_duration"]
        width = ctx["width"]
        height = ctx["height"]

        # Calcular a duração total dos vídeos de abertura
        opening_total_duration = 0
        opening_inputs = []
        opening_labels = []

        # Adicionar os vídeos de abertura aos inputs
        inputs = ctx["inputs"]
        for i, path in enumerate(opening_video_paths):
            if not os.path.exists(path):
                print(f"Aviso: Arquivo de abertura não encontrado: {path}")
                continue

            # Adicionar aos inputs
            video_idx = sum(1 for x in inputs if x == "-i")
            inputs.extend(["-i", str(path)])

            # Calcular duração do vídeo de abertura
            from subprocess import check_output, PIPE
            import json
            ffprobe_cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                path
            ]
            result = check_output(ffprobe_cmd, stderr=PIPE).decode('utf-8')
            duration = float(json.loads(result)["format"]["duration"])

            # Registrar informações para processamento
            opening_inputs.append((video_idx, duration))
            opening_total_duration += duration

            # Criar label para o vídeo de abertura com escala e padding para corresponder à resolução principal
            in_lbl = f"{video_idx}:v"
            out_lbl = f"opening_{i}"
            # Assegurar que o vídeo de abertura tenha a mesma resolução do vídeo principal
            fb.add_filter(
                f"[{in_lbl}]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS[{out_lbl}]"
            )
            opening_labels.append(out_lbl)

        # Atualizar os inputs no contexto
        ctx["inputs"] = inputs

        if not opening_labels:
            return ctx

        # Concatenar os vídeos de abertura
        if len(opening_labels) > 1:
            concat_lbls = "".join(f"[{l}]" for l in opening_labels)
            fb.add_filter(f"{concat_lbls}concat=n={len(opening_labels)}:v=1:a=0[opening_concat]")
            opening_output = "opening_concat"
        else:
            opening_output = opening_labels[0]

        # Remover o map_out da string se estiver dentro de colchetes
        map_out_clean = map_out.strip("[]")

        # Calcular nova duração do vídeo principal para ajustar ao tempo da narração
        adjusted_duration = max(0.1, audio_duration - opening_total_duration)

        # Ajustar o vídeo principal para a nova duração
        fb.add_filter(f"[{map_out_clean}]trim=duration={adjusted_duration}[main_adjusted]")

        # Concatenar abertura + vídeo principal
        fb.add_filter(f"[{opening_output}][main_adjusted]concat=n=2:v=1:a=0[vout_with_opening]")

        # Atualizar o mapa de saída
        ctx["map_out"] = "[vout_with_opening]"

        # Armazenar a duração total dos vídeos de abertura no contexto
        ctx["opening_total_duration"] = opening_total_duration

        return ctx


class MediaPipeline:
    """Pipeline principal para processamento de mídia"""

    def __init__(self, stages: TList[PipelineStage]):
        self.stages = stages

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        total_stages = len(self.stages)
        progress_callback = ctx.get("progress_callback")

        for i, stage in enumerate(self.stages):
            ctx = stage(ctx)

            # Atualiza o progresso se o callback estiver disponível
            if progress_callback:
                # Calcula a porcentagem com base na etapa atual
                progress = int((i + 1) / total_stages * 100)
                progress_callback(progress)

        return ctx
