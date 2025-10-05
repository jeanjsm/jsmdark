from datetime import timedelta
import os
import whisper
import torch
import textwrap
from typing import Optional

def transcribe_audio(path: str, model_name: str = "base") -> Optional[str]:
    """Transcribes an audio file using OpenAI Whisper and saves the SRT file in the same directory.

    Args:
        path (str): Path to the audio file.
        model_name (str): Whisper model to use (e.g., 'tiny', 'base', 'small', 'medium', 'large').

    Returns:
        Optional[str]: Path to the generated SRT file, or None if failed.
    """
    if not os.path.isfile(path):
        print(f"Audio file not found: {path}")
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    try:
        model = whisper.load_model(model_name, device)
    except Exception as e:
        print(f"Failed to load Whisper model '{model_name}': {e}")
        return None
    print("Whisper model loaded.")

    try:
        transcribe = model.transcribe(audio=path)
    except Exception as e:
        print(f"Transcription failed: {e}")
        return None
    segments = transcribe.get('segments', [])

    MAX_SRT_LINE_LENGTH = 42

    def split_text_to_srt_lines(text: str, max_length: int = MAX_SRT_LINE_LENGTH) -> list[str]:
        """Splits text into a list of lines, each with a maximum number of characters."""
        return textwrap.wrap(text, width=max_length, break_long_words=False, replace_whitespace=False)

    def format_srt_time(seconds: float) -> str:
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

    srt_filename = os.path.splitext(path)[0] + ".srt"
    try:
        with open(srt_filename, 'w', encoding='utf-8') as srt_file:
            srt_index = 1
            for segment in segments:
                text = segment['text']
                start = segment['start']
                end = segment['end']
                lines = split_text_to_srt_lines(text[1:] if text and text[0] == ' ' else text)
                n_lines = len(lines)
                if n_lines == 0:
                    continue
                duration = end - start
                duration_per_line = duration / n_lines if n_lines > 0 else duration
                for i, line in enumerate(lines):
                    line_start = start + i * duration_per_line
                    line_end = line_start + duration_per_line
                    srt_start = format_srt_time(line_start)
                    srt_end = format_srt_time(min(line_end, end))
                    srt_file.write(f"{srt_index}\n{srt_start} --> {srt_end}\n{line}\n\n")
                    srt_index += 1
    except Exception as e:
        print(f"Failed to write SRT file: {e}")
        return None

    return srt_filename

if __name__ == "__main__":
    audio_path = "C:\\Users\\Jean\\youtube\\maria passa a frente\\10-Outubro\\02-Audio\\04\\video 2\\04.wav"  # Change this to your audio file path
    srt_file_path = transcribe_audio(audio_path, model_name="base")
    if srt_file_path:
        print(f"SRT file created at: {srt_file_path}")
    else:
        print("Failed to create SRT file.")
