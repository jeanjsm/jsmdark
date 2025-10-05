# ui_main_window.py
from typing import Optional
import logging

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QListWidget, QTextEdit, QSplitter,
    QGroupBox, QTabWidget, QScrollArea, QFormLayout
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt
from ui_tabs import BasicTab, VideoTab, OverlayTab, SubtitleTab

WINDOW_TITLE = "Gerador de Vídeos Automatizado"
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
SPLITTER_LEFT_SIZE = 700
SPLITTER_RIGHT_SIZE = 500
QUEUE_TITLE_FONT_SIZE = 14
QUEUE_TITLE_FONT_FAMILY = "Arial"
QUEUE_TITLE_FONT_WEIGHT = QFont.Bold


class VideoGeneratorGUI(QMainWindow):
    """Main application window for the video generator GUI.

    Handles the appearance and layout of the main window, including configuration tabs,
    queue panel, progress bar, and action buttons.
    """

    def __init__(self) -> None:
        """Initializes the main window and its UI components."""
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setWindowIcon(QIcon.fromTheme("multimedia-video-player"))
        try:
            self._setup_ui()
            self.apply_stylesheet()
        except Exception as exc:
            logging.error(f"Error setting up UI: {exc}")
            QMessageBox.critical(self, "Erro", f"Falha ao inicializar a interface: {exc}")

    def _setup_ui(self) -> None:
        """Sets up the main UI layout, tabs, panels, and buttons."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Config panel (left) with scroll
        self.config_panel = QWidget()
        config_layout = QVBoxLayout(self.config_panel)
        config_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        self.tabs = QTabWidget()
        self.basic_tab = BasicTab()
        self.video_tab = VideoTab()
        self.overlay_tab = OverlayTab()
        self.subtitle_tab = SubtitleTab()

        self.tabs.addTab(self.basic_tab, "1. Básico")
        self.tabs.addTab(self.video_tab, "2. Vídeo e Efeitos")
        self.tabs.addTab(self.overlay_tab, "3. Overlays")
        self.tabs.addTab(self.subtitle_tab, "4. Legendas")

        scroll_area.setWidget(self.tabs)
        config_layout.addWidget(scroll_area)

        # Action buttons
        action_buttons_layout = QHBoxLayout()
        self.generate_button = QPushButton("Gerar Vídeo Único")
        self.add_to_queue_button = QPushButton("Adicionar à Fila")
        self.save_config_button = QPushButton("Salvar Configurações")
        self.manage_slots_button = QPushButton("Gerenciar Save Slots")
        self.quick_save_button = QPushButton("Save Rápido")
        action_buttons_layout.addWidget(self.generate_button)
        action_buttons_layout.addWidget(self.add_to_queue_button)
        action_buttons_layout.addWidget(self.save_config_button)
        action_buttons_layout.addWidget(self.manage_slots_button)
        action_buttons_layout.addWidget(self.quick_save_button)
        config_layout.addLayout(action_buttons_layout)

        splitter.addWidget(self.config_panel)

        # Queue panel (right)
        self.queue_panel = self._create_queue_panel()
        splitter.addWidget(self.queue_panel)
        splitter.setSizes([SPLITTER_LEFT_SIZE, SPLITTER_RIGHT_SIZE])

        # Global progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Progresso Geral: %p%")
        main_layout.addWidget(self.progress_bar)

    def _create_queue_panel(self) -> QWidget:
        """Creates the queue panel with list, buttons, and log area.

        Returns:
            QWidget: The queue panel widget.
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("Fila de Processamento")
        title.setFont(QFont(QUEUE_TITLE_FONT_FAMILY, QUEUE_TITLE_FONT_SIZE, QUEUE_TITLE_FONT_WEIGHT))
        layout.addWidget(title)

        self.queue_list = QListWidget()
        layout.addWidget(self.queue_list)

        queue_buttons_layout = QHBoxLayout()
        self.start_queue_button = QPushButton("Processar Fila")
        self.stop_queue_button = QPushButton("Parar Fila")
        self.clear_queue_button = QPushButton("Limpar Fila")
        self.remove_selected_button = QPushButton("Remover")

        queue_buttons_layout.addWidget(self.start_queue_button)
        queue_buttons_layout.addWidget(self.stop_queue_button)
        queue_buttons_layout.addWidget(self.clear_queue_button)
        queue_buttons_layout.addWidget(self.remove_selected_button)
        layout.addLayout(queue_buttons_layout)

        log_group = QGroupBox("Log de Atividades")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        return panel

    def apply_stylesheet(self) -> None:
        """Applies the dark theme stylesheet to the main window."""
        self.setStyleSheet("""
            /* ... (Cole o CSS do tema escuro da resposta anterior aqui) ... */
        """)

    def closeEvent(self, event: Optional[object]) -> None:
        """Intercepts the window close event for controller handling.

        Args:
            event (Optional[object]): The close event object.
        """
        pass

    def _collect_params(self) -> dict:
        """Coleta todos os parâmetros das abas, incluindo o caminho do SRT."""
        params = {}
        # Exemplo de coleta dos campos principais (adapte conforme necessário)
        params["narration_path"] = self.basic_tab.narration_path.text().strip()
        params["videos_folder"] = self.basic_tab.videos_folder.text().strip()
        params["out_path"] = self.basic_tab.output_folder.text().strip()
        params["video_mode"] = self.basic_tab.video_mode.currentText()
        params["seed"] = self.basic_tab.seed.value() if self.basic_tab.seed.value() != -1 else None
        params["shuffle"] = self.basic_tab.shuffle.isChecked()
        # ...coleta dos demais campos das outras abas...
        # Legendas
        params["enable_subtitles"] = self.subtitle_tab.enable_subtitles.isChecked()
        params["subtitle_font_size"] = self.subtitle_tab.subtitle_font_size.value()
        params["subtitle_color"] = self.subtitle_tab.subtitle_color.currentText()
        params["subtitle_position"] = self.subtitle_tab.subtitle_position.currentText()
        params["subtitle_font"] = self.subtitle_tab.subtitle_font.text().strip()
        params["words_per_subtitle"] = self.subtitle_tab.words_per_subtitle.value()
        params["vosk_model_path"] = self.subtitle_tab.vosk_model_path.text().strip()
        params["subtitle_outline_color"] = self.subtitle_tab.subtitle_outline_color.currentText()
        params["subtitle_outline_width"] = self.subtitle_tab.subtitle_outline_width.value()
        params["subtitle_shadow_color"] = self.subtitle_tab.subtitle_shadow_color.currentText()
        params["subtitle_shadow_x"] = self.subtitle_tab.subtitle_shadow_x.value()
        params["subtitle_shadow_y"] = self.subtitle_tab.subtitle_shadow_y.value()
        params["subtitle_effect"] = self.subtitle_tab.subtitle_effect.currentText()
        # Novo: caminho do SRT
        srt_path = self.subtitle_tab.get_srt_path()
        params["srt_path"] = srt_path if srt_path else None
        # ...coleta dos demais campos das outras abas...
        return params
