"""Inspect one frame with OCR-free structural detectors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.screen.fast_detector import SingleFrameInspector


def read_input(args: argparse.Namespace) -> tuple[str, object]:
    if args.image:
        image = cv2.imread(str(args.image))
        if image is None:
            raise SystemExit(f"无法读取图片: {args.image}")
        return str(args.image), image
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit(f"无法打开视频: {args.video}")
    capture.set(cv2.CAP_PROP_POS_MSEC, args.time * 1000.0)
    ok, image = capture.read()
    capture.release()
    if not ok:
        raise SystemExit(f"无法读取视频时间点: {args.time}")
    return f"{args.video}@{args.time:.3f}s", image


def main() -> None:
    parser = argparse.ArgumentParser(description="对单帧执行 OCR-free 结构解析并绘制候选框")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image")
    source.add_argument("--video")
    parser.add_argument("--time", type=float, default=0.0, help="视频时间点，单位秒")
    parser.add_argument("--output", default="data/screen/inspection/frame_annotated.jpg")
    parser.add_argument("--json", dest="json_path", default="data/screen/inspection/frame_analysis.json")
    args = parser.parse_args()
    source_name, image = read_input(args)
    inspector = SingleFrameInspector()
    analysis = inspector.analyze(image, source_name)
    output = Path(args.output)
    json_path = Path(args.json_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), inspector.annotate(image, analysis))
    json_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output.resolve()), "json": str(json_path.resolve()), "scene": analysis["scene"], "scores": analysis["scores"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
