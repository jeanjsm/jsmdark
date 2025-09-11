# threads.py

import time
from PySide6.QtCore import QThread, Signal
from typing import List, Dict
from models import QueueItem

# --- CORREÇÃO: IMPORTAÇÃO REAL ---
# Remova a função mock e importe a sua função de processamento original.
# Certifique-se de que o arquivo 'video_from_narration.py' está na mesma pasta
# ou em um local que o Python possa encontrar.
from video_from_narration import create_video_from_narration


# ----------------------------------------------------------------

class ProcessVideoThread(QThread):
    """Thread para processar um único vídeo."""
    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        try:
            # Adiciona o callback de progresso aos parâmetros
            self.params['progress_callback'] = lambda p: self.progress.emit(p)

            # Chama a SUA função de processamento real
            create_video_from_narration(**self.params)

            self.finished.emit(True, f"Vídeo gerado com sucesso: {self.params['out_path']}")
        except Exception as e:
            self.finished.emit(False, f"Erro ao gerar vídeo: {e}")


class QueueWorkerThread(QThread):
    """Thread para processar a fila de vídeos com lógica robusta."""
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
        """
        Lógica de execução da thread. Itera sobre os itens e os processa um a um.
        """
        for i in range(len(self.queue_items)):
            if not self._is_running:
                break

            item = self.queue_items[i]

            if item.status != "waiting":
                continue

            self.item_started.emit(i)

            params = self.base_params.copy()
            params['narration_path'] = item.narration_path
            params['out_path'] = item.output_path

            params['progress_callback'] = lambda p, index=i: self.item_progress.emit(index, p)

            try:
                # Chama a SUA função de processamento real
                create_video_from_narration(**params)
                self.item_finished.emit(i, True, f"Concluído: {item.output_path}")
            except Exception as e:
                self.item_finished.emit(i, False, str(e))

        self.queue_finished.emit()

    def stop(self):
        """
        Sinaliza para a thread que ela deve parar a execução.
        """
        self._is_running = False
