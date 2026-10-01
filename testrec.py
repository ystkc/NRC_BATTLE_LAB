#!/usr/bin/env python3
"""
全屏录屏脚本
- 开始：直接运行
- 停止：按键盘 q，或关闭预览窗口，或 Ctrl+C
- 输出：当前目录下的 recording_时间戳.mp4
"""

import time
import datetime
import os

import cv2
import numpy as np
from mss import mss, ScreenShotError


def record_screen(fps: float = 30.0, output_file: str | None = None):
    if output_file is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"recording_{ts}.mp4"

    # 选主显示器（monitors[0] 是所有显示器拼接，monitors[1] 是第一个屏）
    with mss() as sct:
        monitor = sct.monitors[1]
        width, height = monitor["width"], monitor["height"]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_file, fourcc, fps, (width, height))

        if not writer.isOpened():
            raise RuntimeError("VideoWriter 打开失败，换编码或检查文件路径")

        print(f"[录屏中] {width}x{height} @ {fps}fps")
        print("停止方式：按 q / 关窗口 / Ctrl+C")

        frame_interval = 1.0 / fps
        last_grab = 0.0

        try:
            while True:
                # 控制采集节奏，避免录出来比实际快
                now = time.time()
                if now - last_grab < frame_interval:
                    time.sleep(0.001)
                    continue
                last_grab = now

                img = np.array(sct.grab(monitor))
                # mss 返回 BGRA，OpenCV 用 BGR
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                writer.write(frame)
                cv2.imshow("Recording - press q to stop", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[用户按 q 停止]")
                    break

                # 窗口被关掉也停
                if cv2.getWindowProperty("Recording - press q to stop",
                                         cv2.WND_PROP_VISIBLE) < 1:
                    print("[窗口关闭，停止]")
                    break

        except KeyboardInterrupt:
            print("[Ctrl+C 停止]")
        finally:
            writer.release()
            cv2.destroyAllWindows()
            if os.path.exists(output_file):
                print(f"[已保存] {output_file}")
            else:
                print("[未生成文件]")


if __name__ == "__main__":
    record_screen(fps=30.0)