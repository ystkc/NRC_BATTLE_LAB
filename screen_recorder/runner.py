"""串行执行识别轮次、触发动作和全局等待。"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from random import choice
from threading import Event, Lock, Thread
from time import monotonic
from typing import TextIO

import numpy as np
import yaml

from .desktop import Capture, Desktop
from .frames import RegionHistory, RegionTiming, RegionTimings, ScreenFrame
from .program import (
    CaptureSource, ClickAction, Condition, OCRAction, Program, WaitAction,
)
from .recognition import Polygon, Recognizer


RoundPreview = tuple[np.ndarray, list[Polygon]]


class RunBusy(RuntimeError):
    """表示已有一个轮次循环占用桌面。"""


class RunStopped(Exception):
    """从任意可中断的步骤退出执行循环。"""


class RecordingDumper(yaml.SafeDumper):
    """将坐标和耗时序列化为紧凑的行内数组。"""


def _dump_sequence(dumper: RecordingDumper, values: tuple[str | int | float, ...]) -> yaml.SequenceNode:
    """保留数组类型并写在同一行。"""
    return dumper.represent_sequence("tag:yaml.org,2002:seq", values, flow_style=True)


def _dump_timing(dumper: RecordingDumper, timing: RegionTiming) -> yaml.MappingNode:
    """用一行记录一次识别的区域和耗时。"""
    if len(timing.names) == 1:
        label = timing.names[0]
    else:
        # 将框名列表作为字符串键，便于普通 YAML 解析器读取。
        label = yaml.dump(timing.names, Dumper=RecordingDumper, allow_unicode=True, width=float("inf")).strip()
    return dumper.represent_mapping("tag:yaml.org,2002:map", {label: timing.samples}, flow_style=True)


RecordingDumper.add_representer(tuple, _dump_sequence)
RecordingDumper.add_representer(RegionTiming, _dump_timing)


@dataclass
class RoundFrames:
    """收集一轮中共用的区域历史、截图、触发区域和耗时。"""

    regions: dict[str, RegionHistory]
    timings: RegionTimings | None
    image: np.ndarray | None = None
    triggered: set[str] = field(default_factory=set)

    def boxes(self) -> list[Polygon]:
        """取得本轮要标出的最近有效文字轮廓。"""
        boxes = []
        for name, history in self.regions.items():
            region = history.region
            if (region.periodic and region.detect) or name in self.triggered:
                boxes.extend(line.box for line in history.last_valid if line.box is not None)
        return boxes


def dump_yaml(value: dict, *, document: bool = False) -> str:
    """输出保留中文和字段顺序的 YAML。"""
    return yaml.dump(
        value, Dumper=RecordingDumper, allow_unicode=True, sort_keys=False,
        explicit_start=document, width=float("inf") if document else None,
    )


class Recorder:
    """管理一个可停止的后台桌面识别任务。"""

    def __init__(self, desktop: Desktop, recognizer: Recognizer, directory: Path) -> None:
        """保存桌面、OCR 引擎和记录目录。"""
        self.desktop = desktop
        self.recognizer = recognizer
        self.directory = directory
        self._lock = Lock()
        self._cancel = Event()
        self._thread: Thread | None = None
        self._phase = "idle"
        self._deadline: float | None = None
        self._trial = False
        self._error = ""
        self._completed = 0
        self._latest = ""
        self._filename = ""
        self._region_results: list[dict] = []
        self._round_preview: RoundPreview | None = None

    def preview(self, source: CaptureSource) -> np.ndarray:
        """只在待机时响应配置界面的截图。"""
        with self._lock:
            if self._thread is not None:
                raise RunBusy("请先停止当前任务再截图")
            with self.desktop.open_capture(source) as capture:
                return capture()

    def start(self, program: Program, *, trial: bool = False) -> None:
        """验证截图来源并启动单一执行线程。"""
        with self._lock:
            if self._thread is not None:
                raise RunBusy("已有任务正在运行")
            if not any(region.periodic for region in program.regions) and not program.triggers:
                raise ValueError("请先设置每轮识别区域或触发器")
            self.desktop.validate_source(program.source)
            self.directory.mkdir(parents=True, exist_ok=True)
            self._cancel.clear()
            self._phase = "preparing"
            self._deadline = None
            self._trial = trial
            self._completed = 0
            self._error = self._latest = ""
            self._region_results = []
            self._round_preview = None
            self._filename = datetime.now().strftime("%Y%m%d-%H%M%S-%f.yaml")
            self._thread = Thread(target=self._run, args=(program, trial), daemon=True)
            self._thread.start()

    def stop(self) -> Thread | None:
        """取消等待并阻止执行线程发出下一次点击。"""
        with self._lock:
            thread = self._thread
            if thread is not None:
                self._cancel.set()
                self._phase = "stopping"
                self._deadline = None
            return thread

    def status(self) -> dict:
        """返回当前阶段、倒计时和最近一次输出。"""
        return self.snapshot()[0]

    def snapshot(self) -> tuple[dict, RoundPreview | None]:
        """从同一轮获取任务状态和画面，供前端同步显示。"""
        with self._lock:
            remaining = max(0, self._deadline - monotonic()) if self._deadline is not None else 0
            status = {
                "active": self._thread is not None,
                "phase": self._phase,
                "trial": self._trial,
                "remaining_seconds": remaining,
                "rounds": self._completed,
                "yaml": self._latest,
                "recording": self._filename if self._latest else None,
                "regions": self._region_results,
                "error": self._error,
            }
            return status, self._round_preview

    def _run(self, program: Program, trial: bool) -> None:
        """按设定频率运行，识别超时或等待期间跳过错过的周期。"""
        error = ""
        try:
            self._check_stop()
            if program.uses_ocr():
                self.recognizer.prepare(program.ocr_models)
            deadline = monotonic() + program.start_delay
            self._set_phase("starting", deadline)
            self._sleep_until(deadline)
            regions = {region.name: RegionHistory(region) for region in program.regions}
            period = 1 / program.frequency_hz
            path = self.directory / self._filename
            with (
                self.desktop.open_capture(program.source) as capture,
                path.open("x", encoding="utf-8", newline="\n") as stream,
            ):
                while True:
                    self._check_stop()
                    started = monotonic()
                    self._set_phase("running")
                    self._run_round(stream, capture, program, regions, trial)
                    if trial:
                        break
                    self._sleep_until(started + period)
        except RunStopped:
            pass
        except Exception as exc:
            logging.getLogger(__name__).exception("屏幕 OCR 运行中断")
            error = str(exc) or type(exc).__name__
        finally:
            with self._lock:
                self._phase = "error" if error else "idle"
                self._error = error
                self._deadline = None
                self._thread = None

    def _run_round(
        self, stream: TextIO, capture: Capture, program: Program, regions: dict[str, RegionHistory], trial: bool,
    ) -> None:
        """汇总这一轮并保留中断前已完成的结果。"""
        record = {
            "轮次": self._completed + 1,
            "时间": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "识别": {},
        }
        frames = RoundFrames(regions, [] if program.record_timings else None)
        try:
            self._execute_round(record, capture, program, trial, frames)
        except Exception as exc:
            if record["识别"] or record.get("触发器") or frames.timings:
                record["状态"] = "已停止" if isinstance(exc, RunStopped) else "中断"
                self._publish(stream, record, frames)
            raise
        self._publish(stream, record, frames)

    def _execute_round(
        self, record: dict, capture: Capture, program: Program, trial: bool, frames: RoundFrames,
    ) -> None:
        """先做每轮识别，再按顺序判定和执行触发器。"""
        frame = self._capture(capture, frames)
        periodic = [region.name for region in program.regions if region.periodic]
        try:
            frame.read_regions(periodic, self._check_stop)
        finally:
            for name in periodic:
                if name in frame.cache:
                    record["识别"][name] = frame.result(name, program.include_scores)
        for trigger in program.triggers:
            self._check_stop()
            if trigger.conditions:
                if frame is None:
                    frame = self._capture(capture, frames)
                if not self._matches(frame, trigger.conditions):
                    continue
            executed: list[dict] = []
            record.setdefault("触发器", []).append({"名称": trigger.name, "操作": executed})
            index = 0
            while index < len(trigger.actions):
                self._check_stop()
                action = trigger.actions[index]
                if not isinstance(action, OCRAction):
                    frame, result = self._execute_action(action, capture, program, trial, frames)
                    executed.append(result)
                    index += 1
                    continue

                # 连续读取不同区域时共享截图，重复读取同一区域会开始新一段。
                names: dict[str, None] = {}
                for offset in range(index, len(trigger.actions)):
                    next_action = trigger.actions[offset]
                    if not isinstance(next_action, OCRAction) or next_action.region in names:
                        break
                    names[next_action.region] = None
                frame = self._capture(capture, frames)
                try:
                    frame.read_regions(list(names), self._check_stop)
                finally:
                    for name in names:
                        if name in frame.cache:
                            frames.triggered.add(name)
                            result = frame.result(name, program.include_scores)
                            executed.append({"额外识别": {name: result}})
                index += len(names)

    def _execute_action(
        self, action: ClickAction | WaitAction, capture: Capture, program: Program, trial: bool, frames: RoundFrames,
    ) -> tuple[ScreenFrame | None, dict]:
        """按操作类型返回最新画面和结果。"""
        if isinstance(action, WaitAction):
            deadline = monotonic() + action.seconds
            self._set_phase("waiting", deadline)
            self._sleep_until(deadline)
            self._set_phase("running")
            return None, {"等待": action.seconds}

        frame = self._capture(capture, frames)
        return self._click_action(action, program.source, frame, trial)

    def _click_action(
        self, action: ClickAction, source: CaptureSource, frame: ScreenFrame, trial: bool,
    ) -> tuple[ScreenFrame | None, dict]:
        """在同一张新截图上筛选候选点并随机取一个。"""
        eligible = {
            (candidate.point.x, candidate.point.y): candidate.point
            for candidate in action.candidates
            if self._matches(frame, candidate.conditions)
        }
        key = "预演点击" if trial else "点击"
        if not eligible:
            return frame, {key: None}
        point = choice(list(eligible.values()))
        if not trial:
            # 点击和停止请求共用锁，停止返回后不会再发出点击。
            with self._lock:
                self._check_stop()
                if self.desktop.click(source, point) is False:
                    return frame, {key: None, "原因": "选定的窗口点击位置不可用"}
        return None, {key: (point.x, point.y)}

    def _capture(self, capture: Capture, frames: RoundFrames) -> ScreenFrame:
        """检查停止信号后抓取一帧并建立识别缓存。"""
        self._check_stop()
        image = capture()
        self._check_stop()
        frames.image = image
        return ScreenFrame(image, frames.regions, self.recognizer, frames.timings)

    def _matches(self, frame: ScreenFrame, conditions: list[Condition]) -> bool:
        """要求条件全部通过，每项检查前允许停止。"""
        for condition in conditions:
            self._check_stop()
            if not frame.matches(condition):
                return False
        return True

    def _publish(self, stream: TextIO, record: dict, frames: RoundFrames) -> None:
        """追加一个独立的 YAML 文档并更新界面输出。"""
        if frames.timings:
            record["OCR耗时(ms)"] = frames.timings
        output = dump_yaml(record, document=True)
        stream.write(output)
        stream.flush()
        regions = [
            {
                "name": name,
                "last_valid": [line.text for line in history.last_valid],
                "skipped_frames": history.skipped_frames,
            }
            for name, history in frames.regions.items()
        ]
        preview = (frames.image, frames.boxes()) if frames.image is not None else None
        with self._lock:
            self._completed += 1
            self._latest = output
            self._region_results = regions
            self._round_preview = preview

    def _set_phase(self, phase: str, deadline: float | None = None) -> None:
        """更新进度，同时保留已发出的停止请求。"""
        with self._lock:
            self._check_stop()
            self._phase = phase
            self._deadline = deadline

    def _sleep_until(self, deadline: float) -> None:
        """用可中断的等待避免积压周期任务。"""
        while (remaining := deadline - monotonic()) > 0:
            if self._cancel.wait(min(remaining, 60)):
                break
        self._check_stop()

    def _check_stop(self) -> None:
        """在开始下一步前响应停止请求。"""
        if self._cancel.is_set():
            raise RunStopped
