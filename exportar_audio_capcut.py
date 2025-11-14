import sys
import os
import json
import subprocess
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QFileDialog,
                             QTextEdit, QProgressBar, QGroupBox, QFormLayout)
from PySide6.QtCore import QThread, Signal


class AudioProcessorThread(QThread):
    progress_signal = Signal(str)
    progress_bar_signal = Signal(int)
    finished_signal = Signal(bool, str)

    def __init__(self, json_path, output_path):
        super().__init__()
        self.json_path = json_path
        self.output_path = output_path
        self.project_folder = os.path.dirname(json_path)
        self.text_reading_folder = os.path.join(self.project_folder, 'textReading')
        self.temp_dir = os.path.join(output_path, 'temp_audio_files')

    def run(self):
        try:
            if not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir)

            self.progress_signal.emit("Lendo arquivo JSON do projeto...")
            self.progress_bar_signal.emit(10)
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            audio_map = {}
            if 'materials' in data and 'audios' in data['materials']:
                for audio in data['materials']['audios']:
                    if 'path' in audio and 'textReading/' in audio['path']:
                        audio_map[audio['id']] = audio['path']

            if not audio_map:
                self.finished_signal.emit(False,
                                          "Nenhuma referência a áudios de 'textReading' foi encontrada em 'materials.audios' no JSON.")
                return

            # Extração na ordem natural dos segmentos
            audio_segments = []
            for track in data.get('tracks', []):
                if track.get('type') == 'audio':
                    for segment in track.get('segments', []):
                        material_id = segment.get('material_id')
                        if material_id in audio_map:
                            relative_path = audio_map[material_id]
                            audio_segments.append(relative_path)

            ordered_audio_files = [os.path.join(self.text_reading_folder, os.path.basename(path)) for path in audio_segments]

            if not ordered_audio_files:
                self.finished_signal.emit(False,
                                          "Nenhum segmento de áudio de 'textReading' foi encontrado na timeline do projeto.")
                return

            self.progress_signal.emit(
                f"Encontrados {len(ordered_audio_files)} arquivos de áudio. Concatenando na ordem do JSON...")
            self.progress_bar_signal.emit(20)

            project_name = os.path.splitext(os.path.basename(self.json_path))[0]
            concatenated_audio_path = os.path.join(self.temp_dir, f"{project_name}_concatenated.wav")

            self.progress_signal.emit("Juntando arquivos de áudio...")
            file_list_path = os.path.join(self.temp_dir, 'filelist.txt')

            found_files_count = 0
            with open(file_list_path, 'w', encoding='utf-8') as f:
                for audio_file in ordered_audio_files:
                    if os.path.exists(audio_file):
                        f.write(f"file '{os.path.abspath(audio_file)}'\n")
                        found_files_count += 1
                    else:
                        self.progress_signal.emit(f"AVISO: Arquivo de áudio não encontrado: {audio_file}")

            if found_files_count == 0:
                self.finished_signal.emit(False,
                                          "Nenhum dos arquivos de áudio listados no JSON foi encontrado no disco.")
                return

            command = [
                'ffmpeg', '-f', 'concat', '-safe', '0', '-i', file_list_path,
                '-y', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2', concatenated_audio_path
            ]

            subprocess.run(command, check=True, capture_output=True, text=True)
            self.progress_signal.emit("Áudios juntados com sucesso.")
            self.progress_bar_signal.emit(50)

            self.progress_signal.emit("Removendo silêncios do áudio...")
            final_output_path = os.path.join(self.output_path, f"{project_name}_sem_silencio.mp3")

            command_remove_silence = [
                'ffmpeg', '-i', concatenated_audio_path,
                '-af', 'silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-30dB',
                '-y', final_output_path
            ]

            subprocess.run(command_remove_silence, check=True, capture_output=True, text=True)

            self.progress_signal.emit("Silêncios removidos com sucesso!")
            self.progress_bar_signal.emit(100)
            self.finished_signal.emit(True, f"Processo concluído! Áudio final salvo em:\n{final_output_path}")

        except subprocess.CalledProcessError as e:
            error_message = f"Ocorreu um erro com o FFmpeg:\n"
            error_message += f"Comando: {' '.join(e.cmd)}\n"
            error_message += f"Stderr: {e.stderr}"
            self.finished_signal.emit(False, error_message)
        except Exception as e:
            import traceback
            self.finished_signal.emit(False, f"Ocorreu um erro inesperado: {str(e)}\n{traceback.format_exc()}")
        finally:
            try:
                if os.path.exists(self.temp_dir):
                    import shutil
                    shutil.rmtree(self.temp_dir)
                    self.progress_signal.emit("Arquivos temporários limpos.")
            except Exception as e:
                self.progress_signal.emit(f"Erro ao limpar arquivos temporários: {e}")


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('CapCut Audio Exporter')
        self.setGeometry(100, 100, 700, 500)
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()

        input_group = QGroupBox("Arquivos de Entrada")
        form_layout = QFormLayout()

        self.json_path_edit = QLineEdit()
        self.json_path_button = QPushButton("Selecionar")
        self.json_path_button.clicked.connect(self.select_json_file)

        self.output_path_edit = QLineEdit()
        self.output_path_button = QPushButton("Selecionar")
        self.output_path_button.clicked.connect(self.select_output_folder)

        json_layout = QHBoxLayout()
        json_layout.addWidget(self.json_path_edit)
        json_layout.addWidget(self.json_path_button)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.output_path_button)

        form_layout.addRow("JSON do Projeto:", json_layout)
        form_layout.addRow("Pasta de Saída:", output_layout)
        input_group.setLayout(form_layout)

        log_group = QGroupBox("Log de Processamento")
        log_layout = QVBoxLayout()
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_layout.addWidget(self.log_edit)
        log_group.setLayout(log_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        self.process_button = QPushButton("🚀 PROCESSAR ÁUDIOS")
        self.process_button.setFixedHeight(40)
        self.process_button.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.process_button.clicked.connect(self.start_processing)

        main_layout.addWidget(input_group)
        main_layout.addWidget(log_group)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.process_button)

        self.setLayout(main_layout)

    def select_json_file(self):
        default_path = os.path.expanduser("~\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft")
        fname, _ = QFileDialog.getOpenFileName(self, 'Selecione o arquivo JSON do projeto', default_path,
                                               'JSON files (*.json)')
        if fname:
            self.json_path_edit.setText(fname)
            if not self.output_path_edit.text():
                output_suggestion = os.path.join(os.path.dirname(os.path.dirname(fname)), "Audio_Output")
                self.output_path_edit.setText(output_suggestion)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Selecione a Pasta de Saída')
        if folder:
            self.output_path_edit.setText(folder)

    def start_processing(self):
        json_path = self.json_path_edit.text()
        output_path = self.output_path_edit.text()

        if not os.path.exists(json_path) or not json_path.endswith('.json'):
            self.log_edit.append("ERRO: Caminho do JSON inválido.")
            return
        if not os.path.isdir(output_path):
            try:
                os.makedirs(output_path)
                self.log_edit.append(f"INFO: Pasta de saída criada em '{output_path}'.")
            except Exception as e:
                self.log_edit.append(f"ERRO: Não foi possível criar a pasta de saída: {e}")
                return

        self.process_button.setEnabled(False)
        self.process_button.setText("Processando...")
        self.progress_bar.setValue(0)
        self.log_edit.clear()

        self.thread = AudioProcessorThread(json_path, output_path)
        self.thread.progress_signal.connect(self.update_log)
        self.thread.progress_bar_signal.connect(self.update_progress_bar)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.start()

    def update_log(self, message):
        self.log_edit.append(message)

    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)

    def on_finished(self, success, message):
        self.log_edit.append(message)
        self.process_button.setEnabled(True)
        self.process_button.setText("🚀 PROCESSAR ÁUDIOS")
        self.progress_bar.setValue(100 if success else 0)
        if success:
            self.log_edit.append("\n✅ Concluído!")
        else:
            self.log_edit.append("\n❌ Falha no Processamento.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    sys.exit(app.exec())
