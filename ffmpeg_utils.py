import subprocess
from typing import List

def run(cmd: List[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print("\n[FFmpeg command failed]")
        print("Command:", " ".join(cmd))
        print("\n[FFmpeg stderr]")
        print(e.stderr)
        raise
