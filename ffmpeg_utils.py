import subprocess
import tempfile
import os
from typing import List

def run(cmd: List[str]) -> subprocess.CompletedProcess:
    try:
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
