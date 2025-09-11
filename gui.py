#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
    QTabWidget, QFileDialog, QFormLayout, QGroupBox, QProgressBar,
    QMessageBox, QListWidget, QTextEdit, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QTextCursor


# --- Mock da função de processamento para o código rodar de forma independente ---
# Em seu projeto real, você importaria sua função original.
def create_video_from_narration(**kwargs):
    import time
    print("Iniciando a criação do vídeo com os parâmetros:")
    # print(json.dumps(kwargs, indent=2, default=str)) # Descomente para depurar

    progress_callback = kwargs.get('progress_callback')
    if progress_callback:
        for i in range(101):
            time.sleep(0.05)  # Simula trabalho
            progress_callback(i)
    print(f"Vídeo salvo em: {kwargs.get('out_path')}")
    return {"status": "success"}


# --- MODELO DE DADOS ---
# Uma única fonte da verdade para todas as configurações.

@dataclass
class QueueItem:
    narration_path: str
    output_path: str
    status: str = "waiting"  # waiting, processing, completed, error
    progress: int = 0
    error_message: str = ""


@dataclass
class ConfigModel:
    """Armazena todas as configurações da aplicação."""
    narration_path: str = ""
    videos_folder: str = ""
    output_folder: str = ""
    video_mode: str = "videos"
    seed: int = -1
    shuffle: bool = True
    # ... (adicione todos os outros campos aqui)
    # Esta é uma versão simplificada para demonstração.
    # Você deve adicionar todos os campos de get_current_params aqui.
    fps: int = 30
    width: int = 1920
    height: int = 1080
    enable_subtitles: bool = False
    subtitle_font_size: int = 60

    def save(self, filepath="config.json"):
        """Salva o modelo de dados em um arquivo JSON."""
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=4, ensure_ascii=False)

    @classmethod
    def load(cls, filepath="config.json"):
        """Carrega o modelo de dados de um arquivo JSON."""
        if not Path(filepath).exists():
            return cls()  # Retorna um modelo padrão se o arquivo não existir
        try:
            with open(filepath, "r", encoding='utf-8') as f:
                data = json.load(f)
                # Filtra apenas as chaves que existem no modelo para evitar erros
                valid_keys = cls.__annotations__.keys()
                filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                return cls(**filtered_data)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Erro ao carregar config.json: {e}. Usando configurações padrão.")
            return cls()


# --- LÓGICA DE PROCESSAMENTO (THREADS) ---
# (Mantido praticamente igual, pois já estava bem estruturado)

class ProcessVideoThread(QThread):
    """Thread para processar um único vídeo."""
    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        try:
            self.params['progress_callback'] = lambda p: self.progress.emit(p)
            create_video_from_narration(**self.params)
            self.finished.emit(True, f"Vídeo gerado com sucesso: {self.params['out_path']}")
        except Exception as e:
            self.finished.emit(False, f"Erro ao gerar vídeo: {e}")


class QueueWorkerThread(QThread):
    """Thread para processar a fila de vídeos."""
    item_started = Signal(int)
    item_progress = Signal(int, int)
    item_finished = Signal(int, bool, str)
    queue_finished = Signal()

    def __init__(self, queue_items: List[QueueItem], base_params: dict):
        super().__init__()
        self.queue_items = queue_items
        self.base_params = base_params
        self._is_running = True

    def run(self):
        for i, item in enumerate(self.queue_items):
            if not self._is_running:
                break
            if item.status != "waiting":
                continue

            self.item_started.emit(i)
            params = self.base_params.copy()
            params['narration_path'] = item.narration_path
            params['out_path'] = item.output_path

            try:
                params['progress_callback'] = lambda p, index=i: self.item_progress.emit(index, p)
                create_video_from_narration(**params)
                self.item_finished.emit(i, True, f"Concluído: {item.output_path}")
            except Exception as e:
                self.item_finished.emit(i, False, str(e))

        self.queue_finished.emit()

    def stop(self):
        self._is_running = False


# --- COMPONENTES DA UI (MODULARIZADOS) ---

