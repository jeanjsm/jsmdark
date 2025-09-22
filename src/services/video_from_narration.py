"""
video_from_narration.py

Generates a video from a narration audio file, randomly selecting clips or images from a folder and assembling them into a final video.
Output: 1920x1080, 30fps, H.264, narration audio.
"""
import argparse
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List as TList, Optional

# Local imports (relative)
from .pipeline import (
    MediaPipeline,
    VideoBaseStage,
    OverlayStage,
    LogoStage,
    ChromaStage,
    TransitionStage,
    SubtitleStage,
    CinematicStage,
    EncoderStage,
    OutputStage,
    BackgroundMusicStage,
    EndingStage,
    MediaCacheStage,
    OpeningStage,
)

# Named constants for magic numbers
DEFAULT_FPS = 30
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_CRF = 18
DEFAULT_PRESET = "medium"
DEFAULT_IMAGE_SEGMENT_DURATION = 2.0
DEFAULT_OVERLAY_OPACITY = 1.0
DEFAULT_LOGO_SCALE = 0.15
DEFAULT_LOGO_X = 20
DEFAULT_LOGO_Y = 20
DEFAULT_LOGO_POSITION = "top_right"
DEFAULT_CHROMA_SCALE = 0.5
DEFAULT_CHROMA_POSITION = "bottom_right"
DEFAULT_CHROMA_START = 0.0
DEFAULT_TRANSITION_TYPE = "none"
DEFAULT_SUBTITLE_FONT_SIZE = 24
DEFAULT_SUBTITLE_COLOR = "white"
DEFAULT_SUBTITLE_POSITION = "bottom_center"
DEFAULT_SUBTITLE_OUTLINE_COLOR = "black"
DEFAULT_SUBTITLE_OUTLINE_WIDTH = 2
DEFAULT_SUBTITLE_SHADOW_COLOR = "black"
DEFAULT_SUBTITLE_SHADOW_X = 2
DEFAULT_SUBTITLE_SHADOW_Y = 2
DEFAULT_WORDS_PER_SUBTITLE = 1
DEFAULT_VOSK_MODEL_PATH = "_internal/vosk_models/vosk-model-pt"
DEFAULT_VIGNETTE_INTENSITY = 1.0
DEFAULT_ENCODER = "libx264"
DEFAULT_PERFORMANCE_PROFILE = "quality"
DEFAULT_THREADS = 0
DEFAULT_GPU_QUALITY = 18
DEFAULT_RESOLUTION_PRESET = "horizontal_1080p"
DEFAULT_BACKGROUND_MUSIC_VOLUME = 0.2
DEFAULT_SUBTITLE_EFFECT = "none"

class VideoFromNarrationError(Exception):
    """Custom exception for video generation errors."""
    pass

