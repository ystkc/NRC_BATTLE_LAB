"""Low-latency Windows screen monitor for battle UI events.

The hot path intentionally does not run OCR.  It downsamples the latest
window frame and evaluates a handful of fixed, scale-independent regions.
OCR is requested explicitly through the control named pipe and is performed
on a copy of the newest frame by a single worker.
"""

from __future__ import annotations

import ctypes
import json
import os
import queue
import struct
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import cv2
import numpy as np
from ctypes import wintypes


REQUEST_MAGIC = 0x3152434F
RESPONSE_MAGIC = 0x3153434F
PROTOCOL_VERSION = 1
FORMAT_BGRA32 = 1
STATUS_OK = 0
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
REQUEST_HEADER = struct.Struct("<IHHIIIIQ")
RESPONSE_HEADER = struct.Struct("<IHHIIIIQ")


def _crop(image: np.ndarray, rect: tuple[float, float, float, float]) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = rect
    return image[
        max(0, int(y1 * height)):min(height, int(y2 * height)),
        max(0, int(x1 * width)):min(width, int(x2 * width)),
    ]


def _hsv_stats(image: np.ndarray) -> dict[str, float]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2]
    saturation = hsv[:, :, 1]
    hue = hsv[:, :, 0]
    return {
        "dark": float(np.mean(value < 70)),
        "light": float(np.mean((value > 175) & (saturation < 75))),
        "saturated": float(np.mean(saturation > 100)),
        "blue": float(np.mean((hue > 90) & (hue < 135) & (saturation > 70))),
        "orange": float(np.mean((hue < 25) & (saturation > 80) & (value > 100))),
    }


@dataclass(frozen=True)
class FeatureObservation:
    entrance: bool = False
    normal_icon: bool = False
    perform: bool = False
    perform_counter: bool = False
    speedcomp: bool = False
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def banner(self) -> bool:
        return self.perform or self.perform_counter

    def has(self, feature: str) -> bool:
        aliases = {
            "state1": "entrance",
            "state2": "normal_icon",
            "normal": "normal_icon",
            "state3": "banner",
            "perform_banner": "banner",
            "state4": "speedcomp",
            "speed": "speedcomp",
        }
        feature = aliases.get(feature.lower(), feature.lower())
        if feature == "banner":
            return self.banner
        return bool(getattr(self, feature, False))


