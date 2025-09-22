# Main package initialization
# This makes the src directory a proper package and allows importing from it

# Expose main modules for easier imports
from .models import ConfigModel, QueueItem, ChromaConfig
from .ui import VideoGeneratorGUI, BasicTab, VideoTab, OverlayTab, SubtitleTab
from .controllers import AppController
from .services import (
    ProcessVideoThread,
    QueueWorkerThread,
    run,  # Changed from run_ffmpeg to run
    create_video_from_narration
)

__all__ = [
    # Models
    "ConfigModel",
    "QueueItem",
    "ChromaConfig",

    # UI
    "VideoGeneratorGUI",
    "BasicTab",
    "VideoTab",
    "OverlayTab",
    "SubtitleTab",

    # Controllers
    "AppController",

    # Services
    "ProcessVideoThread",
    "QueueWorkerThread",
    "run",
    "create_video_from_narration"
]
