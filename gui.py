#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QTabWidget, QFileDialog, QFormLayout,
    QGroupBox, QSlider, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QFont

import sys
import os
import json
from pathlib import Path
from video_from_narration import create_video_from_narration

class ProcessVideoThread(QThread):
    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            # Chamar a função de processamento
            result = create_video_from_narration(**self.params)
            self.finished.emit(True, f"Vídeo gerado com sucesso: {self.params['out_path']}")
        except Exception as e:
            self.finished.emit(False, f"Erro ao gerar vídeo: {str(e)}")


class VideoGeneratorGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Vídeos")
        self.setMinimumSize(900, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout(self.central_widget)

        # Criação das abas
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # Criação das diferentes abas
        basic_tab = QWidget()
        video_tab = QWidget()
        overlay_tab = QWidget()
        subtitle_tab = QWidget()
        effects_tab = QWidget()

        tabs.addTab(basic_tab, "Básico")
        tabs.addTab(video_tab, "Vídeo")
        tabs.addTab(overlay_tab, "Overlays")
        tabs.addTab(subtitle_tab, "Legendas")
        tabs.addTab(effects_tab, "Efeitos")

        # Configuração das abas
        self.setup_basic_tab(basic_tab)
        self.setup_video_tab(video_tab)
        self.setup_overlay_tab(overlay_tab)
        self.setup_subtitle_tab(subtitle_tab)
        self.setup_effects_tab(effects_tab)

        # Área de botões e progresso
        bottom_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        self.generate_button = QPushButton("Gerar Vídeo")
        self.generate_button.clicked.connect(self.generate_video)

        self.save_config_button = QPushButton("Salvar Configuração")
        self.save_config_button.clicked.connect(self.save_config)

        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.save_config_button)

        bottom_layout.addLayout(button_layout)
        main_layout.addLayout(bottom_layout)

        # Carregar configurações salvas
        self.load_config()

        # Conectar eventos para salvar config automaticamente quando os campos mudam
        self.connect_change_events()

    def setup_basic_tab(self, tab):
        layout = QFormLayout(tab)

        # Arquivo de narração
        self.narration_layout = QHBoxLayout()
        self.narration_input = QLineEdit()
        self.narration_input.setPlaceholderText("Selecione o arquivo de narração")
        self.narration_button = QPushButton("Procurar")
        self.narration_button.clicked.connect(lambda: self.browse_file(self.narration_input, "Áudio (*.mp3 *.wav)"))
        self.narration_layout.addWidget(self.narration_input)
        self.narration_layout.addWidget(self.narration_button)
        layout.addRow("Narração:", self.narration_layout)

        # Pasta de vídeos ou imagens
        self.videos_folder_layout = QHBoxLayout()
        self.videos_folder_input = QLineEdit()
        self.videos_folder_input.setPlaceholderText("Selecione a pasta de vídeos/imagens")
        self.videos_folder_button = QPushButton("Procurar")
        self.videos_folder_button.clicked.connect(lambda: self.browse_folder(self.videos_folder_input))
        self.videos_folder_layout.addWidget(self.videos_folder_input)
        self.videos_folder_layout.addWidget(self.videos_folder_button)
        layout.addRow("Pasta de vídeos/imagens:", self.videos_folder_layout)

        # Arquivo de saída
        self.output_layout = QHBoxLayout()
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Selecione o arquivo de saída")
        self.output_button = QPushButton("Procurar")
        self.output_button.clicked.connect(lambda: self.save_file(self.output_input, "Vídeo (*.mp4)"))
        self.output_layout.addWidget(self.output_input)
        self.output_layout.addWidget(self.output_button)
        layout.addRow("Arquivo de saída:", self.output_layout)

        # Modo de vídeo
        self.video_mode = QComboBox()
        self.video_mode.addItems(["videos", "images"])
        layout.addRow("Modo de vídeo:", self.video_mode)

        # Trilha sonora de fundo
        self.bg_music_layout = QHBoxLayout()
        self.bg_music_input = QLineEdit()
        self.bg_music_input.setPlaceholderText("Selecione o arquivo de música de fundo (opcional)")
        self.bg_music_button = QPushButton("Procurar")
        self.bg_music_button.clicked.connect(lambda: self.browse_file(self.bg_music_input, "Áudio (*.mp3 *.wav)"))
        self.bg_music_layout.addWidget(self.bg_music_input)
        self.bg_music_layout.addWidget(self.bg_music_button)
        layout.addRow("Música de fundo:", self.bg_music_layout)

        # Volume da música de fundo
        self.bg_music_volume = QDoubleSpinBox()
        self.bg_music_volume.setRange(0.0, 1.0)
        self.bg_music_volume.setValue(0.2)
        self.bg_music_volume.setSingleStep(0.05)
        layout.addRow("Volume da música:", self.bg_music_volume)

        # Seed
        self.seed = QSpinBox()
        self.seed.setRange(-1, 99999)
        self.seed.setValue(-1)
        self.seed.setSpecialValueText("Aleatório")
        layout.addRow("Seed:", self.seed)

        # Opções de remoção de silêncio
        self.remove_silence = QCheckBox("Remover silêncio")
        self.remove_silence.setChecked(True)
        layout.addRow("", self.remove_silence)

        silence_group = QGroupBox("Configurações de silêncio")
        silence_layout = QFormLayout(silence_group)

        self.silence_threshold = QSpinBox()
        self.silence_threshold.setRange(-60, -20)
        self.silence_threshold.setValue(-40)
        silence_layout.addRow("Limiar (dB):", self.silence_threshold)

        self.silence_duration = QDoubleSpinBox()
        self.silence_duration.setRange(0.1, 2.0)
        self.silence_duration.setValue(0.5)
        self.silence_duration.setSingleStep(0.1)
        silence_layout.addRow("Duração mínima (s):", self.silence_duration)

        layout.addRow("", silence_group)

        # Encerramento (opcional)
        self.ending_layout = QHBoxLayout()
        self.ending_input = QLineEdit()
        self.ending_input.setPlaceholderText("Selecione o vídeo de encerramento (opcional)")
        self.ending_button = QPushButton("Procurar")
        self.ending_button.clicked.connect(lambda: self.browse_file(self.ending_input, "Vídeo (*.mp4 *.mov *.avi)"))
        self.ending_layout.addWidget(self.ending_input)
        self.ending_layout.addWidget(self.ending_button)
        layout.addRow("Vídeo de encerramento:", self.ending_layout)

    def setup_video_tab(self, tab):
        layout = QFormLayout(tab)

        # Grupo de configurações de resolução
        resolution_group = QGroupBox("Resolução e FPS")
        resolution_layout = QFormLayout(resolution_group)

        # Preset de resolução
        self.resolution_preset = QComboBox()
        self.resolution_preset.addItems([
            "horizontal_480p", "horizontal_720p", "horizontal_1080p", "horizontal_2k",
            "vertical_480p", "vertical_720p", "vertical_1080p", "vertical_2k",
            "custom"
        ])
        self.resolution_preset.currentTextChanged.connect(self.update_resolution_preset)
        resolution_layout.addRow("Preset:", self.resolution_preset)

        # Largura e altura
        self.width = QSpinBox()
        self.width.setRange(320, 3840)
        self.width.setValue(1920)
        resolution_layout.addRow("Largura:", self.width)

        self.height = QSpinBox()
        self.height.setRange(240, 2160)
        self.height.setValue(1080)
        resolution_layout.addRow("Altura:", self.height)

        # FPS
        self.fps = QSpinBox()
        self.fps.setRange(24, 60)
        self.fps.setValue(30)
        resolution_layout.addRow("FPS:", self.fps)

        layout.addRow("", resolution_group)

        # Grupo de configurações de encoder
        encoder_group = QGroupBox("Configurações de Encoder")
        encoder_layout = QFormLayout(encoder_group)

        # Tipo de encoder
        self.encoder = QComboBox()
        self.encoder.addItems(["libx264", "h264_nvenc", "h264_amf", "h264_qsv"])
        encoder_layout.addRow("Encoder:", self.encoder)

        # Perfil de performance
        self.performance_profile = QComboBox()
        self.performance_profile.addItems(["quality", "balanced", "speed"])
        encoder_layout.addRow("Perfil:", self.performance_profile)

        # CRF / Qualidade
        self.crf = QSpinBox()
        self.crf.setRange(0, 51)
        self.crf.setValue(18)
        encoder_layout.addRow("CRF (CPU):", self.crf)

        self.gpu_quality = QSpinBox()
        self.gpu_quality.setRange(1, 51)
        self.gpu_quality.setValue(18)
        encoder_layout.addRow("Qualidade (GPU):", self.gpu_quality)

        # Preset de codificação
        self.preset = QComboBox()
        self.preset.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset.setCurrentText("medium")
        encoder_layout.addRow("Preset:", self.preset)

        # Threads
        self.threads = QSpinBox()
        self.threads.setRange(0, 32)
        self.threads.setValue(0)
        self.threads.setSpecialValueText("Auto")
        encoder_layout.addRow("Threads:", self.threads)

        layout.addRow("", encoder_group)

        # Configurações para modo de imagens
        images_group = QGroupBox("Modo de Imagens")
        images_layout = QFormLayout(images_group)

        self.image_segment_duration = QDoubleSpinBox()
        self.image_segment_duration.setRange(0.5, 15.0)
        self.image_segment_duration.setValue(6.0)
        self.image_segment_duration.setSingleStep(0.5)
        images_layout.addRow("Duração por imagem (s):", self.image_segment_duration)

        self.transition_type = QComboBox()
        self.transition_type.addItems(["none", "fade", "fadewhite", "zoomin", "smoothleft", "smoothright", "horzopen", "random"])
        images_layout.addRow("Transição:", self.transition_type)

        self.enable_ken_burns = QCheckBox("Habilitar efeito Ken Burns")
        images_layout.addRow("", self.enable_ken_burns)

        layout.addRow("", images_group)

    def setup_overlay_tab(self, tab):
        layout = QFormLayout(tab)

        # Grupo Logo
        logo_group = QGroupBox("Logo")
        logo_layout = QFormLayout(logo_group)

        # Arquivo de logo
        self.logo_layout = QHBoxLayout()
        self.logo_input = QLineEdit()
        self.logo_input.setPlaceholderText("Selecione o arquivo de logo (opcional)")
        self.logo_button = QPushButton("Procurar")
        self.logo_button.clicked.connect(lambda: self.browse_file(self.logo_input, "Imagens (*.png *.jpg)"))
        self.logo_layout.addWidget(self.logo_input)
        self.logo_layout.addWidget(self.logo_button)
        logo_layout.addRow("Arquivo:", self.logo_layout)

        # Escala da logo
        self.logo_scale = QDoubleSpinBox()
        self.logo_scale.setRange(0.05, 1.0)
        self.logo_scale.setValue(0.15)
        self.logo_scale.setSingleStep(0.05)
        logo_layout.addRow("Escala:", self.logo_scale)

        # Posição da logo
        self.logo_position = QComboBox()
        self.logo_position.addItems(["top_left", "top_center", "top_right",
                                     "bottom_left", "bottom_center", "bottom_right", "center"])
        self.logo_position.setCurrentText("top_right")
        logo_layout.addRow("Posição:", self.logo_position)

        # Coordenadas X, Y
        self.logo_x = QSpinBox()
        self.logo_x.setRange(0, 1000)
        self.logo_x.setValue(20)
        logo_layout.addRow("X:", self.logo_x)

        self.logo_y = QSpinBox()
        self.logo_y.setRange(0, 1000)
        self.logo_y.setValue(20)
        logo_layout.addRow("Y:", self.logo_y)

        layout.addRow("", logo_group)

        # Grupo Overlay
        overlay_group = QGroupBox("Overlay de Vídeo")
        overlay_layout = QFormLayout(overlay_group)

        # Arquivo de overlay
        self.overlay_layout = QHBoxLayout()
        self.overlay_input = QLineEdit()
        self.overlay_input.setPlaceholderText("Selecione o arquivo de overlay (opcional)")
        self.overlay_button = QPushButton("Procurar")
        self.overlay_button.clicked.connect(lambda: self.browse_file(self.overlay_input, "Vídeos (*.mp4)"))
        self.overlay_layout.addWidget(self.overlay_input)
        self.overlay_layout.addWidget(self.overlay_button)
        overlay_layout.addRow("Arquivo:", self.overlay_layout)

        # Opacidade do overlay
        self.overlay_opacity = QDoubleSpinBox()
        self.overlay_opacity.setRange(0.1, 1.0)
        self.overlay_opacity.setValue(0.3)
        self.overlay_opacity.setSingleStep(0.1)
        overlay_layout.addRow("Opacidade:", self.overlay_opacity)

        layout.addRow("", overlay_group)

        # Grupo Chroma Key List
        chroma_group = QGroupBox("Lista de Chroma Keys")
        chroma_layout = QVBoxLayout(chroma_group)

        # Lista de widgets para cada chroma
        self.chroma_widgets = []
        self.chroma_list_layout = QVBoxLayout()

        # Botões para adicionar/remover chromas
        btn_layout = QHBoxLayout()
        self.add_chroma_btn = QPushButton("Adicionar Chroma Key")
        self.add_chroma_btn.clicked.connect(self.add_chroma_widget)
        btn_layout.addWidget(self.add_chroma_btn)

        chroma_layout.addLayout(self.chroma_list_layout)
        chroma_layout.addLayout(btn_layout)

        layout.addRow("", chroma_group)

        # Adiciona um chroma inicial
        self.add_chroma_widget()

    def add_chroma_widget(self):
        # Cria grupo para este chroma
        idx = len(self.chroma_widgets)
        chroma_item_group = QGroupBox(f"Chroma #{idx+1}")
        chroma_item_layout = QFormLayout(chroma_item_group)

        # Arquivo de chroma
        chroma_file_layout = QHBoxLayout()
        chroma_input = QLineEdit()
        chroma_input.setPlaceholderText("Selecione o arquivo de chroma (opcional)")
        chroma_button = QPushButton("Procurar")
        chroma_button.clicked.connect(lambda: self.browse_file(chroma_input, "Vídeos (*.mp4)"))
        chroma_file_layout.addWidget(chroma_input)
        chroma_file_layout.addWidget(chroma_button)
        chroma_item_layout.addRow("Arquivo:", chroma_file_layout)

        # Escala do chroma
        chroma_scale = QDoubleSpinBox()
        chroma_scale.setRange(0.1, 2.0)
        chroma_scale.setValue(0.3)
        chroma_scale.setSingleStep(0.1)
        chroma_item_layout.addRow("Escala:", chroma_scale)

        # Posição do chroma
        chroma_position = QComboBox()
        chroma_position.addItems(["top_left", "top_center", "top_right",
                                  "bottom_left", "bottom_center", "bottom_right", "center"])
        chroma_position.setCurrentText("bottom_center")
        chroma_item_layout.addRow("Posição:", chroma_position)

        # Tempo de início
        chroma_start = QDoubleSpinBox()
        chroma_start.setRange(0, 600)
        chroma_start.setValue(30)
        chroma_start.setSingleStep(1)
        chroma_item_layout.addRow("Iniciar em (s):", chroma_start)

        # Botão para remover este chroma
        remove_btn_layout = QHBoxLayout()
        remove_btn = QPushButton("Remover")
        remove_btn.clicked.connect(lambda: self.remove_chroma_widget(chroma_item_group, idx))
        remove_btn_layout.addWidget(remove_btn)
        remove_btn_layout.addStretch()
        chroma_item_layout.addRow("", remove_btn_layout)

        # Adiciona widgets ao dicionário para acesso posterior
        chroma_data = {
            "group": chroma_item_group,
            "input": chroma_input,
            "scale": chroma_scale,
            "position": chroma_position,
            "start": chroma_start,
            "remove_btn": remove_btn
        }

        # Conecta eventos para salvar automaticamente
        chroma_input.textChanged.connect(self.save_config)
        chroma_scale.valueChanged.connect(self.save_config)
        chroma_position.currentTextChanged.connect(self.save_config)
        chroma_start.valueChanged.connect(self.save_config)

        self.chroma_widgets.append(chroma_data)
        self.chroma_list_layout.addWidget(chroma_item_group)

    def remove_chroma_widget(self, group_widget, idx):
        # Remove o widget do layout e da lista
        self.chroma_list_layout.removeWidget(group_widget)
        group_widget.deleteLater()

        # Remover da lista (mantém índice para n��o bagunçar a ordem)
        if idx < len(self.chroma_widgets):
            self.chroma_widgets[idx] = None

        # Salvar configuração atualizada
        self.save_config()

    def setup_subtitle_tab(self, tab):
        layout = QFormLayout(tab)

        # Habilitar legendas
        self.enable_subtitles = QCheckBox("Habilitar legendas automáticas")
        layout.addRow("", self.enable_subtitles)

        # Grupo de configurações de legendas
        subtitle_group = QGroupBox("Configurações de Legendas")
        subtitle_layout = QFormLayout(subtitle_group)

        # Tamanho da fonte
        self.subtitle_font_size = QSpinBox()
        self.subtitle_font_size.setRange(10, 100)
        self.subtitle_font_size.setValue(60)
        subtitle_layout.addRow("Tamanho da fonte:", self.subtitle_font_size)

        # Cor da legenda
        self.subtitle_color = QComboBox()
        self.subtitle_color.addItems(["white", "yellow", "black", "red", "green", "blue"])
        self.subtitle_color.setCurrentText("yellow")
        subtitle_layout.addRow("Cor:", self.subtitle_color)

        # Posição da legenda
        self.subtitle_position = QComboBox()
        self.subtitle_position.addItems(["top_left", "top_center", "top_right",
                                        "bottom_left", "bottom_center", "bottom_right", "center"])
        self.subtitle_position.setCurrentText("center")
        subtitle_layout.addRow("Posição:", self.subtitle_position)

        # Arquivo de fonte
        self.subtitle_font_layout = QHBoxLayout()
        self.subtitle_font_input = QLineEdit()
        self.subtitle_font_input.setText("./_internal/_fonts/BebasNeue-Regular.ttf")
        self.subtitle_font_button = QPushButton("Procurar")
        self.subtitle_font_button.clicked.connect(lambda: self.browse_file(self.subtitle_font_input, "Fontes (*.ttf *.otf)"))
        self.subtitle_font_layout.addWidget(self.subtitle_font_input)
        self.subtitle_font_layout.addWidget(self.subtitle_font_button)
        subtitle_layout.addRow("Fonte:", self.subtitle_font_layout)

        # Palavras por legenda
        self.words_per_subtitle = QSpinBox()
        self.words_per_subtitle.setRange(1, 10)
        self.words_per_subtitle.setValue(5)
        subtitle_layout.addRow("Palavras por legenda:", self.words_per_subtitle)

        # Caminho do modelo Vosk
        self.vosk_model_layout = QHBoxLayout()
        self.vosk_model_input = QLineEdit()
        self.vosk_model_input.setText("_internal/vosk_models/vosk-model-pt")
        self.vosk_model_button = QPushButton("Procurar")
        self.vosk_model_button.clicked.connect(lambda: self.browse_folder(self.vosk_model_input))
        self.vosk_model_layout.addWidget(self.vosk_model_input)
        self.vosk_model_layout.addWidget(self.vosk_model_button)
        subtitle_layout.addRow("Modelo Vosk:", self.vosk_model_layout)

        # Efeito na legenda
        self.subtitle_effect = QComboBox()
        self.subtitle_effect.addItems(["none", "fade_in", "fill_bar", "karaoke"])
        subtitle_layout.addRow("Efeito:", self.subtitle_effect)

        layout.addRow("", subtitle_group)

        # Grupo de estilo de legenda
        style_group = QGroupBox("Estilo da Legenda")
        style_layout = QFormLayout(style_group)

        # Configurações de contorno
        self.subtitle_outline_color = QComboBox()
        self.subtitle_outline_color.addItems(["black", "white", "yellow", "red", "green", "blue"])
        style_layout.addRow("Cor do contorno:", self.subtitle_outline_color)

        self.subtitle_outline_width = QSpinBox()
        self.subtitle_outline_width.setRange(0, 5)
        self.subtitle_outline_width.setValue(2)
        style_layout.addRow("Largura do contorno:", self.subtitle_outline_width)

        # Configurações de sombra
        self.subtitle_shadow_color = QComboBox()
        self.subtitle_shadow_color.addItems(["black", "white", "yellow", "red", "green", "blue"])
        style_layout.addRow("Cor da sombra:", self.subtitle_shadow_color)

        self.subtitle_shadow_x = QSpinBox()
        self.subtitle_shadow_x.setRange(0, 10)
        self.subtitle_shadow_x.setValue(2)
        style_layout.addRow("Sombra X:", self.subtitle_shadow_x)

        self.subtitle_shadow_y = QSpinBox()
        self.subtitle_shadow_y.setRange(0, 10)
        self.subtitle_shadow_y.setValue(2)
        style_layout.addRow("Sombra Y:", self.subtitle_shadow_y)

        layout.addRow("", style_group)

    def setup_effects_tab(self, tab):
        layout = QFormLayout(tab)

        # Presets cinematográficos
        self.cinematic_preset = QComboBox()
        self.cinematic_preset.addItems(["nenhum", "warm", "cold", "vintage", "cinematic"])
        self.cinematic_preset.setCurrentText("nenhum")
        layout.addRow("Preset cinematográfico:", self.cinematic_preset)

        # LUT customizado
        self.lut_layout = QHBoxLayout()
        self.lut_input = QLineEdit()
        self.lut_input.setPlaceholderText("Selecione um arquivo LUT (opcional)")
        self.lut_button = QPushButton("Procurar")
        self.lut_button.clicked.connect(lambda: self.browse_file(self.lut_input, "LUT (*.cube)"))
        self.lut_layout.addWidget(self.lut_input)
        self.lut_layout.addWidget(self.lut_button)
        layout.addRow("LUT customizado:", self.lut_layout)

        # Efeito vignette
        self.enable_vignette = QCheckBox("Habilitar efeito vignette")
        layout.addRow("", self.enable_vignette)

        self.vignette_intensity = QDoubleSpinBox()
        self.vignette_intensity.setRange(0.1, 1.0)
        self.vignette_intensity.setValue(0.3)
        self.vignette_intensity.setSingleStep(0.1)
        layout.addRow("Intensidade do vignette:", self.vignette_intensity)

        # Efeito curves
        self.enable_curves = QCheckBox("Habilitar ajuste de curves")
        layout.addRow("", self.enable_curves)

        self.custom_curves = QLineEdit()
        self.custom_curves.setPlaceholderText("Formato FFmpeg: r='0/0 0.5/0.4 1/1':g='0/0 0.5/0.5 1/0.9':b='0/0 0.5/0.5 1/1'")
        layout.addRow("Curves customizadas:", self.custom_curves)

    def browse_file(self, line_edit, filter_str):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", "", filter_str)
        if file_path:
            line_edit.setText(file_path)

    def browse_folder(self, line_edit):
        folder_path = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if folder_path:
            line_edit.setText(folder_path)

    def save_file(self, line_edit, filter_str):
        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar arquivo", "", filter_str)
        if file_path:
            line_edit.setText(file_path)

    def update_resolution_preset(self, preset):
        if preset == "horizontal_1080p":
            self.width.setValue(1920)
            self.height.setValue(1080)
        elif preset == "horizontal_720p":
            self.width.setValue(1280)
            self.height.setValue(720)
        elif preset == "horizontal_480p":
            self.width.setValue(854)
            self.height.setValue(480)
        elif preset == "horizontal_2k":
            self.width.setValue(2560)
            self.height.setValue(1440)
        elif preset == "vertical_1080p":
            self.width.setValue(1080)
            self.height.setValue(1920)
        elif preset == "vertical_720p":
            self.width.setValue(720)
            self.height.setValue(1280)
        elif preset == "vertical_480p":
            self.width.setValue(480)
            self.height.setValue(854)
        elif preset == "vertical_2k":
            self.width.setValue(1440)
            self.height.setValue(2560)
        elif preset == "square_1080p":
            self.width.setValue(1080)
            self.height.setValue(1080)

    def generate_video(self):
        # Validação básica
        if not self.narration_input.text():
            QMessageBox.warning(self, "Atenção", "Selecione um arquivo de narração!")
            return

        if not self.videos_folder_input.text():
            QMessageBox.warning(self, "Atenção", "Selecione uma pasta de vídeos/imagens!")
            return

        if not self.output_input.text():
            QMessageBox.warning(self, "Atenção", "Selecione um arquivo de saída!")
            return

        # Preparar parâmetros
        params = {
            'narration_path': self.narration_input.text(),
            'videos_folder': self.videos_folder_input.text(),
            'out_path': self.output_input.text(),
            'seed': None if self.seed.value() == -1 else self.seed.value(),
            'fps': self.fps.value(),
            'width': self.width.value(),
            'height': self.height.value(),
            'crf': self.crf.value(),
            'preset': self.preset.currentText(),
            'video_mode': self.video_mode.currentText(),
            'image_segment_duration': self.image_segment_duration.value(),
            'overlay': self.overlay_input.text() if self.overlay_input.text() else None,
            'overlay_opacity': self.overlay_opacity.value(),
            'logo': self.logo_input.text() if self.logo_input.text() else None,
            'logo_scale': self.logo_scale.value(),
            'logo_x': self.logo_x.value(),
            'logo_y': self.logo_y.value(),
            'logo_position': self.logo_position.currentText(),
            'transition_type': self.transition_type.currentText(),
            'enable_subtitles': self.enable_subtitles.isChecked(),
            'subtitle_font_size': self.subtitle_font_size.value(),
            'subtitle_color': self.subtitle_color.currentText(),
            'subtitle_position': self.subtitle_position.currentText(),
            'subtitle_font': self.subtitle_font_input.text() if self.subtitle_font_input.text() else None,
            'subtitle_outline_color': self.subtitle_outline_color.currentText(),
            'subtitle_outline_width': self.subtitle_outline_width.value(),
            'subtitle_shadow_color': self.subtitle_shadow_color.currentText(),
            'subtitle_shadow_x': self.subtitle_shadow_x.value(),
            'subtitle_shadow_y': self.subtitle_shadow_y.value(),
            'words_per_subtitle': self.words_per_subtitle.value(),
            'vosk_model_path': self.vosk_model_input.text(),
            'enable_ken_burns': self.enable_ken_burns.isChecked(),
            'cinematic_preset': None if self.cinematic_preset.currentText() == "nenhum" else self.cinematic_preset.currentText(),
            'custom_lut_path': self.lut_input.text() if self.lut_input.text() else None,
            'enable_vignette': self.enable_vignette.isChecked(),
            'vignette_intensity': self.vignette_intensity.value(),
            'enable_curves': self.enable_curves.isChecked(),
            'custom_curves': self.custom_curves.text() if self.custom_curves.text() else None,
            'remove_silence': self.remove_silence.isChecked(),
            'silence_threshold': self.silence_threshold.value(),
            'silence_duration': self.silence_duration.value(),
            'encoder': self.encoder.currentText(),
            'performance_profile': self.performance_profile.currentText(),
            'threads': self.threads.value(),
            'gpu_quality': self.gpu_quality.value(),
            'resolution_preset': self.resolution_preset.currentText(),
            'background_music': self.bg_music_input.text() if self.bg_music_input.text() else None,
            'background_music_volume': self.bg_music_volume.value(),
            'subtitle_effect': self.subtitle_effect.currentText(),
            'ending_video_path': self.ending_input.text() if self.ending_input.text() else None,
        }

        # Adiciona lista de chromas
        chroma_list = []
        for chroma_data in self.chroma_widgets:
            # Pula itens excluídos
            if chroma_data is None:
                continue

            # Somente adiciona o chroma se um caminho estiver definido
            if chroma_data["input"].text():
                chroma_item = {
                    "path": chroma_data["input"].text(),
                    "scale": chroma_data["scale"].value(),
                    "position": chroma_data["position"].currentText(),
                    "start": chroma_data["start"].value()
                }
                chroma_list.append(chroma_item)

        # Adiciona a lista de chromas ao parâmetro se não estiver vazia
        if chroma_list:
            params["chroma_list"] = chroma_list

        # Desabilitar botão e mostrar progresso
        self.generate_button.setEnabled(False)
        self.progress_bar.setValue(0)

        # Iniciar thread de processamento
        self.thread = ProcessVideoThread(params)
        self.thread.finished.connect(self.on_process_finished)
        self.thread.start()

        # Mostrar mensagem de processamento
        QMessageBox.information(self, "Processando", "O vídeo está sendo processado. Isso pode demorar vários minutos dependendo da duração da narração e complexidade do projeto.")

    def on_process_finished(self, success, message):
        self.generate_button.setEnabled(True)
        self.progress_bar.setValue(100 if success else 0)

        if success:
            QMessageBox.information(self, "Sucesso", message)
        else:
            QMessageBox.critical(self, "Erro", message)

    def save_config(self):
        # Coletar todos os parâmetros atuais
        config = {
            'narration_path': self.narration_input.text(),
            'videos_folder': self.videos_folder_input.text(),
            'out_path': self.output_input.text(),
            'seed': self.seed.value(),
            'fps': self.fps.value(),
            'width': self.width.value(),
            'height': self.height.value(),
            'crf': self.crf.value(),
            'preset': self.preset.currentText(),
            'video_mode': self.video_mode.currentText(),
            'image_segment_duration': self.image_segment_duration.value(),
            'overlay': self.overlay_input.text() if self.overlay_input.text() else None,
            'overlay_opacity': self.overlay_opacity.value(),
            'logo': self.logo_input.text() if self.logo_input.text() else None,
            'logo_scale': self.logo_scale.value(),
            'logo_x': self.logo_x.value(),
            'logo_y': self.logo_y.value(),
            'logo_position': self.logo_position.currentText(),
            'transition_type': self.transition_type.currentText(),
            'enable_subtitles': self.enable_subtitles.isChecked(),
            'subtitle_font_size': self.subtitle_font_size.value(),
            'subtitle_color': self.subtitle_color.currentText(),
            'subtitle_position': self.subtitle_position.currentText(),
            'subtitle_font': self.subtitle_font_input.text() if self.subtitle_font_input.text() else None,
            'subtitle_outline_color': self.subtitle_outline_color.currentText(),
            'subtitle_outline_width': self.subtitle_outline_width.value(),
            'subtitle_shadow_color': self.subtitle_shadow_color.currentText(),
            'subtitle_shadow_x': self.subtitle_shadow_x.value(),
            'subtitle_shadow_y': self.subtitle_shadow_y.value(),
            'words_per_subtitle': self.words_per_subtitle.value(),
            'vosk_model_path': self.vosk_model_input.text(),
            'enable_ken_burns': self.enable_ken_burns.isChecked(),
            'cinematic_preset': None if self.cinematic_preset.currentText() == "nenhum" else self.cinematic_preset.currentText(),
            'custom_lut_path': self.lut_input.text() if self.lut_input.text() else None,
            'enable_vignette': self.enable_vignette.isChecked(),
            'vignette_intensity': self.vignette_intensity.value(),
            'enable_curves': self.enable_curves.isChecked(),
            'custom_curves': self.custom_curves.text() if self.custom_curves.text() else None,
            'remove_silence': self.remove_silence.isChecked(),
            'silence_threshold': self.silence_threshold.value(),
            'silence_duration': self.silence_duration.value(),
            'encoder': self.encoder.currentText(),
            'performance_profile': self.performance_profile.currentText(),
            'threads': self.threads.value(),
            'gpu_quality': self.gpu_quality.value(),
            'resolution_preset': self.resolution_preset.currentText(),
            'background_music': self.bg_music_input.text() if self.bg_music_input.text() else None,
            'background_music_volume': self.bg_music_volume.value(),
            'subtitle_effect': self.subtitle_effect.currentText(),
            'ending_video_path': self.ending_input.text() if self.ending_input.text() else None,
        }

        # Adiciona lista de chromas
        chroma_list = []
        for chroma_data in self.chroma_widgets:
            # Pula itens excluídos
            if chroma_data is None:
                continue

            # Somente adiciona o chroma se um caminho estiver definido
            if chroma_data["input"].text():
                chroma_item = {
                    "path": chroma_data["input"].text(),
                    "scale": chroma_data["scale"].value(),
                    "position": chroma_data["position"].currentText(),
                    "start": chroma_data["start"].value()
                }
                chroma_list.append(chroma_item)

        # Adiciona a lista de chromas à configuração se não estiver vazia
        if chroma_list:
            config["chroma_list"] = chroma_list

        # Salvar em config.json silenciosamente
        with open("config.json", "w") as config_file:
            json.dump(config, config_file, indent=4, ensure_ascii=False)

    def load_config(self):
        # Carregar configurações de config.json
        if not os.path.exists("config.json"):
            return

        with open("config.json", "r") as config_file:
            config = json.load(config_file)

        # Aplicar configurações
        self.narration_input.setText(config.get('narration_path', ''))
        self.videos_folder_input.setText(config.get('videos_folder', ''))
        self.output_input.setText(config.get('out_path', ''))
        self.seed.setValue(config.get('seed', -1))
        self.fps.setValue(config.get('fps', 30))
        self.width.setValue(config.get('width', 1920))
        self.height.setValue(config.get('height', 1080))
        self.crf.setValue(config.get('crf', 18))
        self.preset.setCurrentText(config.get('preset', 'medium'))
        self.video_mode.setCurrentText(config.get('video_mode', 'videos'))
        self.image_segment_duration.setValue(config.get('image_segment_duration', 6.0))
        self.overlay_input.setText(config.get('overlay', ''))
        self.overlay_opacity.setValue(config.get('overlay_opacity', 0.3))
        self.logo_input.setText(config.get('logo', ''))
        self.logo_scale.setValue(config.get('logo_scale', 0.15))
        self.logo_x.setValue(config.get('logo_x', 20))
        self.logo_y.setValue(config.get('logo_y', 20))
        self.logo_position.setCurrentText(config.get('logo_position', 'top_right'))
        self.transition_type.setCurrentText(config.get('transition_type', 'none'))
        self.enable_subtitles.setChecked(config.get('enable_subtitles', False))
        self.subtitle_font_size.setValue(config.get('subtitle_font_size', 60))
        self.subtitle_color.setCurrentText(config.get('subtitle_color', 'yellow'))
        self.subtitle_position.setCurrentText(config.get('subtitle_position', 'center'))
        self.subtitle_font_input.setText(config.get('subtitle_font', ''))
        self.subtitle_outline_color.setCurrentText(config.get('subtitle_outline_color', 'black'))
        self.subtitle_outline_width.setValue(config.get('subtitle_outline_width', 2))
        self.subtitle_shadow_color.setCurrentText(config.get('subtitle_shadow_color', 'black'))
        self.subtitle_shadow_x.setValue(config.get('subtitle_shadow_x', 2))
        self.subtitle_shadow_y.setValue(config.get('subtitle_shadow_y', 2))
        self.words_per_subtitle.setValue(config.get('words_per_subtitle', 5))
        self.vosk_model_input.setText(config.get('vosk_model_path', ''))
        self.enable_ken_burns.setChecked(config.get('enable_ken_burns', False))
        self.cinematic_preset.setCurrentText(config.get('cinematic_preset', 'nenhum'))
        self.lut_input.setText(config.get('custom_lut_path', ''))
        self.enable_vignette.setChecked(config.get('enable_vignette', False))
        self.vignette_intensity.setValue(config.get('vignette_intensity', 0.3))
        self.enable_curves.setChecked(config.get('enable_curves', False))
        self.custom_curves.setText(config.get('custom_curves', ''))
        self.remove_silence.setChecked(config.get('remove_silence', True))
        self.silence_threshold.setValue(config.get('silence_threshold', -40))
        self.silence_duration.setValue(config.get('silence_duration', 0.5))
        self.encoder.setCurrentText(config.get('encoder', 'libx264'))
        self.performance_profile.setCurrentText(config.get('performance_profile', 'balanced'))
        self.threads.setValue(config.get('threads', 0))
        self.gpu_quality.setValue(config.get('gpu_quality', 18))
        self.resolution_preset.setCurrentText(config.get('resolution_preset', 'horizontal_1080p'))
        self.bg_music_input.setText(config.get('background_music', ''))
        self.bg_music_volume.setValue(config.get('background_music_volume', 0.2))
        self.subtitle_effect.setCurrentText(config.get('subtitle_effect', 'none'))
        self.ending_input.setText(config.get('ending_video_path', ''))

        # Carrega lista de chromas
        chroma_list = config.get('chroma_list', [])

        # Limpa widgets existentes de chroma
        for chroma_data in self.chroma_widgets:
            if chroma_data is not None and chroma_data["group"] is not None:
                self.chroma_list_layout.removeWidget(chroma_data["group"])
                chroma_data["group"].deleteLater()
        self.chroma_widgets.clear()

        # Se não tiver nenhum chroma na configuração, adiciona um vazio
        if not chroma_list:
            self.add_chroma_widget()
        else:
            # Adiciona um widget para cada chroma na configuração
            for chroma_item in chroma_list:
                # Adiciona novo widget
                self.add_chroma_widget()
                idx = len(self.chroma_widgets) - 1

                # Preenche com valores do config
                if idx >= 0 and self.chroma_widgets[idx] is not None:
                    self.chroma_widgets[idx]["input"].setText(chroma_item.get("path", ""))
                    self.chroma_widgets[idx]["scale"].setValue(chroma_item.get("scale", 0.3))
                    self.chroma_widgets[idx]["position"].setCurrentText(chroma_item.get("position", "bottom_center"))
                    self.chroma_widgets[idx]["start"].setValue(chroma_item.get("start", 30.0))

    def connect_change_events(self):
        # Conectar eventos de mudança para salvar configuração automaticamente
        self.narration_input.textChanged.connect(self.save_config)
        self.videos_folder_input.textChanged.connect(self.save_config)
        self.output_input.textChanged.connect(self.save_config)
        self.seed.valueChanged.connect(self.save_config)
        self.fps.valueChanged.connect(self.save_config)
        self.width.valueChanged.connect(self.save_config)
        self.height.valueChanged.connect(self.save_config)
        self.crf.valueChanged.connect(self.save_config)
        self.preset.currentTextChanged.connect(self.save_config)
        self.video_mode.currentTextChanged.connect(self.save_config)
        self.image_segment_duration.valueChanged.connect(self.save_config)
        self.overlay_input.textChanged.connect(self.save_config)
        self.overlay_opacity.valueChanged.connect(self.save_config)
        self.logo_input.textChanged.connect(self.save_config)
        self.logo_scale.valueChanged.connect(self.save_config)
        self.logo_x.valueChanged.connect(self.save_config)
        self.logo_y.valueChanged.connect(self.save_config)
        self.logo_position.currentTextChanged.connect(self.save_config)
        self.transition_type.currentTextChanged.connect(self.save_config)
        self.enable_subtitles.toggled.connect(self.save_config)
        self.subtitle_font_size.valueChanged.connect(self.save_config)
        self.subtitle_color.currentTextChanged.connect(self.save_config)
        self.subtitle_position.currentTextChanged.connect(self.save_config)
        self.subtitle_font_input.textChanged.connect(self.save_config)
        self.subtitle_outline_color.currentTextChanged.connect(self.save_config)
        self.subtitle_outline_width.valueChanged.connect(self.save_config)
        self.subtitle_shadow_color.currentTextChanged.connect(self.save_config)
        self.subtitle_shadow_x.valueChanged.connect(self.save_config)
        self.subtitle_shadow_y.valueChanged.connect(self.save_config)
        self.words_per_subtitle.valueChanged.connect(self.save_config)
        self.vosk_model_input.textChanged.connect(self.save_config)
        self.enable_ken_burns.toggled.connect(self.save_config)
        self.cinematic_preset.currentTextChanged.connect(self.save_config)
        self.lut_input.textChanged.connect(self.save_config)
        self.enable_vignette.toggled.connect(self.save_config)
        self.vignette_intensity.valueChanged.connect(self.save_config)
        self.enable_curves.toggled.connect(self.save_config)
        self.custom_curves.textChanged.connect(self.save_config)
        self.remove_silence.toggled.connect(self.save_config)
        self.silence_threshold.valueChanged.connect(self.save_config)
        self.silence_duration.valueChanged.connect(self.save_config)
        self.encoder.currentTextChanged.connect(self.save_config)
        self.performance_profile.currentTextChanged.connect(self.save_config)
        self.threads.valueChanged.connect(self.save_config)
        self.gpu_quality.valueChanged.connect(self.save_config)
        self.resolution_preset.currentTextChanged.connect(self.save_config)
        self.bg_music_input.textChanged.connect(self.save_config)
        self.bg_music_volume.valueChanged.connect(self.save_config)
        self.subtitle_effect.currentTextChanged.connect(self.save_config)
        self.ending_input.textChanged.connect(self.save_config)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoGeneratorGUI()
    window.show()
    sys.exit(app.exec())