"""Shared data, scoring, and OCR adapters for the benchmark experiments."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np


BENCHMARK_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BENCHMARK_DIR.parent
DEFAULT_IMAGE = BENCHMARK_DIR / "test.png"
DEFAULT_FULL_RESULTS = BENCHMARK_DIR / "full_image_results.json"
DEFAULT_REGION_RESULTS = BENCHMARK_DIR / "region_results.json"
DEFAULT_PREVIEW_DIR = BENCHMARK_DIR / "region_preview"

EXPECTED_LINES = [
    "画间沉铁兽60级",
    "恶魔狼60级",
    "490/490",
    "100%",
    "★10",
    "★10",
    "★2 37 连续爪击",
    "★2 62 反击拳",
    "★1 30 幻象",
    "★3 -- 鼓劲",
    "Enter",
    "聊天",
    "Tab",
    "战报",
    "★10/10",
    "聚能",
    "背包",
    "逃跑",
    "更换",
    "技能",
]

REGIONS: dict[str, tuple[tuple[int, int, int, int], str]] = {
    "left_header": ((86, 29, 169, 62), "画间沉铁兽60级490/490"),
    "right_header": ((1359, 29, 162, 60), "恶魔狼60级100%"),
    "left_energy": ((203, 87, 41, 26), "★10"),
    "right_energy": ((1359, 84, 44, 29), "★10"),
    "skill_1": ((245, 407, 94, 29), "连续爪击"),
    "skill_2": ((224, 516, 84, 32), "反击拳"),
    "skill_3": ((238, 629, 89, 32), "幻象"),
    "skill_4": ((294, 725, 106, 41), "鼓劲"),
    "energy_1": ((251, 334, 45, 32), "★2"),
    "energy_2": ((214, 447, 50, 34), "★2"),
    "energy_3": ((222, 569, 52, 28), "★1"),
    "energy_4": ((277, 669, 49, 36), "★3"),
    "power_1": ((292, 390, 47, 29), "37"),
    "power_2": ((260, 498, 54, 28), "62"),
    "power_3": ((274, 607, 55, 32), "30"),
    "power_4": ((331, 708, 58, 29), "--"),
}


def region_bounds(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Convert the region format (x, y, width, height) to slice bounds."""
    x, y, width, height = box
    return x, y, x + width, y + height


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("，", ",").replace("％", "%")


def edit_distance(left: str, right: str) -> int:
    row = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, 1):
        next_row = [left_index]
        for right_index, right_char in enumerate(right, 1):
            next_row.append(min(
                next_row[-1] + 1,
                row[right_index] + 1,
                row[right_index - 1] + (left_char != right_char),
            ))
        row = next_row
    return row[-1]


def score_text(predicted: str) -> dict[str, Any]:
    expected = normalize("".join(EXPECTED_LINES))
    predicted = normalize(predicted)
    expected_numeric = "".join(re.findall(r"[0-9/%]+", expected))
    predicted_numeric = "".join(re.findall(r"[0-9/%]+", predicted))
    expected_words = "".join(re.findall(r"[\u3400-\u9fffA-Za-z]+", expected))
    predicted_words = "".join(re.findall(r"[\u3400-\u9fffA-Za-z]+", predicted))
    char_distance = edit_distance(expected, predicted)
    numeric_distance = edit_distance(expected_numeric, predicted_numeric)
    text_distance = edit_distance(expected_words, predicted_words)
    return {
        "exact_normalized": predicted == expected,
        "char_edit_distance": char_distance,
        "char_accuracy": max(0.0, 1.0 - char_distance / max(1, len(expected))),
        "numeric_exact": predicted_numeric == expected_numeric,
        "numeric_edit_distance": numeric_distance,
        "numeric_accuracy": max(0.0, 1.0 - numeric_distance / max(1, len(expected_numeric))),
        "text_edit_distance": text_distance,
        "text_accuracy": max(0.0, 1.0 - text_distance / max(1, len(expected_words))),
        "expected_numeric": expected_numeric,
        "predicted_numeric": predicted_numeric,
    }


def score_region(expected: str, predicted: str) -> dict[str, Any]:
    expected_compact = normalize(expected)
    predicted_compact = normalize(predicted)
    expected_numeric = "".join(re.findall(r"[0-9/%]+", expected_compact))
    predicted_numeric = "".join(re.findall(r"[0-9/%]+", predicted_compact))
    return {
        "numeric_exact": predicted_numeric == expected_numeric,
        "numeric_edit_distance": edit_distance(expected_numeric, predicted_numeric),
        "text_edit_distance": edit_distance(expected_compact, predicted_compact),
        "expected_numeric": expected_numeric,
        "predicted_numeric": predicted_numeric,
    }


def sort_detections(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> tuple[float, float]:
        box = item.get("box") or []
        if not box:
            return (0.0, 0.0)
        points = np.asarray(box, dtype=float)
        return (float(points[:, 1].mean()), float(points[:, 0].mean()))

    return sorted(detections, key=key)


def join_detections(detections: list[dict[str, Any]]) -> str:
    return "\n".join(str(item["text"]) for item in sort_detections(detections) if item.get("text"))


def parse_rapidocr(result: object) -> list[dict[str, Any]]:
    texts = getattr(result, "txts", None)
    scores = getattr(result, "scores", None)
    boxes = getattr(result, "boxes", None)
    if texts is None:
        texts = []
    if scores is None:
        scores = []
    if boxes is None:
        boxes = []
    return sort_detections([
        {"text": str(text), "score": float(score), "box": np.asarray(box).tolist()}
        for text, score, box in zip(texts, scores, boxes)
    ])


def image_variants(crop: np.ndarray) -> dict[str, np.ndarray]:
    enlarged = cv2.resize(crop, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
    contrast = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    return {"color_x3": enlarged, "gray_x3": gray, "contrast_x3": contrast}


def extract_pixpin_text(payload: dict[str, Any]) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    for block in payload.get("result", {}).get("blocks", []):
        for line in block.get("textLines", []):
            scores = [float(score) for score in line.get("scores", [])]
            detections.append({
                "text": str(line.get("text", "")),
                "score": sum(scores) / len(scores) if scores else 1.0,
                "box": line.get("box", block.get("box", [])),
            })
    return sort_detections(detections)


class PixPinOCRClient:
    """Keep one named-pipe connection alive for the whole experiment."""

    def __init__(self, pipe_name: str) -> None:
        from ocr_service.example_client import normalize_pipe_name, request

        self._request = request
        self._pipe = open(normalize_pipe_name(pipe_name), "r+b", buffering=0)
        self._request_id = 1
        self.pipe_name = pipe_name

    def recognize(self, width: int, height: int, pixels: bytes) -> dict[str, Any]:
        status, payload, timings = self._request(self._pipe, width, height, pixels, self._request_id)
        self._request_id += 1
        if status != 0 or not payload.get("ok", False):
            raise RuntimeError(f"PixPin_OCR status={status}: {payload}")
        return payload

    def close(self) -> None:
        if not self._pipe.closed:
            self._pipe.close()

    def __enter__(self) -> "PixPinOCRClient":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def run_winrt(helper: Path, image_path: Path, repeats: int) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(helper), "-ImagePath", str(image_path), "-Repeats", str(repeats),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return next(json.loads(line) for line in reversed(completed.stdout.splitlines()) if line.startswith("{"))
