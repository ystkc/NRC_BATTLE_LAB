"""Single-frame, OCR-free structural inspection.

This module intentionally prefers cheap geometric evidence over colors or text.
It is for inspecting detector behavior, not for making final battle decisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class SingleFrameInspector:
    fixed_rois = {
        "top_left_status": (0.00, 0.00, 0.28, 0.16),
        "top_right_status": (0.72, 0.00, 1.00, 0.16),
        "entrance_left_team": (0.03, 0.12, 0.36, 0.78),
        "entrance_center": (0.35, 0.10, 0.66, 0.88),
        "skill_panel": (0.00, 0.35, 0.30, 0.88),
        "action_banner": (0.00, 0.08, 1.00, 0.32),
        "report_center": (0.28, 0.28, 0.78, 0.78),
        "own_icon_area": (0.35, 0.45, 0.62, 0.82),
        "control_area": (0.72, 0.78, 1.00, 1.00),
    }

    colors = {
        "fixed": (150, 150, 150),
        "dark_banner": (0, 0, 255),
        "bright_panel": (255, 180, 0),
        "horizontal_band": (0, 200, 0),
        "skill_card": (255, 0, 180),
        "circle": (0, 220, 220),
        "willpower": (180, 0, 255),
    }

    def __init__(self, min_area_ratio: float = 0.0015):
        self.min_area_ratio = min_area_ratio

    @staticmethod
    def _rect_from_norm(width: int, height: int, rect: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = rect
        return round(x1 * width), round(y1 * height), round(x2 * width), round(y2 * height)

    @staticmethod
    def _clip_rect(rect: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = rect
        return max(0, x1), max(0, y1), min(width, x2), min(height, y2)

    @staticmethod
    def _roi(image: np.ndarray, rect: tuple[int, int, int, int]) -> np.ndarray:
        x1, y1, x2, y2 = rect
        return image[y1:y2, x1:x2]

    @staticmethod
    def _features(image: np.ndarray) -> dict[str, float]:
        if image.size == 0:
            return {"edge_density": 0.0, "dark_ratio": 0.0, "bright_ratio": 0.0, "large_components": 0.0}
        small = cv2.resize(image, (64, 32), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        edges = cv2.Canny(gray, 60, 140)
        dark = gray < 65
        bright = (gray > 205) & (hsv[:, :, 1] < 90)
        components, _, stats, _ = cv2.connectedComponentsWithStats(dark.astype(np.uint8), 8)
        large = sum(1 for area in stats[1:, cv2.CC_STAT_AREA] if area >= 25)
        return {
            "edge_density": round(float(np.mean(edges > 0)), 5),
            "dark_ratio": round(float(np.mean(dark)), 5),
            "bright_ratio": round(float(np.mean(bright)), 5),
            "large_components": float(large),
        }

    def _contour_boxes(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        rect: tuple[int, int, int, int],
        *,
        min_ratio: float | None = None,
        aspect_low: float = 0.0,
        aspect_high: float = 100.0,
    ) -> list[dict[str, Any]]:
        x1, y1, x2, y2 = rect
        roi = self._roi(image, rect)
        local_mask = self._roi(mask, rect)
        kernel = np.ones((3, 3), np.uint8)
        local_mask = cv2.morphologyEx(local_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, _ = cv2.findContours(local_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_area = image.shape[0] * image.shape[1]
        threshold = image_area * (min_ratio if min_ratio is not None else self.min_area_ratio)
        boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            bx, by, bw, bh = cv2.boundingRect(contour)
            if area < threshold or bw < 8 or bh < 8:
                continue
            aspect = bw / max(1, bh)
            if not aspect_low <= aspect <= aspect_high:
                continue
            boxes.append({
                "box": [x1 + bx, y1 + by, x1 + bx + bw, y1 + by + bh],
                "area": round(float(area), 2),
                "aspect": round(float(aspect), 3),
                "fill": round(float(area / max(1, bw * bh)), 3),
            })
        return sorted(boxes, key=lambda item: item["area"], reverse=True)

    def _horizontal_bands(self, image: np.ndarray, rect: tuple[int, int, int, int]) -> list[dict[str, Any]]:
        x1, y1, x2, y2 = rect
        roi = self._roi(image, rect)
        if roi.size == 0:
            return []
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 130)
        dark = gray < 100
        signal = edges.mean(axis=1) + 0.45 * dark.mean(axis=1)
        kernel = np.ones(9, np.float32) / 9.0
        signal = np.convolve(signal, kernel, mode="same")
        threshold = max(float(np.percentile(signal, 62)), float(signal.mean() + 0.18 * signal.std()))
        active = signal >= threshold
        bands = []
        start = None
        for index, value in enumerate(np.r_[active, False]):
            if value and start is None:
                start = index
            elif not value and start is not None:
                if index - start >= max(8, roi.shape[0] // 45):
                    bands.append({
                        "box": [x1, y1 + start, x2, y1 + index],
                        "signal": round(float(signal[start:index].mean()), 4),
                    })
                start = None
        return bands

    @staticmethod
    def _purple_ratio(image: np.ndarray, rect: tuple[int, int, int, int]) -> float:
        roi = image[rect[1]:rect[3], rect[0]:rect[2]]
        if roi.size == 0:
            return 0.0
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        purple = ((hsv[:, :, 0] >= 125) & (hsv[:, :, 0] <= 165) & (hsv[:, :, 1] > 55) & (hsv[:, :, 2] > 55))
        return float(np.mean(purple))

    def analyze(self, image: np.ndarray, source: str = "") -> dict[str, Any]:
        if image is None or image.size == 0:
            raise ValueError("输入图片为空")
        height, width = image.shape[:2]
        roi_rects = {name: self._rect_from_norm(width, height, rect) for name, rect in self.fixed_rois.items()}
        features = {name: self._features(self._roi(image, rect)) for name, rect in roi_rects.items()}

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        dark_mask = (gray < 70).astype(np.uint8) * 255
        bright_mask = ((gray > 210) & (cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1] < 95)).astype(np.uint8) * 255
        edges = cv2.Canny(gray, 60, 140)
        dark_banners = self._contour_boxes(image, dark_mask, roi_rects["action_banner"], min_ratio=0.002, aspect_low=3.0, aspect_high=30.0)
        bright_panels = self._contour_boxes(image, bright_mask, roi_rects["report_center"], min_ratio=0.004, aspect_low=1.15, aspect_high=5.5)
        skill_cards = self._contour_boxes(image, edges, roi_rects["skill_panel"], min_ratio=0.001, aspect_low=0.45, aspect_high=2.5)
        bands = self._horizontal_bands(image, roi_rects["entrance_left_team"])

        central = roi_rects["report_center"]
        central_features = features["report_center"]
        purple_ratio = self._purple_ratio(image, roi_rects["entrance_center"])
        entrance_score = min(1.0, len(bands) / 6.0) * 0.7 + min(1.0, features["entrance_left_team"]["edge_density"] * 5.0) * 0.3
        battle_score = min(1.0, (features["top_left_status"]["edge_density"] + features["top_right_status"]["edge_density"]) * 3.0)
        panel_score = min(1.0, len(skill_cards) / 4.0)
        report_score = min(1.0, sum(item["area"] for item in bright_panels) / max(1.0, width * height * 0.08))
        willpower_score = min(1.0, purple_ratio * 5.0 + central_features["edge_density"] * 1.5)
        scores = {
            "entrance": round(float(entrance_score), 4),
            "battle": round(float(battle_score), 4),
            "skill_panel": round(float(panel_score), 4),
            "report_panel": round(float(report_score), 4),
            "willpower_candidate": round(float(willpower_score), 4),
        }
        scene, scene_score = max(scores.items(), key=lambda item: item[1])
        return {
            "source": source,
            "image": {"width": width, "height": height},
            "scene": scene,
            "scene_score": scene_score,
            "scores": scores,
            "fixed_rois": roi_rects,
            "roi_features": features,
            "detections": {
                "dark_banners": dark_banners[:20],
                "bright_panels": bright_panels[:20],
                "skill_cards": skill_cards[:20],
                "entrance_bands": bands[:12],
                "purple_ratio": round(purple_ratio, 5),
            },
        }

    def annotate(self, image: np.ndarray, analysis: dict[str, Any]) -> np.ndarray:
        output = image.copy()
        for name, box in analysis["fixed_rois"].items():
            x1, y1, x2, y2 = box
            cv2.rectangle(output, (x1, y1), (x2, y2), self.colors["fixed"], 1)
            cv2.putText(output, name, (x1 + 3, max(14, y1 + 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, self.colors["fixed"], 1, cv2.LINE_AA)

        for kind, color in (("dark_banners", "dark_banner"), ("bright_panels", "bright_panel"), ("skill_cards", "skill_card"), ("entrance_bands", "horizontal_band")):
            for item in analysis["detections"][kind]:
                x1, y1, x2, y2 = item["box"]
                cv2.rectangle(output, (x1, y1), (x2, y2), self.colors[color], 3)
                cv2.putText(output, kind, (x1 + 3, max(16, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, self.colors[color], 1, cv2.LINE_AA)

        scores = " | ".join(f"{key}:{value:.2f}" for key, value in analysis["scores"].items())
        cv2.rectangle(output, (0, 0), (output.shape[1], 34), (25, 25, 25), -1)
        cv2.putText(output, f"scene={analysis['scene']} score={analysis['scene_score']:.2f}", (8, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(output, scores[:220], (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (220, 220, 220), 1, cv2.LINE_AA)
        return output

    def inspect_file(self, input_path: str | Path, output_image: str | Path, output_json: str | Path) -> dict[str, Any]:
        image = cv2.imread(str(input_path))
        if image is None:
            raise ValueError(f"无法读取图片: {input_path}")
        result = self.analyze(image, str(input_path))
        Path(output_image).parent.mkdir(parents=True, exist_ok=True)
        Path(output_json).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_image), self.annotate(image, result))
        Path(output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
