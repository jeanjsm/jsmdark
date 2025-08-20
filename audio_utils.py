import json
from pathlib import Path
from ffmpeg_utils import run

FFPROBE_BIN = "ffprobe"

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
