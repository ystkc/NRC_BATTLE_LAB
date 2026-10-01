from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.audit.builder import build_skill_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="从 skills_all.csv 构建技能分支审计表")
    parser.add_argument("--input", default="data/skills_all.csv")
    parser.add_argument("--output-dir", default="data/audit")
    parser.add_argument("--strict", action="store_true", help="存在解析失败时返回非零")
    args = parser.parse_args()
    payload = build_skill_audit(args.input, args.output_dir, strict=args.strict)
    print(f"records={payload['record_count']} unresolved={payload['unresolved_count']}")


if __name__ == "__main__":
    main()
