# UI package initialization
from .ui_main_window import VideoGeneratorGUI
from .ui_tabs import BasicTab, VideoTab, OverlayTab, SubtitleTab

__all__ = [
    "VideoGeneratorGUI",
    "BasicTab",
    "VideoTab",
    "OverlayTab",
    "SubtitleTab"
]
