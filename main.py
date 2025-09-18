# main.py
import sys
from PySide6.QtWidgets import QApplication

from models import ConfigModel
from ui_main_window import VideoGeneratorGUI
from app_controller import AppController


def main() -> None:
    """Main entry point for the application.

    Sets up the QApplication, loads the model, creates the view and controller,
    connects signals, updates the UI, and starts the event loop.
    """
    app = QApplication(sys.argv)

    # 1. Load the data model
    model = ConfigModel.load()

    # 2. Create the main window (View)
    view = VideoGeneratorGUI()

    # 3. Create the Controller, connecting Model and View
    controller = AppController(view, model)

    # 4. Connect signals and load data into the UI
    controller.connect_signals()
    controller.update_ui_from_model()

    # 5. Show the window and start the application loop
    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
