"""Render only the fixed OCR-region preview; no recognition is performed."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from ocr_benchmark_common import DEFAULT_IMAGE, DEFAULT_PREVIEW_DIR, REGIONS, region_bounds


def main() -> None:
    parser = argparse.ArgumentParser(description="Render OCR region crops and a contact sheet.")
    parser.add_argument("image", nargs="?", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_PREVIEW_DIR)
    args = parser.parse_args()
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"Cannot read image: {args.image}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    annotated = image.copy()
    for name, (box, _) in REGIONS.items():
        x1, y1, x2, y2 = region_bounds(box)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(annotated, name, (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
        crop = image[y1:y2, x1:x2]
        cv2.imwrite(str(args.output_dir / f"{name}.png"), cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC))
    cv2.imwrite(str(args.output_dir / "all_regions_on_original.jpg"), annotated)

    contact_regions = {name: box for name, (box, _) in REGIONS.items()}
    cell_width, cell_height, columns = 620, 300, 2
    rows = (len(contact_regions) + columns - 1) // columns
    sheet = np.full((rows * cell_height, columns * cell_width, 3), 245, dtype=np.uint8)
    for index, (name, box) in enumerate(contact_regions.items()):
        x1, y1, x2, y2 = region_bounds(box)
        crop = cv2.resize(image[y1:y2, x1:x2], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        scale = min((cell_width - 20) / crop.shape[1], (cell_height - 45) / crop.shape[0], 1.0)
        if scale < 1.0:
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        row, column = divmod(index, columns)
        x = column * cell_width + (cell_width - crop.shape[1]) // 2
        y = row * cell_height + 35 + (cell_height - 35 - crop.shape[0]) // 2
        sheet[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
        cv2.putText(sheet, name, (column * cell_width + 10, row * cell_height + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.imwrite(str(args.output_dir / "contact_sheet.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"Saved preview to {args.output_dir}")


if __name__ == "__main__":
    main()
