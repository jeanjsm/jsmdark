import json
import wave
import subprocess
from pathlib import Path
from typing import List, Tuple
import unicodedata

import vosk
from ffmpeg_utils import get_ffmpeg_path


# -----------------------------
# Utilitários de texto/Unicode
# -----------------------------


def normalize_text(s: str) -> str:
    """
    Normaliza o texto para NFC e remove caracteres de controle invisíveis
    (mantém quebras de linha).
    """
    s = unicodedata.normalize("NFC", s)
    return "".join(ch for ch in s if ch == "\n" or ch >= " ")


def ff_escape(s: str) -> str:
    """
    Escapa os caracteres especiais para uso seguro no drawtext.
    Isso cobre barra invertida, aspas simples, dois-pontos, colchetes,
    porcento e vírgula, que frequentemente quebram o parser do FFmpeg.
    """
    s = s.replace("\\", "\\\\")
    s = s.replace("'", r"\'")
    s = s.replace(":", r"\:")
    s = s.replace("%", r"\%")
    s = s.replace("[", r"\[")
    s = s.replace("]", r"\]")
    s = s.replace(",", r"\,")
    return s


# ------------------------------------------
# Extração de áudio para transcrição (Vosk)
# ------------------------------------------


def extract_audio_for_transcription(video_path: str, output_path: str) -> None:
    """Extrai áudio do vídeo em formato WAV mono 16kHz para o Vosk (mais enxuto e performático)."""
    cmd = [
        get_ffmpeg_path(),
        "-y",
        "-nostdin",
        "-vn",  # descarta vídeo
        "-sn",  # descarta legendas
        "-dn",  # descarta data streams
        "-i",
        video_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "wav",
        output_path,
    ]
    # Não use capture_output=True para evitar buffers gigantes desnecessários
    subprocess.run(cmd, check=True)


# ------------------------------------------
# Transcrição com Vosk
# ------------------------------------------


def transcribe_audio(
    audio_path: str, model_path: str = "_internal/vosk_models/vosk-model-pt"
) -> List[Tuple[float, float, str]]:
    """Transcreve áudio usando Vosk e retorna lista de (start, end, text)."""
    if not Path(model_path).exists():
        raise FileNotFoundError(f"Modelo Vosk não encontrado: {model_path}")

    model = vosk.Model(model_path)
    rec = vosk.KaldiRecognizer(model, 16000)
    rec.SetWords(True)

    segments: List[Tuple[float, float, str]] = []

    # Opcional: validar que o WAV está 16kHz mono
    with wave.open(audio_path, "rb") as wf:
        # Leitura por blocos (~0,25s a 16kHz mono com 4000 frames)
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if "result" in result and result["result"]:
                    for word in result["result"]:
                        start = float(word.get("start", 0.0))
                        end = float(word.get("end", 0.0))
                        text = normalize_text(word.get("word", ""))
                        if text:
                            segments.append((start, end, text))

    # Processa resultado final
    final_result = json.loads(rec.FinalResult())
    if "result" in final_result and final_result["result"]:
        for word in final_result["result"]:
            start = float(word.get("start", 0.0))
            end = float(word.get("end", 0.0))
            text = normalize_text(word.get("word", ""))
            if text:
                segments.append((start, end, text))

    return segments


# ------------------------------------------
# Posicionamento de legenda
# ------------------------------------------


def get_subtitle_position(position: str) -> str:
    """Retorna as coordenadas x,y para a posição da legenda."""
    positions = {
        "top_left": "x=20:y=20",
        "top_center": "x=(w-text_w)/2:y=20",
        "top_right": "x=w-text_w-20:y=20",
        "center": "x=(w-text_w)/2:y=(h-text_h)/2",
        "bottom_left": "x=20:y=h-text_h-20",
        "bottom_center": "x=(w-text_w)/2:y=h-60",
        "bottom_right": "x=w-text_w-20:y=h-text_h-20",
    }
    return positions.get(position, "x=(w-text_w)/2:y=h-60")


# ------------------------------------------
# Agrupamento de palavras em legendas
# ------------------------------------------


