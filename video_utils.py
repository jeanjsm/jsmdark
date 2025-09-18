from pathlib import Path
from typing import List, Tuple, Optional
from audio_utils import duration_seconds
import random
import logging

SUPPORTED_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

# Constants
MIN_SEGMENT_REMAINING = 0.05
SEGMENT_EPSILON = 1e-3

class VideoUtilsError(Exception):
    """Custom exception for video utilities."""
    pass

def list_videos(folder: Path) -> List[Path]:
    """List videos in a folder with supported extensions.

    Args:
        folder (Path): Path to the folder.

    Returns:
        List[Path]: Sorted list of video file paths.
    """
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS])

def pick_segments_to_cover(
    audio_dur: float,
    videos: List[Path],
    seed: Optional[int] = None,
    shuffle: bool = True
) -> List[Tuple[Path, float]]:
    """Select video segments to cover the audio duration.

    Args:
        audio_dur (float): Duration of the audio in seconds.
        videos (List[Path]): List of video file paths.
        seed (Optional[int]): Random seed for shuffling.
        shuffle (bool): Whether to shuffle the video order.

    Returns:
        List[Tuple[Path, float]]: List of (video path, segment duration).

    Raises:
        VideoUtilsError: If the video folder is empty.
    """
    if seed is not None and shuffle:
        random.seed(seed)
    if not videos:
        logging.error("Video folder is empty.")
        raise VideoUtilsError("A pasta de vídeos está vazia.")
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
            if remaining <= MIN_SEGMENT_REMAINING:
                break
            take = min(vdur, remaining)
            chosen.append((v, take))
            total += take
            pool.remove(v)
            if total >= audio_dur - SEGMENT_EPSILON:
                break
    return chosen

def list_images(folder: Path) -> List[Path]:
    """List images in a folder with supported extensions.

    Args:
        folder (Path): Path to the folder.

    Returns:
        List[Path]: Sorted list of image file paths.
    """
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS])

def pick_image_segments_to_cover(
    audio_dur: float,
    images: List[Path],
    image_segment_duration: float,
    seed: Optional[int] = None,
    shuffle: bool = True
) -> List[Tuple[Path, float]]:
    """Select images to cover the audio duration, each shown for image_segment_duration seconds.

    Args:
        audio_dur (float): Duration of the audio in seconds.
        images (List[Path]): List of image file paths.
        image_segment_duration (float): Duration for each image segment.
        seed (Optional[int]): Random seed for shuffling.
        shuffle (bool): Whether to shuffle the image order.

    Returns:
        List[Tuple[Path, float]]: List of (image path, segment duration).

    Raises:
        VideoUtilsError: If the image folder is empty.
    """
    if not images:
        logging.error("Image folder is empty.")
        raise VideoUtilsError("A pasta de imagens está vazia.")
    if seed is None and shuffle:
        rng = random.Random()
    else:
        rng = random.Random(seed) if shuffle else random
    chosen = []
    total = 0.0
    pool = images[:]
    if shuffle:
        rng.shuffle(pool)
    while total < audio_dur:
        if not pool:
            pool = images[:]
            if shuffle:
                rng.shuffle(pool)
        for img in list(pool):
            remaining = audio_dur - total
            if remaining <= MIN_SEGMENT_REMAINING:
                break
            take = min(image_segment_duration, remaining)
            chosen.append((img, take))
            total += take
        pool = []
    return chosen
