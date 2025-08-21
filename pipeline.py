from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List as TList
from audio_utils import duration_seconds
from video_utils import list_videos, pick_segments_to_cover, list_images, pick_image_segments_to_cover
import random
import hashlib
import time
from ffmpeg_utils import run, get_ffmpeg_path

class PipelineStage(ABC):
    @abstractmethod
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        pass

class VideoBaseStage(PipelineStage):
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        narration_path = ctx["narration_path"]
        videos_folder = ctx["videos_folder"]
        seed = ctx["seed"]
        fps = ctx["fps"]
        width = ctx["width"]
        height = ctx["height"]
        crf = ctx["crf"]
        preset = ctx["preset"]
        video_mode = ctx["video_mode"]
        image_segment_duration = ctx["image_segment_duration"]
        out_path = ctx["out_path"]
        narration = Path(narration_path)
        folder = Path(videos_folder)
        out = Path(out_path)
        if not narration.exists():
            raise FileNotFoundError(f"Narração não encontrada: {narration}")
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Pasta de entrada não encontrada ou inválida: {folder}")
        audio_dur = duration_seconds(narration)
        ffmpeg_bin = get_ffmpeg_path()
        inputs = ["-y", "-hide_banner", "-loglevel", "error", "-i", str(narration)]
        vf_parts = []
        vlabels = []
        segments = []
        if video_mode == "videos":
            vids = list_videos(folder)
            if not vids:
                raise FileNotFoundError(f"Nenhum vídeo com extensões suportadas em: {folder}")
            segments = pick_segments_to_cover(audio_dur, vids, seed=seed)
            if len(segments) != len([v for v, _ in segments]):
                raise ValueError(f"Número de segmentos ({len(segments)}) difere do número de vídeos selecionados ({len([v for v, _ in segments])})")
            for v, _ in segments:
                inputs += ["-i", str(v)]
            for idx, (_, take) in enumerate(segments, start=1):
                label_in = f"{idx}:v"
                take_str = f"{take:.3f}"
                vout = f"v{idx}"
                chain = (
                    f"[{label_in}]"
                    f"fps={fps},"
                    f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                    f"setsar=1,"
                    f"trim=0:{take_str},setpts=PTS-STARTPTS"
                    f"[{vout}]"
                )
                vf_parts.append(chain)
                vlabels.append(f"[{vout}]")
            concat = "".join(vlabels) + f"concat=n={len(segments)}:v=1:a=0[vout]"
            filter_complex = ";".join(vf_parts + [concat])
        elif video_mode == "images":
            images = list_images(folder)
            if not images:
                raise FileNotFoundError(f"Nenhuma imagem com extensões suportadas em: {folder}")
            segments = pick_image_segments_to_cover(audio_dur, images, image_segment_duration, seed=seed)

            # Usa vídeos em cache se disponível
            cached_images = ctx.get("cached_images", {})

            for img, take in segments:
                # Verifica se existe versão em cache
                if str(img) in cached_images:
                    # Usa o vídeo pré-renderizado do cache
                    cached_video = cached_images[str(img)]
                    inputs += ["-i", cached_video]
                else:
                    # Fallback: usa a imagem original
                    inputs += ["-loop", "1", "-t", f"{take:.3f}", "-i", str(img)]

            for idx, (img, take) in enumerate(segments, start=1):
                label_in = f"{idx}:v"
                take_str = f"{take:.3f}"
                vout = f"v{idx}"

                ken_burns_enabled = ctx.get("enable_ken_burns", False)

                # Se usa cache, aplica apenas Ken Burns se habilitado
                if str(img) in cached_images:
                    if ken_burns_enabled:
                        # Ken Burns effect com posição aleatória
                        zoom_duration = int(take * fps)
                        zoom_positions = {
                            "center": ("iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
                            "top_right": ("iw-iw/zoom", "0"),
                            "top_left": ("0", "0"),
                            "bottom_right": ("iw-iw/zoom", "ih-ih/zoom"),
                            "bottom_left": ("0", "ih-ih/zoom")
                        }
                        position = random.choice(list(zoom_positions.keys()))
                        x_pos, y_pos = zoom_positions[position]

                        chain = (
                            f"[{label_in}]"
                            f"zoompan=z='min(zoom+0.0015,1.1)':d={zoom_duration}:x='{x_pos}':y='{y_pos}',"
                            f"trim=0:{take_str},setpts=PTS-STARTPTS"
                            f"[{vout}]"
                        )
                    else:
                        chain = (
                            f"[{label_in}]"
                            f"trim=0:{take_str},setpts=PTS-STARTPTS"
                            f"[{vout}]"
                        )
                else:
                    # Fallback: processamento original da imagem
                    if ken_burns_enabled:
                        # Ken Burns effect with zoompan - 5 posições aleatórias
                        zoom_duration = int(take * fps)

                        # Define as 5 posições de zoom
                        zoom_positions = {
                            "center": ("iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
                            "top_right": ("iw-iw/zoom", "0"),
                            "top_left": ("0", "0"),
                            "bottom_right": ("iw-iw/zoom", "ih-ih/zoom"),
                            "bottom_left": ("0", "ih-ih/zoom")
                        }

                        # Escolhe posição aleatória
                        position = random.choice(list(zoom_positions.keys()))
                        x_pos, y_pos = zoom_positions[position]

                        chain = (
                            f"[{label_in}]"
                            f"zoompan=z='min(zoom+0.0015,1.1)':d={zoom_duration}:x='{x_pos}':y='{y_pos}',"
                            f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
                            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                            f"setsar=1,"
                            f"trim=0:{take_str},setpts=PTS-STARTPTS"
                            f"[{vout}]"
                        )
                    else:
                        chain = (
                            f"[{label_in}]"
                            f"fps={fps},"
                            f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
                            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                            f"setsar=1,"
                            f"trim=0:{take_str},setpts=PTS-STARTPTS"
                            f"[{vout}]"
                        )
                vf_parts.append(chain)
                vlabels.append(f"[{vout}]")
            concat = "".join(vlabels) + f"concat=n={len(segments)}:v=1:a=0[vout]"
            filter_complex = ";".join(vf_parts + [concat])
        else:
            raise ValueError(f"Modo de vídeo inválido: {video_mode}. Use 'videos' ou 'images'.")

        # Salva filter_complex em arquivo se muito grande
        if len(filter_complex) > 32768:  # 32KB limit
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(filter_complex)
                ctx["filter_complex_file"] = f.name
                ctx["use_filter_complex_file"] = True
        else:
            ctx["filter_complex"] = filter_complex
            ctx["use_filter_complex_file"] = False

        ctx["inputs"] = inputs
        ctx["map_out"] = "[vout]"
        ctx["audio_idx"] = 0
        ctx["segments"] = segments
        return ctx

class OverlayStage(PipelineStage):
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if ctx.get("overlay"):
            overlay = ctx["overlay"]
            overlay_opacity = ctx["overlay_opacity"]
            inputs = ctx["inputs"]
            use_filter_file = ctx.get("use_filter_complex_file", False)

            if use_filter_file:
                # Lê o filtro do arquivo
                with open(ctx["filter_complex_file"], 'r') as f:
                    filter_complex = f.read()
            else:
                filter_complex = ctx["filter_complex"]

            map_out = ctx["map_out"]
            audio_idx = ctx["audio_idx"]
            overlay_path = str(overlay)
            overlay_idx = sum(1 for x in inputs if x == "-i")
            inputs += ["-stream_loop", "-1", "-i", overlay_path]
            overlay_filter = f"[{overlay_idx}:v]format=rgba,colorchannelmixer=aa={overlay_opacity}[ol];{map_out}[ol]overlay=shortest=1:format=auto[vfinal]"
            filter_complex = f"{filter_complex};{overlay_filter}"
            map_out = "[vfinal]"

            # Atualiza arquivo ou variável
            if len(filter_complex) > 32768:
                import tempfile
                if use_filter_file:
                    # Sobrescreve arquivo existente
                    with open(ctx["filter_complex_file"], 'w') as f:
                        f.write(filter_complex)
                else:
                    # Cria novo arquivo
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(filter_complex)
                        ctx["filter_complex_file"] = f.name
                        ctx["use_filter_complex_file"] = True
            else:
                ctx["filter_complex"] = filter_complex
                ctx["use_filter_complex_file"] = False

            ctx["inputs"] = inputs
            ctx["map_out"] = map_out
            ctx["audio_idx"] = audio_idx
        return ctx

class LogoStage(PipelineStage):
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if ctx.get("logo"):
            logo = ctx["logo"]
            logo_scale = ctx.get("logo_scale", 0.15)
            logo_position = ctx.get("logo_position", "top_right")
            width = ctx.get("width", 1920)
            height = ctx.get("height", 1080)
            inputs = ctx["inputs"]
            use_filter_file = ctx.get("use_filter_complex_file", False)

            if use_filter_file:
                with open(ctx["filter_complex_file"], 'r') as f:
                    filter_complex = f.read()
            else:
                filter_complex = ctx["filter_complex"]

            map_out = ctx["map_out"]
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
            filter_complex = f"{filter_complex};{logo_filter}"
            map_out = "[vlogo]"

            # Atualiza arquivo ou variável
            if len(filter_complex) > 32768:
                import tempfile
                if use_filter_file:
                    with open(ctx["filter_complex_file"], 'w') as f:
                        f.write(filter_complex)
                else:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(filter_complex)
                        ctx["filter_complex_file"] = f.name
                        ctx["use_filter_complex_file"] = True
            else:
                ctx["filter_complex"] = filter_complex
                ctx["use_filter_complex_file"] = False

            ctx["inputs"] = inputs
            ctx["map_out"] = map_out
        return ctx

class ChromaStage(PipelineStage):
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
        if chroma_list:
            inputs = ctx["inputs"]
            use_filter_file = ctx.get("use_filter_complex_file", False)

            if use_filter_file:
                with open(ctx["filter_complex_file"], 'r') as f:
                    filter_complex = f.read()
            else:
                filter_complex = ctx["filter_complex"]

            map_out = ctx["map_out"]
            from audio_utils import duration_seconds
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
                chroma_idx = sum(1 for x in inputs if x == "-i")
                inputs += ["-i", str(chroma_path)]
                chroma_x, chroma_y = pos_map.get(chroma_position, (20, 20))
                chroma_filter = (
                    f"[{chroma_idx}:v]trim=start=0:end={chroma_duration},setpts=PTS+{chroma_start}/TB,colorkey=0x00FF00:0.3:0.2,scale=iw*{chroma_scale}:ih*{chroma_scale}[chroma{chroma_idx}];"
                    f"{last_map}[chroma{chroma_idx}]overlay=x={chroma_x}:y={chroma_y}:enable='between(t,{chroma_start},{chroma_end})':format=auto[vchroma{chroma_idx}]"
                )
                filter_complex = f"{filter_complex};{chroma_filter}"
                last_map = f"[vchroma{chroma_idx}]"

            # Atualiza arquivo ou variável
            if len(filter_complex) > 32768:
                import tempfile
                if use_filter_file:
                    with open(ctx["filter_complex_file"], 'w') as f:
                        f.write(filter_complex)
                else:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(filter_complex)
                        ctx["filter_complex_file"] = f.name
                        ctx["use_filter_complex_file"] = True
            else:
                ctx["filter_complex"] = filter_complex
                ctx["use_filter_complex_file"] = False

            ctx["inputs"] = inputs
            ctx["map_out"] = last_map
        return ctx

class TransitionStage(PipelineStage):
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
    # Subconjunto de transições leves para random
    LIGHT_TRANSITIONS = [
        "fade", "wipeleft", "wiperight", "wipeup", "wipedown",
        "slideleft", "slideright", "slideup", "slidedown", "dissolve"
    ]
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        transition_type = ctx.get("transition_type", "none")
        if transition_type == "none":
            return ctx

        segments = ctx.get("segments", [])
        if len(segments) < 2:
            return ctx

        existing_filter = ctx.get("filter_complex", "")
        fps = ctx.get("fps", 30)

        # OTIMIZAÇÃO: Em vez de processar cada imagem separadamente e depois aplicar
        # transições em cascata, vamos criar um filter graph mais eficiente

        # 1) Prepara entradas de vídeo com configurações uniformes - apenas uma vez
        prep_filters = []
        clean_labels = []
        for i in range(1, len(segments) + 1):
            src = f"v{i}"
            dst = f"vc{i}"  # "v-clean"
            # Aplica configurações básicas uniformes apenas uma vez por imagem
            prep_filters.append(f"[{src}]settb=AVTB,fps={fps},format=yuv420p[{dst}]")
            clean_labels.append(dst)

        # 2) Transições em grupos paralelos, sem encadeamento excessivo
        transition_opts = [t for t in self.SUPPORTED_TRANSITIONS if t != "fade"]

        # Vamos processar em grupos de 4-6 imagens para evitar cascata muito longa
        group_size = min(6, max(4, len(segments) // 3))
        if len(segments) <= group_size:
            # Se tivermos poucas imagens, usamos o método original
            group_size = len(segments)

        groups = []
        for i in range(0, len(clean_labels), group_size):
            groups.append(clean_labels[i:i+group_size])

        # Processa cada grupo separadamente
        group_outputs = []
        group_filters = []

        for group_idx, group in enumerate(groups):
            if len(group) == 1:
                # Se só tem um item no grupo, não precisa de transição
                group_outputs.append(group[0])
                continue

            # Processa transições dentro do grupo
            prev_label = group[0]
            prev_dur = segments[group_idx * group_size][1]  # duração do primeiro take no grupo
            transitions = []

            for i in range(1, len(group)):
                global_idx = group_idx * group_size + i
                if global_idx >= len(segments):  # Proteção contra índice fora do limite
                    continue

                if transition_type == "random":
                    ttype = random.choice(transition_opts)
                else:
                    ttype = transition_type if transition_type in self.SUPPORTED_TRANSITIONS else "fade"

                curr_label = group[i]
                curr_dur = segments[global_idx][1]

                # offset relativo ao primeiro input do xfade atual
                offset = max(prev_dur - 1, 0)

                mid = f"t{group_idx}_{i}"
                out = f"trans{group_idx}_{i}"
                trans = (
                    f"[{prev_label}][{curr_label}]xfade=transition={ttype}:duration=1:offset={offset}[{out}]"
                )
                transitions.append(trans)

                prev_label = out
                prev_dur = prev_dur + curr_dur - 1

            # Adiciona as transições do grupo
            group_filters.extend(transitions)
            # Último output do grupo
            if transitions:  # Se tiver transições, usa o último label de saída
                group_outputs.append(prev_label)
            else:  # Caso contrário, usa a primeira entrada limpa
                group_outputs.append(group[0])

        # 3) Concatena os grupos
        if len(group_outputs) > 1:
            concat_labels = "".join(f"[{label}]" for label in group_outputs)
            final_out = "vout"  # Mudança: usar "vout" em vez de "final_out"
            concat_filter = f"{concat_labels}concat=n={len(group_outputs)}:v=1:a=0[{final_out}]"
            group_filters.append(concat_filter)
            final_label = f"[{final_out}]"  # Adicionamos os colchetes aqui
        else:
            final_label = f"[{group_outputs[0]}]"

        # 4) Recria o filter_complex removendo o concat original
        filter_parts = [f for f in existing_filter.split(";") if "concat=" not in f]
        filter_parts.extend(prep_filters)
        filter_parts.extend(group_filters)

        # Cria filter_complex como arquivo temporário se for muito grande
        filter_complex = ";".join(filter_parts)
        if len(filter_complex) > 50000:
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(filter_complex)
                ctx["filter_complex_file"] = f.name
                ctx["use_filter_complex_file"] = True
        else:
            ctx["filter_complex"] = filter_complex
            ctx["use_filter_complex_file"] = False

        ctx["map_out"] = final_label
        return ctx

class CinematicStage(PipelineStage):
    """Aplica efeitos cinematográficos como LUT, curves, vignette"""

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

        use_filter_file = ctx.get("use_filter_complex_file", False)

        if use_filter_file:
            # Lê o filtro do arquivo
            with open(ctx["filter_complex_file"], 'r') as f:
                filter_complex = f.read()
        else:
            filter_complex = ctx["filter_complex"]

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
                cinematic_filters.append("colorchannelmixer=rr=0.393:rg=0.769:rb=0.189:gr=0.349:gg=0.686:gb=0.168:br=0.272:bg=0.534:bb=0.131")
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

        # Aplicar vignette - funciona independente do preset
        if enable_vignette:
            angle_value = vignette_intensity * 3.14159 / 4
            cinematic_filters.append(f"vignette=angle={angle_value}")

        if cinematic_filters:
            cinematic_chain = ",".join(cinematic_filters)
            cinematic_out = "[vcinematic]"
            cinematic_filter = f"{map_out}{cinematic_chain}{cinematic_out}"
            filter_complex = f"{filter_complex};{cinematic_filter}"

            # Atualiza arquivo ou variável
            if len(filter_complex) > 32768:
                import tempfile
                if use_filter_file:
                    # Sobrescreve arquivo existente
                    with open(ctx["filter_complex_file"], 'w') as f:
                        f.write(filter_complex)
                else:
                    # Cria novo arquivo
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                        f.write(filter_complex)
                        ctx["filter_complex_file"] = f.name
                        ctx["use_filter_complex_file"] = True
            else:
                ctx["filter_complex"] = filter_complex
                ctx["use_filter_complex_file"] = False

            ctx["map_out"] = cinematic_out

        return ctx

class SubtitleStage(PipelineStage):
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        if ctx.get("enable_subtitles"):
            from subtitle_utils import extract_audio_for_transcription, transcribe_audio, create_subtitle_filter
            import tempfile
            import os

            narration_path = ctx["narration_path"]
            subtitle_font_size = ctx.get("subtitle_font_size", 24)
            subtitle_color = ctx.get("subtitle_color", "white")
            subtitle_position = ctx.get("subtitle_position", "bottom_center")
            subtitle_font = ctx.get("subtitle_font", None)
            words_per_subtitle = ctx.get("words_per_subtitle", 1)
            vosk_model_path = ctx.get("vosk_model_path", "_internal/vosk_models/vosk-model-pt")

            use_filter_file = ctx.get("use_filter_complex_file", False)

            if use_filter_file:
                with open(ctx["filter_complex_file"], 'r') as f:
                    filter_complex = f.read()
            else:
                filter_complex = ctx["filter_complex"]

            map_out = ctx["map_out"]

            # Extrai áudio temporário para transcrição
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                temp_audio_path = temp_audio.name

            try:
                extract_audio_for_transcription(narration_path, temp_audio_path)
                segments = transcribe_audio(temp_audio_path, vosk_model_path)

                if segments:
                    subtitle_filter = create_subtitle_filter(
                        segments,
                        subtitle_font_size,
                        subtitle_color,
                        subtitle_position,
                        words_per_subtitle,
                        subtitle_font,
                        ctx.get("subtitle_outline_color", "black"),
                        ctx.get("subtitle_outline_width", 2),
                        ctx.get("subtitle_shadow_color", "black"),
                        ctx.get("subtitle_shadow_x", 2),
                        ctx.get("subtitle_shadow_y", 2)
                    )
                    if subtitle_filter:
                        filter_complex = f"{filter_complex};{map_out}{subtitle_filter}[vsubtitles]"
                        ctx["map_out"] = "[vsubtitles]"

                        # Atualiza arquivo ou variável
                        if len(filter_complex) > 32768:
                            if use_filter_file:
                                with open(ctx["filter_complex_file"], 'w') as f:
                                    f.write(filter_complex)
                            else:
                                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                                    f.write(filter_complex)
                                    ctx["filter_complex_file"] = f.name
                                    ctx["use_filter_complex_file"] = True
                        else:
                            ctx["filter_complex"] = filter_complex
                            ctx["use_filter_complex_file"] = False

            finally:
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)

        return ctx

class ImageCacheStage(PipelineStage):
    """Pré-renderiza imagens em vídeos curtos para cache"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        import time

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

class OutputStage(PipelineStage):
    """Estágio final que gera o vídeo de saída"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        import time
        import os
        import glob

        print("Iniciando renderização final...")
        start_time = time.time()

        inputs = ctx["inputs"]
        map_out = ctx["map_out"]
        audio_idx = ctx["audio_idx"]
        out_path = ctx["out_path"]
        encoder_config = ctx.get("encoder_config", {})
        use_filter_file = ctx.get("use_filter_complex_file", False)

        # Comando base
        cmd = [get_ffmpeg_path()] + inputs

        # Usa arquivo de filtro se disponível, senão filtro inline
        if use_filter_file and ctx.get("filter_complex_file"):
            cmd.extend(["-filter_complex_script", ctx["filter_complex_file"]])
        else:
            filter_complex = ctx.get("filter_complex", "")
            cmd.extend(["-filter_complex", filter_complex])

        cmd.extend(["-map", map_out])

        # Processamento de áudio com trilha de fundo
        background_music_idx = ctx.get("background_music_idx")
        background_music_volume = ctx.get("background_music_volume", 0.2)

        if background_music_idx is not None:
            # Calcula duração da narração para repetir a música
            from audio_utils import duration_seconds
            narration_duration = duration_seconds(ctx["narration_path"])

            # Cria filtro de áudio que repete a música e mixa com a narração
            audio_filter = (
                f"[{background_music_idx}:a]aloop=loop=-1:size=2e+09,volume={background_music_volume}[bg];"
                f"[{audio_idx}:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )

            # Adiciona filtro de áudio ao filtro complexo existente
            if use_filter_file and ctx.get("filter_complex_file"):
                with open(ctx["filter_complex_file"], 'r') as f:
                    filter_complex = f.read()
                filter_complex = f"{filter_complex};{audio_filter}"
                with open(ctx["filter_complex_file"], 'w') as f:
                    f.write(filter_complex)
            else:
                filter_complex = ctx.get("filter_complex", "")
                filter_complex = f"{filter_complex};{audio_filter}"
                cmd[cmd.index("-filter_complex") + 1] = filter_complex

            cmd.extend(["-map", "[aout]"])
        else:
            cmd.extend(["-map", f"{audio_idx}:a"])

        # Configurações do encoder
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

        # Configurações de áudio e saída
        cmd.extend(["-c:a", "aac", "-b:a", "128k", str(out_path)])

        try:
            # Log do comando (sem mostrar filtro complexo se muito grande)
            if use_filter_file:
                print(f"\nUsando arquivo de filtro: {ctx['filter_complex_file']}")

            print("Executando renderização...")
            run(cmd)

        finally:
            # Remove arquivo temporário de filtro se existir
            if use_filter_file and ctx.get("filter_complex_file"):
                filter_file = ctx["filter_complex_file"]
                if os.path.exists(filter_file):
                    os.unlink(filter_file)

            # Remove arquivos de comando .txt da pasta cache
            cache_dir = Path(out_path).parent / "cache"
            if cache_dir.exists():
                cmd_files = glob.glob(str(cache_dir / "cmd_*.txt"))
                for cmd_file in cmd_files:
                    try:
                        os.unlink(cmd_file)
                    except OSError:
                        pass
                print(f"Removidos {len(cmd_files)} arquivos de comando da cache")

        total_time = time.time() - start_time
        print(f"Renderização final concluída em {total_time:.1f}s")

        ctx["render_time"] = total_time
        return ctx

class MediaPipeline:
    def __init__(self, stages: TList[PipelineStage]):
        self.stages = stages
    def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        for stage in self.stages:
            ctx = stage(ctx)
        return ctx

class BackgroundMusicStage(PipelineStage):
    """Estágio que adiciona trilha de fundo ao áudio"""

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        background_music = ctx.get("background_music")
        background_music_volume = ctx.get("background_music_volume", 0.2)

        if not background_music:
            return ctx

        from pathlib import Path
        music_path = Path(background_music)
        if not music_path.exists():
            print(f"Aviso: Arquivo de música de fundo não encontrado: {background_music}")
            return ctx

        print(f"Adicionando trilha de fundo: {background_music} (volume: {background_music_volume})")

        # Adiciona a música de fundo aos inputs
        inputs = ctx["inputs"]
        inputs.extend(["-i", str(music_path)])

        # Atualiza índice da música de fundo
        music_idx = len([inp for inp in inputs if inp == "-i"]) - 1
        ctx["background_music_idx"] = music_idx
        ctx["background_music_volume"] = background_music_volume
        ctx["inputs"] = inputs

        return ctx