def group_words_by_count(
    segments: List[Tuple[float, float, str]], words_per_group: int = 1
) -> List[Tuple[float, float, str]]:
    """Agrupa palavras consecutivas respeitando o limite de palavras por grupo."""
    if not segments or words_per_group <= 1:
        return segments

    grouped: List[Tuple[float, float, str]] = []
    current_group: List[str] = []
    current_start = None
    current_end = None

    for start, end, word in segments:
        if len(current_group) == 0:
            current_start = start

        current_group.append(word)
        current_end = end

        if len(current_group) >= words_per_group:
            grouped_text = " ".join(current_group)
            grouped.append((float(current_start), float(current_end), grouped_text))
            current_group = []

    # Adiciona grupo restante se houver
    if current_group:
        grouped_text = " ".join(current_group)
        grouped.append((float(current_start), float(current_end), grouped_text))

    return grouped


# ------------------------------------------
# (FALLBACK) Geração de filtro drawtext
# ------------------------------------------


def create_subtitle_filter(
    segments: List[Tuple[float, float, str]],
    font_size: int = 24,
    font_color: str = "white",
    position: str = "bottom_center",
    words_per_subtitle: int = 1,
    font_path: str = None,
    outline_color: str = "black",
    outline_width: int = 2,
    shadow_color: str = "black",
    shadow_x: int = 2,
    shadow_y: int = 2,
) -> str:
    """
    Cria filtro FFmpeg para legendas baseado nos segmentos transcritos.

    AVISO DE PERFORMANCE:
    - Este método encadeia vários 'drawtext', o que pode ficar lento e frágil para muitas legendas.
    - Prefira gerar SRT/ASS e usar `-vf subtitles=...` (ver funções abaixo).

    Mantido por compatibilidade, mas otimizado com normalização/escape.
    """
    if not segments:
        return ""

    # Agrupa palavras se necessário
    if words_per_subtitle > 1:
        segments = group_words_by_count(segments, words_per_subtitle)

    position_coords = get_subtitle_position(position)

    # Define fonte
    font_config = ""
    if font_path:
        # Se for caminho existente, usa fontfile (filtro drawtext exige escapes para ':' e '\')
        p = Path(font_path)
        if p.exists():
            # Escapa ':' e '\' no caminho
            safe_path = str(p).replace("\\", "\\\\").replace(":", "\\:")
            font_config = f":fontfile='{safe_path}'"
        else:
            # Tenta como família de fonte
            font_config = f":fontfamily='{ff_escape(font_path)}'"

    # Define outline e sombra
    outline_config = f":bordercolor={outline_color}:borderw={outline_width}"
    shadow_config = f":shadowcolor={shadow_color}:shadowx={shadow_x}:shadowy={shadow_y}"

    # Cria um único filtro drawtext por segmento
    drawtext_filters = []
    for start, end, text in segments:
        text = normalize_text(text)
        if not text:
            continue
        text_escaped = ff_escape(text)
        drawtext_filters.append(
            f"drawtext=text='{text_escaped}':fontsize={font_size}:fontcolor={font_color}:"
            f"{position_coords}{font_config}{outline_config}{shadow_config}:enable='between(t,{start},{end})'"
        )

    return ",".join(drawtext_filters)


# ------------------------------------------
# Geração de arquivos de legenda (SRT / ASS)
# ------------------------------------------


def generate_srt_file(
    segments: List[Tuple[float, float, str]], output_path: str, add_bom: bool = False
) -> None:
    """Gera arquivo SRT a partir dos segmentos transcritos (UTF-8; opcional BOM para players antigos)."""
    encoding = "utf-8-sig" if add_bom else "utf-8"
    with open(output_path, "w", encoding=encoding) as f:
        idx = 1
        for start, end, text in segments:
            text = normalize_text(text)
            if not text:
                continue
            start_time = format_time_srt(start)
            end_time = format_time_srt(end)
            f.write(f"{idx}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")
            idx += 1