class BattleFeatureDetector:
    """Fast detector specialized to the supplied 1558x974 UI layout."""

    target_size = (779, 487)
    normal_icon_rect = (10, 350, 95, 465)

    def __init__(self, normal_reference: str | Path | None = None):
        self.normal_icon_template = None
        if normal_reference:
            reference = cv2.imread(str(normal_reference), cv2.IMREAD_GRAYSCALE)
            if reference is not None:
                patch = reference[700:930, 20:190]
                self.normal_icon_template = cv2.resize(
                    patch, (85, 115), interpolation=cv2.INTER_AREA
                )

    def _normal_icon_score(self, gray: np.ndarray) -> float:
        if self.normal_icon_template is None:
            return 0.0
        x1, y1, x2, y2 = self.normal_icon_rect
        roi = gray[y1:y2, x1:x2]
        if roi.shape[0] < 115 or roi.shape[1] < 85:
            return 0.0
        return float(cv2.matchTemplate(roi, self.normal_icon_template, cv2.TM_CCOEFF_NORMED).max())

    def detect(self, image: np.ndarray) -> FeatureObservation:
        if image is None or image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
            raise ValueError("Expected a non-empty BGR image")
        small = cv2.resize(image, self.target_size, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        top_center = _hsv_stats(_crop(small, (0.36, 0.0, 0.64, 0.14)))
        entrance_center = _hsv_stats(_crop(small, (0.35, 0.10, 0.65, 0.45)))
        left_banner = _hsv_stats(_crop(small, (0.0, 0.075, 0.31, 0.19)))
        right_banner = _hsv_stats(_crop(small, (0.69, 0.075, 1.0, 0.19)))
        speed_header = _hsv_stats(_crop(small, (0.36, 0.20, 0.94, 0.33)))
        speed_body = _hsv_stats(_crop(small, (0.36, 0.33, 0.94, 0.78)))

        entrance_score = min(
            1.0,
            0.45 * max(0.0, (top_center["dark"] - 0.34) / 0.25)
            + 0.35 * max(0.0, (entrance_center["saturated"] - 0.62) / 0.30)
            + 0.20 * max(0.0, (entrance_center["orange"] - 0.28) / 0.30),
        )
        left_banner_score = min(
            1.0,
            0.75 * max(0.0, (left_banner["dark"] - 0.18) / 0.25)
            + 0.25 * max(0.0, (left_banner["saturated"] - 0.08) / 0.40),
        )
        right_banner_score = min(
            1.0,
            0.75 * max(0.0, (right_banner["dark"] - 0.18) / 0.25)
            + 0.25 * max(0.0, (right_banner["saturated"] - 0.08) / 0.40),
        )
        speed_score = min(
            1.0,
            0.70 * max(0.0, (speed_header["light"] - 0.35) / 0.40)
            + 0.30 * max(0.0, (speed_body["dark"] - 0.30) / 0.45),
        )
        icon_score = self._normal_icon_score(gray)
        return FeatureObservation(
            entrance=entrance_score >= 0.48,
            normal_icon=icon_score >= 0.84,
            perform=left_banner_score >= 0.35 and left_banner["saturated"] < 0.45,
            perform_counter=right_banner_score >= 0.35 and right_banner["saturated"] < 0.45,
            speedcomp=speed_score >= 0.48,
            scores={
                "entrance": round(entrance_score, 4),
                "normal_icon": round(icon_score, 4),
                "perform": round(left_banner_score, 4),
                "perform_counter": round(right_banner_score, 4),
                "speedcomp": round(speed_score, 4),
            },
        )


@dataclass(frozen=True)
class WindowRect:
    left: int
    top: int
    width: int
    height: int

    def as_mss(self) -> dict[str, int]:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}


class ForegroundWindowSelector:
    """Select a top-level window without requiring the user to type its title."""

    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Window selection is only available on Windows")
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self._set_dpi_awareness()

    def _set_dpi_awareness(self) -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                self.user32.SetProcessDPIAware()
            except AttributeError:
                pass

    def _root_window(self, hwnd: int) -> int:
        return int(self.user32.GetAncestor(hwnd, 2) or hwnd)

    def _belongs_to_current_process(self, hwnd: int) -> bool:
        process_id = ctypes.c_ulong()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return int(process_id.value) == os.getpid()

    def _client_rect(self, hwnd: int) -> WindowRect:
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        if not self.user32.GetClientRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError("GetClientRect failed")
        origin = POINT(0, 0)
        if not self.user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            raise RuntimeError("ClientToScreen failed")
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width <= 0 or height <= 0:
            raise RuntimeError("Selected window has an empty client area")
        return WindowRect(origin.x, origin.y, width, height)

    def current(self) -> tuple[int, WindowRect]:
        hwnd = int(self.user32.GetForegroundWindow())
        if not hwnd or not self.user32.IsWindowVisible(hwnd):
            raise RuntimeError("No visible foreground window")
        hwnd = self._root_window(hwnd)
        return hwnd, self._client_rect(hwnd)

    def prompt_and_select(self, timeout: float = 120.0) -> tuple[int, WindowRect]:
        print("请切换到目标窗口；检测到目标窗口后会自动记录句柄。按 Ctrl+C 取消。", flush=True)
        deadline = time.monotonic() + timeout
        own_hwnd = int(self.user32.GetConsoleWindow() or 0)
        last_hwnd = 0
        stable_since = 0.0
        while time.monotonic() < deadline:
            hwnd = int(self.user32.GetForegroundWindow() or 0)
            root = self._root_window(hwnd) if hwnd else 0
            if root and root != own_hwnd and not self._belongs_to_current_process(root) and self.user32.IsWindowVisible(root):
                if root != last_hwnd:
                    last_hwnd, stable_since = root, time.monotonic()
                if time.monotonic() - stable_since >= 0.35:
                    rect = self._client_rect(root)
                    print(f"已选择窗口 hwnd=0x{root:x}, client={rect.width}x{rect.height}", flush=True)
                    return root, rect
            time.sleep(0.05)
        raise TimeoutError("Timed out while waiting for a target window")


