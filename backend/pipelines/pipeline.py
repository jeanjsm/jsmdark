from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any
from backend.services.audio_utils import duration_seconds
from backend.services.video_utils import list_videos, pick_segments_to_cover, list_images, pick_image_segments_to_cover
import random
from backend.utils.ffmpeg_utils import run, get_ffmpeg_path

class PipelineStage(ABC):
    @abstractmethod
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        pass

class VideoBaseStage(PipelineStage):
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # ...código da VideoBaseStage migrado de pipeline.py...
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
            cached_images = ctx.get("cached_images", {})
            for img, take in segments:
                if str(img) in cached_images:
                    cached_video = cached_images[str(img)]
                    inputs += ["-i", cached_video]
                else:
                    inputs += ["-loop", "1", "-t", f"{take:.3f}", "-i", str(img)]
            for idx, (img, take) in enumerate(segments, start=1):
                label_in = f"{idx}:v"
                take_str = f"{take:.3f}"
                vout = f"v{idx}"
                ken_burns_enabled = ctx.get("enable_ken_burns", False)
                if str(img) in cached_images:
                    if ken_burns_enabled:
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
                    if ken_burns_enabled:
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
        if len(filter_complex) > 32768:
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
        # ...código da OverlayStage migrado de pipeline.py...
        if ctx.get("overlay"):
            overlay = ctx["overlay"]
            overlay_opacity = ctx["overlay_opacity"]
            inputs = ctx["inputs"]
            use_filter_file = ctx.get("use_filter_complex_file", False)
            if use_filter_file:
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
            ctx["audio_idx"] = audio_idx
        return ctx

class LogoStage(PipelineStage):
    def __call__(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        # ...código da LogoStage migrado de pipeline.py...
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
        # ...código da ChromaStage migrado de pipeline.py...
        chroma_list = ctx.get("chroma_list")
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
            # ...restante da lógica da ChromaStage...
        return ctx
