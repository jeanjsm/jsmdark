import subprocess
import tempfile
import os
import logging
from typing import List, Optional
from pathlib import Path

# Constants
FILTER_COMPLEX_LENGTH_LIMIT = 8000
CAMERA_SHAKE_INTENSITY_MIN = 0.01
CAMERA_SHAKE_INTENSITY_MULTIPLIER = 1.5

class FFmpegError(Exception):
    """Custom exception for FFmpeg command failures."""
    pass


def get_ffmpeg_path() -> str:
    """Return the path to the local FFmpeg executable if available, otherwise fallback to system FFmpeg.

    Returns:
        str: Path to FFmpeg executable.
    """
    current_dir = Path(__file__).parent
    ffmpeg_path = current_dir / "_internal" / "ffmpeg" / "bin" / "ffmpeg.exe"

    if ffmpeg_path.exists():
        return str(ffmpeg_path)

    return "ffmpeg"


def run(cmd: List[str]) -> subprocess.CompletedProcess:
    """Run an FFmpeg command, handling long filter_complex arguments and errors.

    Args:
        cmd (List[str]): Command arguments for FFmpeg.

    Returns:
        subprocess.CompletedProcess: The result of the FFmpeg command.

    Raises:
        FFmpegError: If the FFmpeg command fails.
    """
    try:
        if cmd[0] == "ffmpeg":
            cmd[0] = get_ffmpeg_path()

        logging.debug(f"Executing command: {cmd[0]} {' '.join(cmd[1:])}")

        filter_complex_idx = None
        for i, arg in enumerate(cmd):
            if arg == "-filter_complex" and i + 1 < len(cmd):
                filter_complex_idx = i + 1
                break

        if filter_complex_idx and len(cmd[filter_complex_idx]) > FILTER_COMPLEX_LENGTH_LIMIT:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(cmd[filter_complex_idx])
                temp_file = f.name

            try:
                new_cmd = cmd[:filter_complex_idx-1] + ["-filter_complex_script", temp_file] + cmd[filter_complex_idx+1:]
                return subprocess.run(new_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            finally:
                os.unlink(temp_file)
        else:
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logging.error("[FFmpeg command failed]")
        logging.error(f"Command: {' '.join(cmd[:10]) + '...' if len(cmd) > 10 else ' '.join(cmd)}")
        logging.error(f"[FFmpeg stderr]\n{e.stderr}")
        raise FFmpegError("FFmpeg command failed") from e


def apply_camera_shake(
    input_path: str,
    output_path: str,
    intensity: float = 0.03,
    frequency: int = 30,
    duration: Optional[float] = None
) -> None:
    """Apply CapCut-style camera shake effect using FFmpeg.

    Args:
        input_path (str): Path to input video.
        output_path (str): Path to output video.
        intensity (float, optional): Shake intensity. Defaults to 0.03.
        frequency (int, optional): Shake frequency. Defaults to 30.
        duration (float, optional): Duration of effect. Defaults to None.
    """
    intensity = max(intensity, CAMERA_SHAKE_INTENSITY_MIN) * CAMERA_SHAKE_INTENSITY_MULTIPLIER

    scale = 1.05

    if duration is not None and duration > 0:
        h_expr = f"if(lt(t,{duration}),sin(t*{frequency}*PI)*{intensity}*w,0)"
        v_expr = f"if(lt(t,{duration}),sin((t+0.25)*{frequency}*PI)*{intensity}*h,0)"
    else:
        h_expr = f"sin(t*{frequency}*PI)*{intensity}*w"
        v_expr = f"sin((t+0.25)*{frequency}*PI)*{intensity}*h"

    shake_filter = f"scale=iw*{scale}:ih*{scale},setpts=PTS-STARTPTS"
    shake_filter += f",translate={h_expr}:{v_expr}"

    cmd = [
        get_ffmpeg_path(), '-y', '-i', input_path,
        '-vf', shake_filter,
        '-c:a', 'copy',
        output_path
    ]

    logging.info(f"Applying camera shake with intensity={intensity}, frequency={frequency}")
    run(cmd)
