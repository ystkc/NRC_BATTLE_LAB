"""Run a semantic-segmentation baseline on game screenshots.

The first backend uses torchvision's COCO-pretrained DeepLabV3 model. Its
label vocabulary is generic (person, chair, floor, ...), so this command is
intended as a reproducible baseline and visualization tool, not as a trained
game-UI detector. The output format is deliberately model-agnostic so a
future UI-specific checkpoint can replace the backend without changing the
inspection workflow.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision.models.segmentation import (
    DeepLabV3_ResNet50_Weights,
    deeplabv3_resnet50,
)
from torchvision.transforms import Compose, Normalize, Resize, ToTensor


class DeepLabSegmenter:
    """COCO-pretrained semantic segmenter with an original-size output mask."""

    def __init__(self, device: str = "auto", inference_size: int = 520) -> None:
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.inference_size = inference_size
        self.weights = DeepLabV3_ResNet50_Weights.DEFAULT
        self.labels = list(self.weights.meta["categories"])
        self.model = deeplabv3_resnet50(weights=self.weights).to(self.device).eval()
        self.preprocess = Compose(
            [
                Resize(inference_size),
                ToTensor(),
                Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                ),
            ]
        )

    def predict(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        height, width = image.shape[:2]
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        tensor = self.preprocess(Image.fromarray(rgb)).unsqueeze(0).to(self.device)
        start = time.perf_counter()
        with torch.inference_mode():
            logits = self.model(tensor)["out"]
            logits = torch.nn.functional.interpolate(
                logits,
                size=(height, width),
                mode="bilinear",
                align_corners=False,
            )
            labels = logits.argmax(dim=1)[0].to("cpu").numpy().astype(np.uint8)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return labels, elapsed_ms


def _palette(size: int) -> np.ndarray:
    palette = np.zeros((size, 3), dtype=np.uint8)
    for index in range(1, size):
        value = index * 0x45D9F3
        palette[index] = (
            (value >> 0) & 0xFF,
            (value >> 8) & 0xFF,
            (value >> 16) & 0xFF,
        )
    return palette


def _write_result(
    image_path: Path,
    output_dir: Path,
    segmenter: DeepLabSegmenter,
) -> dict[str, Any]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    mask, elapsed_ms = segmenter.predict(image)
    palette = _palette(len(segmenter.labels))
    color_mask = palette[mask]
    overlay = cv2.addWeighted(image, 0.55, color_mask, 0.45, 0.0)
    boundaries = cv2.Canny(mask, 0, 1)
    overlay[boundaries > 0] = (255, 255, 255)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = image_path.stem
    mask_path = output_dir / f"{stem}_deeplab_labels.png"
    overlay_path = output_dir / f"{stem}_deeplab_overlay.jpg"
    cv2.imwrite(str(mask_path), mask)
    cv2.imwrite(str(overlay_path), overlay)

    total = int(mask.size)
    counts = np.bincount(mask.reshape(-1), minlength=len(segmenter.labels))
    classes = []
    for class_id, count in enumerate(counts):
        if count == 0:
            continue
        classes.append(
            {
                "id": class_id,
                "label": segmenter.labels[class_id],
                "pixels": int(count),
                "ratio": round(float(count) / total, 6),
            }
        )
    classes.sort(key=lambda item: item["pixels"], reverse=True)

    return {
        "source": str(image_path),
        "model": "torchvision/deeplabv3_resnet50",
        "weights": "COCO_WITH_VOC_LABELS_V1",
        "device": str(segmenter.device),
        "image": {"width": int(image.shape[1]), "height": int(image.shape[0])},
        "inference_ms": round(elapsed_ms, 3),
        "outputs": {"labels": str(mask_path), "overlay": str(overlay_path)},
        "classes": classes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a replaceable semantic-segmentation baseline on screenshots"
    )
    parser.add_argument(
        "images",
        nargs="*",
        type=Path,
        help="Input screenshots; defaults to ../entrance.jpg and ../normal.jpg",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/screen/inspection/segmentation"),
        help="Directory for masks, overlays, and JSON",
    )
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--inference-size", type=int, default=520)
    args = parser.parse_args()

    images = args.images or [Path("../entrance.jpg"), Path("../normal.jpg")]
    images = [path for path in images if path.exists()]
    if not images:
        raise SystemExit("No input images found; pass image paths explicitly.")

    segmenter = DeepLabSegmenter(device=args.device, inference_size=args.inference_size)
    results = [_write_result(path, args.output_dir, segmenter) for path in images]
    report_path = args.output_dir / "deeplab_report.json"
    report_path.write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"report": str(report_path), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
