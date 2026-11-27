"""定义识别区域、触发条件和有序操作。"""

from math import cos, radians, sin
from collections import Counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints, model_validator


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Settings(BaseModel):
    """拒绝配置中拼错或未知的字段。"""

    model_config = ConfigDict(extra="forbid")


class Monitor(Settings):
    """记录显示器编号和物理像素范围。"""

    index: int = Field(ge=1)
    left: int
    top: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Window(Settings):
    """记录窗口标识及其客户区尺寸，位置在运行时读取。"""

    handle: int = Field(gt=0, le=2**53 - 1)
    pid: int = Field(gt=0)
    class_name: Name
    title: Name
    width: int = Field(gt=0)
    height: int = Field(gt=0)


CaptureSource = Monitor | Window


class Point(Settings):
    """表示截图内的像素坐标。"""

    x: int = Field(ge=0)
    y: int = Field(ge=0)


class Region(Settings):
    """记录以中心为锚点的旋转矩形。"""

    name: Name
    x: FiniteFloat = Field(ge=0)
    y: FiniteFloat = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    angle: FiniteFloat = Field(default=0, ge=-180, le=180)
    periodic: bool = True
    detect: bool = True
    confidence: FiniteFloat = Field(default=0, ge=0, le=1)
    frame_diff_threshold: FiniteFloat = Field(default=0, ge=0, le=1)
    allowed_chars: str = ""
    adaptive_recognition: bool = False

    def fits(self, source: CaptureSource) -> bool:
        """检查旋转矩形的四角是否都在截图范围内。"""
        angle = radians(self.angle)
        half_width = (self.width * abs(cos(angle)) + self.height * abs(sin(angle))) / 2
        half_height = (self.width * abs(sin(angle)) + self.height * abs(cos(angle))) / 2
        return (
            half_width <= min(self.x, source.width - self.x) + 1e-6
            and half_height <= min(self.y, source.height - self.y) + 1e-6
        )


class ConfidenceCondition(Settings):
    """检查区域中是否有文字行超过置信度阈值。"""

    type: Literal["confidence"]
    region: Name
    threshold: FiniteFloat = Field(ge=0, le=1)


class TextCondition(Settings):
    """检查区域文字是否包含或等于目标文本。"""

    type: Literal["text"]
    region: Name
    text: Name
    match: Literal["contains", "equals"] = "contains"


class ColorCondition(Settings):
    """检查某点的 RGB 三通道误差。"""

    type: Literal["color"]
    point: Point
    reference: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    tolerance: int = Field(default=0, ge=0, le=255)


class TriggerCondition(Settings):
    """检查前面的触发器是否已在本轮触发。"""

    type: Literal["trigger"]
    trigger: Name


Condition = Annotated[ConfidenceCondition | TextCondition | ColorCondition | TriggerCondition, Field(discriminator="type")]


class OCRAction(Settings):
    """使用该段额外 OCR 的截图识别指定区域。"""

    type: Literal["ocr"]
    region: Name


class ClickCandidate(Settings):
    """为一个点击点绑定自己的判定条件。"""

    point: Point
    conditions: list[Condition] = Field(min_length=1)


class ClickAction(Settings):
    """在通过条件的坐标中等概率选一个左击。"""

    type: Literal["click"]
    candidates: list[ClickCandidate] = Field(min_length=1)


class WaitAction(Settings):
    """暂停执行循环指定秒数。"""

    type: Literal["wait"]
    seconds: FiniteFloat = Field(gt=0)


Action = Annotated[OCRAction | ClickAction | WaitAction, Field(discriminator="type")]


class Trigger(Settings):
    """在条件全部满足时依次执行操作。"""

    name: Name
    show: bool = True
    conditions: list[Condition] = Field(default_factory=list)
    actions: list[Action] = Field(min_length=1)


ModelVariant = Literal["tiny", "small", "medium", "local"]


class RecognitionStage(Settings):
    """为分级识别配置一个模型及其通过阈值。"""

    model: ModelVariant
    threshold: FiniteFloat = Field(ge=0, le=1)
    model_path: Name | None = None
    keys_path: Name | None = None

    @model_validator(mode="after")
    def validate_local_path(self) -> "RecognitionStage":
        """要求为本地识别模型填写路径。"""
        if self.model == "local" and self.model_path is None:
            raise ValueError("请填写分级识别的本地 ONNX 路径")
        return self


