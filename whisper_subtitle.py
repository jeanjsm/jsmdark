from datetime import timedelta
import os
import torch
import textwrap
from typing import Optional, Union
import importlib.util
import sys
import subprocess


def check_fast_whisper_available() -> bool:
    """Check if faster-whisper is available."""
    try:
        import faster_whisper
        return True
    except ImportError:
        return False


def check_whisper_available() -> bool:
    """Check if openai-whisper is available."""
    try:
        import whisper
        return True
    except ImportError:
        return False


def get_installation_instructions() -> dict:
    """Get platform-specific installation instructions."""
    import platform

    system = platform.system().lower()
    instructions = {
        "system": system,
        "fast_whisper": {
            "command": "pip install faster-whisper",
            "alternative": None
        },
        "whisper": {
            "command": "pip install openai-whisper",
            "alternative": None
        }
    }

    if system == "windows":
        instructions["fast_whisper"]["alternative"] = [
            "Se houver erro de permissão, tente:",
            "1. Executar como administrador",
            "2. pip install --user faster-whisper",
            "3. python -m pip install --upgrade pip setuptools",
            "4. pip install faster-whisper --force-reinstall"
        ]
        instructions["whisper"]["alternative"] = [
            "Como alternativa mais simples:",
            "pip install openai-whisper"
        ]

    return instructions


def transcribe_audio(path: str, model_name: str = "base", use_fast_whisper: bool = True) -> Optional[str]:
    """Transcribes an audio file using OpenAI Whisper or faster-whisper and saves the SRT file in the same directory.

    Args:
        path (str): Path to the audio file.
        model_name (str): Whisper model to use (e.g., 'tiny', 'base', 'small', 'medium', 'large', 'turbo').
        use_fast_whisper (bool): Whether to use faster-whisper (if available) or original whisper.

    Returns:
        Optional[str]: Path to the generated SRT file, or None if failed.
    """
    if not os.path.isfile(path):
        print(f"Audio file not found: {path}")
        return None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Check which Whisper implementation to use
    fast_available = check_fast_whisper_available()
    whisper_available = check_whisper_available()

    if use_fast_whisper and fast_available:
        print("Using faster-whisper")
        return _transcribe_with_fast_whisper(path, model_name, device)
    elif whisper_available:
        print("Using openai-whisper")
        return _transcribe_with_whisper(path, model_name, device)
    elif fast_available:
        print("faster-whisper selected but openai-whisper not available, using faster-whisper")
        return _transcribe_with_fast_whisper(path, model_name, device)
    else:
        print("❌ Neither faster-whisper nor openai-whisper is available.")
        print("\n📦 Installation options:")

        instructions = get_installation_instructions()

        print("\n🚀 Option 1 (Recommended - faster performance):")
        print(f"   {instructions['fast_whisper']['command']}")

        if instructions['fast_whisper']['alternative']:
            print("\n⚠️  If you encounter permission errors on Windows:")
            for tip in instructions['fast_whisper']['alternative']:
                print(f"   {tip}")

        print("\n🔄 Option 2 (More compatible):")
        print(f"   {instructions['whisper']['command']}")

        print("\n💡 After installation, restart your Python environment and try again.")
        return None


