import json
import tempfile
import os
import logging
from pathlib import Path
from ffmpeg_utils import run, get_ffmpeg_path
from typing import Optional

# Constants
SILENCE_STOP_DURATION_DEFAULT = 0.5
SILENCE_THRESHOLD_DB_DEFAULT = -40

class AudioProcessingError(Exception):
    """Custom exception for audio processing errors."""
    pass


def get_ffprobe_path() -> str:
    """Return the path to the local FFprobe executable if available, otherwise fallback to system FFprobe.

    Returns:
        str: Path to FFprobe executable.
    """
    current_dir = Path(__file__).parent
    ffprobe_path = current_dir / "_internal" / "ffmpeg" / "bin" / "ffprobe.exe"

    if ffprobe_path.exists():
        return str(ffprobe_path)

    return "ffprobe"


def duration_seconds(path: Path) -> float:
    """Get duration (in seconds) of an audio/video file using ffprobe.

    Args:
        path (Path): Path to the media file.

    Returns:
        float: Duration in seconds.

    Raises:
        AudioProcessingError: If duration cannot be determined.
    """
    cmd = [
        get_ffprobe_path(), "-v", "error", "-hide_banner",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(path)
    ]
    out = run(cmd).stdout
    info = json.loads(out)
    if "format" in info and "duration" in info["format"]:
        return float(info["format"]["duration"])
    for s in info.get("streams", []):
        if "duration" in s:
            try:
                return float(s["duration"])
            except Exception:
                continue
    logging.error(f"Could not get duration for: {path}")
    raise AudioProcessingError(f"Could not get duration: {path}")


def remove_audio_silence(
    input_path: str,
    output_path: Optional[str] = None,
    stop_duration: float = SILENCE_STOP_DURATION_DEFAULT,
    threshold_db: int = SILENCE_THRESHOLD_DB_DEFAULT
) -> str:
    """Remove silences from audio using FFmpeg.

    Args:
        input_path (str): Path to input audio file.
        output_path (Optional[str]): Path to output file. If None, uses a temporary file.
        stop_duration (float): Minimum silence duration to remove (seconds).
        threshold_db (int): Volume threshold to consider silence (dB).

    Returns:
        str: Path to processed audio file.

    Raises:
        FileNotFoundError: If input file does not exist.
        AudioProcessingError: If processing fails.
    """
    input_path = Path(input_path)

    if not input_path.exists():
        logging.error(f"Audio file not found: {input_path}")
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    if output_path is None:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{input_path.stem}_no_silence{input_path.suffix}")

    # Comando FFmpeg para remover silêncios
    cmd = [
        get_ffmpeg_path(),
        "-i", str(input_path),
        "-af", f"silenceremove=stop_periods=-1:stop_duration={stop_duration}:stop_threshold={threshold_db}dB",
        "-y", str(output_path)
    ]

    run(cmd)
    return str(output_path)
