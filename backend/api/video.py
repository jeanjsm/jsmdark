from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
from backend.pipelines.video_pipeline import process_video
from typing import Optional
import shutil
import tempfile
import os

router = APIRouter()

@router.post("/process")
async def process_video_route(
    narration: UploadFile = File(...),
    videos_folder: Optional[str] = Form(None),
    video_mode: Optional[str] = Form("images"),
    output_path: Optional[str] = Form("output_videos/output.mp4"),
    seed: Optional[int] = Form(42),
    fps: Optional[int] = Form(30),
    width: Optional[int] = Form(1280),
    height: Optional[int] = Form(720),
    crf: Optional[int] = Form(23),
    preset: Optional[str] = Form("medium"),
    image_segment_duration: Optional[float] = Form(3.0),
    overlay: Optional[str] = Form(None),
    overlay_opacity: Optional[float] = Form(0.3),
    logo: Optional[str] = Form(None),
    logo_scale: Optional[float] = Form(0.15),
    logo_position: Optional[str] = Form("top_right"),
    chroma: Optional[str] = Form(None),
    chroma_scale: Optional[float] = Form(0.5),
    chroma_position: Optional[str] = Form("bottom_right"),
    chroma_start: Optional[float] = Form(0),
    enable_ken_burns: Optional[bool] = Form(False),
    enable_subtitles: Optional[bool] = Form(False),
    subtitle_effect: Optional[str] = Form(None),
    subtitle_font: Optional[str] = Form(None),
    subtitle_fontsize: Optional[int] = Form(None),
    subtitle_color: Optional[str] = Form(None),
    subtitle_box: Optional[bool] = Form(None),
    subtitle_boxcolor: Optional[str] = Form(None),
    subtitle_boxborderw: Optional[int] = Form(None),
    background_music: Optional[str] = Form(None),
    music_volume: Optional[float] = Form(0.15),
    music_fade: Optional[bool] = Form(True),
    music_offset: Optional[float] = Form(0),
    extra_ffmpeg_args: Optional[str] = Form(None)
):
    # Salva o arquivo temporariamente
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
        shutil.copyfileobj(narration.file, tmp)
        narration_path = tmp.name
    # Corrige parâmetros enviados como 'string' (Swagger UI default)
    def fix_param(val):
        return None if val in (None, '', 'string') else val
    overlay = fix_param(overlay)
    logo = fix_param(logo)
    chroma = fix_param(chroma)
    background_music = fix_param(background_music)
    subtitle_font = fix_param(subtitle_font)
    subtitle_color = fix_param(subtitle_color)
    subtitle_boxcolor = fix_param(subtitle_boxcolor)
    subtitle_effect = fix_param(subtitle_effect)
    logo_position = fix_param(logo_position)
    chroma_position = fix_param(chroma_position)
    preset = fix_param(preset)
    video_mode = fix_param(video_mode)
    output_path = fix_param(output_path)
    out_path = process_video(
        narration_path,
        videos_folder=videos_folder,
        video_mode=video_mode,
        output_path=output_path,
        seed=seed,
        fps=fps,
        width=width,
        height=height,
        crf=crf,
        preset=preset,
        image_segment_duration=image_segment_duration,
        overlay=overlay,
        overlay_opacity=overlay_opacity,
        logo=logo,
        logo_scale=logo_scale,
        logo_position=logo_position,
        chroma=chroma,
        chroma_scale=chroma_scale,
        chroma_position=chroma_position,
        chroma_start=chroma_start,
        enable_ken_burns=enable_ken_burns,
        enable_subtitles=enable_subtitles,
        subtitle_effect=subtitle_effect,
        subtitle_font=subtitle_font,
        subtitle_fontsize=subtitle_fontsize,
        subtitle_color=subtitle_color,
        subtitle_box=subtitle_box,
        subtitle_boxcolor=subtitle_boxcolor,
        subtitle_boxborderw=subtitle_boxborderw,
        background_music=background_music,
        music_volume=music_volume,
        music_fade=music_fade,
        music_offset=music_offset,
        extra_ffmpeg_args=extra_ffmpeg_args
    )
    if os.path.exists(out_path):
        return FileResponse(out_path, media_type="video/mp4", filename=os.path.basename(out_path))
    return {"error": "Erro ao gerar vídeo."}