def _transcribe_with_fast_whisper(path: str, model_name: str, device: str) -> Optional[str]:
    """Transcribe using faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        print(f"❌ Failed to import faster-whisper: {e}")
        print("💡 Try installing with: pip install faster-whisper")
        return None

    try:
        # For faster-whisper, device should be "cuda" or "cpu"
        # and we can specify compute_type for better performance
        if device == "cuda":
            # Try different compute types for CUDA
            compute_types = ["float16", "int8_float16", "int8"]
        else:
            compute_types = ["int8", "float32"]

        model = None
        for compute_type in compute_types:
            try:
                model = WhisperModel(model_name, device=device, compute_type=compute_type)
                print(f"✅ Faster-Whisper model '{model_name}' loaded with compute_type '{compute_type}'")
                break
            except Exception as e:
                print(f"⚠️  Failed to load with compute_type '{compute_type}': {e}")
                continue

        if model is None:
            print("❌ Failed to load faster-whisper model with any compute type")
            return None

    except Exception as e:
        print(f"❌ Failed to load faster-whisper model '{model_name}': {e}")
        return None

    try:
        print("🎵 Starting transcription...")
        segments, info = model.transcribe(path, beam_size=5)
        print(f"🗣️  Detected language: {info.language} (probability: {info.language_probability:.2f})")

        # Convert generator to list and format segments
        segment_list = []
        for segment in segments:
            segment_dict = {
                'text': segment.text,
                'start': segment.start,
                'end': segment.end
            }
            segment_list.append(segment_dict)

        print(f"📝 Found {len(segment_list)} segments")

    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return None

    return _write_srt_file(path, segment_list)


def _transcribe_with_whisper(path: str, model_name: str, device: str) -> Optional[str]:
    """Transcribe using original openai-whisper."""
    try:
        import whisper
    except ImportError as e:
        print(f"❌ Failed to import openai-whisper: {e}")
        print("💡 Try installing with: pip install openai-whisper")
        return None

    try:
        print(f"📥 Loading OpenAI Whisper model '{model_name}'...")
        model = whisper.load_model(model_name, device)
        print(f"✅ OpenAI Whisper model '{model_name}' loaded")
    except Exception as e:
        print(f"❌ Failed to load Whisper model '{model_name}': {e}")
        return None

    try:
        print("🎵 Starting transcription...")
        result = model.transcribe(audio=path)
        segments = result.get('segments', [])
        print(f"📝 Found {len(segments)} segments")
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        return None

    return _write_srt_file(path, segments)


def _write_srt_file(audio_path: str, segments: list) -> Optional[str]:
    """Write segments to SRT file."""
    MAX_SRT_LINE_LENGTH = 42

    def split_text_to_srt_lines(text: str, max_length: int = MAX_SRT_LINE_LENGTH) -> list[str]:
        """Splits text into a list of lines, each with a maximum number of characters."""
        return textwrap.wrap(text, width=max_length, break_long_words=False, replace_whitespace=False)

    def format_srt_time(seconds: float) -> str:
        """Format time in SRT format (HH:MM:SS,mmm)."""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

    srt_filename = os.path.splitext(audio_path)[0] + ".srt"

    try:
        print(f"💾 Writing SRT file: {srt_filename}")
        with open(srt_filename, 'w', encoding='utf-8') as srt_file:
            srt_index = 1
            for segment in segments:
                text = segment['text']
                start = segment['start']
                end = segment['end']

                # Remove leading space if present
                text = text[1:] if text and text[0] == ' ' else text

                lines = split_text_to_srt_lines(text)
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
        print(f"❌ Failed to write SRT file: {e}")
        return None

    print(f"✅ SRT file created: {srt_filename}")
    return srt_filename


def get_available_models() -> list[str]:
    """Get list of available Whisper models."""
    return ["tiny", "base", "small", "medium", "large", "turbo"]


def get_whisper_info() -> dict:
    """Get information about available Whisper implementations."""
    info = {
        "fast_whisper_available": check_fast_whisper_available(),
        "whisper_available": check_whisper_available(),
        "models": get_available_models()
    }
    return info


def get_whisper_info() -> dict:
    """Get information about available Whisper implementations."""
    info = {
        "fast_whisper_available": check_fast_whisper_available(),
        "whisper_available": check_whisper_available(),
        "models": get_available_models(),
        "installation_instructions": get_installation_instructions()
    }
    return info


def diagnose_installation():
    """Diagnose the current installation and provide recommendations."""
    print("🔍 Whisper Installation Diagnostics")
    print("=" * 50)

    info = get_whisper_info()

    print(f"🖥️  System: {info['installation_instructions']['system'].title()}")
    print(f"🔥 CUDA Available: {'Yes' if torch.cuda.is_available() else 'No'}")

    if torch.cuda.is_available():
        print(f"   GPU: {torch.cuda.get_device_name(0)}")

    print(f"\n📦 Package Status:")
    print(f"   faster-whisper: {'✅ Available' if info['fast_whisper_available'] else '❌ Not installed'}")
    print(f"   openai-whisper: {'✅ Available' if info['whisper_available'] else '❌ Not installed'}")

    if not info['fast_whisper_available'] and not info['whisper_available']:
        print(f"\n⚠️  No Whisper implementation found!")
        print(f"\n📥 Installation Commands:")
        print(f"   Recommended: {info['installation_instructions']['fast_whisper']['command']}")
        print(f"   Alternative: {info['installation_instructions']['whisper']['command']}")

        if info['installation_instructions']['fast_whisper']['alternative']:
            print(f"\n💡 Troubleshooting tips:")
            for tip in info['installation_instructions']['fast_whisper']['alternative']:
                print(f"   {tip}")

    elif info['fast_whisper_available']:
        print(f"\n✅ Ready to use faster-whisper (recommended)")

    elif info['whisper_available']:
        print(f"\n✅ Ready to use openai-whisper")
        print(f"💡 Consider installing faster-whisper for better performance:")
        print(f"   {info['installation_instructions']['fast_whisper']['command']}")

    print(f"\n🎯 Available models: {', '.join(info['models'])}")


if __name__ == "__main__":
    # Run diagnostics first
    diagnose_installation()

    print("\n" + "=" * 50)

    # Example usage
    audio_path = "your_audio_file.wav"  # Change this to your audio file path

    if os.path.exists(audio_path):
        print(f"\n🎵 Processing: {audio_path}")
        # Try with fast-whisper first (if available), then fallback to regular whisper
        srt_file_path = transcribe_audio(audio_path, model_name="base", use_fast_whisper=True)
        if srt_file_path:
            print(f"✅ Success! SRT file created at: {srt_file_path}")
        else:
            print("❌ Failed to create SRT file.")
    else:
        print(f"\n💡 To test transcription, update the 'audio_path' variable to point to your audio file.")
        print("   Then run this script again.")