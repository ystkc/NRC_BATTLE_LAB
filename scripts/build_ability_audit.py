from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.audit.ability_builder import build_ability_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="生成特性人工审计表")
    parser.add_argument("--db", default="data/nrc.db")
    parser.add_argument("--output-dir", default="data/audit")
    args = parser.parse_args()
    payload = build_ability_audit(args.db, args.output_dir)
    print(f"records={payload['record_count']} status=manual_required")


if __name__ == "__main__":
    main()

