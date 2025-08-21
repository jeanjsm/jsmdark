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
        ctx["inputs"] = inputs
        ctx["filter_complex"] = filter_complex
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
            filter_complex = ctx["filter_complex"]
            map_out = ctx["map_out"]
            audio_idx = ctx["audio_idx"]
            overlay_path = str(overlay)
            overlay_idx = sum(1 for x in inputs if x == "-i")
            inputs += ["-stream_loop", "-1", "-i", overlay_path]
            overlay_filter = f"[{overlay_idx}:v]format=rgba,colorchannelmixer=aa={overlay_opacity}[ol];{map_out}[ol]overlay=shortest=1:format=auto[vfinal]"
            filter_complex = f"{filter_complex};{overlay_filter}"
            map_out = "[vfinal]"
            ctx["inputs"] = inputs
            ctx["filter_complex"] = filter_complex
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
            filter_complex = ctx["filter_complex"]
            map_out = ctx["map_out"]
            logo_idx = sum(1 for x in inputs if x == "-i")
            inputs += ["-i", str(logo)]
            # Calcula posição
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
            ctx["inputs"] = inputs
            ctx["filter_complex"] = filter_complex
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
            ctx["inputs"] = inputs
            ctx["filter_complex"] = filter_complex
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

    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        transition_type = ctx.get("transition_type", "none")
        if transition_type == "none":
            return ctx

        segments = ctx.get("segments", [])
        if len(segments) < 2:
            return ctx

        existing_filter = ctx.get("filter_complex", "")
        fps = ctx.get("fps", 30)

        # 1) Normaliza CADA [vN] antes de entrar em qualquer xfade
        #    Isso evita "current rate of 1/0" já no primeiro xfade.
        prep_filters = []
        clean_labels = []
        for i in range(1, len(segments) + 1):
            src = f"v{i}"
            dst = f"vc{i}"           # "v-clean"
            prep_filters.append(f"[{src}]settb=AVTB,fps={fps},format=yuv420p[{dst}]")
            clean_labels.append(dst)

        # 2) Encadeia as transições usando as labels normalizadas
        transition_opts = [t for t in self.SUPPORTED_TRANSITIONS if t != "fade"]

        prev_label = clean_labels[0]
        prev_dur = segments[0][1]  # duração do primeiro take
        transitions = []

        for i in range(1, len(segments)):
            if transition_type == "random":
                ttype = random.choice(transition_opts)
            else:
                ttype = transition_type if transition_type in self.SUPPORTED_TRANSITIONS else "fade"

            curr_label = clean_labels[i]
            curr_dur = segments[i][1]

            # offset relativo ao primeiro input do xfade atual
            offset = max(prev_dur - 1, 0)

            mid = f"t{i}"
            out = f"trans{i}"
            # xfade -> normaliza a SAÍDA para alimentar o próximo xfade
            trans = (
                f"[{prev_label}][{curr_label}]xfade=transition={ttype}:duration=1:offset={offset}[{mid}];"
                f"[{mid}]settb=AVTB,fps={fps},format=yuv420p[{out}]"
            )
            transitions.append(trans)

            prev_label = out
            prev_dur = prev_dur + curr_dur - 1

        # 3) Remove o concat original e injeta prep + transições
        filter_parts = existing_filter.split(";")
        filter_parts = [f for f in filter_parts if "concat=" not in f]
        filter_parts.extend(prep_filters)
        filter_parts.extend(transitions)

        ctx["filter_complex"] = ";".join(filter_parts)
        ctx["map_out"] = f"[{prev_label}]"
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
            ctx["filter_complex"] = filter_complex
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
                        # Aplica legendas como novo filtro no mapa atual
                        filter_complex = f"{filter_complex};{map_out}{subtitle_filter}[vsubtitles]"
                        ctx["map_out"] = "[vsubtitles]"

            finally:
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)

            ctx["filter_complex"] = filter_complex
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
                encoder_config
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

    def _prerender_image(self, img_path, output_path, duration, fps, width, height, encoder_config):
        """Renderiza uma imagem em vídeo curto sem efeitos"""

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

        print("Iniciando renderização final...")
        start_time = time.time()

        inputs = ctx["inputs"]
        filter_complex = ctx["filter_complex"]
        map_out = ctx["map_out"]
        audio_idx = ctx["audio_idx"]
        out_path = ctx["out_path"]
        encoder_config = ctx.get("encoder_config", {})

        # Comando base
        cmd = ["ffmpeg"] + inputs + ["-filter_complex", filter_complex, "-map", map_out, "-map", f"{audio_idx}:a"]

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

        # Executa o comando
        run(cmd)

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
