"""
Interface gráfica para transcrição de áudio em legendas SRT usando Whisper ou faster-whisper.
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from whisper_subtitle import transcribe_audio, get_whisper_info, get_available_models
from typing import Optional
import threading

class WhisperSubtitleGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Whisper Subtitle Generator")
        self.geometry("520x300")
        self.resizable(False, False)
        self.audio_path: Optional[str] = None

        # Get available models and whisper info
        self.whisper_info = get_whisper_info()
        self.models = get_available_models()

        # Variables
        self.model_var = tk.StringVar(value=self.models[1])  # Default to "base"
        self.use_fast_whisper_var = tk.BooleanVar(value=self.whisper_info["fast_whisper_available"])

        self._build_widgets()
        self._update_whisper_status()

    def _build_widgets(self) -> None:
        main_frame = tk.Frame(self)
        main_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Whisper implementation status
        status_frame = tk.LabelFrame(main_frame, text="Status do Whisper", padx=10, pady=5)
        status_frame.pack(fill="x", pady=(0, 10))

        self.status_text = tk.Text(status_frame, height=3, width=60, state="disabled",
                                  bg=self.cget("bg"), relief="flat")
        self.status_text.pack(fill="x")

        # File selection
        file_frame = tk.LabelFrame(main_frame, text="Seleção de Arquivo", padx=10, pady=5)
        file_frame.pack(fill="x", pady=(0, 10))

        file_inner = tk.Frame(file_frame)
        file_inner.pack(fill="x")

        tk.Label(file_inner, text="Arquivo de áudio:").pack(side="left")
        self.file_entry = tk.Entry(file_inner, width=35, state="readonly")
        self.file_entry.pack(side="left", padx=(8, 4), fill="x", expand=True)
        tk.Button(file_inner, text="Selecionar", command=self.select_file).pack(side="left")

        # Configuration
        config_frame = tk.LabelFrame(main_frame, text="Configurações", padx=10, pady=5)
        config_frame.pack(fill="x", pady=(0, 10))

        # Model selection
        model_frame = tk.Frame(config_frame)
        model_frame.pack(fill="x", pady=(0, 5))
        tk.Label(model_frame, text="Modelo Whisper:").pack(side="left")
        model_combo = ttk.Combobox(model_frame, textvariable=self.model_var,
                                  values=self.models, state="readonly", width=12)
        model_combo.pack(side="left", padx=(8, 0))

        # Implementation selection
        impl_frame = tk.Frame(config_frame)
        impl_frame.pack(fill="x")

        self.fast_whisper_check = tk.Checkbutton(
            impl_frame,
            text="Usar faster-whisper (mais rápido)",
            variable=self.use_fast_whisper_var,
            command=self._on_implementation_changed
        )
        self.fast_whisper_check.pack(side="left")

        # Process button and progress
        action_frame = tk.Frame(main_frame)
        action_frame.pack(fill="x", pady=(10, 0))

        self.process_btn = tk.Button(action_frame, text="Processar",
                                   command=self.process, width=20, height=2)
        self.process_btn.pack(pady=(0, 5))

        # Progress bar
        self.progress = ttk.Progressbar(action_frame, mode='indeterminate')
        self.progress.pack(fill="x", pady=(0, 5))

        # Status label
        self.status_label = tk.Label(action_frame, text="", fg="blue")
        self.status_label.pack()

    def _update_whisper_status(self) -> None:
        """Update the status display with available Whisper implementations."""
        self.status_text.config(state="normal")
        self.status_text.delete(1.0, tk.END)

        status_lines = []
        if self.whisper_info["fast_whisper_available"]:
            status_lines.append("✅ faster-whisper disponível (recomendado para velocidade)")
        else:
            status_lines.append("❌ faster-whisper não instalado")

        if self.whisper_info["whisper_available"]:
            status_lines.append("✅ openai-whisper disponível (mais compatível)")
        else:
            status_lines.append("❌ openai-whisper não instalado")

        if not any([self.whisper_info["fast_whisper_available"],
                   self.whisper_info["whisper_available"]]):
            status_lines.append("⚠️  NENHUMA implementação encontrada!")
            status_lines.append("📦 Instale: pip install openai-whisper (recomendado)")

        self.status_text.insert(1.0, "\n".join(status_lines))
        self.status_text.config(state="disabled")

        # Update checkbox state
        if not self.whisper_info["fast_whisper_available"]:
            self.fast_whisper_check.config(state="disabled")
            self.use_fast_whisper_var.set(False)

    def _on_implementation_changed(self) -> None:
        """Handle implementation selection change."""
        if self.use_fast_whisper_var.get() and not self.whisper_info["fast_whisper_available"]:
            messagebox.showwarning(
                "Aviso",
                "faster-whisper não está instalado.\n\n"
                "Para instalá-lo, execute:\n"
                "pip install faster-whisper"
            )
            self.use_fast_whisper_var.set(False)

    def select_file(self) -> None:
        """Open file dialog to select audio file."""
        audio_extensions = [
            ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus",
            ".webm", ".mp4", ".mkv", ".avi", ".mov", ".mpg", ".mpeg", ".mp2",
            ".m4b", ".m4p", ".mpga", ".3gp", ".3g2", ".amr", ".ts", ".m2ts",
            ".mxf", ".flv", ".wmv", ".aiff", ".alac", ".caf", ".dsf", ".wv",
            ".ape", ".tta", ".tak", ".dff", ".dsd", ".mpc", ".spx", ".oga",
            ".ra", ".rm", ".ram", ".ac3", ".au", ".snd", ".raw", ".pcm"
        ]

        filetypes = [
            ("Arquivos de áudio", " ".join([f"*{ext}" for ext in audio_extensions])),
            ("Todos os arquivos", "*.*")
        ]

        path = filedialog.askopenfilename(
            title="Selecione o arquivo de áudio",
            filetypes=filetypes
        )

        if path:
            self.audio_path = path
            self.file_entry.config(state="normal")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, path)
            self.file_entry.config(state="readonly")
            self.status_label.config(text="")

    def _process_audio_thread(self) -> None:
        """Process audio in a separate thread to avoid freezing the GUI."""
        try:
            model = self.model_var.get()
            use_fast = self.use_fast_whisper_var.get()

            srt_path = transcribe_audio(
                self.audio_path,
                model_name=model,
                use_fast_whisper=use_fast
            )

            # Update GUI in main thread
            self.after(0, self._process_complete, srt_path)

        except Exception as e:
            self.after(0, self._process_error, str(e))

    def _process_complete(self, srt_path: Optional[str]) -> None:
        """Handle successful processing."""
        self.progress.stop()
        self.process_btn.config(state="normal")

        if srt_path:
            filename = os.path.basename(srt_path)
            self.status_label.config(text=f"Legenda criada: {filename}", fg="green")
            messagebox.showinfo("Sucesso", f"Legenda criada:\n{srt_path}")
        else:
            self.status_label.config(text="Falha ao criar legenda.", fg="red")
            messagebox.showerror("Erro", "Falha ao criar legenda. Verifique o console para detalhes.")

    def _process_error(self, error_msg: str) -> None:
        """Handle processing error."""
        self.progress.stop()
        self.process_btn.config(state="normal")
        self.status_label.config(text="Erro durante o processamento.", fg="red")
        messagebox.showerror("Erro", f"Erro durante o processamento:\n{error_msg}")

    def process(self) -> None:
        """Start audio processing."""
        if not self.audio_path:
            messagebox.showwarning("Aviso", "Selecione um arquivo de áudio.")
            return

        # Check if any Whisper implementation is available
        if not any([self.whisper_info["fast_whisper_available"],
                   self.whisper_info["whisper_available"]]):
            messagebox.showerror(
                "Erro",
                "Nenhuma implementação do Whisper está disponível.\n\n"
                "Instale uma das seguintes opções:\n"
                "• pip install faster-whisper (recomendado)\n"
                "• pip install openai-whisper"
            )
            return

        # Check if selected implementation is available
        if (self.use_fast_whisper_var.get() and
            not self.whisper_info["fast_whisper_available"]):
            messagebox.showerror(
                "Erro",
                "faster-whisper selecionado mas não está instalado.\n\n"
                "Para instalá-lo: pip install faster-whisper"
            )
            return

        # Start processing
        impl_name = "faster-whisper" if self.use_fast_whisper_var.get() else "openai-whisper"
        model = self.model_var.get()

        self.status_label.config(
            text=f"Processando com {impl_name} (modelo: {model})... Aguarde.",
            fg="blue"
        )

        self.progress.start()
        self.process_btn.config(state="disabled")

        # Start processing in a separate thread
        thread = threading.Thread(target=self._process_audio_thread, daemon=True)
        thread.start()

def main() -> None:
    """Run the GUI application."""
    app = WhisperSubtitleGUI()
    app.mainloop()

if __name__ == "__main__":
    main()