def create_video_from_narration(
    narration_path: str,
    videos_folder: str,
    out_path: str = "output.mp4",
    seed: Optional[int] = None,
    shuffle: Optional[bool] = True,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    crf: int = DEFAULT_CRF,
    preset: str = DEFAULT_PRESET,
    video_mode: str = "videos",
    image_segment_duration: float = DEFAULT_IMAGE_SEGMENT_DURATION,
    overlay: Optional[str] = None,
    overlay_opacity: float = DEFAULT_OVERLAY_OPACITY,
    logo: Optional[str] = None,
    logo_scale: float = DEFAULT_LOGO_SCALE,
    logo_x: int = DEFAULT_LOGO_X,
    logo_y: int = DEFAULT_LOGO_Y,
    logo_position: str = DEFAULT_LOGO_POSITION,
    chroma: Optional[str] = None,
    chroma_scale: float = DEFAULT_CHROMA_SCALE,
    chroma_position: str = DEFAULT_CHROMA_POSITION,
    chroma_start: float = DEFAULT_CHROMA_START,
    chroma_list: Optional[TList[Dict[str, Any]]] = None,
    transition_type: str = DEFAULT_TRANSITION_TYPE,
    enable_subtitles: bool = False,
    subtitle_font_size: int = DEFAULT_SUBTITLE_FONT_SIZE,
    subtitle_color: str = DEFAULT_SUBTITLE_COLOR,
    subtitle_position: str = DEFAULT_SUBTITLE_POSITION,
    subtitle_font: Optional[str] = None,
    subtitle_outline_color: str = DEFAULT_SUBTITLE_OUTLINE_COLOR,
    subtitle_outline_width: int = DEFAULT_SUBTITLE_OUTLINE_WIDTH,
    subtitle_shadow_color: str = DEFAULT_SUBTITLE_SHADOW_COLOR,
    subtitle_shadow_x: int = DEFAULT_SUBTITLE_SHADOW_X,
    subtitle_shadow_y: int = DEFAULT_SUBTITLE_SHADOW_Y,
    words_per_subtitle: int = DEFAULT_WORDS_PER_SUBTITLE,
    vosk_model_path: str = DEFAULT_VOSK_MODEL_PATH,
    cinematic_preset: Optional[str] = None,
    custom_lut_path: Optional[str] = None,
    enable_vignette: bool = False,
    vignette_intensity: float = DEFAULT_VIGNETTE_INTENSITY,
    enable_curves: bool = False,
    custom_curves: Optional[str] = None,
    remove_silence: bool = False,
    silence_threshold: int = -40,
    silence_duration: float = 0.5,
    encoder: str = DEFAULT_ENCODER,
    performance_profile: str = DEFAULT_PERFORMANCE_PROFILE,
    threads: int = DEFAULT_THREADS,
    gpu_quality: int = DEFAULT_GPU_QUALITY,
    resolution_preset: str = DEFAULT_RESOLUTION_PRESET,
    background_music: Optional[str] = None,
    background_music_volume: float = DEFAULT_BACKGROUND_MUSIC_VOLUME,
    subtitle_effect: str = DEFAULT_SUBTITLE_EFFECT,
    ending_video_path: Optional[str] = None,
    opening_video_paths: Optional[TList[str]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Any:
    """
    Generates a video from a narration audio file and media folder.

    Args:
        narration_path (str): Path to narration audio file.
        videos_folder (str): Path to folder with video/image clips.
        out_path (str): Output video file path.
        ... (other parameters documented above)
    Returns:
        Any: Result of pipeline.run(ctx)
    Raises:
        VideoFromNarrationError: If video generation fails.
    """
    try:
        if remove_silence:
            from .audio_utils import remove_audio_silence
            narration_path = remove_audio_silence(
                narration_path,
                threshold_db=silence_threshold,
                stop_duration=silence_duration,
            )

        stages = [
            EncoderStage(),
            MediaCacheStage(),
            VideoBaseStage(),
            TransitionStage(),
            OpeningStage(),
            OverlayStage(),
            LogoStage(),
            ChromaStage(),
            CinematicStage(),
            SubtitleStage(),
            BackgroundMusicStage(),
            EndingStage(),
            OutputStage()
        ]
        ctx = {
            "narration_path": narration_path,
            "videos_folder": videos_folder,
            "out_path": out_path,
            "seed": seed,
            "shuffle": shuffle,
            "fps": fps,
            "width": width,
            "height": height,
            "crf": crf,
            "preset": preset,
            "video_mode": video_mode,
            "image_segment_duration": image_segment_duration,
            "overlay": overlay,
            "overlay_opacity": overlay_opacity,
            "logo": logo,
            "logo_scale": logo_scale,
            "logo_x": logo_x,
            "logo_y": logo_y,
            "logo_position": logo_position,
            "chroma": chroma,
            "chroma_scale": chroma_scale,
            "chroma_position": chroma_position,
            "chroma_start": chroma_start,
            "chroma_list": chroma_list,
            "transition_type": transition_type,
            "enable_subtitles": enable_subtitles,
            "subtitle_font_size": subtitle_font_size,
            "subtitle_color": subtitle_color,
            "subtitle_position": subtitle_position,
            "subtitle_font": subtitle_font,
            "subtitle_outline_color": subtitle_outline_color,
            "subtitle_outline_width": subtitle_outline_width,
            "subtitle_shadow_color": subtitle_shadow_color,
            "subtitle_shadow_x": subtitle_shadow_x,
            "subtitle_shadow_y": subtitle_shadow_y,
            "words_per_subtitle": words_per_subtitle,
            "vosk_model_path": vosk_model_path,
            "cinematic_preset": cinematic_preset,
            "custom_lut_path": custom_lut_path,
            "enable_vignette": enable_vignette,
            "vignette_intensity": vignette_intensity,
            "enable_curves": enable_curves,
            "custom_curves": custom_curves,
            "encoder": encoder,
            "performance_profile": performance_profile,
            "threads": threads,
            "gpu_quality": gpu_quality,
            "resolution_preset": resolution_preset,
            "background_music": background_music,
            "background_music_volume": background_music_volume,
            "subtitle_effect": subtitle_effect,
            "ending_video_path": ending_video_path,
            "opening_video_paths": opening_video_paths if opening_video_paths else [],
            "progress_callback": progress_callback,
        }
        pipeline = MediaPipeline(stages)
        return pipeline.run(ctx)
    except Exception as exc:
        logging.error(f"Video generation failed: {exc}")
        raise VideoFromNarrationError(f"Video generation failed: {exc}") from exc

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera vídeo a partir de narração e clipes ou imagens.")
    parser.add_argument("--narracao", default='./arquivos_teste/narracao.mp3', help="Caminho para o arquivo de narração (áudio)")
    parser.add_argument("--pasta_videos", default='./arquivos_teste/1/', help="Pasta com os vídeos ou imagens de entrada")
    parser.add_argument("--pasta_destino", default="output_videos/", help="Pasta de destino para o vídeo gerado")
    parser.add_argument("--seed", type=int, default=None, help="Seed para sorteio dos vídeos/imagens")
    parser.add_argument("--shuffle", type=bool, default=None, help="Randomiza a ordem dos vídeos/imagens (default: True)")
    parser.add_argument("--fps", type=int, default=30, help="Frames por segundo do vídeo final")
    parser.add_argument("--width", type=int, default=854, help="Largura do vídeo final")
    parser.add_argument("--height", type=int, default=480, help="Altura do vídeo final")
    parser.add_argument("--crf", type=int, default=18, help="CRF do x264 (qualidade, menor é melhor)")
    parser.add_argument("--preset", default="medium", help="Preset do x264 (ultrafast, fast, medium, slow, etc)")
    parser.add_argument("--video_mode", choices=["videos", "images"], default="videos", help="Modo de montagem: videos ou images")
    parser.add_argument("--image_segment_duration", type=float, default=6, help="Duração de cada imagem no vídeo (em segundos, só para modo images)")
    parser.add_argument("--overlay", default=None, help="Arquivo de vídeo overlay (mp4)")
    parser.add_argument("--overlay_opacity", type=float, default=0.3, help="Opacidade do overlay (0 a 1)")
    parser.add_argument("--logo", default=None, help="Arquivo de imagem da logo (png)")
    parser.add_argument("--logo_scale", type=float, default=0.15, help="Escala da logo (0.1 a 1.0)")
    parser.add_argument("--logo_x", type=int, default=20, help="Posição X da logo (em pixels)")
    parser.add_argument("--logo_y", type=int, default=20, help="Posição Y da logo (em pixels)")
    parser.add_argument("--logo_position", default="top_right", choices=[
        "top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right", "center"
    ], help="Posição da logo na tela")
    parser.add_argument("--chroma", default=None, help="Arquivo de vídeo chroma (mp4)")
    parser.add_argument("--chroma_scale", type=float, default=0.3, help="Escala do chroma (0.1 a 2.0)")
    parser.add_argument("--chroma_position", default="bottom_center", choices=[
        "top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right", "center"
    ], help="Posição do chroma na tela")
    parser.add_argument("--chroma_start", type=float, default=30, help="Tempo de início do chroma (em segundos)")
    parser.add_argument('--chroma_list', type=str, default=None, help='Lista de chromas em JSON. Exemplo: \'[{"path": "./chroma1.mp4", "scale": 1, "position": "bottom_center", "start": 4}]\'')

    parser.add_argument('--transition_type', default='none', choices=['none','fade', 'fadewhite', 'zoomin', 'smoothleft', 'smoothright', 'horzopen', 'random'], help='Tipo de transição entre vídeos')

    # Novos parâmetros para legendas
    parser.add_argument("--enable_subtitles", action="store_true", help="Habilita a adição de legendas automáticas no vídeo")
    parser.add_argument("--subtitle_font_size", type=int, default=60, help="Tamanho da fonte das legendas")
    parser.add_argument("--subtitle_color", default="yellow", help="Cor das legendas (em formato hexadecimal ou nome da cor)")
    parser.add_argument("--subtitle_position", default="center", choices=[
        "top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right", "center"
    ], help="Posição das legendas na tela")
    parser.add_argument("--subtitle_font", default="./_internal/_fonts/BebasNeue-Regular.ttf", help="Fonte das legendas (caminho do arquivo ou nome da fonte instalada)")
    parser.add_argument("--words_per_subtitle", type=int, default=5, help="Número de palavras por legenda")
    parser.add_argument("--vosk_model_path", default="_internal/vosk_models/vosk-model-pt", help="Caminho para o modelo do Vosk")
    parser.add_argument("--subtitle_outline_color", default="black", help="Cor do contorno das legendas (em formato hexadecimal ou nome da cor)")
    parser.add_argument("--subtitle_outline_width", type=int, default=2, help="Largura do contorno das legendas (em pixels)")
    parser.add_argument("--subtitle_shadow_color", default="black", help="Cor da sombra das legendas (em formato hexadecimal ou nome da cor)")
    parser.add_argument("--subtitle_shadow_x", type=int, default=2, help="Deslocamento da sombra das legendas no eixo X (em pixels)")
    parser.add_argument("--subtitle_shadow_y", type=int, default=2, help="Deslocamento da sombra das legendas no eixo Y (em pixels)")
    parser.add_argument("--enable_ken_burns", action="store_true", help="Habilita o efeito Ken Burns (zoom e pan) nas imagens")

    # Parâmetros cinematográficos
    parser.add_argument("--cinematic_preset", choices=["warm", "cold", "vintage", "cinematic"], default=None, help="Preset de efeitos cinematográficos")
    parser.add_argument("--custom_lut_path", default=None, help="Caminho para arquivo LUT customizado (.cube)")
    parser.add_argument("--enable_vignette", action="store_true", help="Habilita efeito vignette")
    parser.add_argument("--vignette_intensity", type=float, default=0.3, help="Intensidade do vignette (0.1 a 1.0)")
    parser.add_argument("--enable_curves", action="store_true", help="Habilita ajuste de curves do preset")
    parser.add_argument("--custom_curves", default=None, help="Curves customizadas (formato FFmpeg)")
    parser.add_argument("--remove_silence", default=True, action="store_true", help="Remove silêncio da narração")
    parser.add_argument("--silence_threshold", type=int, default=-40, help="Limite de silêncio (em dB)")
    parser.add_argument("--silence_duration", type=float, default=0.5, help="Duração mínima para considerar silêncio (em segundos)")

    # Novos parâmetros para encoder
    parser.add_argument("--encoder", default="libx264", help="Encoder a ser utilizado (libx264, h264_nvenc, etc.)")
    parser.add_argument("--performance_profile", default="quality", help="Perfil de performance para o encoder (quality, speed, etc.)")
    parser.add_argument("--threads", type=int, default=0, help="Número de threads para o encoder (0 para automático)")
    parser.add_argument("--gpu_quality", type=int, default=18, help="Qualidade da codificação GPU (1 a 31, menor é melhor)")
    parser.add_argument("--resolution_preset", default="horizontal_1080p", help="Preset de resolução (horizontal_1080p, vertical_720p, etc.)")

    # Novos parâmetros para trilha de fundo
    parser.add_argument("--background_music", default=None, help="Arquivo de áudio para trilha de fundo (mp3, wav, etc.)")
    parser.add_argument("--background_music_volume", type=float, default=0.2, help="Volume da trilha de fundo (0.0 a 1.0)")
    parser.add_argument("--subtitle_effect", choices=["none", "fade_in", "fill_bar"], default="none", help="Efeito na legenda: none, fade_in ou fill_bar")

    # Parâmetros para vídeos de encerramento e abertura
    parser.add_argument("--ending_video_path", default=None, help="Arquivo de vídeo para encerramento (mp4)")
    parser.add_argument("--opening_video_paths", nargs='+', default=None, help="Lista de arquivos de vídeo para abertura (mp4)")

    args = parser.parse_args()

    # Gera nome do arquivo de saída igual ao da narração, mas com extensão .mp4
    narracao_nome = Path(args.narracao).stem + ".mp4"
    out_path = str(Path(args.pasta_destino) / narracao_nome)

    create_video_from_narration(
        narration_path=args.narracao,
        videos_folder=args.pasta_videos,
        out_path=out_path,
        seed=args.seed,
        shuffle=args.shuffle,
        fps=args.fps,
        width=args.width,
        height=args.height,
        crf=args.crf,
        preset=args.preset,
        video_mode=args.video_mode,
        image_segment_duration=args.image_segment_duration,
        overlay=args.overlay,
        overlay_opacity=args.overlay_opacity,
        logo=args.logo,
        logo_scale=args.logo_scale,
        logo_x=args.logo_x,
        logo_y=args.logo_y,
        logo_position=args.logo_position,
        chroma=args.chroma,
        chroma_scale=args.chroma_scale,
        chroma_position=args.chroma_position,
        chroma_start=args.chroma_start,
        chroma_list=None,
        transition_type=args.transition_type,
        enable_subtitles=args.enable_subtitles,
        subtitle_font_size=args.subtitle_font_size,
        subtitle_color=args.subtitle_color,
        subtitle_position=args.subtitle_position,
        subtitle_font=args.subtitle_font,
        subtitle_outline_color=args.subtitle_outline_color,
        subtitle_outline_width=args.subtitle_outline_width,
        subtitle_shadow_color=args.subtitle_shadow_color,
        subtitle_shadow_x=args.subtitle_shadow_x,
        subtitle_shadow_y=args.subtitle_shadow_y,
        words_per_subtitle=args.words_per_subtitle,
        vosk_model_path=args.vosk_model_path,
        cinematic_preset=args.cinematic_preset,
        custom_lut_path=args.custom_lut_path,
        enable_vignette=args.enable_vignette,
        vignette_intensity=args.vignette_intensity,
        enable_curves=args.enable_curves,
        custom_curves=args.custom_curves,
        remove_silence=args.remove_silence,
        silence_threshold=args.silence_threshold,
        silence_duration=args.silence_duration,
        encoder=args.encoder,
        performance_profile=args.performance_profile,
        threads=args.threads,
        gpu_quality=args.gpu_quality,
        resolution_preset=args.resolution_preset,
        background_music=args.background_music,
        background_music_volume=args.background_music_volume,
        subtitle_effect=args.subtitle_effect,
        ending_video_path=args.ending_video_path,
        opening_video_paths=args.opening_video_paths,
    )
