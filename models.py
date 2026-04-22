# models.py
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import os
from datetime import datetime
from abc import ABC, abstractmethod

# Constants
DEFAULT_STATUS = "waiting"
DEFAULT_PROGRESS = 0
DEFAULT_ERROR_MESSAGE = ""
DEFAULT_CHROMA_SCALE = 0.3
DEFAULT_CHROMA_POSITION = "bottom_center"
DEFAULT_CHROMA_START = 30.0


# --- DDD Value Objects ---
@dataclass(frozen=True)
class VignetteEffect:
    """Value Object representing vignette effect configuration.

    Encapsulates the domain logic for vignette parameters validation and
    FFmpeg filter generation following DDD principles.
    """
    intensity: float = 0.3
    angle: str = "PI/4"

    def __post_init__(self):
        """Validates vignette parameters according to domain rules."""
        if not (0.0 <= self.intensity <= 1.0):
            raise ValueError(f"Vignette intensity must be between 0.0 and 1.0, got {self.intensity}")

    def to_ffmpeg_filter(self, input_map: str, output_map: str) -> str:
        """Generates valid FFmpeg vignette filter string.

        Args:
            input_map: Input video stream map (e.g., "[v0]")
            output_map: Output video stream map (e.g., "[vvignette]")

        Returns:
            Valid FFmpeg vignette filter string
        """
        # Use standard vignette filter parameters that are universally supported
        return f"{input_map}vignette=angle={self.angle}:mode=forward:eval=init{output_map}"


# --- CLASSE QueueItem RESTAURADA ---
@dataclass
class QueueItem:
    """Represents a single item in the processing queue.

    Attributes:
        narration_path (str): Path to the narration file.
        output_path (str): Path to the output file.
        status (str): Processing status (waiting, processing, completed, error).
        progress (int): Progress percentage.
        error_message (str): Error message if any.
    """
    narration_path: str
    output_path: str
    status: str = DEFAULT_STATUS  # waiting, processing, completed, error
    progress: int = DEFAULT_PROGRESS
    error_message: str = DEFAULT_ERROR_MESSAGE


@dataclass
class ChromaConfig:
    """Configuration for chroma overlay.

    Attributes:
        path (str): Path to chroma file.
        scale (float): Scale factor for chroma.
        position (str): Position of chroma overlay.
        start (float): Start time for chroma effect.
    """
    path: str = ""
    scale: float = DEFAULT_CHROMA_SCALE
    position: str = DEFAULT_CHROMA_POSITION
    start: float = DEFAULT_CHROMA_START


