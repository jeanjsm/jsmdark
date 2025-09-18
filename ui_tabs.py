# ui_tabs.py
from typing import Optional, Tuple
import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QFileDialog,
    QListWidget,
)
from PySide6.QtCore import Signal, QObject

# Named constants for magic numbers
MIN_WIDTH = 320
MAX_WIDTH = 3840
MIN_HEIGHT = 240
MAX_HEIGHT = 2160
MIN_FPS = 24
MAX_FPS = 60
MIN_CRF = 0
MAX_CRF = 51
MIN_GPU_QUALITY = 1
MAX_GPU_QUALITY = 51
MIN_THREADS = 0
MAX_THREADS = 32
MIN_IMAGE_SEGMENT_DURATION = 0.5
MAX_IMAGE_SEGMENT_DURATION = 60.0
MIN_VIGNETTE_INTENSITY = 0.0
MAX_VIGNETTE_INTENSITY = 1.0
MIN_BG_MUSIC_VOLUME = 0.0
MAX_BG_MUSIC_VOLUME = 1.0
MIN_SILENCE_THRESHOLD = -60
MAX_SILENCE_THRESHOLD = -20
MIN_SILENCE_DURATION = 0.1
MAX_SILENCE_DURATION = 2.0
MIN_LOGO_SCALE = 0.05
MAX_LOGO_SCALE = 1.0
MIN_LOGO_OFFSET = 0
MAX_LOGO_OFFSET = 2000
MIN_OVERLAY_OPACITY = 0.1
MAX_OVERLAY_OPACITY = 1.0
MIN_CHROMA_SCALE = 0.1
MAX_CHROMA_SCALE = 2.0
MIN_CHROMA_START = 0
MAX_CHROMA_START = 6000
MIN_SUBTITLE_FONT_SIZE = 10
MAX_SUBTITLE_FONT_SIZE = 150


