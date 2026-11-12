"""复用人工动作，独立记录多回合、只读查询及固定种子证据。"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
AUDIT = OUT.parents[1]
ROOT = AUDIT.parents[2]
sys.path.insert(0, str(ROOT))

from nrc_core.debug import configure_core_logging
from nrc_platform.platform import BattlePlatform, PlatformError

ROUNDS = [
    ("skill:slot=0", "skill:slot=0"),
    ("skill:slot=2", "switch:index=1"),
    ("skill:slot=0", "skill:slot=0"),
    ("skill:slot=0", "switch:index=4"),
    ("charge", "skill:slot=1"),
    ("skill:slot=1", "skill:slot=0"),
    ("skill:slot=1", "switch:index=3"),
    ("charge", "skill:slot=0"),
    ("skill:slot=3", "switch:index=2"),
    ("skill:slot=0", "skill:slot=0"),
    ("skill:slot=1", "skill:slot=2"),
]


def build() -> tuple[BattlePlatform, str]:
    """为每次复演建立独立内存对局。"""
    platform = BattlePlatform()
    battle_id = platform.create_battle(mode="full", seed=1007)["battle_id"]
    for side, filename in (("own", "1007A.json"), ("opponent", "1007B.json")):
        roster = json.loads((ROOT / filename).read_text(encoding="utf-8"))["roster"]
        for item in roster:
            item["skills"] = [{"name": name} for name in item["skills"]]
        platform.set_roster(battle_id, side, {"creatures": roster, "active_index": 0})
    return platform, battle_id


def replay(reverse_submission: bool) -> dict:
    """记录动作、双视角观测、显示、实际事件和输入状态。"""
    platform, battle_id = build()
    records, checks = [], []
    for turn, actions in enumerate(ROUNDS, 1):
        before = copy.deepcopy(platform.export_battle(battle_id))
        panels = {}
        for _ in range(3):
            for side in ("own", "opponent"):
                panels[side] = platform.get_display_info(battle_id, side)
                platform.get_legal_actions(battle_id, side)
                platform.get_public_observation(battle_id, side)
        unchanged = before == platform.export_battle(battle_id)
        checks.append({"name": f"round{turn}_queries_read_only", "passed": unchanged})
        result = None
        sides = ("opponent", "own") if reverse_submission else ("own", "opponent")
        for side in sides:
            selection = actions[0 if side == "own" else 1]
            request_id = f"audit-{turn}-{side}"
            result = platform.submit_selection(battle_id, side, selection, request_id=request_id)
            snapshot = copy.deepcopy(platform.export_battle(battle_id))
            repeated = platform.submit_selection(battle_id, side, selection, request_id=request_id)
            checks.append({"name": f"round{turn}_{side}_idempotent", "passed": result == repeated and snapshot == platform.export_battle(battle_id)})
        records.append({"turn": turn, "actions": actions, "before": before, "panels": panels, "result": result,
                        "views": {side: platform.get_public_observation(battle_id, side) for side in ("own", "opponent")}})
        if result["phase"] == "replacement":
            replacement_index = {8: 2, 10: 4}.get(turn)
            if replacement_index is None:
                records[-1]["blocked"] = "人工动作后出现额外补位，需独立核对"
                break
            records[-1]["replacement"] = platform.submit_selection(battle_id, "own", f"switch:index={replacement_index}", request_id=f"replace-{turn}")
    try:
        platform.submit_selection(battle_id, "own", "charge", request_id="old-decision", decision_index=0)
        stale = "accepted"
    except PlatformError as error:
        stale = error.code
    checks.append({"name": "stale_request_rejected", "actual": stale, "passed": stale == "stale_decision"})
    return {"reverse_submission": reverse_submission, "checks": checks, "records": records}


def main() -> None:
    """保存完整证据；不将人工战报中的数值直接当正确预期。"""
    configure_core_logging("")
    runs = [replay(False), replay(True)]
    first, second = runs
    events_equal = [row["result"]["result"]["events"] for row in first["records"]] == [row["result"]["result"]["events"] for row in second["records"]]
    summary = {"rounds": [len(run["records"]) for run in runs], "submission_order_same_seed_events_equal": events_equal,
               "checks_passed": sum(check["passed"] for run in runs for check in run["checks"]),
               "checks_total": sum(len(run["checks"]) for run in runs),
               "failures": [check for run in runs for check in run["checks"] if not check["passed"]],
               "limits": "此脚本验证查询、幂等和复现契约；人工伤害数值另行推导，未用实现生成预期。"}
    (OUT / "1007_replay.json").write_text(json.dumps({"summary": summary, "runs": runs}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