def generate_ass_file(
    segments: List[Tuple[float, float, str]],
    out_path: str,
    font: str = "Arial",
    size: int = 36,
    color: str = "&H00FFFFFF&",  # BGR + AA (ASS)
    outline_color: str = "&H00000000&",
    outline: int = 2,
    shadow: int = 1,
    alignment: int = 5,  # 2=bottom-center, 8=top-center, etc.
    playres_x: int = 1920,
    playres_y: int = 1080,
    margin_v: int = 40,
    subtitle_effect: str = "none",
    shadow_opacity: float = None,  # Opacidade da sombra (0-1)
    shadow_blur: float = None,  # Desfoque da sombra (0-1)
    shadow_distance: int = None,  # Distância da sombra em pixels
    shadow_angle: int = None,  # Ângulo da sombra em graus
) -> None:
    """Gera arquivo ASS estilizado com encoding UTF-8 BOM para compatibilidade."""
    # Calcular sombra avançada para o estilo CapCut se especificada
    shadow_x = shadow
    shadow_y = shadow

    if shadow_distance and shadow_angle is not None:
        import math

        # Converter ângulo em radianos (CapCut usa ângulo no sentido horário)
        angle_rad = math.radians(shadow_angle)
        # Calcular componentes x e y com base na distância e ângulo
        shadow_x = round(math.cos(angle_rad) * shadow_distance)
        shadow_y = round(math.sin(angle_rad) * shadow_distance)

    # Aplicar opacidade à sombra se especificada (o formato ASS usa &Haa no começo para alfa)
    back_colour = "&H64000000&"  # Padrão: alfa 64 (semi-transparente)
    if shadow_opacity is not None:
        # Converter opacidade de 0-1 para 00-FF em hexadecimal (invertido, pois 00 é opaco em ASS)
        alpha_hex = format(round(255 * (1 - shadow_opacity)), "02X")
        back_colour = f"&H{alpha_hex}000000&"

    header = (
        "[Script Info]\n"
        "Title: Auto-generated subtitles\n"
        "ScriptType: v4.00+\n"
        "Collisions: Normal\n"
        f"PlayResX: {playres_x}\n"
        f"PlayResY: {playres_y}\n"
        "Timer: 100.0000\n"
        "\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{size},{color},&H00FFFFFF&,{outline_color},{back_colour},"
        f"-1,0,0,0,100,100,0,0,1,{outline},{1 if shadow_blur is None else 0},{alignment},20,20,{margin_v},1\n"
        "\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    def ass_time(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h:d}:{m:02d}:{s:05.2f}"

    # Grava com UTF-8 BOM para máxima compatibilidade
    with open(out_path, "w", encoding="utf-8-sig") as f:
        f.write(header)
        for start, end, text in segments:
            text = normalize_text(text)
            if not text:
                continue
            # Escapa caracteres especiais para ASS
            text = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
            text = text.replace("\n", r"\N")
            text = text.upper()

            # Aplicar efeitos especiais
            if subtitle_effect == "fade_in":
                text = "{\\fad(1000,0)}" + text
            elif subtitle_effect == "karaoke":
                # Efeito karaoke: divide por palavras e aplica tag {\k}
                words = text.split()
                total_time = end - start
                if len(words) > 0 and total_time > 0:
                    dur_per_word = total_time / len(words)
                    # {\k} espera centésimos de segundo
                    karaoke_text = ""
                    for w in words:
                        karaoke_text += f"{{\\k{int(dur_per_word*100)}}}{w} "
                    text = karaoke_text.strip()
            elif subtitle_effect == "capcut_shadow":
                # Aplicar efeito de sombra estilo CapCut
                # Se shadow_blur foi definido, usaremos a tag \blur para desfoque
                if shadow_blur is not None:
                    # Converter porcentagem de blur (0-1) para valor absoluto (0-5)
                    blur_value = round(shadow_blur * 5, 1)
                    if blur_value > 0:
                        text = f"{{\\blur{blur_value}}}{text}"

            f.write(
                f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}\n"
            )


# ------------------------------------------
# Presets de legendas estilizadas (CapCut-style)
# ------------------------------------------


