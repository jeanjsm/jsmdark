# videos_ffmpeg

Este projeto automatiza a criação de vídeos a partir de narrações, imagens e trilhas sonoras, utilizando FFmpeg, FastAPI, Electron e modelos de transcrição Vosk.

## Funcionalidades
- Geração de vídeo a partir de narração (MP3/WAV)
- Suporte a imagens ou vídeos como base visual
- Efeitos de legenda (fade, barra, etc.)
- Adição de trilha sonora de fundo
- Suporte a legendas automáticas via Vosk
- Diversos perfis de encoder (CPU/GPU)
- Resoluções e presets customizáveis
- API web (FastAPI) com Swagger UI (/docs)
- Frontend desktop (Electron)

## Requisitos
- Python 3.10+
- FFmpeg (incluso em _internal/ffmpeg/bin)
- Modelos Vosk (inclusos em _internal/vosk_models)
- Node.js 18+

## Estrutura
- `backend/` - Backend FastAPI
    - `main.py`: Inicialização FastAPI
    - `api/`: Rotas (ex: video.py)
    - `pipelines/`: Pipelines de processamento
    - `services/`: Serviços de áudio, vídeo, legendas
    - `models/`: Schemas Pydantic
    - `utils/`: Utilitários
    - `tests/`: Testes automatizados
    - `requirements.txt`: Dependências Python
- `frontend/` - Frontend Electron
    - `main.js`: Entry point Electron
    - `src/`: Código JS/React/Vue
    - `public/`: Assets estáticos
    - `package.json`: Configuração Electron
- `_internal/ffmpeg/`: binários do FFmpeg
- `_internal/vosk_models/`: modelos de transcrição
- `arquivos_teste/`: arquivos de exemplo
- `output_videos/`: saída dos vídeos

## Como executar
### Backend (API)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```
Acesse a documentação interativa em http://localhost:8000/docs

### Frontend (Electron)
```bash
cd frontend
npm install
npm start
```

## Testes
Execute:
```bash
cd backend
pytest
```

## Observações
- O endpoint `/video/process` aceita todos os parâmetros do pipeline via multipart/form-data.
- O vídeo gerado é retornado diretamente como download.
- Parâmetros opcionais não preenchidos são ignorados.
- Logs detalhados de erro do FFmpeg são exibidos no terminal do backend.

## Licença
MIT
