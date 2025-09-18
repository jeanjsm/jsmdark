import logging
# app_controller.py
from dataclasses import asdict
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QMessageBox,
    QListWidgetItem,
    QLineEdit,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QFileDialog,
)
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtCore import QObject
from models import ConfigModel, QueueItem, ChromaConfig
from ui_main_window import VideoGeneratorGUI
from threads import ProcessVideoThread, QueueWorkerThread
from ui_tabs import FileBrowseWidget, ChromaItemWidget


class AppController(QObject):
    """Controller for the main application logic, connecting the view and model.

    Attributes:
        view (VideoGeneratorGUI): The main window view.
        model (ConfigModel): The data model.
        queue_items (list[QueueItem]): List of items in the processing queue.
        queue_worker: Worker thread for queue processing.
        is_processing_queue (bool): Whether the queue is being processed.
        chroma_widgets (list[ChromaItemWidget]): List of chroma widgets.
    """
    def __init__(self, view: VideoGeneratorGUI, model: ConfigModel) -> None:
        """Initialize the AppController.

        Args:
            view (VideoGeneratorGUI): The main window view.
            model (ConfigModel): The data model.
        """
        super().__init__()
        self.view = view
        self.model = model
        self.queue_items: list[QueueItem] = []
        self.queue_worker = None
        self.is_processing_queue = False
        self.chroma_widgets: list[ChromaItemWidget] = []

    def connect_signals(self) -> None:
        """Connects UI signals to controller methods."""
        self.view.generate_button.clicked.connect(self.generate_single_video)
        self.view.add_to_queue_button.clicked.connect(self.add_to_queue)
        self.view.save_config_button.clicked.connect(self.save_config)
        self.view.start_queue_button.clicked.connect(self.start_queue_processing)
        self.view.stop_queue_button.clicked.connect(self.stop_queue_processing)
        self.view.clear_queue_button.clicked.connect(self.clear_queue)
        self.view.remove_selected_button.clicked.connect(
            self.remove_selected_from_queue
        )
        self.view.video_tab.add_opening_button.clicked.connect(self._add_opening_video)
        self.view.video_tab.remove_opening_button.clicked.connect(
            self._remove_opening_video
        )
        self.view.overlay_tab.add_chroma_btn.clicked.connect(
            lambda: self._add_chroma_widget()
        )
        # Conecta o evento de alteração do preset de legendas
        self.view.subtitle_tab.subtitle_preset.currentTextChanged.connect(
            self._on_subtitle_preset_change
        )

        self.view.closeEvent = self.on_close_window

    def _on_subtitle_preset_change(self, preset: str) -> None:
        """Event handler for subtitle preset change.

        Args:
            preset (str): The selected subtitle preset.
        """
        if preset == "personalizado":
            return

        # Já implementamos a lógica de atualização na classe SubtitleTab
        # Este método só garante que o modelo será atualizado após a mudança
        # para que possa ser salvo corretamente
        self.update_model_from_ui()

    def _prepare_params_for_function(self) -> dict:
        """Prepara o dicionário de parâmetros para ser compatível com a função original."""
        self.update_model_from_ui()
        params = self.model.to_dict()

        # Remover chaves que são apenas da UI e não da função de processamento
        params.pop("output_folder", None)
        params.pop("resolution_preset", None)

        # Converter a lista de ChromaConfig para uma lista de dicionários
        params["chroma_list"] = [asdict(c) for c in self.model.chroma_list]

        return params

    def generate_single_video(self):
        if not self._validate_inputs():
            return

        params = self._prepare_params_for_function()

        # Construir o caminho de saída completo
        narration_path = Path(self.model.narration_path)
        output_folder = Path(self.model.output_folder)
        out_path_full = str(output_folder / f"{narration_path.stem}.mp4")
        params["out_path"] = out_path_full

        self.thread = ProcessVideoThread(params)
        self.thread.progress.connect(lambda p: self.view.progress_bar.setValue(p))
        self.thread.finished.connect(self._on_single_process_finished)
        self.thread.start()
        self._set_ui_enabled(False)
        self.log_message(f"Iniciando geração do vídeo: {Path(out_path_full).name}")

    def start_queue_processing(self):
        if self.is_processing_queue:
            return
        pending_items = [item for item in self.queue_items if item.status == "waiting"]
        if not pending_items:
            QMessageBox.information(
                self.view, "Fila Vazia", "Não há itens pendentes para processar."
            )
            return

        base_params = self._prepare_params_for_function()
        self.is_processing_queue = True
        self._set_ui_enabled(False)
        self.queue_worker = QueueWorkerThread(self.queue_items, base_params)
        self.queue_worker.item_started.connect(self._on_queue_item_started)
        self.queue_worker.item_progress.connect(self._on_queue_item_progress)
        self.queue_worker.item_finished.connect(self._on_queue_item_finished)
        self.queue_worker.queue_finished.connect(self._on_queue_finished)
        self.queue_worker.start()
        self.log_message(
            f"Iniciando processamento da fila com {len(pending_items)} itens."
        )

    def add_to_queue(self):
        self.update_model_from_ui()
        if not self._validate_inputs():
            return
        narration_path = Path(self.model.narration_path)
        output_folder = Path(self.model.output_folder)
        output_path = str(output_folder / f"{narration_path.stem}.mp4")
        if any(
            item.narration_path == self.model.narration_path
            for item in self.queue_items
        ):
            QMessageBox.warning(
                self.view, "Duplicado", "Este arquivo de narração já está na fila."
            )
            return
        item = QueueItem(
            narration_path=self.model.narration_path, output_path=output_path
        )
        self.queue_items.append(item)
        self._update_queue_display()
        self.log_message(f"Adicionado à fila: {narration_path.name}")

    def save_config(self):
        # Atualiza modelo com valores da UI
        self.update_model_from_ui()
        # Sincroniza width/height do VideoTab
        self.model.width = self.view.video_tab.width.value()
        self.model.height = self.view.video_tab.height.value()
        self.model.fps = self.view.video_tab.fps.value()
        # Garante que o seed seja None quando for -1
        if hasattr(self.view.basic_tab, 'seed') and self.view.basic_tab.seed.value() == -1:
            self.model.seed = None
        self.model.save()
        self.log_message("✅ Configurações salvas em config.json")

    def on_close_window(self, event):
        self.save_config()
        event.accept()

    # --- Métodos de atualização e gerenciamento (sem alterações na lógica interna) ---
    def update_model_from_ui(self):
        for field_name in self.model.__annotations__:
            if field_name in ["opening_video_paths", "chroma_list"]:
                continue
            if field_name == "camera_shake_config":
                self.model.camera_shake_config.enabled = (
                    self.view.subtitle_tab.camera_shake_enabled.isChecked()
                )
                self.model.camera_shake_config.intensity = (
                    self.view.subtitle_tab.camera_shake_intensity.value()
                )
                self.model.camera_shake_config.frequency = (
                    self.view.subtitle_tab.camera_shake_frequency.value()
                )
                self.model.camera_shake_config.duration = (
                    self.view.subtitle_tab.camera_shake_duration.value()
                )
                continue
            widget = self._find_widget_for_field(field_name)
            if not widget:
                continue
            value = None
            if isinstance(widget, (QLineEdit, FileBrowseWidget)):
                value = widget.text()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
                # Tratamento especial para o campo "seed"
                if field_name == "seed" and value == -1:
                    value = None
            elif isinstance(widget, QDoubleSpinBox):
                value = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
            if value is not None and hasattr(self.model, field_name):
                setattr(self.model, field_name, value)
        self._update_chroma_list_from_ui()

    def update_ui_from_model(self):
        for field_name in self.model.__annotations__:
            if field_name in ["opening_video_paths", "chroma_list"]:
                continue
            if field_name == "camera_shake_config":
                config = self.model.camera_shake_config
                self.view.subtitle_tab.camera_shake_enabled.setChecked(config.enabled)
                self.view.subtitle_tab.camera_shake_intensity.setValue(config.intensity)
                self.view.subtitle_tab.camera_shake_frequency.setValue(config.frequency)
                self.view.subtitle_tab.camera_shake_duration.setValue(config.duration)
                continue
            widget = self._find_widget_for_field(field_name)
            if not widget:
                continue
            value = getattr(self.model, field_name)
            if isinstance(widget, (QLineEdit, FileBrowseWidget)):
                widget.setText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QSpinBox):
                # Tratamento especial para o campo "seed"
                if field_name == "seed" and value is None:
                    widget.setValue(-1)
                else:
                    widget.setValue(int(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
        self._update_opening_videos_display()
        self._update_ui_from_chroma_list()

    def _find_widget_for_field(self, field_name: str):
        if field_name.startswith("camera_shake_"):
            sub_field = field_name.replace("camera_shake_", "")
            if hasattr(self.view.subtitle_tab, f"camera_shake_{sub_field}"):
                return getattr(self.view.subtitle_tab, f"camera_shake_{sub_field}")
        for tab in [
            self.view.basic_tab,
            self.view.video_tab,
            self.view.overlay_tab,
            self.view.subtitle_tab,
        ]:
            if hasattr(tab, field_name):
                return getattr(tab, field_name)
        return None

    def _add_chroma_widget(self, config: ChromaConfig = None):
        if config is None:
            config = ChromaConfig()
        index = len(self.chroma_widgets)
        chroma_widget = ChromaItemWidget(index)
        chroma_widget.path.setText(config.path)
        chroma_widget.scale.setValue(config.scale)
        chroma_widget.position.setCurrentText(config.position)
        chroma_widget.start.setValue(config.start)
        chroma_widget.remove_clicked.connect(self._remove_chroma_widget)
        self.view.overlay_tab.chroma_list_layout.addWidget(chroma_widget)
        self.chroma_widgets.append(chroma_widget)

    def _remove_chroma_widget(self, widget_to_remove: ChromaItemWidget):
        widget_to_remove.deleteLater()
        self.chroma_widgets.remove(widget_to_remove)
        for i, widget in enumerate(self.chroma_widgets):
            widget.setTitle(f"Chroma Key #{i + 1}")

    def _update_chroma_list_from_ui(self):
        self.model.chroma_list.clear()
        for widget in self.chroma_widgets:
            self.model.chroma_list.append(
                ChromaConfig(
                    path=widget.path.text(),
                    scale=widget.scale.value(),
                    position=widget.position.currentText(),
                    start=widget.start.value(),
                )
            )

    def _update_ui_from_chroma_list(self):
        for widget in self.chroma_widgets:
            widget.deleteLater()
        self.chroma_widgets.clear()
        for config in self.model.chroma_list:
            self._add_chroma_widget(config)

    def _on_single_process_finished(self, success, message):
        self._set_ui_enabled(True)
        self.view.progress_bar.setValue(100 if success else 0)
        if success:
            QMessageBox.information(self.view, "Sucesso", message)
            self.log_message(f"✅ Sucesso: {message}")
        else:
            QMessageBox.critical(self.view, "Erro", message)
            self.log_message(f"❌ Erro: {message}")

    def stop_queue_processing(self):
        if self.queue_worker and self.queue_worker.isRunning():
            self.queue_worker.stop()
            self.queue_worker.wait()
        self._on_queue_finished(interrupted=True)

    def clear_queue(self):
        if self.is_processing_queue:
            return
        if (
            QMessageBox.question(
                self.view,
                "Confirmar",
                "Limpar toda a fila?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.queue_items.clear()
            self._update_queue_display()
            self.log_message("Fila limpa.")

    def remove_selected_from_queue(self):
        current_row = self.view.queue_list.currentRow()
        if current_row < 0 or self.queue_items[current_row].status == "processing":
            return
        item = self.queue_items.pop(current_row)
        self._update_queue_display()
        self.log_message(f"Removido da fila: {Path(item.narration_path).name}")

    def _on_queue_item_started(self, index):
        if index < len(self.queue_items):
            self.queue_items[index].status = "processing"
            self._update_queue_display()
            self.log_message(f"Iniciando item {index + 1}/{len(self.queue_items)}...")

    def _on_queue_item_progress(self, index, percent):
        processed_count = sum(
            1 for item in self.queue_items if item.status == "completed"
        )
        total_progress = processed_count * 100
        if (
            index < len(self.queue_items)
            and self.queue_items[index].status == "processing"
        ):
            total_progress += percent
        num_items = len(self.queue_items)
        self.view.progress_bar.setValue(
            int(total_progress / num_items if num_items > 0 else 0)
        )

    def _on_queue_item_finished(self, index, success, message):
        if index < len(self.queue_items):
            item = self.queue_items[index]
            item.status = "completed" if success else "error"
            item.error_message = "" if success else message
            self._update_queue_display()
            self.log_message(
                f"✅ Item {index + 1} concluído."
                if success
                else f"❌ Erro no item {index + 1}: {message}"
            )

    def _on_queue_finished(self, interrupted=False):
        self.is_processing_queue = False
        self._set_ui_enabled(True)
        if interrupted:
            self.log_message("Processamento da fila interrompido.")
            return
        completed = sum(1 for item in self.queue_items if item.status == "completed")
        errors = sum(1 for item in self.queue_items if item.status == "error")
        self.log_message(f"🏁 Fila concluída: {completed} sucessos, {errors} erros.")
        QMessageBox.information(
            self.view,
            "Fila Concluída",
            f"Processamento finalizado.\nSucessos: {completed}\nErros: {errors}",
        )
        if len(self.queue_items) > 0 and errors == 0:
            self.view.progress_bar.setValue(100)

    def _update_queue_display(self):
        self.view.queue_list.clear()
        status_map = {
            "waiting": "🟡",
            "processing": "🔵",
            "completed": "🟢",
            "error": "🔴",
        }
        for item in self.queue_items:
            self.view.queue_list.addItem(
                f"{status_map.get(item.status, '❓')} {item.status.capitalize()} | {Path(item.narration_path).name}"
            )

    def _set_ui_enabled(self, enabled: bool):
        self.view.config_panel.setEnabled(enabled)
        self.view.start_queue_button.setEnabled(enabled)
        self.view.stop_queue_button.setEnabled(not enabled)
        if not enabled:
            self.view.progress_bar.setValue(0)

    def _validate_inputs(self) -> bool:
        self.update_model_from_ui()
        if (
            not self.model.narration_path
            or not Path(self.model.narration_path).exists()
        ):
            QMessageBox.warning(
                self.view,
                "Entrada Inválida",
                "Selecione um arquivo de narração válido.",
            )
            return False
        if not self.model.videos_folder or not Path(self.model.videos_folder).is_dir():
            QMessageBox.warning(
                self.view, "Entrada Inválida", "Selecione uma pasta de mídia válida."
            )
            return False
        if not self.model.output_folder:
            QMessageBox.warning(
                self.view, "Entrada Inválida", "Selecione uma pasta de destino válida."
            )
            return False
        try:
            Path(self.model.output_folder).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(
                self.view,
                "Entrada Inválida",
                f"Não foi possível criar a pasta de destino.\nErro: {e}",
            )
            return False
        return True

    def log_message(self, message: str):
        self.view.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.view.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def _add_opening_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self.view, "Selecionar Vídeo de Abertura", "", "Vídeos (*.mp4 *.mov)"
        )
        if path and path not in self.model.opening_video_paths:
            self.model.opening_video_paths.append(path)
            self._update_opening_videos_display()

    def _remove_opening_video(self):
        selected_items = self.view.video_tab.opening_video_paths_widget.selectedItems()
        if not selected_items:
            return
        path_to_remove = selected_items[0].text()
        if path_to_remove in self.model.opening_video_paths:
            self.model.opening_video_paths.remove(path_to_remove)
            self._update_opening_videos_display()

    def _update_opening_videos_display(self):
        widget = self.view.video_tab.opening_video_paths_widget
        widget.clear()
        for path in self.model.opening_video_paths:
            widget.addItem(path)
