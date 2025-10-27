"""
Launcher GUI for Video FFmpeg Tools
Provides a central interface to launch different tools in the suite.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
from pathlib import Path
from typing import Callable


class LauncherApp(tk.Tk):
    """Main launcher application for video processing tools."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Video FFmpeg Tools - Launcher")
        self.geometry("1024x768")
        self.resizable(False, False)

        # Configure style
        self._configure_style()

        # Build UI
        self._build_ui()

        # Center window
        self._center_window()

    def _configure_style(self) -> None:
        """Configure the visual style of the application."""
        style = ttk.Style(self)
        style.theme_use('clam')

        # Configure colors
        bg_color = "#f0f0f0"
        accent_color = "#0078d4"

        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground=accent_color)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground="#666666")
        style.configure("Tool.TButton", font=("Segoe UI", 11), padding=15)

        self.configure(bg=bg_color)

    def _build_ui(self) -> None:
        """Build the user interface."""
        # Main container
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill="both", expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 20))

        title_label = ttk.Label(
            header_frame,
            text="Video FFmpeg Tools",
            style="Title.TLabel"
        )
        title_label.pack()

        subtitle_label = ttk.Label(
            header_frame,
            text="Selecione a ferramenta que deseja utilizar",
            style="Subtitle.TLabel"
        )
        subtitle_label.pack(pady=(5, 0))

        # Separator
        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

        # Tools section
        tools_frame = ttk.Frame(main_frame)
        tools_frame.pack(fill="both", expand=True, pady=10)

        # Tool 1: Video Generator (main.py)
        self._create_tool_card(
            tools_frame,
            title="🎬 Gerador de Vídeos",
            description="Interface principal para geração de vídeos\ncom imagens, áudio, legendas e efeitos",
            command=self._launch_main,
        )

        # Tool 2: Video Creator (video_creator.py)
        self._create_tool_card(
            tools_frame,
            title="🎞️ Criador de Vídeos",
            description="Crie vídeos a partir de imagens ou outros vídeos\ncom efeitos Ken Burns e transições",
            command=self._launch_video_creator,
        )

        # Tool 3: Whisper Subtitle Generator (whisper_subtitle_gui.py)
        self._create_tool_card(
            tools_frame,
            title="Whisper Subtitle Generator",
            description="Transcreva áudio para legendas SRT\nusando Whisper AI",
            command=self._launch_whisper,
        )

        # Footer
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill="x", pady=(20, 0))

        ttk.Separator(footer_frame, orient="horizontal").pack(fill="x", pady=(0, 10))

        exit_button = ttk.Button(
            footer_frame,
            text="Sair",
            command=self.quit,
            width=15
        )
        exit_button.pack(side="right")

        info_label = ttk.Label(
            footer_frame,
            text="Versão 1.0 | Python 3.12",
            style="Subtitle.TLabel"
        )
        info_label.pack(side="left")

    def _create_tool_card(
        self,
        parent: ttk.Frame,
        title: str,
        description: str,
        command: Callable
    ) -> None:
        """Create a tool card with title, description, and launch button."""
        # Card frame
        card_frame = ttk.LabelFrame(
            parent,
            text="",
            padding="15"
        )
        card_frame.pack(fill="x", pady=8)

        # Left side - info
        info_frame = ttk.Frame(card_frame)
        info_frame.pack(side="left", fill="both", expand=True)

        # Use tk.Label instead of ttk.Label for better text rendering
        title_label = tk.Label(
            info_frame,
            text=title,
            font=("Segoe UI", 12, "bold"),
            bg="#f0f0f0",
            anchor="w"
        )
        title_label.pack(anchor="w", fill="x")

        desc_label = tk.Label(
            info_frame,
            text=description,
            font=("Segoe UI", 9),
            fg="#666666",
            bg="#f0f0f0",
            anchor="w",
            justify="left"
        )
        desc_label.pack(anchor="w", pady=(5, 0), fill="x")

        # Right side - button
        button_frame = ttk.Frame(card_frame)
        button_frame.pack(side="right", padx=(10, 0))

        launch_button = ttk.Button(
            button_frame,
            text="Iniciar",
            command=command,
            style="Tool.TButton",
            width=12
        )
        launch_button.pack()

    def _center_window(self) -> None:
        """Center the window on the screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _launch_main(self) -> None:
        """Launch the main video generator application."""
        self._launch_script("main.py", "Gerador de Vídeos")

    def _launch_video_creator(self) -> None:
        """Launch the video creator application."""
        self._launch_script("video_creator.py", "Criador de Vídeos")

    def _launch_whisper(self) -> None:
        """Launch the Whisper subtitle generator application."""
        self._launch_script("whisper_subtitle_gui.py", "Gerador de Legendas")

    def _launch_script(self, script_name: str, app_name: str) -> None:
        """
        Launch a Python script in a new process.

        Args:
            script_name: Name of the Python script to launch
            app_name: Display name of the application
        """
        script_path = Path(__file__).parent / script_name

        if not script_path.exists():
            messagebox.showerror(
                "Erro",
                f"O arquivo {script_name} não foi encontrado.\n\n"
                f"Caminho esperado: {script_path}"
            )
            return

        try:
            # Launch in a new process without waiting
            if sys.platform == "win32":
                # Windows: use CREATE_NEW_CONSOLE to open in new window
                subprocess.Popen(
                    [sys.executable, str(script_path)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=script_path.parent
                )
            else:
                # Unix-like systems
                subprocess.Popen(
                    [sys.executable, str(script_path)],
                    cwd=script_path.parent
                )

            messagebox.showinfo(
                "Aplicação Iniciada",
                f"{app_name} foi iniciado em uma nova janela."
            )

        except Exception as e:
            messagebox.showerror(
                "Erro ao Iniciar",
                f"Não foi possível iniciar {app_name}.\n\n"
                f"Erro: {e}"
            )


def main() -> None:
    """Main entry point for the launcher application."""
    app = LauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
