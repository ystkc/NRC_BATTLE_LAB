from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.audit.records import AuditTable


def main() -> None:
    parser = argparse.ArgumentParser(description="回填技能审计分支记录")
    parser.add_argument("--table", default="data/audit/skills_audit.json")
    parser.add_argument("--name", required=True)
    parser.add_argument("--branch", required=True, help="例如 probability:triggered 或 counter:success")
    parser.add_argument("--battle-id", default="")
    parser.add_argument("--status", default="recorded", choices=["recorded", "failed", "pending"])
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    table = AuditTable(args.table)
    if not table.mark_branch(args.name, args.branch, status=args.status, battle_id=args.battle_id, note=args.note):
        raise SystemExit(f"未找到技能或分支: {args.name} / {args.branch}")
    table.save()
    print(f"marked {args.name} {args.branch} -> {args.status}")


if __name__ == "__main__":
    main()
