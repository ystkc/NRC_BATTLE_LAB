"""Run the fixed-region OCR comparison and save one consolidated JSON result."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import cv2

from ocr_benchmark_common import (
    DEFAULT_IMAGE,
    DEFAULT_REGION_RESULTS,
    PixPinOCRClient,
    REGIONS,
    extract_pixpin_text,
    image_variants,
    parse_rapidocr,
    region_bounds,
    run_winrt,
    score_region,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def save_result(path: Path, result: dict[str, Any]) -> None:
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def selected_regions(value: str | None) -> dict[str, tuple[tuple[int, int, int, int], str]]:
    if not value:
        return REGIONS
    names = {item.strip() for item in value.split(",") if item.strip()}
    unknown = names - REGIONS.keys()
    if unknown:
        raise SystemExit(f"Unknown region(s): {', '.join(sorted(unknown))}")
    return {name: REGIONS[name] for name in REGIONS if name in names}


def append_record(result: dict[str, Any], engine: str, record: dict[str, Any], output: Path) -> None:
    engine_result = next(item for item in result["engines"] if item["engine"] == engine)
    engine_result["results"].append(record)
    save_result(output, result)


def run_rapidocr(image, regions, result, output) -> None:
    sys.path.insert(0, str(PROJECT_DIR / ".screen-deps"))
    from rapidocr import RapidOCR

    engine = RapidOCR()
    for name, (box, expected) in regions.items():
        x1, y1, x2, y2 = region_bounds(box)
        for variant, crop in image_variants(image[y1:y2, x1:x2]).items():
            started = time.perf_counter()
            detections = parse_rapidocr(engine(crop, text_score=0.25))
            elapsed_ms = (time.perf_counter() - started) * 1000
            text = "".join(str(item["text"]) for item in detections)
            record = {
                "region": name, "box": list(box), "variant": variant,
                "elapsed_ms": elapsed_ms, "expected": expected,
                "detections": detections, "text": text,
                "score": score_region(expected, text),
            }
            append_record(result, "RapidOCR", record, output)
            print(f"RapidOCR {name:16} {variant:12} {elapsed_ms:7.1f} ms  {text!r}")


def run_pixpin_ocr(image_path: Path, regions, result, output, pipe_name: str) -> None:
    from ocr_service.example_client import load_bgra

    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".pixpin_ocr_") as temp_dir:
        with PixPinOCRClient(pipe_name) as client:
            image = cv2.imread(str(image_path))
            for name, (box, expected) in regions.items():
                if name.endswith("_number"):
                    continue
                x1, y1, x2, y2 = region_bounds(box)
                source = image[y1:y2, x1:x2]
                for variant, crop in {
                    "native": source,
                    "x3": cv2.resize(source, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC),
                }.items():
                    crop_path = Path(temp_dir) / f"{name}_{variant}.png"
                    cv2.imwrite(str(crop_path), crop)
                    width, height, pixels, timings = load_bgra(crop_path, None)
                    started = time.perf_counter()
                    payload = client.recognize(width, height, pixels)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    detections = extract_pixpin_text(payload)
                    text = "\n".join(str(item["text"]) for item in detections)
                    record = {
                        "region": name, "box": list(box), "variant": variant,
                        "elapsed_ms": elapsed_ms, "expected": expected,
                        "detections": detections, "text": text,
                        "score": score_region(expected, text),
                    }
                    append_record(result, "PixPin_OCR", record, output)
                    print(f"PixPin_OCR {name:12} {variant:7} {elapsed_ms:7.1f} ms  {text!r}")


def run_winrt_engine(image_path: Path, regions, result, output, repeats: int) -> None:
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".winrt_ocr_") as temp_dir:
        image = cv2.imread(str(image_path))
        for name, (box, expected) in regions.items():
            if name.endswith("_number"):
                continue
            x1, y1, x2, y2 = region_bounds(box)
            crop = cv2.resize(image[y1:y2, x1:x2], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            crop_path = Path(temp_dir) / f"{name}.png"
            cv2.imwrite(str(crop_path), crop)
            started = time.perf_counter()
            payload = run_winrt(Path(__file__).with_name("winrt_ocr.ps1"), crop_path, repeats)
            elapsed_ms = (time.perf_counter() - started) * 1000
            text = str(payload.get("text", ""))
            record = {
                "region": name, "box": list(box), "variant": "x3",
                "elapsed_ms": elapsed_ms, "inference_ms": payload.get("inference_ms", []),
                "expected": expected, "detections": payload.get("detections", []),
                "text": text, "score": score_region(expected, text),
            }
            append_record(result, "WinRT OCR", record, output)
            print(f"WinRT OCR {name:14} {elapsed_ms:7.1f} ms  {text!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare OCR engines on fixed regions of test.png.")
    parser.add_argument("image", nargs="?", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--engines", default="pixpin_ocr,rapidocr,winrt", help="Comma-separated: rapidocr,pixpin_ocr,winrt")
    parser.add_argument("--regions", help="Comma-separated region names; defaults to all regions")
    parser.add_argument("--pixpin-ocr-pipe", default=r"\\.\pipe\pixpin-ocr")
    parser.add_argument("--winrt-repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, default=DEFAULT_REGION_RESULTS)
    args = parser.parse_args()
    if args.winrt_repeats <= 0:
        raise SystemExit("--winrt-repeats must be positive")
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"Cannot read image: {args.image}")
    engines = [item.strip().lower() for item in args.engines.split(",") if item.strip()]
    allowed = {"rapidocr", "pixpin_ocr", "winrt"}
    unknown = set(engines) - allowed
    if unknown:
        raise SystemExit(f"Unknown engine(s): {', '.join(sorted(unknown))}")
    regions = selected_regions(args.regions)
    result: dict[str, Any] = {
        "schema_version": 2,
        "experiment": "region",
        "status": "running",
        "image": args.image.name,
        "image_size": [int(image.shape[1]), int(image.shape[0])],
        "repeats": 1,
        "winrt_repeats": args.winrt_repeats,
        "regions": {name: {"box": list(box), "expected": expected} for name, (box, expected) in regions.items()},
        "engines": [{"engine": {"rapidocr": "RapidOCR", "pixpin_ocr": "PixPin_OCR", "winrt": "WinRT OCR"}[name], "results": []} for name in engines],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_result(args.output, result)
    for engine in engines:
        if engine == "rapidocr":
            run_rapidocr(image, regions, result, args.output)
        elif engine == "pixpin_ocr":
            run_pixpin_ocr(args.image, regions, result, args.output, args.pixpin_ocr_pipe)
        else:
            run_winrt_engine(args.image, regions, result, args.output, args.winrt_repeats)
    result["status"] = "complete"
    save_result(args.output, result)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
