# threads.py

import time
import logging
from PySide6.QtCore import QThread, Signal
from typing import List, Dict
from models import QueueItem
from video_from_narration import create_video_from_narration


# ----------------------------------------------------------------

class ProcessVideoThread(QThread):
    """Thread for processing a single video.

    Signals:
        progress (Signal): Emits progress percentage.
        finished (Signal): Emits completion status and message.
    """
    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, params: dict) -> None:
        """Initialize the thread.

        Args:
            params (dict): Parameters for video processing.
        """
        super().__init__()
        self.params = params

    def run(self) -> None:
        """Run the video processing in a separate thread."""
        try:
            self.params['progress_callback'] = lambda p: self.progress.emit(p)
            create_video_from_narration(**self.params)
            self.finished.emit(True, f"Vídeo gerado com sucesso: {self.params['out_path']}")
        except Exception as e:
            logging.error(f"Erro ao gerar vídeo: {e}")
            self.finished.emit(False, f"Erro ao gerar vídeo: {e}")


class QueueWorkerThread(QThread):
    """Thread for robust queue processing of multiple videos.

    Signals:
        item_started (Signal): Emits when an item starts processing.
        item_progress (Signal): Emits progress for an item.
        item_finished (Signal): Emits completion status for an item.
        queue_finished (Signal): Emits when the queue is finished.
    """
    item_started = Signal(int)
    item_progress = Signal(int, int)
    item_finished = Signal(int, bool, str)
    queue_finished = Signal()

    def __init__(self, queue_items: List[QueueItem], base_params: dict) -> None:
        """Initialize the queue worker thread.

        Args:
            queue_items (List[QueueItem]): List of queue items to process.
            base_params (dict): Base parameters for processing.
        """
        super().__init__()
        self.queue_items = queue_items
        self.base_params = base_params
        self._is_running = True

    def run(self) -> None:
        """Executes the thread logic, iterating and processing each item."""
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
