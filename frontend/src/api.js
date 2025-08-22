export async function processVideo(narrationFile) {
  const formData = new FormData();
  formData.append('narration', narrationFile);
  const res = await fetch('http://localhost:8000/video/process', { method: 'POST', body: formData });
  return res.json();
}
# Inicialização FastAPI
from fastapi import FastAPI
from backend.api import video

app = FastAPI()
app.include_router(video.router, prefix="/video")

