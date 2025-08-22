import json
import wave
import subprocess
from pathlib import Path
from typing import List, Tuple
import unicodedata
import vosk
from backend.utils.ffmpeg_utils import get_ffmpeg_path

# Utilitários de legendas
# Conteúdo movido de subtitle_utils.py

def normalize_text(s: str) -> str:
    """
    Normaliza o texto para NFC e remove caracteres de controle invisíveis
    (mantém quebras de linha).
    """
    s = unicodedata.normalize("NFC", s)
    return "".join(ch for ch in s if ch == "\n" or ch >= " ")

def ff_escape(s: str) -> str:
    """
    Escapa os caracteres especiais para uso seguro no drawtext.
    Isso cobre barra invertida, aspas simples, dois-pontos, colchetes,
    porcento e vírgula, que frequentemente quebram o parser do FFmpeg.
    """
    s = s.replace("\\", "\\\\")
    s = s.replace("'", r"\'")
    s = s.replace(":", r"\:")
    s = s.replace("%", r"\%")
    s = s.replace("[", r"\[")
    s = s.replace("]", r"\]")
    s = s.replace(",", r"\,")
    return s

def extract_audio_for_transcription(video_path: str, output_path: str) -> None:
    """Extrai áudio do vídeo em formato WAV mono 16kHz para o Vosk (mais enxuto e performático)."""
    cmd = [
        get_ffmpeg_path(),
        "-y",
        "-nostdin",
        "-i", video_path,
        "-ac", "1",
        "-ar", "16000",
        "-vn",
        "-f", "wav",
        output_path
    ]
    subprocess.run(cmd, check=True)