class OCRModels(Settings):
    """选择检测、识别模型和本地模型文件。"""

    detection: ModelVariant = "small"
    recognition: ModelVariant = "small"
    detection_path: Name | None = None
    recognition_path: Name | None = None
    recognition_keys_path: Name | None = None
    recognition_stages: list[RecognitionStage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_local_paths(self) -> "OCRModels":
        """要求为选中的本地模型填写路径。"""
        if self.detection == "local" and self.detection_path is None:
            raise ValueError("请填写本地检测 ONNX 路径")
        if self.recognition == "local" and self.recognition_path is None:
            raise ValueError("请填写本地识别 ONNX 路径")
        return self


class Program(Settings):
    """定义一份可导入、导出和运行的识别配置。"""

    version: Literal[1] = 1
    monitor: Monitor | None = None
    window: Window | None = None
    frequency_hz: FiniteFloat = Field(default=1, gt=0)
    start_delay: FiniteFloat = Field(default=3, ge=0)
    include_scores: bool = False
    record_timings: bool = False
    record_frame_diffs: bool = False
    ocr_models: OCRModels = Field(default_factory=OCRModels)
    regions: list[Region] = Field(default_factory=list)
    triggers: list[Trigger] = Field(default_factory=list)

    @property
    def source(self) -> CaptureSource:
        """返回本次录制的唯一截图来源。"""
        if self.window is not None:
            return self.window
        assert self.monitor is not None
        return self.monitor

    def uses_ocr(self) -> bool:
        """检查周期识别或触发规则是否可能执行 OCR。"""
        if any(region.periodic for region in self.regions):
            return True
        for trigger in self.triggers:
            if any(isinstance(condition, (ConfidenceCondition, TextCondition)) for condition in trigger.conditions):
                return True
            for action in trigger.actions:
                if isinstance(action, OCRAction):
                    return True
                if isinstance(action, ClickAction) and any(
                    isinstance(condition, (ConfidenceCondition, TextCondition))
                    for candidate in action.candidates
                    for condition in candidate.conditions
                ):
                    return True
        return False

    @model_validator(mode="after")
    def validate_references(self) -> "Program":
        """确认备注名唯一、所有引用存在且选区和取点有效。"""
        if (self.monitor is None) == (self.window is None):
            raise ValueError("请指定一个显示器或窗口作为截图来源")
        names = set()
        for region in self.regions:
            if region.adaptive_recognition and not self.ocr_models.recognition_stages:
                raise ValueError(f"区域「{region.name}」启用了分级识别，请先添加识别模型和阈值")
            if region.name in names:
                raise ValueError(f"识别区域备注名重复：{region.name}")
            if not region.fits(self.source):
                raise ValueError(f"识别区域超出截图范围：{region.name}")
            names.add(region.name)

        trigger_counts = Counter(trigger.name for trigger in self.triggers)
        earlier = set()
        for trigger in self.triggers:
            self._validate_conditions(trigger.conditions, names, trigger.name, earlier)
            for action in trigger.actions:
                if isinstance(action, OCRAction):
                    self._check_region(action.region, names, trigger.name)
                if isinstance(action, ClickAction):
                    for candidate in action.candidates:
                        self._check_point(candidate.point, trigger.name)
                        self._validate_conditions(candidate.conditions, names, trigger.name, earlier)
            if trigger_counts[trigger.name] == 1:
                earlier.add(trigger.name)
        return self

    def _validate_conditions(
        self, conditions: list[Condition], names: set[str], source: str, earlier: set[str],
    ) -> None:
        """检查条件中的区域引用和取色坐标。"""
        for condition in conditions:
            if isinstance(condition, ColorCondition):
                self._check_point(condition.point, source)
            elif isinstance(condition, TriggerCondition):
                if condition.trigger not in earlier:
                    raise ValueError(f"触发器「{source}」须引用名称唯一且排在前面的触发器「{condition.trigger}」")
            else:
                self._check_region(condition.region, names, source)

    @staticmethod
    def _check_region(name: str, names: set[str], source: str) -> None:
        """拒绝指向不存在的识别区域。"""
        if name not in names:
            raise ValueError(f"触发器「{source}」引用了不存在的区域「{name}」")

    def _check_point(self, point: Point, source: str) -> None:
        """拒绝超出截图范围的取色点或点击点。"""
        if point.x >= self.source.width or point.y >= self.source.height:
            raise ValueError(f"触发器「{source}」的坐标 ({point.x}, {point.y}) 超出截图范围")
