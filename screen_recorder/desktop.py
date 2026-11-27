"""统一显示器、窗口截图和 Windows 鼠标左键点击。"""

import ctypes
import sys
from contextlib import contextmanager
from ctypes import wintypes
from typing import Callable, Iterator

import cv2
import numpy as np
from mss import MSS
from mss.exception import ScreenShotError

from .program import CaptureSource, Monitor, Point, Window
from .window_capture import CaptureError, checked_client_area, click_position, open_window_capture, windows


Capture = Callable[[], np.ndarray]


class MouseInput(ctypes.Structure):
    """声明 Windows 的 MOUSEINPUT 结构体。"""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class Input(ctypes.Structure):
    """声明 INPUT 中鼠标事件使用的成员及布局。"""

    _fields_ = [("type", wintypes.DWORD), ("mouse", MouseInput)]


class Desktop:
    """在物理像素坐标系下截图和点击。"""

    def monitors(self) -> list[Monitor]:
        """返回当前连接的显示器。"""
        with MSS() as desktop:
            return [
                self._monitor(index, screen)
                for index, screen in enumerate(desktop.monitors[1:], start=1)
            ]

    def validate_monitor(self, monitor: Monitor) -> None:
        """确认配置里的屏幕范围仍与桌面一致。"""
        if monitor not in self.monitors():
            raise ValueError("显示器布局已变更，请刷新显示器列表并重新选取截图")

    def windows(self) -> list[Window]:
        """返回当前可选的应用窗口。"""
        return windows()

    def validate_source(self, source: CaptureSource) -> None:
        """确认截图来源当前可用。"""
        if isinstance(source, Window):
            checked_client_area(source)
        else:
            self.validate_monitor(source)

    @contextmanager
    def open_capture(self, source: CaptureSource) -> Iterator[Capture]:
        """为预览或录制任务提供重复采样同一来源的方法。"""
        if isinstance(source, Window):
            with open_window_capture(source) as capture:
                yield capture
        else:
            yield lambda: self.capture(source)

    def capture(self, monitor: Monitor) -> np.ndarray:
        """截取所选显示器并返回 BGR 像素。"""
        try:
            with MSS() as desktop:
                if monitor.index >= len(desktop.monitors):
                    raise ValueError("所选显示器已断开，请刷新显示器列表")
                screen = desktop.monitors[monitor.index]
                if self._monitor(monitor.index, screen) != monitor:
                    raise ValueError("显示器布局已变更，请刷新显示器列表并重新选取截图")
                pixels = np.asarray(desktop.grab(screen))
                return cv2.cvtColor(pixels, cv2.COLOR_BGRA2BGR)
        except ScreenShotError as exc:
            raise CaptureError("无法读取桌面截图，请从已解锁的 Windows 桌面终端启动服务") from exc

    def click(self, source: CaptureSource, point: Point) -> bool:
        """将截图内坐标转换为桌面坐标并左击。"""
        if sys.platform != "win32":
            raise RuntimeError("鼠标点击需要 Windows 桌面会话")
        if isinstance(source, Window):
            position = click_position(source, point)
            if position is None:
                return False
        else:
            self.validate_monitor(source)
            position = (source.left + point.x, source.top + point.y)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        if not user32.SetPhysicalCursorPos(*position):
            raise ctypes.WinError(ctypes.get_last_error())
        if isinstance(source, Window):
            cursor = wintypes.POINT()
            if not user32.GetPhysicalCursorPos(ctypes.byref(cursor)):
                raise ctypes.WinError(ctypes.get_last_error())
            if position != (cursor.x, cursor.y) or position != click_position(source, point):
                return False

        left_down = 0x0002
        left_up = 0x0004
        events = (Input * 2)(
            Input(mouse=MouseInput(dwFlags=left_down)),
            Input(mouse=MouseInput(dwFlags=left_up)),
        )
        sent = user32.SendInput(len(events), events, ctypes.sizeof(Input))
        if sent != len(events):
            if sent == 1:
                user32.SendInput(1, ctypes.byref(events[1]), ctypes.sizeof(Input))
            raise RuntimeError("Windows 未能完成左键点击，请检查目标窗口的权限")
        return True

    @staticmethod
    def _monitor(index: int, screen: dict) -> Monitor:
        """从 MSS 的信息中取出用于校验的显示器范围。"""
        return Monitor(
            index=index, left=screen["left"], top=screen["top"],
            width=screen["width"], height=screen["height"],
        )
