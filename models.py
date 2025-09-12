# models.py
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict


# --- CLASSE QueueItem RESTAURADA ---
@dataclass
class QueueItem:
    """Representa um único item na fila de processamento."""
    narration_path: str
    output_path: str
    status: str = "waiting"  # waiting, processing, completed, error
    progress: int = 0
    error_message: str = ""


# ------------------------------------

@dataclass
class ChromaConfig:
    path: str = ""
    scale: float = 0.3
    position: str = "bottom_center"
    start: float = 30.0


@dataclass
class ConfigModel:
    """
    Modelo de dados que corresponde 1:1 aos parâmetros da função original.
    """
    # Parâmetros básicos
    narration_path: str = ""
    videos_folder: str = ""
    output_folder: str = ""  # Usado pela UI, mas não passado diretamente para a função
    seed: int = -1
    shuffle: bool = True
    video_mode: str = "videos"
    image_segment_duration: float = 6.0

    # Parâmetros de vídeo e encoder
    fps: int = 30
    width: int = 1920
    height: int = 1080
    crf: int = 18
    preset: str = "medium"
    encoder: str = "libx264"
    threads: int = 0
    gpu_quality: int = 18
    resolution_preset: str = "horizontal_1080p"

    # Parâmetros de overlay e efeitos
    overlay: str = ""
    overlay_opacity: float = 0.3
    logo: str = ""
    logo_scale: float = 0.15
    logo_x: int = 20
    logo_y: int = 20
    logo_position: str = "top_right"
    transition_type: str = "none"
    chroma_list: List[ChromaConfig] = field(default_factory=list)

    # Parâmetros de legendas
    enable_subtitles: bool = False
    subtitle_font_size: int = 60
    subtitle_color: str = "yellow"
    subtitle_position: str = "center"
    subtitle_font: str = "./_internal/_fonts/BebasNeue-Regular.ttf"
    subtitle_outline_color: str = "black"
    subtitle_outline_width: int = 2
    subtitle_shadow_color: str = "black"
    subtitle_shadow_x: int = 2
    subtitle_shadow_y: int = 2
    words_per_subtitle: int = 5
    vosk_model_path: str = "_internal/vosk_models/vosk-model-pt"
    subtitle_effect: str = "none"

    # Efeitos cinematográficos
    cinematic_preset: str = "nenhum"
    custom_lut_path: str = ""
    enable_vignette: bool = False
    vignette_intensity: float = 0.3
    enable_curves: bool = False
    custom_curves: str = ""

    # Parâmetros de áudio
    remove_silence: bool = True
    silence_threshold: int = -40
    silence_duration: float = 0.5
    background_music: str = ""
    background_music_volume: float = 0.2

    # Abertura e Encerramento
    opening_video_paths: List[str] = field(default_factory=list)
    ending_video_path: str = ""

    def to_dict(self):
        # Converte o dataclass para um dicionário, incluindo os aninhados
        data = asdict(self)
        # Garante que a lista de chromas seja uma lista de dicionários
        data['chroma_list'] = [asdict(c) for c in self.chroma_list]
        return data

    def save(self, filepath="config.json"):
        try:
            with open(filepath, "w", encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")

    @classmethod
    def load(cls, filepath="config.json"):
        if not Path(filepath).exists():
            return cls()
        try:
            with open(filepath, "r", encoding='utf-8') as f:
                data = json.load(f)

                # Recria os dataclasses aninhados a partir dos dicionários
                if 'chroma_list' in data:
                    data['chroma_list'] = [ChromaConfig(**c) for c in data.get('chroma_list', [])]

                # Filtra chaves inválidas para evitar erros ao desempacotar
                valid_keys = cls.__annotations__.keys()
                filtered_data = {k: v for k, v in data.items() if k in valid_keys}

                return cls(**filtered_data)
        except Exception as e:
            print(f"Erro ao carregar config.json: {e}. Usando configurações padrão.")
            return cls()
