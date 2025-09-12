# ui_tabs.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QFormLayout,
    QGroupBox, QFileDialog, QListWidget
)
from PySide6.QtCore import Signal, QObject


class FileBrowseWidget(QWidget):
    """Widget reutilizável para um campo de texto com um botão 'Procurar'."""
    textChanged = Signal(str)

    def __init__(self, placeholder="", browse_mode="file", file_filter="Todos (*.*)"):
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
        else:  # folder
            self.browse_button.clicked.connect(self._browse_folder)

    def _browse_file(self, file_filter):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo", "", file_filter)
        if path: self.line_edit.setText(path)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if path: self.line_edit.setText(path)

    def text(self):
        return self.line_edit.text()

    def setText(self, text):
        self.line_edit.setText(text)


# (O resto do arquivo ui_tabs.py permanece exatamente o mesmo)
# ...
class BasicTab(QWidget):
    """Aba de configurações básicas (Arquivos e Modo)."""

    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)
        layout.setSpacing(15)

        self.narration_path = FileBrowseWidget("Arquivo de narração (.mp3, .wav)", "file", "Áudios (*.mp3 *.wav)")
        self.videos_folder = FileBrowseWidget("Pasta com vídeos ou imagens", "folder")
        self.output_folder = FileBrowseWidget("Pasta onde o vídeo final será salvo", "folder")
        self.video_mode = QComboBox();
        self.video_mode.addItems(["videos", "images"])
        self.seed = QSpinBox();
        self.seed.setRange(-1, 99999);
        self.seed.setSpecialValueText("Aleatório")
        self.shuffle = QCheckBox("Randomizar ordem dos vídeos/imagens")

        layout.addRow("Narração:", self.narration_path)
        layout.addRow("Pasta de Mídia:", self.videos_folder)
        layout.addRow("Pasta de Saída:", self.output_folder)
        layout.addRow("Modo de Mídia:", self.video_mode)
        layout.addRow("Seed:", self.seed)
        layout.addRow(self.shuffle)


