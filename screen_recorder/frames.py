"""缓存每个识别区域最近的裁剪图和识别结果。"""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

import cv2
import numpy as np

from .program import ColorCondition, Condition, ConfidenceCondition, Region
from .recognition import Recognizer, TextLine, upright_crop


@dataclass(frozen=True)
class RegionTiming:
    """记录一次识别中各选区的名称和耗时。"""

    names: tuple[str, ...]
    samples: tuple[float, ...]


RegionTimings = list[RegionTiming]


@dataclass(frozen=True)
class FrameResult:
    """区分本帧新识别结果和帧差命中的缓存结果。"""

    lines: list[TextLine]
    skipped: bool = False


@dataclass
class RegionHistory:
    """记录同一任务中一个区域的比较基准和最近有效内容。"""

    region: Region
    previous_image: np.ndarray | None = None
    previous_lines: list[TextLine] = field(default_factory=list)
    last_valid: list[TextLine] = field(default_factory=list)
    skipped_frames: int = 0

    def reuse(self, crop: np.ndarray) -> FrameResult | None:
        """帧差达到跳过条件时，沿用上次识别结果。"""
        if self.previous_image is not None:
            difference = cv2.norm(crop, self.previous_image, cv2.NORM_L1) / (255 * crop.size)
            if difference <= self.region.frame_diff_threshold:
                self.skipped_frames += 1
                return FrameResult(self.previous_lines, skipped=True)
        return None

    def remember(self, crop: np.ndarray, lines: list[TextLine]) -> FrameResult:
        """更新实际识别的图像和最近有效结果。"""
        self.previous_image = crop
        self.previous_lines = lines
        if lines:
            self.last_valid = lines
            self.skipped_frames = 0
        return FrameResult(lines)

    def read(self, image: np.ndarray, recognizer: Recognizer, timings: RegionTimings | None) -> FrameResult:
        """比较校正后的像素，超过帧差阈值时执行 OCR。"""
        started = perf_counter() if timings is not None else None
        crop = upright_crop(image, self.region)
        cached = self.reuse(crop)
        if cached is not None:
            return cached

        try:
            lines = recognizer.read_crop(crop, self.region)
        finally:
            if timings is not None and started is not None:
                elapsed_ms = round((perf_counter() - started) * 1000, 3)
                timings.append(RegionTiming((self.region.name,), (elapsed_ms,)))
        return self.remember(crop, lines)


class ScreenFrame:
    """保存某次截图和基于该截图得到的 OCR 结果。"""

    def __init__(
        self, image: np.ndarray, regions: dict[str, RegionHistory], recognizer: Recognizer,
        timings: RegionTimings | None = None,
    ) -> None:
        """使用同一份截图判定一组条件。"""
        self.image = image
        self.regions = regions
        self.recognizer = recognizer
        self.timings = timings
        self.cache: dict[str, FrameResult] = {}

    def read_regions(self, names: list[str], check_stop: Callable[[], None]) -> None:
        """先批量识别直读框，再补齐本帧的其他结果。"""
        self._read_direct([name for name in names if not self.regions[name].region.detect], check_stop)
        for name in names:
            check_stop()
            self._read(name)

    def _read_direct(self, names: list[str], check_stop: Callable[[], None]) -> None:
        """对同一截图中的直读框做帧差检查并批量识别。"""
        if len(names) < 2:
            return
        pending: dict[str, tuple[np.ndarray, float]] = {}
        for name in names:
            check_stop()
            if name in self.cache or name in pending:
                continue
            started = perf_counter()
            history = self.regions[name]
            crop = upright_crop(self.image, history.region)
            cached = history.reuse(crop)
            if cached is None:
                pending[name] = (crop, perf_counter() - started)
            else:
                self.cache[name] = cached

        crops = [(self.regions[name].region, crop) for name, (crop, _) in pending.items()]
        for batch in self.recognizer.read_direct(crops, check_stop):
            samples = []
            for name, lines, elapsed in batch:
                crop, cropping = pending[name]
                self.cache[name] = self.regions[name].remember(crop, lines)
                if self.timings is not None:
                    samples.append(round((cropping + elapsed) * 1000, 3))
            if self.timings is not None:
                self.timings.append(RegionTiming(tuple(name for name, _, _ in batch), tuple(samples)))

    def _read(self, name: str) -> FrameResult:
        """复用同一次截图中同一区域的识别或跳过结果。"""
        if name not in self.cache:
            self.cache[name] = self.regions[name].read(self.image, self.recognizer, self.timings)
        return self.cache[name]

    def matches(self, condition: Condition) -> bool:
        """判断这一帧是否满足指定条件。"""
        if isinstance(condition, ColorCondition):
            x, y = condition.point.x, condition.point.y
            pixel = self.image[y, x, ::-1]
            reference = bytes.fromhex(condition.reference[1:])
            return all(abs(int(actual) - expected) <= condition.tolerance
                       for actual, expected in zip(pixel, reference))
        lines = self._read(condition.region).lines
        if isinstance(condition, ConfidenceCondition):
            return any(line.score > condition.threshold for line in lines)
        text = " ".join(word for line in lines for word in line.text.split())
        target = " ".join(condition.text.split())
        return text == target if condition.match == "equals" else target in text

    def result(self, name: str, include_scores: bool) -> str | list | None:
        """生成适合 YAML 展示的简短识别结果。"""
        result = self._read(name)
        if result.skipped:
            return "跳过"
        if not result.lines:
            return None
        if include_scores:
            return [{"文字": line.text, "置信度": round(line.score, 4)} for line in result.lines]
        if len(result.lines) == 1:
            return result.lines[0].text
        return [line.text for line in result.lines]
