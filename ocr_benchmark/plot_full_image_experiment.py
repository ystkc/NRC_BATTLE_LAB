"""Render full-image OCR detections from the consolidated JSON result."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ocr_benchmark_common import DEFAULT_FULL_RESULTS, DEFAULT_IMAGE


def safe_name(value: str) -> str:
    if value == "PixPin_OCR":
        value = "OCR Service"
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_").lower() or "ocr"


def font_path() -> Path:
    for candidate in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No Chinese-capable Windows font was found")


def render(image_path: Path, output_path: Path, engine: str, detections: list[dict[str, Any]], note: str | None) -> None:
    source = Image.open(image_path).convert("RGB")
    scale = 2
    image = source.resize((source.width * scale, source.height * scale))
    draw = ImageDraw.Draw(image, "RGBA")
    regular = ImageFont.truetype(str(font_path()), 14 * scale)
    title = ImageFont.truetype(str(font_path()), 20 * scale)
    draw.rectangle((0, 0, image.width, 38 * scale), fill=(0, 0, 0, 190))
    draw.text((10 * scale, 6 * scale), engine, font=title, fill="white")
    if note:
        draw.text((10 * scale, 44 * scale), note, font=regular, fill=(255, 220, 100, 255))
    for item in detections:
        box = item.get("box") or []
        if len(box) < 2:
            continue
        points = [(float(point[0]) * scale, float(point[1]) * scale) for point in box]
        score = item.get("score")
        score_text = "N/A" if score is None else f"{float(score):.2f}"
        label = f"{item.get('text', '') or '<empty>'} · {score_text}"
        color = (35, 185, 75) if score is None or float(score) >= 0.8 else (245, 150, 30) if float(score) >= 0.5 else (235, 45, 45)
        draw.line(points + [points[0]], fill=color + (255,), width=scale, joint="curve")
        bounds = draw.textbbox((0, 0), label, font=regular)
        width = bounds[2] - bounds[0] + 8 * scale
        height = bounds[3] - bounds[1] + 5 * scale
        x = max(0, min(int(min(point[0] for point in points)), image.width - width))
        y = max(38 * scale, int(min(point[1] for point in points) - height))
        draw.rounded_rectangle((x, y, x + width, y + height), radius=3 * scale, fill=color + (220,))
        draw.text((x + 4 * scale, y + scale), label, font=regular, fill="white")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=95)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render full-image OCR result boxes.")
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--results", type=Path, default=DEFAULT_FULL_RESULTS)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).with_name("visualizations"))
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    manifest: list[dict[str, Any]] = []
    for result in data.get("engines", []):
        engine = str(result.get("engine", "OCR"))
        display_engine = "OCR Service" if engine == "PixPin_OCR" else engine
        detections = result.get("detections", [])
        note = f"ERROR: {result['error']}" if result.get("error") else None
        if not result.get("raw_detections_available", True) and not note:
            note = "Raw detection boxes are not included in this migrated summary."
        output = args.output_dir / f"{safe_name(engine)}.jpg"
        if not detections and output.exists() and result.get("raw_detections_available", True) and not result.get("error"):
            print(f"{display_engine}: kept existing visualization ({output})")
        else:
            render(args.image, output, display_engine, detections, note)
        detection_count = int(result.get("detection_count", len(detections)))
        manifest.append({"engine": display_engine, "output": str(output), "detection_count": detection_count})
        print(f"{display_engine}: {output} ({detection_count} boxes)")
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
