"""枚举 Windows 窗口，捕获客户区并换算点击坐标。"""

import ctypes
import sys
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable, Iterator

import cv2
import numpy as np

from .program import Point, Window

if sys.platform == "win32":
    import pywintypes
    import win32gui
    import win32process


class CaptureError(RuntimeError):
    """表示系统无法读取当前画面。"""


@dataclass(frozen=True)
class ClientArea:
    """记录客户区在桌面上的物理像素范围。"""

    left: int
    top: int
    width: int
    height: int


@contextmanager
def _physical_coordinates():
    """调用 Win32 接口时使用显示器的物理像素。"""
    set_context = ctypes.windll.user32.SetThreadDpiAwarenessContext
    set_context.argtypes = [ctypes.c_void_p]
    set_context.restype = ctypes.c_void_p
    per_monitor_aware_v2 = -4
    previous = set_context(per_monitor_aware_v2)
    try:
        yield
    finally:
        if previous:
            set_context(previous)


def _frame_bounds(handle: int) -> wintypes.RECT:
    """获取 Windows Graphics Capture 窗口帧对应的边界。"""
    extended_frame_bounds = 9
    frame = wintypes.RECT()
    result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(handle), extended_frame_bounds, ctypes.byref(frame), ctypes.sizeof(frame),
    )
    if result != 0:
        return wintypes.RECT(*win32gui.GetWindowRect(handle))
    return frame


def _client_area(handle: int) -> ClientArea:
    """将客户区与窗口帧的交集换算为截图范围。"""
    frame = _frame_bounds(handle)
    x0, y0, x1, y1 = win32gui.GetClientRect(handle)
    x0, y0 = win32gui.ClientToScreen(handle, (x0, y0))
    x1, y1 = win32gui.ClientToScreen(handle, (x1, y1))
    left = max(min(x0, x1), frame.left)
    top = max(min(y0, y1), frame.top)
    width = min(max(x0, x1), frame.right) - left
    height = min(max(y0, y1), frame.bottom) - top
    if width <= 0 or height <= 0:
        raise ValueError("窗口客户区为空，请恢复窗口后重试")
    return ClientArea(left, top, width, height)


def _visible(handle: int) -> bool:
    """检查窗口是否可见，排除最小化和其他虚拟桌面上的窗口。"""
    if not win32gui.IsWindowVisible(handle) or win32gui.IsIconic(handle):
        return False
    dwmwa_cloaked = 14
    cloaked = wintypes.DWORD()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(handle), dwmwa_cloaked, ctypes.byref(cloaked), ctypes.sizeof(cloaked),
    )
    return not cloaked.value


def windows() -> list[Window]:
    """列出当前桌面上可选的应用窗口。"""
    if sys.platform != "win32":
        return []
    result = []

    def add(handle: int, _) -> bool:
        """忽略枚举期间关闭或无法读取的窗口。"""
        try:
            title = win32gui.GetWindowText(handle).strip()
            if title and _visible(handle):
                area = _client_area(handle)
                _, pid = win32process.GetWindowThreadProcessId(handle)
                result.append(Window(
                    handle=handle, pid=pid, title=title, class_name=win32gui.GetClassName(handle),
                    width=area.width, height=area.height,
                ))
        except (pywintypes.error, ValueError):
            pass
        return True

    with _physical_coordinates():
        win32gui.EnumWindows(add, None)
    return result


def checked_client_area(window: Window) -> ClientArea:
    """确认窗口可用，且尺寸仍与选区和坐标匹配。"""
    if sys.platform != "win32":
        raise CaptureError("窗口截图需要 Windows 桌面会话")
    handle = window.handle
    try:
        with _physical_coordinates():
            _, pid = win32process.GetWindowThreadProcessId(handle)
            if pid != window.pid or win32gui.GetClassName(handle) != window.class_name:
                raise ValueError("原窗口已关闭，请刷新窗口列表并重新选择")
            if not _visible(handle):
                raise ValueError("请恢复所选窗口，再重新截图或开始运行")
            area = _client_area(handle)
    except pywintypes.error as exc:
        raise ValueError("原窗口已关闭，请刷新窗口列表并重新选择") from exc
    if (area.width, area.height) != (window.width, window.height):
        raise ValueError("窗口尺寸已变更，请刷新窗口列表并重新截图")
    return area


def click_position(window: Window, point: Point) -> tuple[int, int] | None:
    """返回目标窗口当前接得到点击的桌面位置。"""
    area = checked_client_area(window)
    if point.x >= area.width or point.y >= area.height:
        raise ValueError("点击坐标超出窗口客户区")
    position = (area.left + point.x, area.top + point.y)
    with _physical_coordinates():
        handle = win32gui.WindowFromPoint(position)
        if handle and win32gui.GetAncestor(handle, 2) == window.handle:  # GA_ROOT
            return position
    return None


@contextmanager
def open_window_capture(window: Window) -> Iterator[Callable[[], np.ndarray]]:
    """在一次预览或整个录制任务中复用同一窗口捕获会话。"""
    checked_client_area(window)
    try:
        import capturekit
    except ImportError as exc:
        raise CaptureError("缺少窗口捕获组件，请安装项目根目录 requirements.txt 中的 Windows 依赖") from exc

    capture = capturekit.ScreenCapture(capturekit.WindowSource(window.handle, client_area_only=True))

    def read() -> np.ndarray:
        """读取客户区画面并检查坐标尺寸。"""
        checked_client_area(window)
        image = capture.grab(timeout=3).data
        if image.shape[:2] != (window.height, window.width):
            raise CaptureError("窗口帧尺寸与客户区不一致，请刷新窗口列表并重新截图")
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    try:
        with capture:
            yield read
    except capturekit.CaptureTimeoutError as exc:
        raise CaptureError("没有收到窗口画面，请恢复窗口并确认该应用支持截图") from exc
    except capturekit.CaptureError as exc:
        raise CaptureError(f"Windows 无法捕获所选窗口：{exc}") from exc
