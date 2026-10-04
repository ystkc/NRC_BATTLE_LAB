"""Run the full-image OCR comparison and save one JSON result."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from ocr_benchmark_common import (
    DEFAULT_FULL_RESULTS,
    DEFAULT_IMAGE,
    EXPECTED_LINES,
    PixPinOCRClient,
    extract_pixpin_text,
    join_detections,
    parse_rapidocr,
    score_text,
    sort_detections,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def rapidocr_runner(image: np.ndarray) -> tuple[Callable[[], list[dict[str, Any]]], dict[str, Any]]:
    sys.path.insert(0, str(PROJECT_DIR / ".screen-deps"))
    from rapidocr import RapidOCR

    engine = RapidOCR()

    def run() -> list[dict[str, Any]]:
        return parse_rapidocr(engine(image))

    return run, {"model": "PP-OCRv6_det_small + PP-OCRv6_rec_small", "backend": "onnxruntime"}


def easyocr_runner(image: np.ndarray) -> tuple[Callable[[], list[dict[str, Any]]], dict[str, Any]]:
    import easyocr

    reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)

    def run() -> list[dict[str, Any]]:
        return sort_detections([
            {"text": str(text), "score": float(score), "box": np.asarray(box).tolist()}
            for box, text, score in reader.readtext(image, detail=1, paragraph=False)
        ])

    return run, {"model": "craft_mlt_25k + zh_sim_g2", "backend": "torch CPU"}


def paddleocr_runner(image_path: Path) -> tuple[Callable[[], list[dict[str, Any]]], dict[str, Any]]:
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    from paddleocr import PaddleOCR

    engine = PaddleOCR(
        lang="ch",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )

    def run() -> list[dict[str, Any]]:
        result = next(iter(engine.predict(str(image_path))))
        data = result.json if callable(getattr(result, "json", None)) else getattr(result, "json", result)
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, list):
            data = data[0] if data else {}
        data = data.get("res", data) if isinstance(data, dict) else {}
        return sort_detections([
            {"text": str(text), "score": float(score), "box": np.asarray(box).tolist()}
            for text, score, box in zip(
                data.get("rec_texts", []),
                data.get("rec_scores", []),
                data.get("rec_polys", data.get("dt_polys", [])),
            )
        ])

    return run, {"model": "PaddleOCR default PP-OCRv6", "backend": "Paddle Inference CPU"}


def pixpin_ocr_runner(image_path: Path, client: PixPinOCRClient) -> tuple[Callable[[], list[dict[str, Any]]], dict[str, Any]]:
    from ocr_service.example_client import load_bgra

    width, height, pixels, timings = load_bgra(image_path, None)

    def run() -> list[dict[str, Any]]:
        return extract_pixpin_text(client.recognize(width, height, pixels))

    return run, {
        "model": "PixPin OCR / PixOCR2 resident service",
        "backend": "Windows named pipe + native ONNX runtime",
        "service_pipe": client.pipe_name,
    }


def benchmark_engine(name: str, factory: Callable[[], tuple[Callable[[], list[dict[str, Any]]], dict[str, Any]]], repeats: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        runner, metadata = factory()
        init_ms = (time.perf_counter() - started) * 1000
        runner()
        elapsed: list[float] = []
        detections: list[dict[str, Any]] = []
        for _ in range(repeats):
            tick = time.perf_counter()
            detections = runner()
            elapsed.append((time.perf_counter() - tick) * 1000)
        close = getattr(runner, "close", None)
        if close is not None:
            close()
        text = join_detections(detections)
        return {
            "engine": name,
            **metadata,
            "init_ms": init_ms,
            "inference_ms": elapsed,
            "average_ms": sum(elapsed) / len(elapsed),
            "detections": sort_detections(detections),
            "text": text,
            "score": score_text(text),
        }
    except Exception as exc:
        return {"engine": name, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}


def benchmark_winrt(image_path: Path, repeats: int) -> dict[str, Any]:
    from ocr_benchmark_common import run_winrt

    try:
        payload = run_winrt(Path(__file__).with_name("winrt_ocr.ps1"), image_path, repeats)
        payload["score"] = score_text(payload.get("text", ""))
        return payload
    except Exception as exc:
        return {"engine": "WinRT OCR", "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare OCR engines on test.png.")
    parser.add_argument("image", nargs="?", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--engines", default="pixpin_ocr,easyocr,paddleocr,rapidocr,winrt", help="Comma-separated: pixpin_ocr,easyocr,paddleocr,rapidocr,winrt")
    parser.add_argument("--pixpin-ocr-pipe", default=os.environ.get("PIXPin_OCR_PIPE", r"\\.\pipe\pixpin-ocr"))
    parser.add_argument("--output", type=Path, default=DEFAULT_FULL_RESULTS)
    args = parser.parse_args()
    if args.repeats <= 0:
        raise SystemExit("--repeats must be positive")
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"Cannot read image: {args.image}")

    engines: list[dict[str, Any]] = []
    pixpin_client = None
    try:
        for engine in args.engines.split(","):
            if engine == "pixpin_ocr":
                pixpin_client = PixPinOCRClient(args.pixpin_ocr_pipe)
                engines.append(benchmark_engine("PixPin_OCR", lambda: pixpin_ocr_runner(args.image, pixpin_client), args.repeats))
            elif engine == "RapidOCR":
                engines.append(benchmark_engine("RapidOCR", lambda: rapidocr_runner(image), args.repeats))
            elif engine == "EasyOCR":
                engines.append(benchmark_engine("EasyOCR", lambda: easyocr_runner(image), args.repeats))
            elif engine == "PaddleOCR":
                engines.append(benchmark_engine("PaddleOCR", lambda: paddleocr_runner(args.image), args.repeats))
            elif engine == "winrt":
                engines.append(benchmark_winrt(args.image, args.repeats))
        result = {
            "schema_version": 2,
            "experiment": "full_image",
            "image": args.image.name,
            "image_size": [int(image.shape[1]), int(image.shape[0])],
            "repeats": args.repeats,
            "expected_lines": EXPECTED_LINES,
            "engines": engines,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        for item in engines:
            if item.get("error"):
                print(f"{item['engine']}: ERROR {item['error']}")
                continue
            score = item["score"]
            print(f"{item['engine']}: avg={item['average_ms']:.1f} ms, chars={score['char_accuracy']:.1%}, numbers={score['numeric_accuracy']:.1%}")
        print(f"Saved {args.output}")
    finally:
        if pixpin_client is not None:
            pixpin_client.close()


if __name__ == "__main__":
    main()
