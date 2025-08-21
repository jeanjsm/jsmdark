import json
import tempfile
import os
from pathlib import Path
from ffmpeg_utils import run

FFPROBE_BIN = "ffprobe"
FFMPEG_BIN = "ffmpeg"

def duration_seconds(path: Path) -> float:
    """Obtém duração (segundos) via ffprobe."""
    cmd = [
        FFPROBE_BIN, "-v", "error", "-hide_banner",
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
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {input_path}")

    # Define output path se não fornecido
    if output_path is None:
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"{input_path.stem}_no_silence{input_path.suffix}")

    # Comando FFmpeg para remover silêncios
    cmd = [
        FFMPEG_BIN,
        "-i", str(input_path),
        "-af", f"silenceremove=stop_periods=-1:stop_duration={stop_duration}:stop_threshold={threshold_db}dB",
        "-y", str(output_path)
    ]

    run(cmd)
    return str(output_path)
