# videos_ffmpeg

Este projeto automatiza a criação de vídeos a partir de narrações, imagens e trilhas sonoras, utilizando FFmpeg e modelos de transcrição Vosk.

## Funcionalidades
- Geração de vídeo a partir de narração (MP3/WAV)
- Suporte a imagens ou vídeos como base visual
- Efeitos de legenda (fade, barra, etc.)
- Adição de trilha sonora de fundo
- Suporte a legendas automáticas via Vosk
- Diversos perfis de encoder (CPU/GPU)
- Resoluções e presets customizáveis

## Requisitos
- Python 3.10+
- FFmpeg (incluso em _internal/ffmpeg/bin)
- Modelos Vosk (inclusos em _internal/vosk_models)

## Uso
Exemplo de comando:

```
python video_from_narration.py --narracao ./arquivos_teste/narracao.mp3 --video_mode images --saida ./output_videos/output.mp4 --background_music ./arquivos_teste/fundo.mp3 --enable_subtitles --subtitle_effect fade_in
```

## Estrutura
- `video_from_narration.py`: Script principal
- `pipeline.py`: Pipeline de processamento
- `audio_utils.py`, `video_utils.py`, `subtitle_utils.py`: utilitários
- `_internal/ffmpeg/`: binários do FFmpeg
- `_internal/vosk_models/`: modelos de transcrição

## Testes
Execute:
```
python test_pipeline.py
```

## Licença
MIT

