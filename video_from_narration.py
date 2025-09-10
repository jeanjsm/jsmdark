# video_from_narration.py
# Cria um vídeo a partir de uma narração, sorteando clipes de uma pasta e cortando apenas o último.
# Saída: 1920x1080, 30fps, H.264, áudio da narração.
from pathlib import Path
from typing import Callable, Dict, Any, List as TList
from audio_utils import duration_seconds
from video_utils import list_videos, pick_segments_to_cover, list_images, pick_image_segments_to_cover
from ffmpeg_utils import run
from pipeline import MediaPipeline, VideoBaseStage, OverlayStage, LogoStage, ChromaStage, TransitionStage, \
    SubtitleStage, CinematicStage, ImageCacheStage, EncoderStage, OutputStage, BackgroundMusicStage, EndingStage, \
    MediaCacheStage, OpeningStage
import json
import argparse


def create_video_from_narration(
    narration_path: str,
    videos_folder: str,
    out_path: str = "output.mp4",
    seed: int | None = None,
    shuffle: bool | None = True,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    crf: int = 18,
    preset: str = "medium",
    video_mode: str = "videos",
    image_segment_duration: float = 2.0,
    overlay: str | None = None,
    overlay_opacity: float = 1.0,
    logo: str | None = None,
    logo_scale: float = 0.15,
    logo_x: int = 20,
    logo_y: int = 20,
    logo_position: str = "top_right",
    chroma: str | None = None,
    chroma_scale: float = 0.5,
    chroma_position: str = "bottom_right",
    chroma_start: float = 0.0,
    chroma_list: TList[Dict[str, Any]] | None = None,
    transition_type: str = "none",
    enable_subtitles: bool = False,
    subtitle_font_size: int = 24,
    subtitle_color: str = "white",
    subtitle_position: str = "bottom_center",
    subtitle_font: str = None,
    subtitle_outline_color: str = "black",
    subtitle_outline_width: int = 2,
    subtitle_shadow_color: str = "black",
    subtitle_shadow_x: int = 2,
    subtitle_shadow_y: int = 2,
    words_per_subtitle: int = 1,
    vosk_model_path: str = "_internal/vosk_models/vosk-model-pt",
    enable_ken_burns: bool = False,
    cinematic_preset: str = None,
    custom_lut_path: str = None,
    enable_vignette: bool = False,
    vignette_intensity: float = 1,
    enable_curves: bool = False,
    custom_curves: str = None,
    remove_silence: bool = False,
    silence_threshold: int = -40,
    silence_duration: float = 0.5,
    encoder: str = "libx264",
    performance_profile: str = "quality",
    threads: int = 0,
    gpu_quality: int = 18,
    resolution_preset: str = "horizontal_1080p",
    background_music: str = None,
    background_music_volume: float = 0.2,
    subtitle_effect: str = "none",
    ending_video_path: str = None,
    opening_video_paths: TList[str] = None,
    progress_callback: Callable[[int], None] = None,
):
    # Remove silêncio da narração se habilitado
    if remove_silence:
        from audio_utils import remove_audio_silence
        narration_path = remove_audio_silence(
            narration_path,
            threshold_db=silence_threshold,
            stop_duration=silence_duration
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
        "enable_ken_burns": enable_ken_burns,
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
        enable_ken_burns=args.enable_ken_burns,
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