class BasicTab(QWidget):
    """Aba de configurações básicas (Arquivos e Modo)."""

    def __init__(self, model: ConfigModel):
        super().__init__()
        self.model = model
        self.widgets = {}
        self.setLayout(self._create_layout())

    def _create_layout(self):
        layout = QFormLayout(self)
        layout.setSpacing(15)

        # Mapeamento de 'nome_do_campo' para (WidgetClass, {opções})
        # Isso facilita a criação e o acesso posterior
        widget_map = {
            "narration_path": (QLineEdit, {"placeholderText": "Caminho para o arquivo de narração (.mp3, .wav)"}),
            "videos_folder": (QLineEdit, {"placeholderText": "Pasta com os vídeos ou imagens de fundo"}),
            "output_folder": (QLineEdit, {"placeholderText": "Pasta onde o vídeo final será salvo"}),
            "video_mode": (QComboBox, {"items": ["videos", "images"]}),
            "seed": (QSpinBox, {"range": (-1, 99999), "specialValueText": "Aleatório"}),
            "shuffle": (QCheckBox, {"text": "Randomizar ordem dos vídeos/imagens"}),
        }

        for name, (widget_class, options) in widget_map.items():
            label_text = name.replace("_", " ").capitalize() + ":"
            if widget_class in [QLineEdit, QComboBox, QSpinBox]:
                widget = widget_class()
                if "items" in options: widget.addItems(options.pop("items"))
                if "range" in options: widget.setRange(*options.pop("range"))
                if "specialValueText" in options: widget.setSpecialValueText(options.pop("specialValueText"))

                # Para campos de arquivo/pasta, adicionar um botão "Procurar"
                if "_path" in name or "_folder" in name:
                    container = QHBoxLayout()
                    container.setContentsMargins(0, 0, 0, 0)
                    container.addWidget(widget)
                    browse_btn = QPushButton("Procurar...")
                    if "_folder" in name:
                        browse_btn.clicked.connect(lambda _, w=widget: self._browse_folder(w))
                    else:
                        browse_btn.clicked.connect(lambda _, w=widget: self._browse_file(w, "Áudios (*.mp3 *.wav)"))
                    container.addWidget(browse_btn)
                    layout.addRow(label_text, container)
                else:
                    layout.addRow(label_text, widget)

            elif widget_class == QCheckBox:
                widget = QCheckBox(options.pop("text"))
                layout.addRow("", widget)

            self.widgets[name] = widget

        return layout

    def _browse_file(self, line_edit: QLineEdit, filter_str: str):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo", "", filter_str)
        if path:
            line_edit.setText(path)

    def _browse_folder(self, line_edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if path:
            line_edit.setText(path)

    def update_ui_from_model(self):
        """Atualiza os widgets com os valores do modelo."""
        for name, widget in self.widgets.items():
            value = getattr(self.model, name, None)
            if value is None: continue

            if isinstance(widget, QLineEdit):
                widget.setText(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            elif isinstance(widget, QSpinBox):
                widget.setValue(value)
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(value)

    def update_model_from_ui(self):
        """Atualiza o modelo com os valores dos widgets."""
        for name, widget in self.widgets.items():
            if isinstance(widget, QLineEdit):
                setattr(self.model, name, widget.text())
            elif isinstance(widget, QCheckBox):
                setattr(self.model, name, widget.isChecked())
            elif isinstance(widget, QSpinBox):
                setattr(self.model, name, widget.value())
            elif isinstance(widget, QComboBox):
                setattr(self.model, name, widget.currentText())


# --- CLASSE PRINCIPAL E CONTROLADOR ---

class VideoGeneratorGUI(QMainWindow):
    """
    Classe principal da janela. Agora é responsável apenas por montar a estrutura
    principal da UI e delegar o resto para o controlador.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerador de Vídeos Automatizado")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(QIcon.fromTheme("multimedia-video-player"))  # Ícone genérico

        # Carregar o modelo de dados
        self.model = ConfigModel.load()

        # Configurar o controlador que gerencia a lógica
        self.controller = AppController(self, self.model)

        # Configurar a UI
        self._setup_ui()
        self.controller.connect_signals()
        self.controller.update_ui_from_model()  # Carrega os dados salvos na UI

    def _setup_ui(self):
        """Configura a estrutura visual principal da aplicação."""
        self.apply_stylesheet()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Painel de Configurações (Esquerda)
        self.config_panel = QWidget()
        config_layout = QVBoxLayout(self.config_panel)

        self.tabs = QTabWidget()
        # Adicionar abas modularizadas
        self.tabs.addTab(BasicTab(self.model), "1. Arquivos e Modo")
        # Você criaria classes para as outras abas da mesma forma:
        # self.tabs.addTab(VideoTab(self.model), "2. Vídeo e Qualidade")
        # self.tabs.addTab(SubtitlesTab(self.model), "3. Legendas")
        # self.tabs.addTab(EffectsTab(self.model), "4. Efeitos e Overlays")
        config_layout.addWidget(self.tabs)

        # Botões de Ação
        action_buttons_layout = QHBoxLayout()
        self.generate_button = QPushButton("Gerar Vídeo Único")
        self.add_to_queue_button = QPushButton("Adicionar à Fila")
        action_buttons_layout.addWidget(self.generate_button)
        action_buttons_layout.addWidget(self.add_to_queue_button)
        config_layout.addLayout(action_buttons_layout)

        splitter.addWidget(self.config_panel)

        # Painel da Fila (Direita)
        self.queue_panel = self._create_queue_panel()
        splitter.addWidget(self.queue_panel)
        splitter.setSizes([700, 500])

        # Barra de Progresso Global
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Progresso: %p%")
        main_layout.addWidget(self.progress_bar)

    def _create_queue_panel(self) -> QWidget:
        """Cria o painel direito com a fila e logs."""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        title = QLabel("Fila de Processamento")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        self.queue_list = QListWidget()
        layout.addWidget(self.queue_list)

        # Botões da Fila
        queue_buttons_layout = QHBoxLayout()
        self.start_queue_button = QPushButton("Processar Fila")
        self.stop_queue_button = QPushButton("Parar Fila")
        self.clear_queue_button = QPushButton("Limpar Fila")
        self.remove_selected_button = QPushButton("Remover Selecionado")

        queue_buttons_layout.addWidget(self.start_queue_button)
        queue_buttons_layout.addWidget(self.stop_queue_button)
        queue_buttons_layout.addWidget(self.clear_queue_button)
        queue_buttons_layout.addWidget(self.remove_selected_button)
        layout.addLayout(queue_buttons_layout)

        # Log
        log_group = QGroupBox("Log de Atividades")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        return panel

    def apply_stylesheet(self):
        """Aplica um estilo visual moderno e limpo."""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2e2e2e;
                color: #e0e0e0;
                font-family: Arial;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #4a4a4a;
                border-radius: 5px;
                margin-top: 10px;
                background-color: #383838;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #008ae6; }
            QPushButton:pressed { background-color: #006bb3; }
            QPushButton:disabled { background-color: #555; color: #888; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                background-color: #444;
                selection-background-color: #007acc;
            }
            QTabWidget::pane {
                border: 1px solid #4a4a4a;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #383838;
                padding: 10px 20px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border: 1px solid #4a4a4a;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #2e2e2e;
                border-bottom: 1px solid #2e2e2e;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 3px;
            }
            QListWidget {
                border: 1px solid #555;
                background-color: #444;
            }
            QListWidget::item:selected {
                background-color: #007acc;
                color: white;
            }
        """)

    def closeEvent(self, event):
        """Salva as configurações ao fechar."""
        self.controller.save_config()
        event.accept()


class AppController:
    """Controlador que gerencia a lógica da aplicação."""

    def __init__(self, view: VideoGeneratorGUI, model: ConfigModel):
        self.view = view
        self.model = model
        self.queue_items: List[QueueItem] = []
        self.queue_worker: Optional[QueueWorkerThread] = None
        self.is_processing_queue = False

    def connect_signals(self):
        """Conecta todos os sinais e slots."""
        # Conectar mudanças na UI para atualizar o modelo
        for i in range(self.view.tabs.count()):
            tab = self.view.tabs.widget(i)
            if hasattr(tab, 'widgets'):
                for widget in tab.widgets.values():
                    if isinstance(widget, (QLineEdit, QTextEdit)):
                        widget.textChanged.connect(self.update_model_from_ui)
                    elif isinstance(widget, QCheckBox):
                        widget.toggled.connect(self.update_model_from_ui)
                    elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                        widget.valueChanged.connect(self.update_model_from_ui)
                    elif isinstance(widget, QComboBox):
                        widget.currentTextChanged.connect(self.update_model_from_ui)

        # Botões de ação
        self.view.generate_button.clicked.connect(self.generate_single_video)
        self.view.add_to_queue_button.clicked.connect(self.add_to_queue)

        # Botões da fila
        self.view.start_queue_button.clicked.connect(self.start_queue_processing)
        self.view.stop_queue_button.clicked.connect(self.stop_queue_processing)
        self.view.clear_queue_button.clicked.connect(self.clear_queue)
        self.view.remove_selected_button.clicked.connect(self.remove_selected_from_queue)

    def update_model_from_ui(self):
        """Coleta dados de todas as abas e atualiza o modelo."""
        for i in range(self.view.tabs.count()):
            tab = self.view.tabs.widget(i)
            if hasattr(tab, 'update_model_from_ui'):
                tab.update_model_from_ui()
        # Salva automaticamente em background
        self.model.save()

    def update_ui_from_model(self):
        """Atualiza a UI com os dados do modelo."""
        for i in range(self.view.tabs.count()):
            tab = self.view.tabs.widget(i)
            if hasattr(tab, 'update_ui_from_model'):
                tab.update_ui_from_model()

    def save_config(self):
        """Força a atualização do modelo e salva em disco."""
        self.update_model_from_ui()
        self.model.save()
        self.log_message("Configurações salvas.")

    def generate_single_video(self):
        """Inicia a geração de um único vídeo."""
        self.update_model_from_ui()
        if not self._validate_inputs(): return

        narration_path = Path(self.model.narration_path)
        output_folder = Path(self.model.output_folder)
        output_path = output_folder / f"{narration_path.stem}.mp4"

        params = asdict(self.model)
        params['out_path'] = str(output_path)

        self.thread = ProcessVideoThread(params)
        self.thread.progress.connect(lambda p: self.view.progress_bar.setValue(p))
        self.thread.finished.connect(self._on_single_process_finished)
        self.thread.start()

        self.view.generate_button.setEnabled(False)
        self.view.config_panel.setEnabled(False)
        self.log_message(f"Iniciando geração do vídeo: {output_path.name}")

    def _on_single_process_finished(self, success, message):
        self.view.generate_button.setEnabled(True)
        self.view.config_panel.setEnabled(True)
        self.view.progress_bar.setValue(100 if success else 0)

        if success:
            QMessageBox.information(self.view, "Sucesso", message)
            self.log_message(f"✅ Sucesso: {message}")
        else:
            QMessageBox.critical(self.view, "Erro", message)
            self.log_message(f"❌ Erro: {message}")

    def add_to_queue(self):
        """Adiciona um item à fila de processamento."""
        self.update_model_from_ui()
        if not self._validate_inputs(): return

        narration_path = Path(self.model.narration_path)
        output_folder = Path(self.model.output_folder)
        output_path = output_folder / f"{narration_path.stem}.mp4"

        # Prevenir duplicatas
        if any(item.narration_path == self.model.narration_path for item in self.queue_items):
            QMessageBox.warning(self.view, "Duplicado", "Este arquivo de narração já está na fila.")
            return

        item = QueueItem(
            narration_path=self.model.narration_path,
            output_path=str(output_path)
        )
        self.queue_items.append(item)
        self._update_queue_display()
        self.log_message(f"Adicionado à fila: {narration_path.name}")

    def start_queue_processing(self):
        """Inicia o processamento da fila."""
        if self.is_processing_queue:
            QMessageBox.warning(self.view, "Atenção", "A fila já está em processamento.")
            return

        pending_items = [item for item in self.queue_items if item.status == "waiting"]
        if not pending_items:
            QMessageBox.information(self.view, "Fila Vazia", "Não há itens pendentes para processar.")
            return

        self.is_processing_queue = True
        self._set_queue_ui_state(processing=True)

        base_params = asdict(self.model)
        self.queue_worker = QueueWorkerThread(self.queue_items, base_params)

        # Conectar sinais do worker
        self.queue_worker.item_started.connect(self._on_queue_item_started)
        self.queue_worker.item_progress.connect(self._on_queue_item_progress)
        self.queue_worker.item_finished.connect(self._on_queue_item_finished)
        self.queue_worker.queue_finished.connect(self._on_queue_finished)

        self.queue_worker.start()
        self.log_message(f"Iniciando processamento da fila com {len(pending_items)} itens.")

    def stop_queue_processing(self):
        if self.queue_worker and self.queue_worker.isRunning():
            self.queue_worker.stop()
            self.queue_worker.wait()  # Espera a thread terminar
        self._on_queue_finished(interrupted=True)
        self.log_message("Processamento da fila interrompido pelo usuário.")

    def clear_queue(self):
        if self.is_processing_queue:
            QMessageBox.warning(self.view, "Atenção", "Não é possível limpar a fila durante o processamento.")
            return

        reply = QMessageBox.question(self.view, "Confirmar", "Limpar toda a fila?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.queue_items.clear()
            self._update_queue_display()
            self.log_message("Fila limpa.")

    def remove_selected_from_queue(self):
        current_row = self.view.queue_list.currentRow()
        if current_row < 0: return

        if self.queue_items[current_row].status == "processing":
            QMessageBox.warning(self.view, "Atenção", "Não é possível remover um item em processamento.")
            return

        item = self.queue_items.pop(current_row)
        self._update_queue_display()
        self.log_message(f"Removido da fila: {Path(item.narration_path).name}")

    def _on_queue_item_started(self, index):
        self.queue_items[index].status = "processing"
        self._update_queue_display()
        self.log_message(f"Iniciando item {index + 1}/{len(self.queue_items)}...")

    def _on_queue_item_progress(self, index, percent):
        # Atualiza a barra de progresso global com o progresso total
        total_progress = 0
        processed_count = 0
        for i, item in enumerate(self.queue_items):
            if item.status == "completed":
                total_progress += 100
                processed_count += 1
            elif i == index:
                total_progress += percent

        overall_percent = total_progress / len(self.queue_items)
        self.view.progress_bar.setValue(int(overall_percent))

        # (Continuação da classe AppController)

        def _on_queue_item_finished(self, index, success, message):
            item = self.queue_items[index]
            item.status = "completed" if success else "error"
            item.error_message = "" if success else message
            self._update_queue_display()

            log_msg = f"✅ Item {index + 1} concluído." if success else f"❌ Erro no item {index + 1}: {message}"
            self.log_message(log_msg)

        def _on_queue_finished(self, interrupted=False):
            self.is_processing_queue = False
            self._set_queue_ui_state(processing=False)

            if interrupted:
                self.log_message("🏁 Processamento da fila interrompido.")
                return

            completed = sum(1 for item in self.queue_items if item.status == "completed")
            errors = sum(1 for item in self.queue_items if item.status == "error")

            self.log_message(f"🏁 Fila concluída: {completed} sucessos, {errors} erros.")
            QMessageBox.information(self.view, "Fila Concluída",
                                    f"Processamento da fila finalizado.\n\nSucessos: {completed}\nErros: {errors}")
            self.view.progress_bar.setValue(100)

        def _update_queue_display(self):
            """Atualiza a lista visual da fila."""
            self.view.queue_list.clear()
            status_map = {
                "waiting": ("🟡", QColor("#b0a800")),
                "processing": ("🔵", QColor("#007acc")),
                "completed": ("🟢", QColor("#009933")),
                "error": ("🔴", QColor("#cc3300")),
            }

            for item in self.queue_items:
                icon, color = status_map.get(item.status, ("❓", QColor("white")))
                narration_name = Path(item.narration_path).name
                list_item = f"{icon} {item.status.capitalize()} | {narration_name}"

                widget_item = QListWidgetItem(list_item)
                widget_item.setForeground(color)
                self.view.queue_list.addItem(widget_item)

        def _set_queue_ui_state(self, processing: bool):
            """Habilita/desabilita os controles da UI durante o processamento."""
            self.view.start_queue_button.setEnabled(not processing)
            self.view.stop_queue_button.setEnabled(processing)
            self.view.config_panel.setEnabled(not processing)
            self.view.generate_button.setEnabled(not processing)
            self.view.clear_queue_button.setEnabled(not processing)
            self.view.remove_selected_button.setEnabled(not processing)

            if not processing:
                self.view.progress_bar.setValue(0)

        def _validate_inputs(self) -> bool:
            """Valida os campos essenciais antes de iniciar uma tarefa."""
            if not self.model.narration_path or not Path(self.model.narration_path).exists():
                QMessageBox.warning(self.view, "Entrada Inválida",
                                    "Por favor, selecione um arquivo de narração válido.")
                return False
            if not self.model.videos_folder or not Path(self.model.videos_folder).is_dir():
                QMessageBox.warning(self.view, "Entrada Inválida",
                                    "Por favor, selecione uma pasta de vídeos/imagens válida.")
                return False
            if not self.model.output_folder or not Path(self.model.output_folder).is_dir():
                QMessageBox.warning(self.view, "Entrada Inválida", "Por favor, selecione uma pasta de destino válida.")
                return False
            return True

        def log_message(self, message: str):
            """Adiciona uma mensagem ao widget de log com timestamp."""
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.view.log_text.append(f"[{timestamp}] {message}")
            self.view.log_text.moveCursor(QTextCursor.MoveOperation.End)

    # --- PONTO DE ENTRADA DA APLICAÇÃO ---

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoGeneratorGUI()
    window.show()
    sys.exit(app.exec())


