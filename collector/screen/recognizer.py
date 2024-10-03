"""Video-to-observation recognition.

The recognizer deliberately keeps raw OCR and template evidence. A failed OCR
result is an unknown observation, not a guessed skill or state transition.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import cv2
import numpy as np

REFERENCE_NAMES = (
    "entrance", "perform", "perform_counter", "buff", "normal", "willpower", "switch",
)


@dataclass
class VideoFrame:
    index: int
    timestamp: float
    image: np.ndarray


class VideoFrameSource:
    def __init__(self, path: str | Path, sample_fps: float = 5.0):
        self.path = Path(path)
        self.sample_fps = sample_fps

    def metadata(self) -> dict[str, Any]:
        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            raise ValueError(f"无法打开视频: {self.path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        result = {
            "path": str(self.path), "fps": fps, "frame_count": frames,
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            "duration": frames / fps if fps else None,
        }
        capture.release()
        return result

    def __iter__(self) -> Iterator[VideoFrame]:
        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            raise ValueError(f"无法打开视频: {self.path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        stride = max(1, round(fps / self.sample_fps))
        index = 0
        try:
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                # A one-frame animation can fall between regular samples. The
                # adjacent sample keeps the stream efficient while catching
                # the short willpower overlay in the supplied recording.
                if index % stride in {0, stride - 1}:
                    yield VideoFrame(index, index / fps, image)
                index += 1
        finally:
            capture.release()


class OCRBackend:
    def __init__(self, project_dir: Path):
        self.engine = None
        dependency_dir = project_dir / ".screen-deps"
        if dependency_dir.exists():
            sys.path.insert(0, str(dependency_dir))
        try:
            from rapidocr import RapidOCR
            self.engine = RapidOCR()
        except Exception:
            self.engine = None

    @property
    def available(self) -> bool:
        return self.engine is not None

    def read(self, image: np.ndarray) -> list[dict[str, Any]]:
        if self.engine is None:
            return []
        try:
            result = self.engine(image)
        except Exception:
            return []
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        boxes = getattr(result, "boxes", None)
        texts = () if texts is None else texts
        scores = () if scores is None else scores
        boxes = () if boxes is None else boxes
        return [
            {"text": str(text), "score": float(score), "box": [[float(x), float(y)] for x, y in box]}
            for text, score, box in zip(texts, scores, boxes)
        ]


class SkillNameResolver:
    def __init__(self, db_path: str | Path):
        try:
            with sqlite3.connect(db_path) as connection:
                self.names = [row[0] for row in connection.execute("SELECT name FROM skill")]
        except Exception:
            self.names = []

    def resolve(self, texts: Iterable[str]) -> tuple[str | None, float]:
        joined = "".join(texts).replace(" ", "")
        if not joined:
            return None, 0.0
        direct = [name for name in self.names if name and name in joined]
        if direct:
            name = max(direct, key=len)
            return name, 1.0
        cleaned = re.sub(r"[^㐀-鿿A-Za-z0-9]", "", joined)
        best_name, best_score = None, 0.0
        for name in self.names:
            score = difflib.SequenceMatcher(None, cleaned, name).ratio()
            if score > best_score:
                best_name, best_score = name, score
        return (best_name, best_score) if best_score >= 0.55 else (None, best_score)


class CreatureNameResolver:
    def __init__(self, db_path: str | Path):
        try:
            with sqlite3.connect(db_path) as connection:
                self.names = [row[0] for row in connection.execute("SELECT name FROM pokemon")]
        except Exception:
            self.names = []

    def resolve(self, texts: Iterable[str]) -> list[str]:
        joined = "".join(texts).replace(" ", "")
        matches = sorted({name for name in self.names if name and name in joined}, key=len, reverse=True)
        selected = []
        for name in matches:
            if not any(name in existing for existing in selected):
                selected.append(name)
        return selected


class ScreenRecognizer:
    thresholds = {
        "entrance": 180.0, "perform": 220.0, "perform_counter": 500.0,
        "buff": 180.0, "normal": 180.0, "willpower": 260.0, "switch": 260.0,
    }

    def __init__(self, reference_dir: str | Path, db_path: str | Path, project_dir: str | Path):
        self.reference_dir = Path(reference_dir)
        self.templates = self._load_templates()
        self.ocr = OCRBackend(Path(project_dir))
        self.skill_names = SkillNameResolver(db_path)
        self.creature_names = CreatureNameResolver(db_path)

    def _load_templates(self) -> dict[str, np.ndarray]:
        templates = {}
        for name in REFERENCE_NAMES:
            image = cv2.imread(str(self.reference_dir / f"{name}.jpg"))
            if image is not None:
                image = cv2.resize(image, (160, 100), interpolation=cv2.INTER_AREA)
                templates[name] = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
        return templates

    def _scores(self, image: np.ndarray) -> dict[str, float]:
        small = cv2.resize(image, (160, 100), interpolation=cv2.INTER_AREA)
        lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
        return {name: float(np.mean((lab - template) ** 2)) for name, template in self.templates.items()}

    @staticmethod
    def _side_from_ocr(ocr: list[dict[str, Any]]) -> str | None:
        left = right = 0
        for item in ocr:
            box = item.get("box") or []
            if not box:
                continue
            center_x = sum(point[0] for point in box) / len(box)
            if center_x < 900:
                left += 1
            elif center_x > 1020:
                right += 1
        if left > right:
            return "own"
        if right > left:
            return "opponent"
        return None

    def observe(self, frame: VideoFrame) -> dict[str, Any]:
        scores = self._scores(frame.image)
        candidates = [(name, score) for name, score in scores.items() if score <= self.thresholds.get(name, 200.0)]
        screen, confidence = "battle", 0.0
        if candidates:
            screen, score = min(candidates, key=lambda item: item[1])
            confidence = max(0.0, min(1.0, 1.0 - score / (self.thresholds[screen] * 1.2)))
        ocr = self.ocr.read(frame.image) if screen != "battle" else []
        texts = [item["text"] for item in ocr if float(item.get("score", 0.0)) >= 0.45]
        skill_name, skill_confidence = self.skill_names.resolve(texts)
        detected_creatures = self.creature_names.resolve(texts)
        detected_skill = skill_name
        if detected_skill is None and screen in {"perform", "perform_counter"}:
            joined = "".join(texts)
            match = re.search(r"(?:使出了|使用了|使用)(?:[★*☆]?d+)?([^！!。s]+)", joined)
            if match:
                detected_skill = match.group(1).strip("★⭑⭐☆*0123456789") or None
                skill_confidence = 0.5 if detected_skill else 0.0
        side = self._side_from_ocr(ocr) if screen in {"perform", "perform_counter"} else None
        if screen == "perform" and side is None:
            side = "own"
        if screen == "perform_counter" and side is None:
            side = "opponent"
        return {
            "frame_index": frame.index, "timestamp": frame.timestamp, "screen": screen,
            "confidence": round(confidence, 4),
            "template_scores": {key: round(value, 3) for key, value in scores.items()},
            "ocr_available": self.ocr.available, "ocr": ocr, "text": "".join(texts),
            "side": side, "skill_name": detected_skill, "skill_confidence": round(skill_confidence, 4),
            "creature_names": detected_creatures,
        }

    def recognize(self, source: VideoFrameSource) -> list[dict[str, Any]]:
        observations, last_screen, last_timestamp = [], None, -999.0
        for frame in source:
            observation = self.observe(frame)
            screen = observation["screen"]
            if screen == "battle":
                continue
            if screen == last_screen and observation["timestamp"] - last_timestamp < 1.0:
                continue
            observation["event_id"] = f"screen-{len(observations) + 1:04d}"
            observations.append(observation)
            last_screen, last_timestamp = screen, observation["timestamp"]
        return observations


def load_manifest(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))
