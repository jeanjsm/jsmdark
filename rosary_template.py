from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import srt


class RosaryTemplateError(Exception):
    """Raised when rosary subtitle entries do not match the expected template."""


@dataclass(frozen=True)
class RosaryTimelineItem:
    slot_key: str
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class PrayerMatch:
    slot_key: str
    trigger: str


# Mapeamento de triggers para slots da estrutura completa
# slotted keys: initial_creed, initial_pai_nosso, initial_ave_maria_1..3, initial_gloria
# decade_X_pai_nosso, decade_X_ave_maria_1..10, decade_X_gloria, decade_X_final_prayer (opcional)
# closing

def get_slot_key_for_prayer(prayer_type: str, decade_number: int = 0) -> str:
    """Mapeia o tipo de oração e dezena para a chave do slot correspondente.

    Args:
        prayer_type: Tipo de oração (creed, pai_nosso, ave_maria, gloria, closing, final_prayer)
        decade_number: Número da dezena (1-5). 0 = orações iniciais

    Returns:
        A chave do slot correspondente na estrutura completa
    """
    if prayer_type == "closing":
        return "closing"
    elif prayer_type == "creed":
        return "initial_creed"
    elif prayer_type == "pai_nosso":
        if decade_number == 0:
            return "initial_pai_nosso"
        else:
            return f"decade_{decade_number}_pai_nosso"
    elif prayer_type == "ave_maria":
        if decade_number == 0:
            # Ave-Marias iniciais são as primeiras 3
            # Precisamos contar qual é a próxima
            # Isso será tratado externamente contando o número de ave-marias até o primeiro glória
            # Vamos implementar isso no build_rosary_timeline
            raise NotImplementedError("Ave-Maria inicial deve ser tratada no contexto da timeline")
        else:
            # Número da ave-maria nesta dezena (1-10)
            # Também será tratado no contexto
            raise NotImplementedError("Ave-Maria de dezena deve ser tratada no contexto da timeline")
    elif prayer_type == "gloria":
        if decade_number == 0:
            return "initial_gloria"
        else:
            return f"decade_{decade_number}_gloria"
    elif prayer_type == "final_prayer":
        return f"decade_{decade_number}_final_prayer"
    else:
        raise ValueError(f"Tipo de oração desconhecido: {prayer_type}")


def normalize_prayer_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.strip().lower())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def parse_srt_file(srt_path: str | Path) -> list[tuple[float, float, str]]:
    path = Path(srt_path)
    subtitles = list(srt.parse(path.read_text(encoding="utf-8")))
    return [
        (float(subtitle.start.total_seconds()), float(subtitle.end.total_seconds()), subtitle.content)
        for subtitle in subtitles
    ]