class VideoTab(QWidget):
    """Aba de configurações de Vídeo, Qualidade, Efeitos, etc."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Resolução e FPS
        res_group = QGroupBox("Resolução e FPS")
        res_layout = QFormLayout(res_group)
        self.resolution_preset = QComboBox();
        self.resolution_preset.addItems(["horizontal_1080p", "horizontal_720p", "vertical_1080p", "custom"])
        self.width = QSpinBox();
        self.width.setRange(320, 3840)
        self.height = QSpinBox();
        self.height.setRange(240, 2160)
        self.fps = QSpinBox();
        self.fps.setRange(24, 60)
        res_layout.addRow("Preset:", self.resolution_preset)
        res_layout.addRow("Largura:", self.width)
        res_layout.addRow("Altura:", self.height)
        res_layout.addRow("FPS:", self.fps)
        layout.addWidget(res_group)

        # Encoder
        enc_group = QGroupBox("Encoder")
        enc_layout = QFormLayout(enc_group)
        self.encoder = QComboBox();
        self.encoder.addItems(["libx264", "h264_nvenc", "h264_amf", "h264_qsv"])
        self.performance_profile = QComboBox();
        self.performance_profile.addItems(["quality", "balanced", "speed"])
        self.crf = QSpinBox();
        self.crf.setRange(0, 51)
        self.gpu_quality = QSpinBox();
        self.gpu_quality.setRange(1, 51)
        self.preset = QComboBox();
        self.preset.addItems(["ultrafast", "medium", "veryslow"])
        self.threads = QSpinBox();
        self.threads.setRange(0, 32);
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
        self.image_segment_duration = QDoubleSpinBox();
        self.image_segment_duration.setRange(0.5, 60.0)
        self.transition_type = QComboBox();
        self.transition_type.addItems(["none", "fade", "random"])
        img_layout.addRow("Duração por imagem (s):", self.image_segment_duration)
        img_layout.addRow("Transição:", self.transition_type)
        layout.addWidget(img_group)

        # Efeitos Visuais
        fx_group = QGroupBox("Efeitos Visuais")
        fx_layout = QFormLayout(fx_group)
        self.cinematic_preset = QComboBox();
        self.cinematic_preset.addItems(["nenhum", "warm", "cold", "vintage", "cinematic"])
        self.custom_lut_path = FileBrowseWidget("Caminho para LUT personalizado", "file", "LUTs (*.cube)")
        self.enable_vignette = QCheckBox("Habilitar vinheta")
        self.vignette_intensity = QDoubleSpinBox();
        self.vignette_intensity.setRange(0.0, 1.0)
        self.enable_curves = QCheckBox("Habilitar curvas personalizadas")
        self.custom_curves = QLineEdit();
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
        self.background_music = FileBrowseWidget("Música de fundo (opcional)", "file", "Áudios (*.mp3 *.wav)")
        self.background_music_volume = QDoubleSpinBox();
        self.background_music_volume.setRange(0.0, 1.0)
        self.remove_silence = QCheckBox("Remover silêncio da narração")
        self.silence_threshold = QSpinBox();
        self.silence_threshold.setRange(-60, -20)
        self.silence_duration = QDoubleSpinBox();
        self.silence_duration.setRange(0.1, 2.0)
        audio_layout.addRow("Música de Fundo:", self.background_music)
        audio_layout.addRow("Volume da Música:", self.background_music_volume)
        audio_layout.addRow(self.remove_silence)
        audio_layout.addRow("Limiar de Silêncio (dB):", self.silence_threshold)
        audio_layout.addRow("Duração Mínima Silêncio (s):", self.silence_duration)
        layout.addWidget(audio_group)

        # Abertura e Encerramento
        open_end_group = QGroupBox("Abertura e Encerramento")
        open_end_layout = QFormLayout(open_end_group)
        self.opening_video_paths_widget = QListWidget()  # Widget para exibir, não para dados
        self.add_opening_button = QPushButton("Adicionar Vídeo de Abertura")
        self.remove_opening_button = QPushButton("Remover Selecionado")
        self.ending_video_path = FileBrowseWidget("Vídeo de encerramento (opcional)", "file", "Vídeos (*.mp4 *.mov)")
        open_end_layout.addRow("Vídeos de Abertura:", self.opening_video_paths_widget)
        btn_layout = QHBoxLayout();
        btn_layout.addWidget(self.add_opening_button);
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
            "custom": (self.width.value(), self.height.value())
        }
        w, h = presets.get(preset, (1920, 1080))
        self.width.setValue(w)
        self.height.setValue(h)


class ChromaItemWidget(QGroupBox):
    """Um widget para configurar um único arquivo de Chroma Key."""
    remove_clicked = Signal(QObject)

    def __init__(self, index: int):
        super().__init__(f"Chroma Key #{index + 1}")

        layout = QFormLayout(self)

        self.path = FileBrowseWidget("Arquivo de vídeo (.mp4)", "file", "Vídeos (*.mp4)")
        self.scale = QDoubleSpinBox();
        self.scale.setRange(0.1, 2.0);
        self.scale.setSingleStep(0.1)
        self.position = QComboBox();
        self.position.addItems(["bottom_center", "center", "top_left", "top_right", "bottom_left", "bottom_right"])
        self.start = QDoubleSpinBox();
        self.start.setRange(0, 6000);
        self.start.setSingleStep(1.0)
        self.remove_button = QPushButton("Remover este Chroma")

        layout.addRow("Arquivo:", self.path)
        layout.addRow("Escala:", self.scale)
        layout.addRow("Posição:", self.position)
        layout.addRow("Iniciar em (s):", self.start)
        layout.addRow(self.remove_button)

        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self))


# --- CLASSE OverlayTab MODIFICADA ---
class OverlayTab(QWidget):
    """Aba para configurar Logo, Overlay de vídeo e Chroma Keys."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # Logo (sem alterações)
        logo_group = QGroupBox("Logo")
        logo_layout = QFormLayout(logo_group)
        self.logo = FileBrowseWidget("Arquivo de logo (.png)", "file", "Imagens (*.png)")
        self.logo_scale = QDoubleSpinBox();
        self.logo_scale.setRange(0.05, 1.0);
        self.logo_scale.setSingleStep(0.05)
        self.logo_position = QComboBox();
        self.logo_position.addItems(
            ["top_right", "top_left", "bottom_right", "bottom_left", "center", "top_center", "bottom_center"])
        self.logo_x = QSpinBox();
        self.logo_x.setRange(0, 2000)
        self.logo_y = QSpinBox();
        self.logo_y.setRange(0, 2000)
        logo_layout.addRow("Arquivo:", self.logo)
        logo_layout.addRow("Escala:", self.logo_scale)
        logo_layout.addRow("Posição:", self.logo_position)
        logo_layout.addRow("Offset X:", self.logo_x)
        logo_layout.addRow("Offset Y:", self.logo_y)
        layout.addWidget(logo_group)

        # Overlay de Vídeo (sem alterações)
        overlay_group = QGroupBox("Overlay de Vídeo")
        overlay_layout = QFormLayout(overlay_group)
        self.overlay = FileBrowseWidget("Arquivo de overlay (.mp4)", "file", "Vídeos (*.mp4)")
        self.overlay_opacity = QDoubleSpinBox();
        self.overlay_opacity.setRange(0.1, 1.0);
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
    """Aba para todas as configurações de legendas."""

    def __init__(self):
        super().__init__()
        # CORREÇÃO: Usar QVBoxLayout como layout principal para suportar addStretch()
        layout = QVBoxLayout(self)

        self.enable_subtitles = QCheckBox("Habilitar legendas automáticas")
        layout.addWidget(self.enable_subtitles)

        # Presets
        preset_group = QGroupBox("Presets Estilizados")
        preset_layout = QFormLayout(preset_group)
        self.subtitle_preset = QComboBox();
        self.subtitle_preset.addItems(
            ["personalizado", "neon", "glow", "shadow_bold", "outline_thick", "retro_3d", "minimal", "gaming",
             "cinema"])
        preset_layout.addRow("Preset:", self.subtitle_preset)
        layout.addWidget(preset_group)

        # Configurações
        sub_group = QGroupBox("Configurações de Legendas")
        sub_layout = QFormLayout(sub_group)
        self.subtitle_font_size = QSpinBox();
        self.subtitle_font_size.setRange(10, 150)
        self.subtitle_color = QComboBox();
        self.subtitle_color.addItems(["white", "yellow", "black", "red", "green", "blue"])
        self.subtitle_position = QComboBox();
        self.subtitle_position.addItems(
            ["bottom_center", "center", "top_center", "top_left", "top_right", "bottom_left", "bottom_right"])
        self.subtitle_font = FileBrowseWidget("Fonte da legenda (.ttf, .otf)", "file", "Fontes (*.ttf *.otf)")
        self.words_per_subtitle = QSpinBox();
        self.words_per_subtitle.setRange(1, 20)
        self.vosk_model_path = FileBrowseWidget("Pasta do modelo Vosk", "folder")
        self.subtitle_effect = QComboBox();
        self.subtitle_effect.addItems(["none", "fade_in", "fill_bar", "karaoke"])
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
        self.subtitle_outline_color = QComboBox();
        self.subtitle_outline_color.addItems(["black", "white", "yellow", "red", "green", "blue"])
        self.subtitle_outline_width = QSpinBox();
        self.subtitle_outline_width.setRange(0, 10)
        self.subtitle_shadow_color = QComboBox();
        self.subtitle_shadow_color.addItems(["black", "white", "yellow", "red", "green", "blue"])
        self.subtitle_shadow_x = QSpinBox();
        self.subtitle_shadow_x.setRange(-10, 10)
        self.subtitle_shadow_y = QSpinBox();
        self.subtitle_shadow_y.setRange(-10, 10)
        style_layout.addRow("Cor do Contorno:", self.subtitle_outline_color)
        style_layout.addRow("Largura do Contorno:", self.subtitle_outline_width)
        style_layout.addRow("Cor da Sombra:", self.subtitle_shadow_color)
        style_layout.addRow("Sombra X:", self.subtitle_shadow_x)
        style_layout.addRow("Sombra Y:", self.subtitle_shadow_y)
        layout.addWidget(style_group)

        # CORREÇÃO: addStretch() agora funciona no QVBoxLayout
        layout.addStretch()
