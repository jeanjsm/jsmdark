# video_from_narration.py
# Cria um vídeo a partir de uma narração, sorteando clipes de uma pasta e cortando apenas o último.
# Saída: 1920x1080, 30fps, H.264, áudio da narração.
from pathlib import Path
from typing import List
from audio_utils import duration_seconds
from video_utils import list_videos, pick_segments_to_cover, list_images, pick_image_segments_to_cover
from ffmpeg_utils import run


def create_video_from_narration(
    narration_path: str,
    videos_folder: str,
    out_path: str = "output.mp4",
    seed: int | None = None,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    crf: int = 18,
    preset: str = "medium",
    video_mode: str = "videos",
    image_segment_duration: float = 2.0,
):
    narration = Path(narration_path)
    folder = Path(videos_folder)
    out = Path(out_path)

    if not narration.exists():
        raise FileNotFoundError(f"Narração não encontrada: {narration}")
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Pasta de entrada não encontrada ou inválida: {folder}")

    audio_dur = duration_seconds(narration)

    FFMPEG_BIN = "ffmpeg"
    inputs = ["-y", "-hide_banner", "-loglevel", "error", "-i", str(narration)]
    vf_parts = []
    vlabels = []
    segments = []

    if video_mode == "videos":
        vids = list_videos(folder)
        if not vids:
            raise FileNotFoundError(f"Nenhum vídeo com extensões suportadas em: {folder}")
        segments = pick_segments_to_cover(audio_dur, vids, seed=seed)
        for v, _ in segments:
            inputs += ["-i", str(v)]
        for idx, (_, take) in enumerate(segments, start=1):
            label_in = f"{idx}:v"
            take_str = f"{take:.3f}"
            vout = f"v{idx}"
            chain = (
                f"[{label_in}]"
                f"fps={fps},"
                f"scale=w=-2:h={height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                f"setsar=1,"
                f"trim=0:{take_str},setpts=PTS-STARTPTS"
                f"[{vout}]"
            )
            vf_parts.append(chain)
            vlabels.append(f"[{vout}]")
        concat = "".join(vlabels) + f"concat=n={len(segments)}:v=1:a=0[vout]"
        filter_complex = ";".join(vf_parts + [concat])
        cmd = [
            FFMPEG_BIN,
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a:0",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out)
        ]
    elif video_mode == "images":
        images = list_images(folder)
        if not images:
            raise FileNotFoundError(f"Nenhuma imagem com extensões suportadas em: {folder}")
        segments = pick_image_segments_to_cover(audio_dur, images, image_segment_duration, seed=seed)
        for img, take in segments:
            # -loop 1: repete a imagem, -t: duração
            inputs += ["-loop", "1", "-t", f"{take:.3f}", "-i", str(img)]
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
        cmd = [
            FFMPEG_BIN,
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a:0",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out)
        ]
    else:
        raise ValueError(f"Modo de vídeo inválido: {video_mode}. Use 'videos' ou 'images'.")
    run(cmd)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gera vídeo a partir de narração e clipes ou imagens.")
    parser.add_argument("--narracao", required=True, help="Caminho para o arquivo de narração (áudio)")
    parser.add_argument("--pasta_videos", required=True, help="Pasta com os vídeos ou imagens de entrada")
    parser.add_argument("--saida", default="output.mp4", help="Arquivo de saída (default: output.mp4)")
    parser.add_argument("--seed", type=int, default=None, help="Seed para sorteio dos vídeos/imagens")
    parser.add_argument("--fps", type=int, default=30, help="Frames por segundo do vídeo final")
    parser.add_argument("--width", type=int, default=1920, help="Largura do vídeo final")
    parser.add_argument("--height", type=int, default=1080, help="Altura do vídeo final")
    parser.add_argument("--crf", type=int, default=18, help="CRF do x264 (qualidade, menor é melhor)")
    parser.add_argument("--preset", default="medium", help="Preset do x264 (ultrafast, fast, medium, slow, etc)")
    parser.add_argument("--video_mode", choices=["videos", "images"], default="videos", help="Modo de montagem: videos ou images")
    parser.add_argument("--image_segment_duration", type=float, default=2.0, help="Duração de cada imagem no vídeo (em segundos, só para modo images)")
    args = parser.parse_args()

    create_video_from_narration(
        narration_path=args.narracao,
        videos_folder=args.pasta_videos,
        out_path=args.saida,
        seed=args.seed,
        fps=args.fps,
        width=args.width,
        height=args.height,
        crf=args.crf,
        preset=args.preset,
        video_mode=args.video_mode,
        image_segment_duration=args.image_segment_duration,
    )
