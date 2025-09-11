# main.py
import sys
from PySide6.QtWidgets import QApplication

from models import ConfigModel
from ui_main_window import VideoGeneratorGUI
from app_controller import AppController


def main():
    """Ponto de entrada principal da aplicação."""
    app = QApplication(sys.argv)

    # 1. Carrega o modelo de dados
    model = ConfigModel.load()

    # 2. Cria a View (Janela Principal)
    view = VideoGeneratorGUI()

    # 3. Cria o Controller, conectando Model e View
    controller = AppController(view, model)

    # 4. Conecta os sinais e carrega os dados na UI
    controller.connect_signals()
    controller.update_ui_from_model()

    # 5. Exibe a janela e inicia o loop da aplicação
    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
