import json
import wave
import subprocess
from pathlib import Path
from typing import List, Tuple
import vosk

def extract_audio_for_transcription(video_path: str, output_path: str) -> None:
    """Extrai áudio do vídeo em formato WAV mono 16kHz para o Vosk."""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ar", "16000", "-ac", "1", "-f", "wav",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def transcribe_audio(audio_path: str, model_path: str = "_internal/vosk_models/vosk-model-pt") -> List[Tuple[float, float, str]]:
    """Transcreve áudio usando Vosk e retorna lista de (start, end, text)."""
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Modelo Vosk não encontrado: {model_path}")

    model = vosk.Model(model_path)
    rec = vosk.KaldiRecognizer(model, 16000)
    rec.SetWords(True)

    segments = []

    with wave.open(audio_path, 'rb') as wf:
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if 'result' in result and result['result']:
                    for word in result['result']:
                        start = word['start']
                        end = word['end']
                        text = word['word']
                        segments.append((start, end, text))

    # Processa resultado final
    final_result = json.loads(rec.FinalResult())
    if 'result' in final_result and final_result['result']:
        for word in final_result['result']:
            start = word['start']
            end = word['end']
            text = word['word']
            segments.append((start, end, text))

    return segments

def get_subtitle_position(position: str) -> str:
    """Retorna as coordenadas x,y para a posição da legenda."""
    positions = {
        "top_left": "x=20:y=20",
        "top_center": "x=(w-text_w)/2:y=20",
        "top_right": "x=w-text_w-20:y=20",
        "center": "x=(w-text_w)/2:y=(h-text_h)/2",
        "bottom_left": "x=20:y=h-text_h-20",
        "bottom_center": "x=(w-text_w)/2:y=h-60",
        "bottom_right": "x=w-text_w-20:y=h-text_h-20"
    }
    return positions.get(position, "x=(w-text_w)/2:y=h-60")

def group_words_by_count(segments: List[Tuple[float, float, str]], words_per_group: int = 1) -> List[Tuple[float, float, str]]:
    """Agrupa palavras consecutivas respeitando o limite de palavras por grupo."""
    if not segments or words_per_group <= 1:
        return segments

    grouped = []
    current_group = []
    current_start = None
    current_end = None

    for start, end, word in segments:
        if len(current_group) == 0:
            current_start = start

        current_group.append(word)
        current_end = end

        if len(current_group) >= words_per_group:
            grouped_text = " ".join(current_group)
            grouped.append((current_start, current_end, grouped_text))
            current_group = []

    # Adiciona grupo restante se houver
    if current_group:
        grouped_text = " ".join(current_group)
        grouped.append((current_start, current_end, grouped_text))

    return grouped

def create_subtitle_filter(segments: List[Tuple[float, float, str]], font_size: int = 24, font_color: str = "white", position: str = "bottom_center", words_per_subtitle: int = 1, font_path: str = None, outline_color: str = "black", outline_width: int = 2, shadow_color: str = "black", shadow_x: int = 2, shadow_y: int = 2) -> str:
    """Cria filtro FFmpeg para legendas baseado nos segmentos transcritos."""
    if not segments:
        return ""

    # Agrupa palavras se necessário
    if words_per_subtitle > 1:
        segments = group_words_by_count(segments, words_per_subtitle)

    position_coords = get_subtitle_position(position)

    # Define fonte
    font_config = ""
    if font_path:
        if Path(font_path).exists():
            font_config = f":fontfile='{font_path}'"
        else:
            font_config = f":fontfamily='{font_path}'"

    # Define outline e sombra
    outline_config = f":bordercolor={outline_color}:borderw={outline_width}"
    shadow_config = f":shadowcolor={shadow_color}:shadowx={shadow_x}:shadowy={shadow_y}"

    # Cria um único filtro drawtext com todas as legendas
    drawtext_options = []
    for start, end, text in segments:
        # Escapa caracteres especiais para FFmpeg
        text_escaped = text.replace("'", "\\'").replace(":", "\\:")
        drawtext_options.append(
            f"drawtext=text='{text_escaped}':fontsize={font_size}:fontcolor={font_color}:"
            f"{position_coords}{font_config}{outline_config}{shadow_config}:enable='between(t,{start},{end})'"
        )

    return ",".join(drawtext_options)

def generate_srt_file(segments: List[Tuple[float, float, str]], output_path: str) -> None:
    """Gera arquivo SRT a partir dos segmentos transcritos."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, (start, end, text) in enumerate(segments, 1):
            start_time = format_time_srt(start)
            end_time = format_time_srt(end)
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")

def format_time_srt(seconds: float) -> str:
    """Formata tempo em segundos para formato SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
