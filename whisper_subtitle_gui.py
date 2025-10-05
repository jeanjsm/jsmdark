"""
Interface gráfica para transcrição de áudio em legendas SRT usando Whisper.
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from whisper_subtitle import transcribe_audio
from typing import Optional

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large", "turbo"]

class WhisperSubtitleGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Whisper Subtitle Generator")
        self.geometry("480x220")
        self.resizable(False, False)
        self.audio_path: Optional[str] = None
        self.model_var = tk.StringVar(value=WHISPER_MODELS[1])
        self._build_widgets()

    def _build_widgets(self) -> None:
        # File selection
        file_frame = tk.Frame(self)
        file_frame.pack(pady=16, padx=16, fill="x")
        tk.Label(file_frame, text="Arquivo de áudio:").pack(side="left")
        self.file_entry = tk.Entry(file_frame, width=40, state="readonly")
        self.file_entry.pack(side="left", padx=8)
        tk.Button(file_frame, text="Selecionar", command=self.select_file).pack(side="left")

        # Model selection
        model_frame = tk.Frame(self)
        model_frame.pack(pady=8, padx=16, fill="x")
        tk.Label(model_frame, text="Modelo Whisper:").pack(side="left")
        model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, values=WHISPER_MODELS, state="readonly", width=10)
        model_combo.pack(side="left", padx=8)

        # Process button
        process_btn = tk.Button(self, text="Processar", command=self.process, width=20)
        process_btn.pack(pady=16)

        # Status
        self.status_label = tk.Label(self, text="", fg="blue")
        self.status_label.pack(pady=4)

    def select_file(self) -> None:
        filetypes = [("Áudio", ".wav .mp3 .m4a .flac .ogg .aac .wma .opus .webm .mp4 .mkv .avi .mov .mpg .mpeg .mp2 .m4b .m4p .mpga .3gp .3g2 .amr .ts .m2ts .mxf .flv .wmv .aiff .alac .caf .dsf .wv .ape .tta .tak .dff .dsd .wv .mpc .spx .oga .ra .rm .ram .ac3 .au .snd .oga .opus .raw .pcm .wav .mp3 .m4a .flac .ogg .aac .wma .opus .webm .mp4 .mkv .avi .mov .mpg .mpeg .mp2 .m4b .m4p .mpga .3gp .3g2 .amr .ts .m2ts .mxf .flv .wmv .aiff .alac .caf .dsf .wv .ape .tta .tak .dff .dsd .wv .mpc .spx .oga .ra .rm .ram .ac3 .au .snd .oga .opus .raw .pcm"), ("Todos os arquivos", "*.*")]
        path = filedialog.askopenfilename(title="Selecione o arquivo de áudio", filetypes=filetypes)
        if path:
            self.audio_path = path
            self.file_entry.config(state="normal")
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, path)
            self.file_entry.config(state="readonly")
            self.status_label.config(text="")

    def process(self) -> None:
        if not self.audio_path:
            messagebox.showwarning("Aviso", "Selecione um arquivo de áudio.")
            return
        model = self.model_var.get()
        self.status_label.config(text="Processando... Aguarde.", fg="blue")
        self.update_idletasks()
        srt_path = transcribe_audio(self.audio_path, model_name=model)
        if srt_path:
            self.status_label.config(text=f"Legenda criada: {os.path.basename(srt_path)}", fg="green")
            messagebox.showinfo("Sucesso", f"Legenda criada:\n{srt_path}")
        else:
            self.status_label.config(text="Falha ao criar legenda.", fg="red")
            messagebox.showerror("Erro", "Falha ao criar legenda. Verifique o console para detalhes.")

def main() -> None:
    app = WhisperSubtitleGUI()
    app.mainloop()

if __name__ == "__main__":
    main()

