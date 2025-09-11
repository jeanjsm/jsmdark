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
        print(f"[DEBUG] Executando comando: {cmd[0]} {' '.join(cmd[1:])}")

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

def apply_camera_shake(input_path: str, output_path: str, intensity: float = 0.03, frequency: int = 30, duration: float = None) -> None:
    """Aplica efeito Camera Shake estilo CapCut usando FFmpeg."""
    # Aumentamos a intensidade para tornar o efeito mais visível
    intensity = max(intensity, 0.01) * 1.5  # Amplifica o efeito para ser mais perceptível

    # Aplicamos um zoom maior para compensar as bordas pretas
    scale = 1.05  # Escala maior para evitar bordas pretas

    # Expressões para movimento horizontal e vertical
    if duration is not None and duration > 0:
        h_expr = f"if(lt(t,{duration}),sin(t*{frequency}*PI)*{intensity}*w,0)"
        v_expr = f"if(lt(t,{duration}),sin((t+0.25)*{frequency}*PI)*{intensity}*h,0)"
    else:
        h_expr = f"sin(t*{frequency}*PI)*{intensity}*w"
        v_expr = f"sin((t+0.25)*{frequency}*PI)*{intensity}*h"

    # Filtro completo: zoom + translate com expressões corrigidas
    shake_filter = f"scale=iw*{scale}:ih*{scale},setpts=PTS-STARTPTS"
    shake_filter += f",translate={h_expr}:{v_expr}"

    cmd = [
        get_ffmpeg_path(), '-y', '-i', input_path,
        '-vf', shake_filter,
        '-c:a', 'copy',
        output_path
    ]

    # Executa o comando
    print(f"[DEBUG] Aplicando camera shake com intensidade={intensity}, frequência={frequency}")
    run(cmd)
