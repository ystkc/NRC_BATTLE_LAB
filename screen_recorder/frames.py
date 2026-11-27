"""缓存每个识别区域最近的裁剪图和识别结果。"""

from dataclasses import dataclass, field
from time import perf_counter

import cv2
import numpy as np

from .program import ColorCondition, Condition, ConfidenceCondition, Region
from .recognition import Recognizer, TextLine, upright_crop


RegionTimings = dict[str, list[float]]


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

    def read(self, image: np.ndarray, recognizer: Recognizer, timings: RegionTimings | None) -> FrameResult:
        """比较校正后的像素，超过帧差阈值时执行 OCR。"""
        started = perf_counter() if timings is not None else None
        crop = upright_crop(image, self.region)
        if self.previous_image is not None:
            difference = cv2.norm(crop, self.previous_image, cv2.NORM_L1) / (255 * crop.size)
            if difference <= self.region.frame_diff_threshold:
                self.skipped_frames += 1
                return FrameResult(self.previous_lines, skipped=True)

        try:
            lines = recognizer.read_crop(crop, self.region)
        finally:
            if timings is not None and started is not None:
                elapsed_ms = round((perf_counter() - started) * 1000, 3)
                timings.setdefault(self.region.name, []).append(elapsed_ms)
        self.previous_image = crop
        self.previous_lines = lines
        if lines:
            self.last_valid = lines
            self.skipped_frames = 0
        return FrameResult(lines)


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
