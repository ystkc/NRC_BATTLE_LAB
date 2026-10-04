from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector.planner import CollectionSession
from nrc_core.codec import battle_request_from_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="根据技能审计表推荐下一步人工操作")
    parser.add_argument("--request", required=False, help="BattleRequest JSON 文件")
    parser.add_argument("--table", default="data/audit/skills_audit.json")
    parser.add_argument("--side", choices=["own", "opponent"], default="own")
    args = parser.parse_args()
    request = battle_request_from_dict(json.loads(Path(args.request).read_text(encoding="utf-8")))
    plan = CollectionSession(args.table).plan_next_action(request, args.side)
    print(json.dumps(plan.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

