# save_slot_dialog.py
from typing import Optional, List, Dict
import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QLabel,
    QMessageBox,
    QInputDialog,
    QGroupBox,
    QFormLayout,
    QTextEdit,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from models import ConfigModel


class SaveSlotDialog(QDialog):
    """Dialog for managing configuration save slots.

    Signals:
        slot_selected: Emitted when a slot is selected for loading with slot name
        slot_saved: Emitted when a new slot is saved with slot name
    """

    slot_selected = Signal(str)
    slot_saved = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gerenciar Configurações Salvas")
        self.setModal(True)
        self.resize(600, 500)

        self._setup_ui()
        self._refresh_slots_list()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Gerenciar Save Slots")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Slots list group
        slots_group = QGroupBox("Configurações Salvas")
        slots_layout = QVBoxLayout(slots_group)

        self.slots_list = QListWidget()
        self.slots_list.itemDoubleClicked.connect(self._load_selected_slot)
        slots_layout.addWidget(self.slots_list)

        # Slot details
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Selecione um slot para ver detalhes...")
        slots_layout.addWidget(QLabel("Detalhes:"))
        slots_layout.addWidget(self.details_text)

        layout.addWidget(slots_group)

        # Buttons for slot management
        buttons_group = QGroupBox("Ações")
        buttons_layout = QVBoxLayout(buttons_group)

        # Row 1: Create new slot
        new_slot_layout = QHBoxLayout()
        self.new_slot_name = QLineEdit()
        self.new_slot_name.setPlaceholderText("Nome para nova configuração...")
        self.new_slot_name.returnPressed.connect(self._create_new_slot)

        self.create_button = QPushButton("Criar Novo Slot")
        self.create_button.clicked.connect(self._create_new_slot)

        new_slot_layout.addWidget(QLabel("Nome:"))
        new_slot_layout.addWidget(self.new_slot_name)
        new_slot_layout.addWidget(self.create_button)
        buttons_layout.addLayout(new_slot_layout)

        # Row 2: Load, Delete, Rename
        actions_layout = QHBoxLayout()

        self.load_button = QPushButton("Carregar Selecionado")
        self.load_button.clicked.connect(self._load_selected_slot)
        self.load_button.setEnabled(False)

        self.rename_button = QPushButton("Renomear")
        self.rename_button.clicked.connect(self._rename_selected_slot)
        self.rename_button.setEnabled(False)

        self.delete_button = QPushButton("Deletar")
        self.delete_button.clicked.connect(self._delete_selected_slot)
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet("QPushButton { color: red; }")

        actions_layout.addWidget(self.load_button)
        actions_layout.addWidget(self.rename_button)
        actions_layout.addWidget(self.delete_button)
        actions_layout.addStretch()
        buttons_layout.addLayout(actions_layout)

        layout.addWidget(buttons_group)

        # Dialog buttons
        dialog_buttons_layout = QHBoxLayout()

        self.refresh_button = QPushButton("Atualizar Lista")
        self.refresh_button.clicked.connect(self._refresh_slots_list)

        self.close_button = QPushButton("Fechar")
        self.close_button.clicked.connect(self.accept)

        dialog_buttons_layout.addWidget(self.refresh_button)
        dialog_buttons_layout.addStretch()
        dialog_buttons_layout.addWidget(self.close_button)
        layout.addLayout(dialog_buttons_layout)

        # Connect selection change
        self.slots_list.itemSelectionChanged.connect(self._on_selection_changed)

    def _refresh_slots_list(self) -> None:
        """Refresh the list of available save slots."""
        try:
            self.slots_list.clear()
            self.details_text.clear()

            slots = ConfigModel.list_save_slots()

            if not slots:
                item = QListWidgetItem("Nenhuma configuração salva encontrada.")
                item.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it unselectable
                self.slots_list.addItem(item)
                return

            for slot in slots:
                display_name = slot['name']
                created_at = datetime.fromisoformat(slot['created_at']).strftime("%d/%m/%Y %H:%M")

                item_text = f"{display_name} - ({created_at})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, slot)  # Store slot data
                self.slots_list.addItem(item)

        except Exception as exc:
            logging.error(f"Error refreshing slots list: {exc}")
            QMessageBox.warning(self, "Erro", f"Erro ao carregar lista de slots: {exc}")

    def _on_selection_changed(self) -> None:
        """Handle slot selection change."""
        current_item = self.slots_list.currentItem()
        has_selection = current_item is not None and current_item.flags() != Qt.ItemFlag.NoItemFlags

        self.load_button.setEnabled(has_selection)
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

        if has_selection:
            slot_data = current_item.data(Qt.UserRole)
            if slot_data:
                created_at = datetime.fromisoformat(slot_data['created_at']).strftime("%d/%m/%Y às %H:%M:%S")
                details = f"Nome: {slot_data['name']}\nCriado em: {created_at}\nArquivo: {slot_data['filename']}.json"
                self.details_text.setText(details)
        else:
            self.details_text.clear()

    def _create_new_slot(self) -> None:
        """Create a new save slot with current configuration."""
        slot_name = self.new_slot_name.text().strip()

        if not slot_name:
            QMessageBox.warning(self, "Nome Obrigatório", "Por favor, digite um nome para o novo slot.")
            return

        # Check if slot already exists
        existing_slots = ConfigModel.list_save_slots()
        for slot in existing_slots:
            if slot['name'].lower() == slot_name.lower():
                reply = QMessageBox.question(
                    self,
                    "Slot Já Existe",
                    f"Um slot com o nome '{slot_name}' já existe. Deseja substituí-lo?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
                break

        try:
            # Get current config from parent (assuming parent has model)
            parent_window = self.parent()
            if hasattr(parent_window, 'model'):
                # Update model with current UI values before saving
                if hasattr(parent_window, 'controller'):
                    parent_window.controller.update_model_from_ui()

                success = parent_window.model.save_slot(slot_name)

                if success:
                    QMessageBox.information(self, "Sucesso", f"Configuração salva como '{slot_name}'!")
                    self.new_slot_name.clear()
                    self._refresh_slots_list()
                    self.slot_saved.emit(slot_name)
                else:
                    QMessageBox.warning(self, "Erro", "Falha ao salvar a configuração.")
            else:
                QMessageBox.warning(self, "Erro", "Não foi possível acessar as configurações atuais.")

        except Exception as exc:
            logging.error(f"Error creating new slot: {exc}")
            QMessageBox.critical(self, "Erro", f"Erro ao criar novo slot: {exc}")

    def _load_selected_slot(self) -> None:
        """Load the selected save slot."""
        current_item = self.slots_list.currentItem()
        if not current_item or current_item.flags() == Qt.ItemFlag.NoItemFlags:
            return

        slot_data = current_item.data(Qt.UserRole)
        if not slot_data:
            return

        slot_name = slot_data['name']

        try:
            reply = QMessageBox.question(
                self,
                "Carregar Configuração",
                f"Deseja carregar a configuração '{slot_name}'?\n\nIsso substituirá as configurações atuais.",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.slot_selected.emit(slot_name)
                QMessageBox.information(self, "Sucesso", f"Configuração '{slot_name}' carregada!")
                self.accept()  # Close dialog

        except Exception as exc:
            logging.error(f"Error loading slot: {exc}")
            QMessageBox.critical(self, "Erro", f"Erro ao carregar configuração: {exc}")

    def _rename_selected_slot(self) -> None:
        """Rename the selected save slot."""
        current_item = self.slots_list.currentItem()
        if not current_item or current_item.flags() == Qt.ItemFlag.NoItemFlags:
            return

        slot_data = current_item.data(Qt.UserRole)
        if not slot_data:
            return

        old_name = slot_data['name']

        new_name, ok = QInputDialog.getText(
            self,
            "Renomear Slot",
            f"Novo nome para '{old_name}':",
            text=old_name
        )

        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        if new_name == old_name:
            return

        try:
            # Load the slot, then save with new name, then delete old
            config = ConfigModel.load_slot(old_name)
            success = config.save_slot(new_name)

            if success:
                # Delete the old slot
                ConfigModel.delete_save_slot(old_name)
                QMessageBox.information(self, "Sucesso", f"Slot renomeado para '{new_name}'!")
                self._refresh_slots_list()
            else:
                QMessageBox.warning(self, "Erro", "Falha ao renomear o slot.")

        except Exception as exc:
            logging.error(f"Error renaming slot: {exc}")
            QMessageBox.critical(self, "Erro", f"Erro ao renomear slot: {exc}")

    def _delete_selected_slot(self) -> None:
        """Delete the selected save slot."""
        current_item = self.slots_list.currentItem()
        if not current_item or current_item.flags() == Qt.ItemFlag.NoItemFlags:
            return

        slot_data = current_item.data(Qt.UserRole)
        if not slot_data:
            return

        slot_name = slot_data['name']

        try:
            reply = QMessageBox.question(
                self,
                "Deletar Slot",
                f"Tem certeza que deseja deletar a configuração '{slot_name}'?\n\nEsta ação não pode ser desfeita.",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                success = ConfigModel.delete_save_slot(slot_name)

                if success:
                    QMessageBox.information(self, "Sucesso", f"Configuração '{slot_name}' deletada!")
                    self._refresh_slots_list()
                else:
                    QMessageBox.warning(self, "Erro", "Falha ao deletar a configuração.")

        except Exception as exc:
            logging.error(f"Error deleting slot: {exc}")
            QMessageBox.critical(self, "Erro", f"Erro ao deletar slot: {exc}")