def get_subtitle_preset(preset_name: str) -> dict:
    """Retorna configurações de estilo para presets populares do CapCut."""
    presets = {
        "neon": {
            "font": "Arial Black",
            "size": 48,
            "color": "&H00FF00FF&",  # Rosa neon
            "outline_color": "&H00FFFFFF&",  # Branco
            "outline": 3,
            "shadow": 0,
            "alignment": 2,
            "subtitle_effect": "glow",
        },
        "glow": {
            "font": "Arial",
            "size": 44,
            "color": "&H00FFFFFF&",  # Branco
            "outline_color": "&H0000FFFF&",  # Amarelo
            "outline": 4,
            "shadow": 2,
            "alignment": 2,
            "subtitle_effect": "glow",
        },
        "shadow_bold": {
            "font": "Arial Black",
            "size": 52,
            "color": "&H00FFFFFF&",  # Branco
            "outline_color": "&H00000000&",  # Preto
            "outline": 2,
            "shadow": 4,
            "alignment": 2,
            "subtitle_effect": "shadow",
        },
        "outline_thick": {
            "font": "Impact",
            "size": 56,
            "color": "&H0000FFFF&",  # Amarelo
            "outline_color": "&H00000000&",  # Preto
            "outline": 6,
            "shadow": 1,
            "alignment": 2,
            "subtitle_effect": "none",
        },
        "retro_3d": {
            "font": "Arial Black",
            "size": 48,
            "color": "&H00FF8080&",  # Rosa claro
            "outline_color": "&H00800080&",  # Roxo escuro
            "outline": 3,
            "shadow": 3,
            "alignment": 2,
            "subtitle_effect": "3d",
        },
        "minimal": {
            "font": "Arial",
            "size": 36,
            "color": "&H00FFFFFF&",  # Branco
            "outline_color": "&H80000000&",  # Preto semi-transparente
            "outline": 1,
            "shadow": 1,
            "alignment": 2,
            "subtitle_effect": "none",
        },
        "gaming": {
            "font": "Arial Black",
            "size": 50,
            "color": "&H0000FF00&",  # Verde
            "outline_color": "&H00000000&",  # Preto
            "outline": 4,
            "shadow": 2,
            "alignment": 2,
            "subtitle_effect": "gaming",
        },
        "cinema": {
            "font": "Times New Roman",
            "size": 40,
            "color": "&H00FFFFFF&",  # Branco
            "outline_color": "&H00000000&",  # Preto
            "outline": 2,
            "shadow": 2,
            "alignment": 2,
            "margin_v": 80,
            "subtitle_effect": "fade_in",
        },
        "capcut_shadow": {
            "font": "Arial",
            "size": 42,
            "color": "&H00FFFFFF&",  # Branco
            "outline_color": "&H00000000&",  # Preto
            "outline": 0,
            "shadow": 3,
            "alignment": 2,
            "shadow_opacity": 0.9,  # Opacidade 90%
            "shadow_blur": 0.23,  # Desfoque 23%
            "shadow_distance": 10,  # Distância 10px
            "shadow_angle": -78,  # Ângulo -78°
            "subtitle_effect": "capcut_shadow",
        },
    }

    return presets.get(preset_name, presets["minimal"])


def generate_ass_file_with_preset(
    segments: List[Tuple[float, float, str]],
    out_path: str,
    preset: str = "minimal",
    playres_x: int = 1920,
    playres_y: int = 1080,
) -> None:
    """Gera arquivo ASS usando preset estilizado."""
    config = get_subtitle_preset(preset)

    # Configurar parâmetros avançados de sombra se disponíveis
    shadow_opacity = config.get("shadow_opacity")
    shadow_blur = config.get("shadow_blur")
    shadow_distance = config.get("shadow_distance")
    shadow_angle = config.get("shadow_angle")

    generate_ass_file(
        segments=segments,
        out_path=out_path,
        font=config["font"],
        size=config["size"],
        color=config["color"],
        outline_color=config["outline_color"],
        outline=config["outline"],
        shadow=config["shadow"],
        alignment=config["alignment"],
        playres_x=playres_x,
        playres_y=playres_y,
        margin_v=config.get("margin_v", 40),
        subtitle_effect=config["subtitle_effect"],
        shadow_opacity=shadow_opacity,
        shadow_blur=shadow_blur,
        shadow_distance=shadow_distance,
        shadow_angle=shadow_angle,
    )


# ------------------------------------------
# Utilitário de formatação de tempo SRT
# ------------------------------------------


def format_time_srt(seconds: float) -> str:
    """Formata tempo em segundos para formato SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds % 1) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
