"""Run the screen-stream collector and optional simulator comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.screen import ScreenCollectionPipeline, load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="从录屏采集对战事件并逐回合调用模拟器")
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", default="data/screen/battle_record.json")
    parser.add_argument("--references", default="..")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--manifest")
    parser.add_argument("--sample-fps", type=float, default=10.0)
    parser.add_argument("--no-simulate", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pipeline = ScreenCollectionPipeline(
        video_path=Path(args.video), output_path=root / args.output,
        reference_dir=Path(args.references), data_dir=root / args.data_dir,
        sample_fps=args.sample_fps, manifest=load_manifest(args.manifest),
    )
    payload = pipeline.run(simulate=not args.no_simulate)
    summary = {
        "output": str((root / args.output).resolve()),
        "observations": len(payload["observations"]), "turns": payload["turn_count"],
        "ocr_available": payload["ocr_available"],
        "statuses": [record["comparison"]["status"] for record in payload["records"]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
