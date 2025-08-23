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


class FilterBuilder:
    """Centralizador de construção de filtros complexos do FFmpeg"""

    def __init__(self):
        self.filters = []
        self.current_output = None
        self.video_duration = 0
        self.audio_duration = 0

    def add_filter(self, filter_str: str):
        """Adiciona um filtro à cadeia"""
        self.filters.append(filter_str)

    def set_output(self, output_label: str):
        """Define o label de saída atual"""
        self.current_output = output_label

    def get_filter_complex(self) -> str:
        """Retorna o filter_complex completo"""
        return ";".join(self.filters) if self.filters else ""

    def save_to_file(self) -> str:
        """Salva o filter_complex em arquivo temporário e retorna o caminho"""
        filter_complex = self.get_filter_complex()
        with tempfile.NamedTemporaryFile(mode='w', suffix='_filter.txt', delete=False) as f:
            f.write(filter_complex)
            return f.name

    def clear(self):
        """Limpa todos os filtros"""
        self.filters = []
        self.current_output = None


class PipelineStage(ABC):
    @abstractmethod
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        pass


class VideoBaseStage(PipelineStage):
    """Estágio base corrigido com eliminação de duplicação de filtros"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        narration_path = ctx["narration_path"]
        videos_folder = ctx["videos_folder"]
        seed = ctx["seed"]
        fps = ctx["fps"]
        width = ctx["width"]
        height = ctx["height"]
        video_mode = ctx["video_mode"]
        image_segment_duration = ctx["image_segment_duration"]

        narration = Path(narration_path)
        folder = Path(videos_folder)

        if not narration.exists():
            raise FileNotFoundError(f"Narração não encontrada: {narration}")
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Pasta de entrada não encontrada ou inválida: {folder}")

        audio_dur = duration_seconds(narration)
        ctx["audio_duration"] = audio_dur

        # Adiciona margem de segurança para garantir cobertura total
        safety_margin = 2.0  # 2 segundos extras

        # Inicializa o FilterBuilder
        filter_builder = FilterBuilder()
        filter_builder.audio_duration = audio_dur

        inputs = ["-y", "-hide_banner", "-loglevel", "error", "-i", str(narration)]
        segments = []

        # Calcula duração extra necessária para compensar transições
        transition_type = ctx.get("transition_type", "none")
        extra_duration_needed = 0

        if video_mode == "videos":
            vids = list_videos(folder)
            if not vids:
                raise FileNotFoundError(f"Nenhum vídeo com extensões suportadas em: {folder}")

            # Se houver transições, adiciona tempo extra
            if transition_type != "none":
                num_transitions = len(vids) - 1 if len(vids) > 1 else 0
                extra_duration_needed = num_transitions * 1.5  # Mais conservador
            else:
                extra_duration_needed = 0

            # Pega segmentos com duração extra
            total_duration_needed = audio_dur + extra_duration_needed + safety_margin
            segments = pick_segments_to_cover(total_duration_needed, vids, seed=seed)

            # Verifica se a duração total dos segmentos é suficiente
            total_segments_duration = sum(take for _, take in segments)
            if total_segments_duration < audio_dur:
                # Extende o último segmento se necessário
                if segments:
                    last_video, last_take = segments[-1]
                    needed_extension = audio_dur - total_segments_duration + safety_margin
                    segments[-1] = (last_video, last_take + needed_extension)

            # Criar arquivo temporário com lista de inputs para FFmpeg
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                temp_file = f.name

                # Define a pasta base para usar caminhos relativos
                base_folder = Path(folder).resolve()

                for v, take in segments:
                    # Para vídeos - usa caminho relativo quando possível
                    try:
                        rel_path = Path(v).resolve().relative_to(base_folder)
                        video_path = str(Path(folder) / rel_path).replace('\\', '/')
                    except ValueError:
                        # Se não conseguir obter caminho relativo, usa absoluto com escape
                        video_path = str(v).replace('\\', '/')

                    f.write(f"file '{video_path}'\n")
                    f.write(f"duration {take:.3f}\n")

            # Usar o arquivo de concatenação
            ctx["concat_file"] = temp_file

            # Adiciona input do concat file
            if segments:
                inputs += ["-f", "concat", "-safe", "0", "-i", temp_file]

        elif video_mode == "images":
            images = list_images(folder)
            if not images:
                raise FileNotFoundError(f"Nenhuma imagem com extensões suportadas em: {folder}")

            # Se houver transições, adiciona tempo extra
            if transition_type != "none":
                num_transitions = (audio_dur / image_segment_duration) - 1
                num_transitions = max(0, int(num_transitions))
                extra_duration_needed = num_transitions * 1.5
            else:
                extra_duration_needed = 0

            total_duration_needed = audio_dur + extra_duration_needed + safety_margin
            segments = pick_image_segments_to_cover(
                total_duration_needed,
                images,
                image_segment_duration,
                seed=seed
            )

            cached_images = ctx.get("cached_images", {})
            ken_burns_enabled = ctx.get("enable_ken_burns", False)

            # Criar arquivo temporário com lista de inputs para FFmpeg
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                temp_file = f.name

                # Define a pasta base para usar caminhos relativos
                base_folder = Path(folder).resolve()

                for img, take in segments:
                    if str(img) in cached_images:
                        # Para imagens em cache (vídeos pré-processados)
                        cache_path = cached_images[str(img)].replace('\\', '/')
                        f.write(f"file '{cache_path}'\n")
                        f.write(f"duration {take:.3f}\n")
                    else:
                        # Para imagens estáticas - usa caminho relativo quando possível
                        try:
                            rel_path = Path(img).resolve().relative_to(base_folder)
                            img_path = str(Path(folder) / rel_path).replace('\\', '/')
                        except ValueError:
                            # Se não conseguir obter caminho relativo, usa absoluto com escape
                            img_path = str(img).replace('\\', '/')

                        f.write(f"file '{img_path}'\n")
                        f.write(f"duration {take:.3f}\n")

            # Usar o arquivo de concatenação
            ctx["concat_file"] = temp_file

            # Adiciona input do concat file
            if segments:
                inputs += ["-f", "concat", "-safe", "0", "-i", temp_file]

            # REMOVIDO: A lógica antiga que criava filtros individuais para cada imagem
            # Isso estava causando conflito com o concat file

        else:
            raise ValueError(f"Modo de vídeo inválido: {video_mode}. Use 'videos' ou 'images'.")

        # CORREÇÃO PRINCIPAL: Lógica unificada para concat file
        if "concat_file" in ctx:
            # Com arquivo de concat, temos apenas um stream de entrada (1:v)
            # Precisamos separar os segmentos via filtros de trim baseados em tempo
            segment_labels = []
            current_time = 0.0
            video_input_idx = 1  # Índice do concat file (sempre 1)

            for idx, (_, take) in enumerate(segments, start=1):
                in_label = f"{video_input_idx}:v"  # Sempre [1:v] pois é concat file
                out_label = f"v{idx}"
                segment_labels.append(out_label)

                # Corta o segmento na posição temporal atual
                trim_filter = (
                    f"[{in_label}]trim=start={current_time}:end={current_time + take},"
                    f"setpts=PTS-STARTPTS[{out_label}]"
                )
                filter_builder.add_filter(trim_filter)
                current_time += take
        else:
            # Modo antigo para compatibilidade (não deve ser usado com a nova arquitetura)
            segment_labels = [f"v{i}" for i in range(1, len(segments) + 1)]

        ctx["filter_builder"] = filter_builder
        ctx["inputs"] = inputs
        ctx["segments"] = segments
        ctx["segment_labels"] = segment_labels
        ctx["video_input_idx"] = 1  # Armazena índice do input de vídeo para uso nos outros estágios
        ctx["audio_idx"] = 0

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
        transition_type = ctx.get("transition_type", "none")
        filter_builder = ctx["filter_builder"]
        segments = ctx.get("segments", [])
        segment_labels = ctx.get("segment_labels", [])
        audio_duration = ctx["audio_duration"]
        fps = ctx.get("fps", 30)

        if transition_type == "none" or len(segments) < 2:
            # Sem transições - apenas concatena
            concat_labels = "".join(f"[{label}]" for label in segment_labels)
            concat_filter = f"{concat_labels}concat=n={len(segments)}:v=1:a=0[vout]"
            filter_builder.add_filter(concat_filter)
            filter_builder.set_output("[vout]")
        else:
            # Prepara filtros de configuração uniforme
            prep_filters = []
            clean_labels = []
            for i, label in enumerate(segment_labels):
                dst = f"vc{i + 1}"
                prep_filter = f"[{label}]settb=AVTB,fps={fps},format=yuv420p[{dst}]"
                filter_builder.add_filter(prep_filter)
                clean_labels.append(dst)

            # Com transições
            transition_opts = [t for t in self.SUPPORTED_TRANSITIONS if t != "fade"]

            prev_label = clean_labels[0]
            prev_dur = segments[0][1]

            for i in range(1, len(clean_labels)):
                if transition_type == "random":
                    ttype = random.choice(transition_opts)
                else:
                    ttype = transition_type if transition_type in self.SUPPORTED_TRANSITIONS else "fade"

                curr_label = clean_labels[i]
                curr_dur = segments[i][1]

                # Offset correto para garantir cobertura total
                offset = max(prev_dur - 1, 0)

                out_label = f"trans{i}"
                trans_filter = (
                    f"[{prev_label}][{curr_label}]xfade=transition={ttype}:"
                    f"duration=1:offset={offset}[{out_label}]"
                )
                filter_builder.add_filter(trans_filter)

                prev_label = out_label
                prev_dur = prev_dur + curr_dur - 1  # Ajusta duração considerando sobreposição

            # Garante que o vídeo cubra toda a duração do áudio
            final_label = prev_label
            if prev_dur < audio_duration:
                # Adiciona padding para cobrir duração restante
                pad_duration = max(audio_duration - prev_dur, 0.1)
                pad_filter = f"[{final_label}]tpad=stop_duration={pad_duration}[vout]"
                filter_builder.add_filter(pad_filter)
                filter_builder.set_output("[vout]")
            else:
                # Renomeia para vout
                rename_filter = f"[{final_label}]null[vout]"
                filter_builder.add_filter(rename_filter)
                filter_builder.set_output("[vout]")

        ctx["map_out"] = "[vout]"
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
                color_ass = "&H00FFFFFF&"  # Branco padrão
                if subtitle_color == "yellow":
                    color_ass = "&H0000FFFF&"
                elif subtitle_color == "red":
                    color_ass = "&H000000FF&"
                elif subtitle_color == "blue":
                    color_ass = "&H00FF0000&"

                grouped = group_words_by_count(segments, words_per_subtitle)
                # Gera arquivo ASS
                generate_ass_file(
                    grouped,
                    ass_file_path,
                    font=subtitle_font,
                    size=subtitle_font_size,
                    color=color_ass,
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
        cache_dir = Path(out_path).parent / "cache"
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
        """Renderiza uma imagem em vídeo curto sem efeitos"""

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

        # Processamento de áudio com música de fundo
        background_music_idx = ctx.get("background_music_idx")
        background_music_volume = ctx.get("background_music_volume", 0.2)

        if background_music_idx is not None:
            # Adiciona filtro de áudio ao FilterBuilder
            audio_filter = (
                f"[{background_music_idx}:a]aloop=loop=-1:size=2e+09,"
                f"volume={background_music_volume}[bg];"
                f"[{audio_idx}:a][bg]amix=inputs=2:duration=first:"
                f"dropout_transition=2[aout]"
            )
            filter_builder.add_filter(audio_filter)
            audio_map = "[aout]"
        else:
            audio_map = f"{audio_idx}:a"

        # Salva filter_complex em arquivo
        filter_file = filter_builder.save_to_file()
        print(f"Filter complex salvo em: {filter_file}")

        # Comando base
        cmd = [get_ffmpeg_path()] + inputs
        cmd.extend(["-filter_complex_script", filter_file])
        cmd.extend(["-map", map_out])
        cmd.extend(["-map", audio_map])

        # Configurações do encoder
        codec = encoder_config.get("codec", "libx264")
        cmd.extend(["-c:v", codec])

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

        if "threads" in encoder_config:
            cmd.extend(["-threads", encoder_config["threads"]])

        # Configurações de áudio e saída
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        # Garante duração exata do vídeo
        cmd.extend(["-t", str(audio_duration)])
        cmd.extend([str(out_path)])

        try:
            print("Executando renderização...")
            run(cmd)
        finally:
            # Limpa arquivo temporário
            if os.path.exists(filter_file):
                os.unlink(filter_file)
                print(f"Arquivo de filtro removido: {filter_file}")

            # Remove arquivo ASS se existir
            if ctx.get("subtitle_file") and os.path.exists(ctx["subtitle_file"]):
                os.unlink(ctx["subtitle_file"])

            # Remove arquivos de comando .txt da pasta cache
            cache_dir = Path(out_path).parent / "cache"
            if cache_dir.exists():
                cmd_files = glob.glob(str(cache_dir / "cmd_*.txt"))
                for cmd_file in cmd_files:
                    try:
                        os.unlink(cmd_file)
                    except OSError:
                        pass
                if cmd_files:
                    print(f"Removidos {len(cmd_files)} arquivos de comando da cache")

        total_time = time.time() - start_time
        print(f"Renderização final concluída em {total_time:.1f}s")

        ctx["render_time"] = total_time
        return ctx


class MediaPipeline:
    """Pipeline principal para processamento de mídia"""

    def __init__(self, stages: TList[PipelineStage]):
        self.stages = stages

    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        for stage in self.stages:
            ctx = stage(ctx)
        return ctx