class WindowFrameSource:
    def __init__(self, hwnd: int, rect: WindowRect):
        if os.name != "nt":
            raise RuntimeError("Window capture is only available on Windows")
        from mss import mss

        self.hwnd = hwnd
        self.rect = rect
        self._mss = mss()
        self._user32 = ctypes.windll.user32

    def refresh_rect(self) -> WindowRect:
        selector = ForegroundWindowSelector()
        self.rect = selector._client_rect(self.hwnd)
        return self.rect

    def grab(self) -> np.ndarray:
        raw = np.asarray(self._mss.grab(self.rect.as_mss()))
        return np.ascontiguousarray(raw[:, :, :3])

    def close(self) -> None:
        self._mss.close()


def _read_exact(pipe: Any, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = pipe.read(size - len(chunks))
        if not chunk:
            raise RuntimeError("named pipe closed while reading")
        chunks.extend(chunk)
    return bytes(chunks)


def _write_all(pipe: Any, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = pipe.write(data[offset:])
        if written is None:
            written = len(data) - offset
        if written <= 0:
            raise RuntimeError("named pipe closed while writing")
        offset += written
    pipe.flush()


class NamedPipeOCRClient:
    """Persistent client for the binary protocol documented by ocr_service."""

    def __init__(self, pipe_name: str = r"\\.\pipe\pixpin-ocr"):
        self.pipe_name = pipe_name
        self.pipe = None
        self.request_id = 0
        self.lock = threading.Lock()

    def _connect(self) -> Any:
        if self.pipe is None:
            self.pipe = open(self.pipe_name, "r+b", buffering=0)
        return self.pipe

    def request(self, frame: np.ndarray) -> dict[str, Any]:
        if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("OCR expects a BGR frame")
        with self.lock:
            self.request_id += 1
            request_id = self.request_id
            height, width = frame.shape[:2]
            bgra = cv2.cvtColor(np.ascontiguousarray(frame), cv2.COLOR_BGR2BGRA)
            payload = bgra.tobytes()
            header = REQUEST_HEADER.pack(
                REQUEST_MAGIC, PROTOCOL_VERSION, FORMAT_BGRA32,
                width, height, width * 4, len(payload), request_id,
            )
            try:
                pipe = self._connect()
                _write_all(pipe, header)
                _write_all(pipe, payload)
                response = _read_exact(pipe, RESPONSE_HEADER.size)
                magic, version, _reserved, status, out_width, out_height, json_bytes, out_id = RESPONSE_HEADER.unpack(response)
                if magic != RESPONSE_MAGIC or version != PROTOCOL_VERSION or out_id != request_id:
                    raise RuntimeError("invalid OCR response header")
                if json_bytes > MAX_RESPONSE_BYTES:
                    raise RuntimeError("OCR response is too large")
                result = json.loads(_read_exact(pipe, json_bytes).decode("utf-8"))
                result.setdefault("_protocol", {})
                result["_protocol"].update({"status": status, "width": out_width, "height": out_height, "request_id": out_id})
                return result
            except Exception:
                self.close()
                raise

    def close(self) -> None:
        if self.pipe is not None:
            try:
                self.pipe.close()
            finally:
                self.pipe = None


@dataclass
class _OCRJob:
    frame: np.ndarray
    feature: str
    request_id: int
    submitted_at: float


class OCRWorker:
    def __init__(self, client: NamedPipeOCRClient, result_callback: Callable[[dict[str, Any]], None] | None = None):
        self.client = client
        self.result_callback = result_callback
        self.jobs: queue.Queue[_OCRJob | None] = queue.Queue(maxsize=1)
        self.results: dict[int, dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.thread = threading.Thread(target=self._run, name="ocr-worker", daemon=True)
        self.thread.start()

    def submit(self, job: _OCRJob) -> bool:
        try:
            self.jobs.get_nowait()
        except queue.Empty:
            pass
        try:
            self.jobs.put_nowait(job)
            return True
        except queue.Full:
            return False

    def result(self, request_id: int, timeout: float) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout
        with self.condition:
            while request_id not in self.results:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.condition.wait(remaining)
            return self.results.pop(request_id)

    def _run(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                return
            try:
                result = self.client.request(job.frame)
                result.update({"feature": job.feature, "request_id": job.request_id, "latency_ms": round((time.monotonic() - job.submitted_at) * 1000, 2)})
            except Exception as error:
                result = {"ok": False, "error": str(error), "feature": job.feature, "request_id": job.request_id}
            with self.condition:
                self.results[job.request_id] = result
                self.condition.notify_all()
            if self.result_callback:
                self.result_callback(result)

    def close(self) -> None:
        try:
            self.jobs.put_nowait(None)
        except queue.Full:
            pass
        self.client.close()


class ControlNamedPipeServer:
    """Line-delimited JSON control pipe for feature-triggered OCR."""

    def __init__(self, pipe_name: str, handler: Callable[[dict[str, Any]], dict[str, Any]]):
        self.pipe_name = pipe_name
        self.handler = handler
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._serve, name="control-pipe", daemon=True)

    def start(self) -> None:
        if os.name != "nt":
            raise RuntimeError("Named pipe server is only available on Windows")
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _serve(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateNamedPipeW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint32, ctypes.c_void_p,
        ]
        kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
        kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel32.ConnectNamedPipe.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        pipe_open = 0x00000003
        pipe_type_byte = 0x00000000
        pipe_readmode_byte = 0x00000000
        pipe_wait = 0x00000000
        invalid_handle = wintypes.HANDLE(-1).value
        while not self.stop_event.is_set():
            handle = kernel32.CreateNamedPipeW(
                self.pipe_name, pipe_open, pipe_type_byte | pipe_readmode_byte | pipe_wait,
                1, 65536, 65536, 1000, None,
            )
            handle_value = handle.value if hasattr(handle, "value") else int(handle)
            if handle_value == invalid_handle:
                time.sleep(0.1)
                continue
            connected = kernel32.ConnectNamedPipe(handle, None)
            if not connected and ctypes.get_last_error() != 535:  # ERROR_PIPE_CONNECTED
                kernel32.CloseHandle(handle)
                continue
            import msvcrt

            fd = msvcrt.open_osfhandle(handle_value, os.O_RDWR | os.O_BINARY)
            pipe = os.fdopen(fd, "r+b", buffering=0)
            try:
                for raw_line in pipe:
                    if self.stop_event.is_set():
                        break
                    try:
                        request = json.loads(raw_line.decode("utf-8"))
                        response = self.handler(request)
                    except Exception as error:
                        response = {"ok": False, "error": str(error)}
                    pipe.write((json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                    pipe.flush()
            finally:
                pipe.close()


class RealtimeBattleMonitor:
    """Capture, detect, transition, record, and serve feature-triggered OCR."""

    def __init__(
        self,
        source: WindowFrameSource,
        detector: BattleFeatureDetector,
        *,
        initial_state: int = 1,
        output_path: str | Path | None = None,
        fps: float = 30.0,
        ocr_pipe: str = r"\\.\pipe\pixpin-ocr",
        control_pipe: str = r"\\.\pipe\nrc-battle-lab",
    ):
        if initial_state not in (1, 2, 3):
            raise ValueError("initial_state must be 1, 2, or 3")
        self.source = source
        self.detector = detector
        self.state = initial_state
        self.fps = fps
        self.output_path = Path(output_path) if output_path else None
        self.writer = None
        self.latest_frame: np.ndarray | None = None
        self.latest_observation = FeatureObservation()
        self.latest_sequence = 0
        self.latest_timestamp = 0.0
        self.condition = threading.Condition()
        self.stop_event = threading.Event()
        self.icon_armed = True
        self.speedcomp_active = False
        self.transition_count = 0
        self.ocr_request_id = 0
        self.ocr = OCRWorker(NamedPipeOCRClient(ocr_pipe))
        self.control = ControlNamedPipeServer(control_pipe, self.handle_control)

    def _transition(self, new_state: int, reason: str) -> None:
        if new_state != self.state:
            self.state = new_state
            self.transition_count += 1
            print(f"state={new_state} reason={reason}", flush=True)

    def _update_state(self, observation: FeatureObservation) -> None:
        if observation.normal_icon:
            if self.icon_armed:
                if self.state == 2:
                    self._transition(3, "normal_icon")
                elif self.state == 3:
                    self._transition(2, "normal_icon")
                self.icon_armed = False
        else:
            self.icon_armed = True
        if self.state == 1 and observation.entrance:
            self._transition(2, "entrance")
        if observation.speedcomp and not self.speedcomp_active:
            print(f"state=4 return_state={self.state}", flush=True)
        self.speedcomp_active = observation.speedcomp

    def _snapshot(self) -> tuple[np.ndarray | None, int, FeatureObservation, float]:
        with self.condition:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
            return frame, self.latest_sequence, self.latest_observation, self.latest_timestamp

    def wait_for_feature(self, feature: str, timeout: float = 10.0, after_sequence: int = 0) -> tuple[np.ndarray, int, FeatureObservation, float] | None:
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                if self.latest_frame is not None and self.latest_sequence > after_sequence and self.latest_observation.has(feature):
                    return self.latest_frame.copy(), self.latest_sequence, self.latest_observation, self.latest_timestamp
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.condition.wait(remaining)

    def _submit_ocr(self, feature: str, frame: np.ndarray) -> dict[str, Any]:
        self.ocr_request_id += 1
        request_id = self.ocr_request_id
        job = _OCRJob(frame.copy(), feature, request_id, time.monotonic())
        if not self.ocr.submit(job):
            return {"ok": False, "error": "OCR queue is busy", "request_id": request_id}
        result = self.ocr.result(request_id, 30.0)
        return result or {"ok": False, "error": "OCR timeout", "request_id": request_id}

    def handle_control(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = str(request.get("op", request.get("command", "status"))).lower()
        if operation == "status":
            _frame, sequence, observation, timestamp = self._snapshot()
            return {
                "ok": True,
                "state": self.state,
                "transient_state": 4 if observation.speedcomp else None,
                "sequence": sequence,
                "timestamp": timestamp,
                "features": observation.scores,
            }
        if operation not in {"ocr", "recognize"}:
            raise ValueError("supported operations: status, ocr")
        feature = str(request.get("feature", "current"))
        timeout = float(request.get("timeout", 10.0))
        if feature == "current":
            frame, sequence, observation, timestamp = self._snapshot()
        else:
            with self.condition:
                after_sequence = self.latest_sequence
            found = self.wait_for_feature(feature, timeout=timeout, after_sequence=after_sequence)
            if found is None:
                return {"ok": False, "error": "feature timeout", "feature": feature}
            frame, sequence, observation, timestamp = found
        if frame is None:
            return {"ok": False, "error": "no frame available"}
        result = self._submit_ocr(feature, frame)
        result.update({"state": self.state, "sequence": sequence, "timestamp": timestamp, "detector": observation.scores})
        return result

    def run(self) -> None:
        self.control.start()
        frame_interval = 1.0 / max(1.0, self.fps)
        next_frame = time.monotonic()
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                if now < next_frame:
                    time.sleep(min(0.002, next_frame - now))
                    continue
                next_frame = max(next_frame + frame_interval, now)
                frame = self.source.grab()
                observation = self.detector.detect(frame)
                self._update_state(observation)
                with self.condition:
                    self.latest_frame = frame
                    self.latest_observation = observation
                    self.latest_sequence += 1
                    self.latest_timestamp = time.time()
                    self.condition.notify_all()
                if self.output_path:
                    if self.writer is None:
                        self.output_path.parent.mkdir(parents=True, exist_ok=True)
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        self.writer = cv2.VideoWriter(str(self.output_path), fourcc, self.fps, (frame.shape[1], frame.shape[0]))
                        if not self.writer.isOpened():
                            raise RuntimeError(f"Could not open video writer: {self.output_path}")
                    self.writer.write(frame)
        finally:
            self.stop_event.set()
            self.control.stop()
            self.ocr.close()
            if self.writer is not None:
                self.writer.release()
            self.source.close()


def iter_json_lines(path: str | Path) -> Iterable[dict[str, Any]]:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)
