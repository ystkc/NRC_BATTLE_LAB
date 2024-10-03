"""Screen-stream collection for battle audit records."""

from .pipeline import ScreenCollectionPipeline, load_manifest
from .recognizer import ScreenRecognizer, VideoFrameSource
from .fast_detector import SingleFrameInspector
from .realtime import BattleFeatureDetector, RealtimeBattleMonitor

__all__ = [
    "ScreenCollectionPipeline", "ScreenRecognizer", "VideoFrameSource", "SingleFrameInspector",
    "BattleFeatureDetector", "RealtimeBattleMonitor", "load_manifest",
]
