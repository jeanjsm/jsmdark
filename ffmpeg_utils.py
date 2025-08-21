import subprocess
import tempfile
import os
from typing import List
from pathlib import Path

def get_ffmpeg_path() -> str:
    """Retorna o caminho para o executável FFmpeg local"""
    current_dir = Path(__file__).parent
    ffmpeg_path = current_dir / "_internal" / "ffmpeg" / "bin" / "ffmpeg.exe"

    if ffmpeg_path.exists():
        return str(ffmpeg_path)

    # Fallback para FFmpeg no PATH se o local não existir
    return "ffmpeg"

def run(cmd: List[str]) -> subprocess.CompletedProcess:
    try:
        # Substitui "ffmpeg" pelo caminho completo se necessário
        if cmd[0] == "ffmpeg":
            cmd[0] = get_ffmpeg_path()

        # Debug: mostra o comando que será executado
        print(f"[DEBUG] Executando comando: {cmd[0]} {' '.join(cmd[1:5])}...")

        # Verifica se há filter_complex muito longo
        filter_complex_idx = None
        for i, arg in enumerate(cmd):
            if arg == "-filter_complex" and i + 1 < len(cmd):
                filter_complex_idx = i + 1
                break

        # Se filter_complex é muito longo, usa arquivo temporário
        if filter_complex_idx and len(cmd[filter_complex_idx]) > 8000:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(cmd[filter_complex_idx])
                temp_file = f.name

            try:
                # Substitui o filtro complexo pelo arquivo
                new_cmd = cmd[:filter_complex_idx-1] + ["-filter_complex_script", temp_file] + cmd[filter_complex_idx+1:]
                return subprocess.run(new_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            finally:
                os.unlink(temp_file)
        else:
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print("\n[FFmpeg command failed]")
        print("Command:", " ".join(cmd[:10]) + "..." if len(cmd) > 10 else " ".join(cmd))
        print("\n[FFmpeg stderr]")
        print(e.stderr)
        raise