def build_rosary_timeline(
    entries: list[tuple[float, float, str]],
    has_initial_prayers: bool = True,
) -> list[RosaryTimelineItem]:
    """
    Constrói a timeline do rosário mapeando as entradas do SRT para os slots da estrutura completa.

    Estrutura (quando has_initial_prayers=True):
    - Orações Iniciais (6 slots):
        initial_creed, initial_pai_nosso, initial_ave_maria_1/2/3, initial_gloria
    - Dezenas 1-5 (cada uma com 13-14 slots):
        decade_X_pai_nosso, decade_X_ave_maria_1..10, decade_X_gloria, decade_X_final_prayer (opcional)
    - Encerramento (1 slot):
        closing

    Quando has_initial_prayers=False, o parser ignora a fase inicial e começa
    diretamente na primeira dezena (o primeiro Pai-Nosso encontrado abre a dezena 1).

    Args:
        entries: Lista de (start, end, text) obtida do SRT.
        has_initial_prayers: Indica se o roteiro contém as orações iniciais
            (Credo, Pai-Nosso inicial, 3 Ave-Marias iniciais, Glória inicial).
            Quando False, qualquer texto de credo é tratado como narrativa e
            o primeiro Pai-Nosso inicia a 1ª dezena diretamente.

    O SRT deve conter as orações na sequência correta.
    """
    if not entries:
        raise RosaryTemplateError("SRT vazio.")

    timeline: list[RosaryTimelineItem] = []

    # Estado do parser
    current_slot: str | None = None
    current_start: float | None = None
    current_end: float | None = None
    current_text_parts: list[str] = []

    # Buffer para textos iniciais não reconhecidos antes do primeiro slot.
    # Isso preserva a duração total do SRT (evita perder minutos iniciais).
    leading_start: float | None = None
    leading_text_parts: list[str] = []

    # Contadores
    decade_number = 0  # 0 = orações iniciais, 1-5 = dezenas
    ave_maria_index = 0  # Índice da Ave-Maria na sequência atual
    # Quando não há orações iniciais, iniciar diretamente após a glória inicial
    # para que o primeiro Pai-Nosso abra a dezena 1
    phase = "initials" if has_initial_prayers else "after_initial_glory"  # "initials", "decade", "closing"

    def flush_current() -> None:
        nonlocal current_slot, current_start, current_end, current_text_parts
        if current_slot is not None and current_start is not None and current_end is not None:
            timeline.append(RosaryTimelineItem(
                slot_key=current_slot,
                start=current_start,
                end=current_end,
                text=" ".join(current_text_parts).strip()
            ))
        current_slot = None
        current_start = None
        current_end = None
        current_text_parts = []

    def ensure_slot(slot_key: str, start: float, end: float, text: str) -> None:
        nonlocal current_slot, current_start, current_end, current_text_parts
        nonlocal leading_start, leading_text_parts
        if current_slot != slot_key:
            flush_current()
            current_slot = slot_key
            # Se houver texto inicial sem slot, anexar ao primeiro slot reconhecido
            if leading_start is not None:
                current_start = leading_start
                current_text_parts = [*leading_text_parts, text]
                leading_start = None
                leading_text_parts = []
            else:
                current_start = start
                current_text_parts = [text]
            current_end = end
        else:
            current_end = end
            current_text_parts.append(text)

    # Helpers para obter slot key
    def get_slot(prayer_type: str) -> str:
        if prayer_type == "closing":
            return "closing"
        elif prayer_type == "creed":
            return "initial_creed"
        elif prayer_type == "pai_nosso":
            if phase == "initials":
                return "initial_pai_nosso"
            else:
                return f"decade_{decade_number}_pai_nosso"
        elif prayer_type == "ave_maria":
            if phase == "initials":
                if ave_maria_index < 3:
                    return f"initial_ave_maria_{ave_maria_index + 1}"
                else:
                    raise RosaryTemplateError("Mais de 3 Ave-Marias nas orações iniciais")
            else:
                if ave_maria_index < 10:
                    return f"decade_{decade_number}_ave_maria_{ave_maria_index + 1}"
                else:
                    raise RosaryTemplateError(f"Mais de 10 Ave-Marias na {decade_number}ª dezena")
        elif prayer_type == "gloria":
            if phase == "initials":
                return "initial_gloria"
            else:
                return f"decade_{decade_number}_gloria"
        else:
            raise RosaryTemplateError(f"Tipo de oração desconhecido: {prayer_type}")

    for start, end, text in entries:
        normalized = normalize_prayer_text(text)
        prayer_type: str | None = None

        # Detectar tipo (ordem importa: checks mais específicos primeiro)
        if "salve rainha" in normalized:
            prayer_type = "closing"
        elif "gloria ao pai" in normalized:
            prayer_type = "gloria"
        elif "pai nosso" in normalized:
            prayer_type = "pai_nosso"
        elif "ave maria" in normalized:
            prayer_type = "ave_maria"
        elif "em nome do pai" in normalized and ("creio" in normalized or "credo" in normalized):
            # Só detecta creed se tiver "em nome do pai" + contexto de credo explícito
            prayer_type = "creed"
        elif "creio" in normalized or "credo" in normalized:
            prayer_type = "creed"
        elif "em nome do pai" in normalized and phase == "initials" and current_slot is None:
            # "Em nome do Pai..." como invocação inicial (sem texto de credo)
            prayer_type = "creed"

        # Quando não há orações iniciais, credo detectado é narrativa (e.g. "Meu Deus, eu creio...")
        if not has_initial_prayers and prayer_type == "creed":
            prayer_type = None

        if prayer_type is None:
            # Texto não reconhecido - anexar ao atual se houver
            if current_slot is not None:
                current_end = end
                current_text_parts.append(text)
            else:
                # Ainda não iniciamos nenhum slot: guardar como bloco inicial
                if leading_start is None:
                    leading_start = start
                leading_text_parts.append(text)
            continue

        # Lógica de transição de estado
        if prayer_type == "closing":
            phase = "closing"
            decade_number = 0
            slot = get_slot("closing")
            ensure_slot(slot, start, end, text)
            ave_maria_index = 0

        elif prayer_type == "gloria":
            slot = get_slot("gloria")
            ensure_slot(slot, start, end, text)
            # Glória finaliza o grupo atual
            if phase == "initials":
                phase = "after_initial_glory"  # Próximo será dezena 1
            else:
                phase = "after_decade_glory"  # Próximo será nova dezena ou closing
            ave_maria_index = 0

        elif prayer_type == "pai_nosso":
            if phase == "initials":
                slot = get_slot("pai_nosso")  # initial_pai_nosso
                ensure_slot(slot, start, end, text)
                phase = "initials"
                ave_maria_index = 0
            elif phase == "after_initial_glory":
                # Primeira dezena
                decade_number = 1
                phase = "decade"
                slot = get_slot("pai_nosso")  # decade_1_pai_nosso
                ensure_slot(slot, start, end, text)
                ave_maria_index = 0
            elif phase in ["after_decade_glory", "decade"]:
                if phase == "after_decade_glory":
                    decade_number += 1
                    if decade_number > 5:
                        raise RosaryTemplateError("Mais de 5 dezenas")
                slot = get_slot("pai_nosso")
                ensure_slot(slot, start, end, text)
                phase = "decade"
                ave_maria_index = 0
            else:
                raise RosaryTemplateError(f"Pai-Nosso inesperado no estado {phase}")

        elif prayer_type == "ave_maria":
            slot = get_slot("ave_maria")
            ensure_slot(slot, start, end, text)
            ave_maria_index += 1

        elif prayer_type == "creed":
            if phase != "initials" and phase != "after_initial_glory":
                raise RosaryTemplateError("Credo fora do início")
            slot = get_slot("creed")  # initial_creed
            ensure_slot(slot, start, end, text)
            phase = "initials"
            ave_maria_index = 0

    flush_current()
    return timeline
