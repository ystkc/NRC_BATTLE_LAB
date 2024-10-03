"""Evaluate the pixel-based entrance detector against separate annotations."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np


from .entrance_detector import EntranceRegionDetector
from .region_geometry import Region


INITIAL_SCORE = 100_000.0
REFERENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "screen" / "entrance_references.json"


def load_references(path: str | Path = REFERENCE_PATH) -> tuple[Region, ...]:
    return tuple(Region(**item) for item in json.loads(Path(path).read_text(encoding="utf-8")))


REFERENCES = load_references()


def _union_area(regions: Iterable[Region]) -> int:
    """Compute rectangle-union area with coordinate compression."""
    items = list(regions)
    if not items:
        return 0
    x_values = sorted({value for region in items for value in (region.x, region.right)})
    area = 0
    for x1, x2 in zip(x_values, x_values[1:]):
        if x2 <= x1:
            continue
        intervals = sorted(
            (region.y, region.bottom)
            for region in items
            if region.x < x2 and region.right > x1
        )
        covered_y = 0
        current_start = current_end = None
        for y1, y2 in intervals:
            if current_start is None:
                current_start, current_end = y1, y2
            elif y1 > current_end:
                covered_y += current_end - current_start
                current_start, current_end = y1, y2
            else:
                current_end = max(current_end, y2)
        if current_start is not None:
            covered_y += current_end - current_start
        area += (x2 - x1) * covered_y
    return area


def _overlap_with_union(region: Region, references: Sequence[Region]) -> int:
    clipped = []
    for reference in references:
        left = max(region.x, reference.x)
        top = max(region.y, reference.y)
        right = min(region.right, reference.right)
        bottom = min(region.bottom, reference.bottom)
        if right > left and bottom > top:
            clipped.append(Region("intersection", left, top, right - left, bottom - top, 0))
    return _union_area(clipped)


def score_regions(
    predictions: Sequence[Region],
    references: Sequence[Region] = REFERENCES,
    average_ms: float = 0.0,
) -> dict[str, object]:
    """Apply the supplied rule and additionally report uncovered-pixel penalties.

    The original score treats a disjoint reference as completely missed. The
    conservative coverage score also penalizes partially uncovered references.
    Predictions overlapping multiple annotations pay excess only outside their
    union, so overlapping target rectangles cannot manufacture covered area.
    """
    missed = []
    missed_penalty = 0.0
    coverage = []
    coverage_missing_penalty = 0.0
    for reference in references:
        covered_area = _overlap_with_union(reference, predictions)
        uncovered_area = reference.area - covered_area
        coverage_missing_penalty += uncovered_area * reference.weight
        coverage.append({
            "name": reference.name, "covered_area": covered_area, "uncovered_area": uncovered_area,
            "coverage_ratio": covered_area / reference.area, "uncovered_penalty": uncovered_area * reference.weight,
        })
        if covered_area == 0:
            penalty = reference.area * reference.weight
            missed.append({"name": reference.name, "area": reference.area, "weight": reference.weight, "penalty": penalty})
            missed_penalty += penalty

    extra_penalty = 0.0
    extra = []
    for prediction in predictions:
        overlap = _overlap_with_union(prediction, references)
        excess = prediction.area - overlap
        if overlap == 0:
            penalty = prediction.area * 15.0
            mode = "disjoint"
        else:
            penalty = excess * 10.0
            mode = "excess"
        if penalty:
            extra.append({"name": prediction.name, "area": prediction.area, "overlap": overlap, "excess": excess, "mode": mode, "penalty": penalty})
        extra_penalty += penalty

    time_penalty = average_ms * 10.0
    final_score = INITIAL_SCORE - missed_penalty - extra_penalty - time_penalty
    return {
        "initial_score": INITIAL_SCORE,
        "missed_penalty": missed_penalty,
        "extra_penalty": extra_penalty,
        "time_penalty": time_penalty,
        "average_ms": average_ms,
        "score": final_score,
        "coverage_score": INITIAL_SCORE - coverage_missing_penalty - extra_penalty - time_penalty,
        "coverage_missing_penalty": coverage_missing_penalty,
        "coverage": coverage,
        "missed": missed,
        "extra": extra,
    }


def benchmark(detector: EntranceRegionDetector, image: np.ndarray, repeats: int = 5) -> tuple[list[Region], list[float]]:
    if repeats <= 0:
        raise ValueError("repeats 必须大于 0")
    predictions = []
    elapsed = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        predictions = detector.detect(image)
        elapsed.append((time.perf_counter_ns() - start) / 1_000_000.0)
    return predictions, elapsed


def annotate(image: np.ndarray, predictions: Sequence[Region]) -> np.ndarray:
    output = image.copy()
    for region in predictions:
        color = (40, 220, 40)
        cv2.rectangle(output, (region.x, region.y), (region.right - 1, region.bottom - 1), color, 2)
        label = region.name
        cv2.putText(output, label, (region.x, max(14, region.y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检测 entrance.jpg 区域并按题目规则评分")
    parser.add_argument("--image", default=str(REFERENCE_PATH.parents[3] / "entrance.jpg"), help="入口截图路径")
    parser.add_argument("--output", default="data/screen/inspection/entrance_regions.jpg", help="标注图路径")
    parser.add_argument("--json", dest="json_path", default="data/screen/inspection/entrance_regions.json", help="评分 JSON 路径")
    parser.add_argument("--repeats", type=int, default=5, help="耗时平均次数")
    parser.add_argument("--references", default=str(REFERENCE_PATH), help="仅供评分使用的参考区域 JSON")
    parser.add_argument("--compare-raw", action="store_true", help="同时评测未补边/未统一宽度的原始轮廓版本")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"无法读取图片: {args.image}")
    references = load_references(args.references)
    cv2.setNumThreads(1)
    experiments = []
    if args.compare_raw:
        raw, raw_elapsed = benchmark(EntranceRegionDetector(align_card_width=False, border_padding=False), image, args.repeats)
        raw_result = score_regions(raw, references, sum(raw_elapsed) / len(raw_elapsed))
        raw_result["variant"] = "raw_contours"
        raw_result["elapsed_ms"] = raw_elapsed
        experiments.append(raw_result)
    predictions, elapsed = benchmark(EntranceRegionDetector(), image, args.repeats)
    average_ms = sum(elapsed) / len(elapsed)
    result = score_regions(predictions, references, average_ms)
    result["image"] = {"width": int(image.shape[1]), "height": int(image.shape[0])}
    result["predictions"] = [asdict(region) for region in predictions]
    result["elapsed_ms"] = elapsed
    result["repeats"] = args.repeats
    result["timing_scope"] = "detect(image) only; excludes image I/O, imports, drawing, and scoring"
    result["experiments"] = experiments

    output_path = Path(args.output)
    json_path = Path(args.json_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), annotate(image, predictions)):
        raise SystemExit(f"无法写入图片: {output_path}")
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output_path.resolve()), "json": str(json_path.resolve()),
        "score": result["score"], "coverage_score": result["coverage_score"],
        "average_ms": average_ms, "elapsed_ms": elapsed, "predictions": len(predictions),
        "experiments": [{"variant": item["variant"], "score": item["score"], "coverage_score": item["coverage_score"], "average_ms": item["average_ms"]} for item in experiments],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