@dataclass
class ConfigModel:
    """
    Modelo de dados que corresponde 1:1 aos parâmetros da função original.
    """
    # Parâmetros básicos
    narration_path: str = ""
    videos_folder: str = ""
    output_folder: str = ""  # Usado pela UI, mas não passado diretamente para a função
    seed: Optional[int] = None
    shuffle: bool = True
    video_mode: str = "videos"
    image_segment_duration: float = 6.0
    enable_ken_burns: bool = True  # Controla se aplica efeito Ken Burns nas imagens

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

    # Rosário - Mapa de imagens para cada slot
    rosary_image_map: Dict[str, str] = field(default_factory=dict)
    # Rosário - indica se o roteiro contém as orações iniciais
    rosary_has_initial_prayers: bool = True

    def to_dict(self):
        # Converte o dataclass para um dicionário, incluindo os aninhados
        data = asdict(self)
        # Garante que a lista de chromas seja uma lista de dicionários
        data['chroma_list'] = [asdict(c) for c in self.chroma_list]
        # Garante explicitamente que None seja preservado no JSON como null
        if self.seed is None:
            data['seed'] = None
        return data

    def save(self, filepath="config.json"):
        try:
            with open(filepath, "w", encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configuração: {e}")

    def save_slot(self, slot_name: str) -> bool:
        """Save current configuration to a named slot.

        Args:
            slot_name (str): Name of the save slot

        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            slots_dir = Path("config_slots")
            slots_dir.mkdir(exist_ok=True)

            # Sanitize slot name for filename
            safe_name = "".join(c for c in slot_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not safe_name:
                safe_name = f"slot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            slot_filepath = slots_dir / f"{safe_name}.json"

            # Add metadata to the save
            data = self.to_dict()
            data['_slot_metadata'] = {
                'name': slot_name,
                'created_at': datetime.now().isoformat(),
                'filename': safe_name
            }

            with open(slot_filepath, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Erro ao salvar slot '{slot_name}': {e}")
            return False

    @classmethod
    def load_slot(cls, slot_name: str):
        """Load configuration from a named slot.

        Args:
            slot_name (str): Name of the save slot

        Returns:
            ConfigModel: Loaded configuration or default if not found
        """
        try:
            slots_dir = Path("config_slots")
            if not slots_dir.exists():
                return cls()

            # Try to find the slot file
            safe_name = "".join(c for c in slot_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            slot_filepath = slots_dir / f"{safe_name}.json"

            if not slot_filepath.exists():
                # Try to find by display name in metadata
                for slot_file in slots_dir.glob("*.json"):
                    try:
                        with open(slot_file, "r", encoding='utf-8') as f:
                            data = json.load(f)
                            if data.get('_slot_metadata', {}).get('name') == slot_name:
                                slot_filepath = slot_file
                                break
                    except Exception:
                        continue

            if not slot_filepath.exists():
                print(f"Slot '{slot_name}' não encontrado.")
                return cls()

            with open(slot_filepath, "r", encoding='utf-8') as f:
                data = json.load(f)

            # Remove metadata before creating instance
            data.pop('_slot_metadata', None)

            # Recria os dataclasses aninhados a partir dos dicionários
            if 'chroma_list' in data:
                data['chroma_list'] = [ChromaConfig(**c) for c in data.get('chroma_list', [])]

            # Filtra chaves inválidas para evitar erros ao desempacotar
            valid_keys = cls.__annotations__.keys()
            filtered_data = {k: v for k, v in data.items() if k in valid_keys}

            return cls(**filtered_data)
        except Exception as e:
            print(f"Erro ao carregar slot '{slot_name}': {e}. Usando configurações padrão.")
            return cls()

    @staticmethod
    def list_save_slots() -> List[Dict[str, str]]:
        """List all available save slots.

        Returns:
            List[Dict[str, str]]: List of slot info dictionaries with 'name', 'created_at', 'filename'
        """
        slots = []
        slots_dir = Path("config_slots")

        if not slots_dir.exists():
            return slots

        for slot_file in slots_dir.glob("*.json"):
            try:
                with open(slot_file, "r", encoding='utf-8') as f:
                    data = json.load(f)
                    metadata = data.get('_slot_metadata', {})

                    # If no metadata, create from filename
                    if not metadata:
                        name = slot_file.stem.replace('_', ' ')
                        created_at = datetime.fromtimestamp(slot_file.stat().st_mtime).isoformat()
                        filename = slot_file.stem
                    else:
                        name = metadata.get('name', slot_file.stem.replace('_', ' '))
                        created_at = metadata.get('created_at', datetime.fromtimestamp(slot_file.stat().st_mtime).isoformat())
                        filename = metadata.get('filename', slot_file.stem)

                    slots.append({
                        'name': name,
                        'created_at': created_at,
                        'filename': filename,
                        'filepath': str(slot_file)
                    })
            except Exception as e:
                print(f"Erro ao ler slot {slot_file}: {e}")
                continue

        # Sort by creation date, newest first
        slots.sort(key=lambda x: x['created_at'], reverse=True)
        return slots

    @staticmethod
    def delete_save_slot(slot_name: str) -> bool:
        """Delete a save slot.

        Args:
            slot_name (str): Name of the save slot to delete

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            slots_dir = Path("config_slots")
            if not slots_dir.exists():
                return False

            # Try to find the slot file
            safe_name = "".join(c for c in slot_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            slot_filepath = slots_dir / f"{safe_name}.json"

            if not slot_filepath.exists():
                # Try to find by display name in metadata
                for slot_file in slots_dir.glob("*.json"):
                    try:
                        with open(slot_file, "r", encoding='utf-8') as f:
                            data = json.load(f)
                            if data.get('_slot_metadata', {}).get('name') == slot_name:
                                slot_filepath = slot_file
                                break
                    except Exception:
                        continue

            if slot_filepath.exists():
                slot_filepath.unlink()
                return True
            else:
                print(f"Slot '{slot_name}' não encontrado.")
                return False

        except Exception as e:
            print(f"Erro ao deletar slot '{slot_name}': {e}")
            return False

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
