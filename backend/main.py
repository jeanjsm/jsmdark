from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import video

app = FastAPI(
    title="Video Processing API",
    description="API para processamento de vídeos com FFmpeg, legendas, overlays, trilha sonora e mais.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(video.router, prefix="/video")
