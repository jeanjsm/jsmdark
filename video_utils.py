from pathlib import Path
from typing import List
from audio_utils import duration_seconds
import random

SUPPORTED_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

def list_videos(folder: Path) -> List[Path]:
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS])

def pick_segments_to_cover(audio_dur: float, videos: List[Path], seed: int | None = None, shuffle: bool = True):
    """
    Seleciona segmentos de vídeos para cobrir a duração do áudio.
    Se shuffle for False, seleciona em ordem crescente.
    """
    if seed is not None and shuffle:
        random.seed(seed)
    if not videos:
        raise ValueError("A pasta de vídeos está vazia.")
    chosen = []
    total = 0.0
    pool = videos[:]
    while total < audio_dur:
        if not pool:
            pool = videos[:]
        if shuffle:
            random.shuffle(pool)
        for v in list(pool):
            vdur = duration_seconds(v)
            remaining = audio_dur - total
            if remaining <= 0.05:
                break
            take = min(vdur, remaining)
            chosen.append((v, take))
            total += take
            pool.remove(v)
            if total >= audio_dur - 1e-3:
                break
    return chosen

def list_images(folder: Path) -> List[Path]:
    """List images in a folder with supported extensions."""
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS])

def pick_image_segments_to_cover(audio_dur: float, images: List[Path], image_segment_duration: float, seed: int | None = None, shuffle: bool = True):
    """Selects images to cover the audio duration, each shown for image_segment_duration seconds."""
    import random
    if seed is not None and shuffle:
        random.seed(seed)
    if not images:
        raise ValueError("A pasta de imagens está vazia.")
    chosen = []
    total = 0.0
    pool = images[:]
    while total < audio_dur:
        if not pool:
            pool = images[:]
            if shuffle:
                random.shuffle(pool)
        for img in list(pool):
            remaining = audio_dur - total
            if remaining <= 0.05:
                break
            take = min(image_segment_duration, remaining)
            chosen.append((img, take))
            total += take
        pool = []
    return chosen
