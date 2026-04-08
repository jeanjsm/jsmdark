from __future__ import annotations

import json
from pathlib import Path

DEFAULT_CONFIG = {
    "srt_path": "",
    "audio_path": "",
    "output_folder": "",
    "video_format": "16:9",
    "crf": 27,
    "preset": "fast",
    "fade_enabled": True,
    "fade_duration": 0.3,
    "export_with_audio": True,
    "image_map": {},
}


def build_rosary_slot_groups() -> list[dict]:
    initial_slots = [
        {"key": "initial_creed", "label": "Crucifixo / Creio"},
        {"key": "initial_pai_nosso", "label": "Pai-Nosso inicial"},
        {"key": "initial_ave_maria_1", "label": "Ave-Maria inicial 1"},
        {"key": "initial_ave_maria_2", "label": "Ave-Maria inicial 2"},
        {"key": "initial_ave_maria_3", "label": "Ave-Maria inicial 3"},
        {"key": "initial_gloria", "label": "Glória inicial"},
    ]
    groups = [{"key": "initial_prayers", "label": "Orações iniciais", "slots": initial_slots}]

    for decade in range(1, 6):
        slots = [{"key": f"decade_{decade}_pai_nosso", "label": "Pai-Nosso"}]
        slots.extend(
            {"key": f"decade_{decade}_ave_maria_{index}", "label": f"Ave-Maria {index}"}
            for index in range(1, 11)
        )
        slots.append({"key": f"decade_{decade}_gloria", "label": "Glória"})
        slots.append(
            {
                "key": f"decade_{decade}_final_prayer",
                "label": "Oração final (opcional)",
                "optional": True,
            }
        )
        groups.append({"key": f"decade_{decade}", "label": f"{decade}ª dezena", "slots": slots})

    groups.append(
        {
            "key": "closing",
            "label": "Encerramento",
            "slots": [{"key": "closing", "label": "Salve Rainha / encerramento"}],
        }
    )
    return groups


def load_rosary_config(config_path: str | Path) -> dict:
    path = Path(config_path)
    if not path.exists():
        return {**DEFAULT_CONFIG, "image_map": dict(DEFAULT_CONFIG["image_map"])}

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {}

    image_map = data.get("image_map", {})
    if not isinstance(image_map, dict):
        image_map = {}

    return {
        **DEFAULT_CONFIG,
        **data,
        "image_map": {**DEFAULT_CONFIG["image_map"], **image_map},
    }



def save_rosary_config(config_path: str | Path, payload: dict) -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
