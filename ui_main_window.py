# ui_main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QListWidget, QTextEdit, QSplitter,
    QGroupBox, QTabWidget, QScrollArea
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt
from ui_tabs import BasicTab, VideoTab, OverlayTab, SubtitleTab


class VideoGeneratorGUI(QMainWindow):
    """Classe da View, responsável apenas pela aparência da janela principal."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Vídeos Automatizado")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(QIcon.fromTheme("multimedia-video-player"))

        self._setup_ui()
        self.apply_stylesheet()

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Painel de Configurações (Esquerda) com Scroll
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

        # --- SEÇÃO MODIFICADA ---
        # Botões de Ação
        action_buttons_layout = QHBoxLayout()
        self.generate_button = QPushButton("Gerar Vídeo Único")
        self.add_to_queue_button = QPushButton("Adicionar à Fila")
        self.save_config_button = QPushButton("Salvar Configurações")  # NOVO BOTÃO

        action_buttons_layout.addWidget(self.generate_button)
        action_buttons_layout.addWidget(self.add_to_queue_button)
        action_buttons_layout.addWidget(self.save_config_button)  # ADICIONADO AO LAYOUT
        config_layout.addLayout(action_buttons_layout)
        # --- FIM DA SEÇÃO MODIFICADA ---

        splitter.addWidget(self.config_panel)

        # Painel da Fila (Direita)
        self.queue_panel = self._create_queue_panel()
        splitter.addWidget(self.queue_panel)
        splitter.setSizes([700, 500])

        # Barra de Progresso Global
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Progresso Geral: %p%")
        main_layout.addWidget(self.progress_bar)

    def _create_queue_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("Fila de Processamento")
        title.setFont(QFont("Arial", 14, QFont.Bold))
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

    def apply_stylesheet(self):
        self.setStyleSheet("""
            /* ... (Cole o CSS do tema escuro da resposta anterior aqui) ... */
        """)

    def closeEvent(self, event):
        # O Controller vai interceptar isso para salvar
        pass