class FileBrowseWidget(QWidget):
    """Reusable widget for a text field with a 'Browse' button.

    Args:
        placeholder (str): Placeholder text for the line edit.
        browse_mode (str): 'file' or 'folder'.
        file_filter (str): File filter for dialog.
    """

    textChanged = Signal(str)

    def __init__(
        self, placeholder: str = "", browse_mode: str = "file", file_filter: str = "Todos (*.*)"
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        self.line_edit.textChanged.connect(self.textChanged)

        self.browse_button = QPushButton("Procurar...")

        layout.addWidget(self.line_edit)
        layout.addWidget(self.browse_button)

        if browse_mode == "file":
            self.browse_button.clicked.connect(lambda: self._browse_file(file_filter))
        else:
            self.browse_button.clicked.connect(self._browse_folder)

    def _browse_file(self, file_filter: str) -> None:
        """Open file dialog and set selected file path."""
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo", "", file_filter)
            if path:
                self.line_edit.setText(path)
        except Exception as exc:
            logging.error(f"Error browsing file: {exc}")

    def _browse_folder(self) -> None:
        """Open folder dialog and set selected folder path."""
        try:
            path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
            if path:
                self.line_edit.setText(path)
        except Exception as exc:
            logging.error(f"Error browsing folder: {exc}")

    def text(self) -> str:
        """Get the current text value."""
        return self.line_edit.text()

    def setText(self, text: str) -> None:
        """Set the text value."""
        self.line_edit.setText(text)


class BasicTab(QWidget):
    """Tab for basic settings (Files and Mode)."""

    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        layout.setSpacing(15)

        self.narration_path = FileBrowseWidget(
            "Arquivo de narração (.mp3, .wav)", "file", "Áudios (*.mp3 *.wav)"
        )
        self.videos_folder = FileBrowseWidget("Pasta com vídeos ou imagens", "folder")
        self.output_folder = FileBrowseWidget(
            "Pasta onde o vídeo final será salvo", "folder"
        )
        self.video_mode = QComboBox()
        self.video_mode.addItems(["videos", "images"])
        self.seed = QSpinBox()
        self.seed.setRange(-1, 99999)
        self.seed.setSpecialValueText("Aleatório")
        self.shuffle = QCheckBox("Randomizar ordem dos vídeos/imagens")

        layout.addRow("Narração:", self.narration_path)
        layout.addRow("Pasta de Mídia:", self.videos_folder)
        layout.addRow("Pasta de Saída:", self.output_folder)
        layout.addRow("Modo de Mídia:", self.video_mode)
        layout.addRow("Seed:", self.seed)
        layout.addRow(self.shuffle)


class VideoTab(QWidget):
    """Tab for video settings, quality, effects, etc."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        # Resolução e FPS
        res_group = QGroupBox("Resolução e FPS")
        res_layout = QFormLayout(res_group)
        self.resolution_preset = QComboBox()
        self.resolution_preset.addItems(
            ["horizontal_1080p", "horizontal_720p", "vertical_1080p", "custom"]
        )
        self.width = QSpinBox()
        self.width.setRange(MIN_WIDTH, MAX_WIDTH)
        self.height = QSpinBox()
        self.height.setRange(MIN_HEIGHT, MAX_HEIGHT)
        self.fps = QSpinBox()
        self.fps.setRange(MIN_FPS, MAX_FPS)
        res_layout.addRow("Preset:", self.resolution_preset)
        res_layout.addRow("Largura:", self.width)
        res_layout.addRow("Altura:", self.height)
        res_layout.addRow("FPS:", self.fps)
        layout.addWidget(res_group)

        # Encoder
        enc_group = QGroupBox("Encoder")
        enc_layout = QFormLayout(enc_group)
        self.encoder = QComboBox()
        self.encoder.addItems(["libx264", "h264_nvenc", "h264_amf", "h264_qsv"])
        self.performance_profile = QComboBox()
        self.performance_profile.addItems(["quality", "balanced", "speed"])
        self.crf = QSpinBox()
        self.crf.setRange(MIN_CRF, MAX_CRF)
        self.gpu_quality = QSpinBox()
        self.gpu_quality.setRange(MIN_GPU_QUALITY, MAX_GPU_QUALITY)
        self.preset = QComboBox()
        self.preset.addItems(["ultrafast", "medium", "veryslow"])
        self.threads = QSpinBox()
        self.threads.setRange(MIN_THREADS, MAX_THREADS)
        self.threads.setSpecialValueText("Auto")
        enc_layout.addRow("Encoder:", self.encoder)
        enc_layout.addRow("Perfil:", self.performance_profile)
        enc_layout.addRow("CRF (CPU):", self.crf)
        enc_layout.addRow("Qualidade (GPU):", self.gpu_quality)
        enc_layout.addRow("Preset:", self.preset)
        enc_layout.addRow("Threads:", self.threads)
        layout.addWidget(enc_group)

        # Modo Imagens
        img_group = QGroupBox("Modo de Imagens")
        img_layout = QFormLayout(img_group)
        self.image_segment_duration = QDoubleSpinBox()
        self.image_segment_duration.setRange(MIN_IMAGE_SEGMENT_DURATION, MAX_IMAGE_SEGMENT_DURATION)
        self.transition_type = QComboBox()
        self.transition_type.addItems(["none", "fade", "random"])
        img_layout.addRow("Duração por imagem (s):", self.image_segment_duration)
        img_layout.addRow("Transição:", self.transition_type)
        layout.addWidget(img_group)

        # Efeitos Visuais
        fx_group = QGroupBox("Efeitos Visuais")
        fx_layout = QFormLayout(fx_group)
        self.cinematic_preset = QComboBox()
        self.cinematic_preset.addItems(
            ["nenhum", "warm", "cold", "vintage", "cinematic"]
        )
        self.custom_lut_path = FileBrowseWidget(
            "Caminho para LUT personalizado", "file", "LUTs (*.cube)"
        )
        self.enable_vignette = QCheckBox("Habilitar vinheta")
        self.vignette_intensity = QDoubleSpinBox()
        self.vignette_intensity.setRange(MIN_VIGNETTE_INTENSITY, MAX_VIGNETTE_INTENSITY)
        self.enable_curves = QCheckBox("Habilitar curvas personalizadas")
        self.custom_curves = QLineEdit()
        self.custom_curves.setPlaceholderText("Ex: 'r=.../g=.../b=...'")
        fx_layout.addRow("Preset Cinematográfico:", self.cinematic_preset)
        fx_layout.addRow("LUT Personalizado:", self.custom_lut_path)
        fx_layout.addRow(self.enable_vignette)
        fx_layout.addRow("Intensidade da Vinheta:", self.vignette_intensity)
        fx_layout.addRow(self.enable_curves)
        fx_layout.addRow("Curvas:", self.custom_curves)
        layout.addWidget(fx_group)

        # Áudio
        audio_group = QGroupBox("Áudio")
        audio_layout = QFormLayout(audio_group)
        self.background_music = FileBrowseWidget(
            "Música de fundo (opcional)", "file", "Áudios (*.mp3 *.wav)"
        )
        self.background_music_volume = QDoubleSpinBox()
        self.background_music_volume.setRange(MIN_BG_MUSIC_VOLUME, MAX_BG_MUSIC_VOLUME)
        self.remove_silence = QCheckBox("Remover silêncio da narração")
        self.silence_threshold = QSpinBox()
        self.silence_threshold.setRange(MIN_SILENCE_THRESHOLD, MAX_SILENCE_THRESHOLD)
        self.silence_duration = QDoubleSpinBox()
        self.silence_duration.setRange(MIN_SILENCE_DURATION, MAX_SILENCE_DURATION)
        audio_layout.addRow("Música de Fundo:", self.background_music)
        audio_layout.addRow("Volume da Música:", self.background_music_volume)
        audio_layout.addRow(self.remove_silence)
        audio_layout.addRow("Limiar de Silêncio (dB):", self.silence_threshold)
        audio_layout.addRow("Duração Mínima Silêncio (s):", self.silence_duration)
        layout.addWidget(audio_group)

        # Abertura e Encerramento
        open_end_group = QGroupBox("Abertura e Encerramento")
        open_end_layout = QFormLayout(open_end_group)
        self.opening_video_paths_widget = (
            QListWidget()
        )  # Widget para exibir, não para dados
        self.add_opening_button = QPushButton("Adicionar Vídeo de Abertura")
        self.remove_opening_button = QPushButton("Remover Selecionado")
        self.ending_video_path = FileBrowseWidget(
            "Vídeo de encerramento (opcional)", "file", "Vídeos (*.mp4 *.mov)"
        )
        open_end_layout.addRow("Vídeos de Abertura:", self.opening_video_paths_widget)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.add_opening_button)
        btn_layout.addWidget(self.remove_opening_button)
        open_end_layout.addRow(btn_layout)
        open_end_layout.addRow("Vídeo de Encerramento:", self.ending_video_path)
        layout.addWidget(open_end_group)

        layout.addStretch()

        # Atualização automática de width/height ao mudar o preset de resolução
        self.resolution_preset.currentTextChanged.connect(self._update_resolution)
        self._update_resolution(self.resolution_preset.currentText())

    def _update_resolution(self, preset):
        presets = {
            "horizontal_1080p": (1920, 1080),
            "horizontal_720p": (1280, 720),
            "vertical_1080p": (1080, 1920),
            "custom": (self.width.value(), self.height.value()),
        }
        w, h = presets.get(preset, (1920, 1080))
        self.width.setValue(w)
        self.height.setValue(h)


class ChromaItemWidget(QGroupBox):
    """Widget for configuring a single Chroma Key file."""

    remove_clicked = Signal(QObject)

    def __init__(self, index: int) -> None:
        super().__init__(f"Chroma Key #{index + 1}")

        layout = QFormLayout(self)

        self.path = FileBrowseWidget(
            "Arquivo de vídeo (.mp4)", "file", "Vídeos (*.mp4)"
        )
        self.scale = QDoubleSpinBox()
        self.scale.setRange(MIN_CHROMA_SCALE, MAX_CHROMA_SCALE)
        self.scale.setSingleStep(0.1)
        self.position = QComboBox()
        self.position.addItems(
            [
                "bottom_center",
                "center",
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
            ]
        )
        self.start = QDoubleSpinBox()
        self.start.setRange(MIN_CHROMA_START, MAX_CHROMA_START)
        self.start.setSingleStep(1.0)
        self.remove_button = QPushButton("Remover este Chroma")

        layout.addRow("Arquivo:", self.path)
        layout.addRow("Escala:", self.scale)
        layout.addRow("Posição:", self.position)
        layout.addRow("Iniciar em (s):", self.start)
        layout.addRow(self.remove_button)

        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self))


class OverlayTab(QWidget):
    """Tab for configuring Logo, Video Overlay, and Chroma Keys."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        # Logo (sem alterações)
        logo_group = QGroupBox("Logo")
        logo_layout = QFormLayout(logo_group)
        self.logo = FileBrowseWidget(
            "Arquivo de logo (.png)", "file", "Imagens (*.png)"
        )
        self.logo_scale = QDoubleSpinBox()
        self.logo_scale.setRange(MIN_LOGO_SCALE, MAX_LOGO_SCALE)
        self.logo_scale.setSingleStep(0.05)
        self.logo_position = QComboBox()
        self.logo_position.addItems(
            [
                "top_right",
                "top_left",
                "bottom_right",
                "bottom_left",
                "center",
                "top_center",
                "bottom_center",
            ]
        )
        self.logo_x = QSpinBox()
        self.logo_x.setRange(MIN_LOGO_OFFSET, MAX_LOGO_OFFSET)
        self.logo_y = QSpinBox()
        self.logo_y.setRange(MIN_LOGO_OFFSET, MAX_LOGO_OFFSET)
        logo_layout.addRow("Arquivo:", self.logo)
        logo_layout.addRow("Escala:", self.logo_scale)
        logo_layout.addRow("Posição:", self.logo_position)
        logo_layout.addRow("Offset X:", self.logo_x)
        logo_layout.addRow("Offset Y:", self.logo_y)
        layout.addWidget(logo_group)

        # Overlay de Vídeo (sem alterações)
        overlay_group = QGroupBox("Overlay de Vídeo")
        overlay_layout = QFormLayout(overlay_group)
        self.overlay = FileBrowseWidget(
            "Arquivo de overlay (.mp4)", "file", "Vídeos (*.mp4)"
        )
        self.overlay_opacity = QDoubleSpinBox()
        self.overlay_opacity.setRange(MIN_OVERLAY_OPACITY, MAX_OVERLAY_OPACITY)
        self.overlay_opacity.setSingleStep(0.1)
        overlay_layout.addRow("Arquivo:", self.overlay)
        overlay_layout.addRow("Opacidade:", self.overlay_opacity)
        layout.addWidget(overlay_group)

        # Chroma Keys (MODIFICADO)
        self.chroma_group = QGroupBox("Lista de Chroma Keys")
        main_chroma_layout = QVBoxLayout(self.chroma_group)

        # Layout para conter os widgets de chroma dinâmicos
        self.chroma_list_layout = QVBoxLayout()

        self.add_chroma_btn = QPushButton("Adicionar Chroma Key")

        main_chroma_layout.addLayout(self.chroma_list_layout)
        main_chroma_layout.addWidget(self.add_chroma_btn)
        layout.addWidget(self.chroma_group)

        layout.addStretch()


class SubtitleTab(QWidget):
    """Tab for all subtitle settings."""

    def __init__(self) -> None:
        super().__init__()
        # CORREÇÃO: Usar QVBoxLayout como layout principal para suportar addStretch()
        layout = QVBoxLayout(self)

        self.enable_subtitles = QCheckBox("Habilitar legendas automáticas")
        layout.addWidget(self.enable_subtitles)

        # Presets
        preset_group = QGroupBox("Presets Estilizados")
        preset_layout = QFormLayout(preset_group)
        self.subtitle_preset = QComboBox()
        self.subtitle_preset.addItems(
            [
                "personalizado",
                "neon",
                "glow",
                "shadow_bold",
                "outline_thick",
                "retro_3d",
                "minimal",
                "gaming",
                "cinema",
                "capcut_shadow",
            ]
        )
        preset_layout.addRow("Preset:", self.subtitle_preset)
        layout.addWidget(preset_group)

        # Configurações
        sub_group = QGroupBox("Configurações de Legendas")
        sub_layout = QFormLayout(sub_group)
        self.subtitle_font_size = QSpinBox()
        self.subtitle_font_size.setRange(MIN_SUBTITLE_FONT_SIZE, MAX_SUBTITLE_FONT_SIZE)
        self.subtitle_color = QComboBox()
        self.subtitle_color.addItems(
            ["white", "yellow", "black", "red", "green", "blue"]
        )
        self.subtitle_position = QComboBox()
        self.subtitle_position.addItems(
            [
                "bottom_center",
                "center",
                "top_center",
                "top_left",
                "top_right",
                "bottom_left",
                "bottom_right",
            ]
        )
        self.subtitle_font = FileBrowseWidget(
            "Fonte da legenda (.ttf, .otf)", "file", "Fontes (*.ttf *.otf)"
        )
        self.words_per_subtitle = QSpinBox()
        self.words_per_subtitle.setRange(1, 20)
        self.vosk_model_path = FileBrowseWidget("Pasta do modelo Vosk", "folder")
        self.subtitle_effect = QComboBox()
        self.subtitle_effect.addItems(
            ["none", "fade_in", "fill_bar", "karaoke", "capcut_shadow"]
        )
        sub_layout.addRow("Tamanho da Fonte:", self.subtitle_font_size)
        sub_layout.addRow("Cor:", self.subtitle_color)
        sub_layout.addRow("Posição:", self.subtitle_position)
        sub_layout.addRow("Arquivo da Fonte:", self.subtitle_font)
        sub_layout.addRow("Palavras por Legenda:", self.words_per_subtitle)
        sub_layout.addRow("Modelo Vosk:", self.vosk_model_path)
        sub_layout.addRow("Efeito:", self.subtitle_effect)
        layout.addWidget(sub_group)

        # Estilo
        style_group = QGroupBox("Estilo (Contorno e Sombra)")
        style_layout = QFormLayout(style_group)
        self.subtitle_outline_color = QComboBox()
        self.subtitle_outline_color.addItems(
            ["black", "white", "yellow", "red", "green", "blue"]
        )
        self.subtitle_outline_width = QSpinBox()
        self.subtitle_outline_width.setRange(0, 10)
        self.subtitle_shadow_color = QComboBox()
        self.subtitle_shadow_color.addItems(
            ["black", "white", "yellow", "red", "green", "blue"]
        )
        self.subtitle_shadow_x = QSpinBox()
        self.subtitle_shadow_x.setRange(-10, 10)
        self.subtitle_shadow_y = QSpinBox()
        self.subtitle_shadow_y.setRange(-10, 10)
        style_layout.addRow("Cor do Contorno:", self.subtitle_outline_color)
        style_layout.addRow("Largura do Contorno:", self.subtitle_outline_width)
        style_layout.addRow("Cor da Sombra:", self.subtitle_shadow_color)
        style_layout.addRow("Sombra X:", self.subtitle_shadow_x)
        style_layout.addRow("Sombra Y:", self.subtitle_shadow_y)
        layout.addWidget(style_group)

        # Conecta o evento de mudança de preset para atualizar os campos
        self.subtitle_preset.currentTextChanged.connect(self._update_subtitle_fields)

        # Conecta os sinais dos campos para mudar para modo personalizado quando alterados
        self._connect_field_signals()

        # CORREÇÃO: addStretch() agora funciona no QVBoxLayout
        layout.addStretch()

    def _update_subtitle_fields(self, preset_name):
        """
        Atualiza os campos de legendas com base no preset selecionado.
        Se o preset for 'personalizado', mantém os valores atuais.
        """
        if preset_name == "personalizado":
            return

        # Importa a função get_subtitle_preset para obter as configurações do preset
        from subtitle_utils import get_subtitle_preset

        # Temporariamente desconecta os sinais para evitar loops
        self._disconnect_field_signals()

        try:
            # Obtem as configurações do preset selecionado
            config = get_subtitle_preset(preset_name)

            # Atualiza os campos da interface com base no preset
            if "size" in config:
                self.subtitle_font_size.setValue(config["size"])

            if "color" in config:
                # Converte a cor do formato ASS para o nome da cor
                color_mapping = {
                    "&H00FFFFFF&": "white",
                    "&H0000FFFF&": "yellow",
                    "&H00000000&": "black",
                    "&H000000FF&": "red",
                    "&H0000FF00&": "green",
                    "&H00FF0000&": "blue",
                    "&H00FF00FF&": "pink",
                }
                color_name = color_mapping.get(config["color"], "white")
                index = self.subtitle_color.findText(color_name)
                if index >= 0:
                    self.subtitle_color.setCurrentIndex(index)

            if "alignment" in config:
                # Mapeia o alinhamento ASS para o posicionamento da interface
                alignment_mapping = {
                    2: "bottom_center",
                    5: "center",
                    8: "top_center",
                    7: "top_left",
                    9: "top_right",
                    1: "bottom_left",
                    3: "bottom_right",
                }
                position = alignment_mapping.get(config["alignment"], "bottom_center")
                index = self.subtitle_position.findText(position)
                if index >= 0:
                    self.subtitle_position.setCurrentIndex(index)

            if "outline" in config:
                self.subtitle_outline_width.setValue(config["outline"])

            if "shadow" in config:
                # Calcula os valores X e Y com base na configuração de sombra
                shadow_x = config.get("shadow_distance", 0)
                shadow_y = config.get("shadow_distance", 0)

                # Se há informações de ângulo e distância, calcula X e Y
                if "shadow_angle" in config and "shadow_distance" in config:
                    import math

                    angle_rad = math.radians(config["shadow_angle"])
                    shadow_x = round(math.cos(angle_rad) * config["shadow_distance"])
                    shadow_y = round(math.sin(angle_rad) * config["shadow_distance"])
                else:
                    shadow_x = shadow_y = config["shadow"]

                self.subtitle_shadow_x.setValue(shadow_x)
                self.subtitle_shadow_y.setValue(shadow_y)

            if "subtitle_effect" in config:
                index = self.subtitle_effect.findText(config["subtitle_effect"])
                if index >= 0:
                    self.subtitle_effect.setCurrentIndex(index)
        finally:
            # Reconecta os sinais
            self._connect_field_signals()

    def _set_to_custom(self):
        """Define o preset como personalizado quando um campo é alterado manualmente."""
        if self.subtitle_preset.currentText() != "personalizado":
            # Temporariamente desconecta o sinal para evitar loops
            self.subtitle_preset.blockSignals(True)

            # Configura o preset como personalizado
            index = self.subtitle_preset.findText("personalizado")
            if index >= 0:
                self.subtitle_preset.setCurrentIndex(index)

            # Reconecta o sinal
            self.subtitle_preset.blockSignals(False)

    def _connect_field_signals(self):
        """Conecta os sinais de todos os campos de legendas para detectar alterações manuais."""
        self.subtitle_font_size.valueChanged.connect(self._set_to_custom)
        self.subtitle_color.currentTextChanged.connect(self._set_to_custom)
        self.subtitle_position.currentTextChanged.connect(self._set_to_custom)
        self.subtitle_font.textChanged.connect(self._set_to_custom)
        self.subtitle_outline_color.currentTextChanged.connect(self._set_to_custom)
        self.subtitle_outline_width.valueChanged.connect(self._set_to_custom)
        self.subtitle_shadow_color.currentTextChanged.connect(self._set_to_custom)
        self.subtitle_shadow_x.valueChanged.connect(self._set_to_custom)
        self.subtitle_shadow_y.valueChanged.connect(self._set_to_custom)
        self.subtitle_effect.currentTextChanged.connect(self._set_to_custom)

    def _disconnect_field_signals(self):
        """Desconecta os sinais de todos os campos de legendas."""
        self.subtitle_font_size.blockSignals(True)
        self.subtitle_color.blockSignals(True)
        self.subtitle_position.blockSignals(True)
        self.subtitle_font.blockSignals(True)
        self.subtitle_outline_color.blockSignals(True)
        self.subtitle_outline_width.blockSignals(True)
        self.subtitle_shadow_color.blockSignals(True)
        self.subtitle_shadow_x.blockSignals(True)
        self.subtitle_shadow_y.blockSignals(True)
        self.subtitle_effect.blockSignals(True)
