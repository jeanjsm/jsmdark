from pathlib import Path
from backend.services.audio_utils import duration_seconds
from backend.services.video_utils import list_videos, pick_segments_to_cover, list_images, pick_image_segments_to_cover
from backend.services.subtitle_utils import normalize_text, ff_escape, extract_audio_for_transcription
from backend.pipelines.pipeline import VideoBaseStage, OverlayStage, LogoStage, ChromaStage
import tempfile
import shutil
import os

def process_video(narration_file, videos_folder=None, video_mode="images", output_path="output_videos/output.mp4", **kwargs):
    """
    Executa o pipeline de vídeo usando stages modulares.
    narration_file: arquivo-like ou caminho da narração
    videos_folder: pasta de imagens ou vídeos
    video_mode: 'images' ou 'videos'
    output_path: caminho de saída
    kwargs: outros parâmetros do pipeline
    """
    # Salva narração temporária se for arquivo-like
    if hasattr(narration_file, 'read'):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
            shutil.copyfileobj(narration_file, tmp)
            narration_path = tmp.name
    else:
        narration_path = str(narration_file)

    ctx = {
        "narration_path": narration_path,
        "videos_folder": videos_folder or "arquivos_teste/1",
        "seed": kwargs.get("seed", 42),
        "fps": kwargs.get("fps", 30),
        "width": kwargs.get("width", 1280),
        "height": kwargs.get("height", 720),
        "crf": kwargs.get("crf", 23),
        "preset": kwargs.get("preset", "medium"),
        "video_mode": video_mode,
        "image_segment_duration": kwargs.get("image_segment_duration", 3.0),
        "out_path": output_path,
        "overlay": kwargs.get("overlay"),
        "overlay_opacity": kwargs.get("overlay_opacity", 0.3),
        "logo": kwargs.get("logo"),
        "logo_scale": kwargs.get("logo_scale", 0.15),
        "logo_position": kwargs.get("logo_position", "top_right"),
        "chroma": kwargs.get("chroma"),
        "chroma_scale": kwargs.get("chroma_scale", 0.5),
        "chroma_position": kwargs.get("chroma_position", "bottom_right"),
        "chroma_start": kwargs.get("chroma_start", 0),
        "chroma_list": kwargs.get("chroma_list"),
        "enable_ken_burns": kwargs.get("enable_ken_burns", False),
        "cached_images": kwargs.get("cached_images", {}),
        # Parâmetros para legendas e trilha sonora
        "enable_subtitles": kwargs.get("enable_subtitles", False),
        "subtitle_effect": kwargs.get("subtitle_effect"),
        "subtitle_font": kwargs.get("subtitle_font"),
        "subtitle_fontsize": kwargs.get("subtitle_fontsize"),
        "subtitle_color": kwargs.get("subtitle_color"),
        "subtitle_box": kwargs.get("subtitle_box"),
        "subtitle_boxcolor": kwargs.get("subtitle_boxcolor"),
        "subtitle_boxborderw": kwargs.get("subtitle_boxborderw"),
        "background_music": kwargs.get("background_music"),
        "music_volume": kwargs.get("music_volume", 0.15),
        "music_fade": kwargs.get("music_fade", True),
        "music_offset": kwargs.get("music_offset", 0),
        # Outros parâmetros possíveis
        "extra_ffmpeg_args": kwargs.get("extra_ffmpeg_args"),
    }
    # Executa stages principais
    for stage_cls in [VideoBaseStage, OverlayStage, LogoStage, ChromaStage]:
        stage = stage_cls()
        ctx = stage(ctx)
    # Monta comando FFmpeg final
    inputs = ctx["inputs"]
    filter_complex = ctx.get("filter_complex")
    use_filter_file = ctx.get("use_filter_complex_file", False)
    out_path = ctx["out_path"]
    map_out = ctx["map_out"]
    audio_idx = ctx["audio_idx"]
    ffmpeg_cmd = ["ffmpeg"] + inputs
    if use_filter_file:
        ffmpeg_cmd += ["-filter_complex_script", ctx["filter_complex_file"]]
    else:
        ffmpeg_cmd += ["-filter_complex", filter_complex]
    ffmpeg_cmd += ["-map", map_out, "-map", f"{audio_idx}:a?", "-c:v", "libx264", "-crf", str(ctx["crf"]), "-preset", ctx["preset"], "-shortest", out_path]
    from backend.utils.ffmpeg_utils import run
    run(ffmpeg_cmd)
    # Remove arquivos temporários
    if hasattr(narration_file, 'read'):
        os.remove(narration_path)
    if use_filter_file:
        os.remove(ctx["filter_complex_file"])
    return out_path
