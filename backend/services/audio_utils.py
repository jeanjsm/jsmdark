import json
import tempfile
import os
from pathlib import Path
from backend.utils.ffmpeg_utils import run, get_ffmpeg_path

def get_ffprobe_path() -> str:
    """Retorna o caminho para o executável FFprobe local"""
    current_dir = Path(__file__).parent.parent.parent
    ffprobe_path = current_dir / "_internal" / "ffmpeg" / "bin" / "ffprobe.exe"
    if ffprobe_path.exists():
        return str(ffprobe_path)
    return "ffprobe"

def duration_seconds(path: Path) -> float:
    """Obtém duração (segundos) via ffprobe."""
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
                pass
    raise RuntimeError(f"Não foi possível obter duração: {path}")

def remove_audio_silence(input_path: str, output_path: str = None,
                        stop_duration: float = 0.5, threshold_db: int = -40) -> str:
    """Remove silêncios do áudio usando FFmpeg.

    Args:
        input_path: Caminho do arquivo de áudio de entrada
        output_path: Caminho de saída (se None, usa arquivo temporário)
        stop_duration: Duração mínima do silêncio para remoção (segundos)
        threshold_db: Threshold de volume para considerar silêncio (dB)

    Returns:
        Caminho do arquivo processado
    """
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
    cmd = [
        get_ffmpeg_path(), '-y', '-i', input_path,
        '-af', f'silenceremove=start_periods=1:start_duration={stop_duration}:start_threshold={threshold_db}dB',
        output_path
    ]
    run(cmd)
    return output_path

