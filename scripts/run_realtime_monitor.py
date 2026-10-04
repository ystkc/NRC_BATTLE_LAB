#!/usr/bin/env python3
"""Run the low-latency Windows battle-window monitor."""

from __future__ import annotations

import argparse
import signal
from pathlib import Path
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from collector.screen.realtime import (
    BattleFeatureDetector,
    ForegroundWindowSelector,
    RealtimeBattleMonitor,
    WindowFrameSource,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal-reference", type=Path, default=Path("normal.jpg"))
    parser.add_argument("--output", type=Path, help="optional MP4 recording of the selected client area")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--ocr-pipe", default=r"\\.\pipe\pixpin-ocr")
    parser.add_argument("--control-pipe", default=r"\\.\pipe\nrc-battle-lab")
    parser.add_argument("--initial-state", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--select-timeout", type=float, default=120.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selector = ForegroundWindowSelector()
    hwnd, rect = selector.prompt_and_select(args.select_timeout)
    source = WindowFrameSource(hwnd, rect)
    detector = BattleFeatureDetector(args.normal_reference if args.normal_reference.is_file() else None)
    monitor = RealtimeBattleMonitor(
        source, detector, initial_state=args.initial_state, output_path=args.output,
        fps=args.fps, ocr_pipe=args.ocr_pipe, control_pipe=args.control_pipe,
    )
    signal.signal(signal.SIGINT, lambda *_args: monitor.stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_args: monitor.stop_event.set())
    print(f"control pipe: {args.control_pipe}", flush=True)
    monitor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
