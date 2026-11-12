"""只读来源创建独立双人对局，复现平台遮蔽及事务边界。"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

OUT = Path(__file__).resolve().parent
AUDIT = OUT.parents[1]
ROOT = AUDIT.parents[2]
sys.path.insert(0, str(ROOT))

from nrc_core.debug import configure_core_logging
from nrc_core.engine import EffectExecutor
from nrc_core.effect_models import Timing
from nrc_platform.platform import BattlePlatform
from nrc_platform.rooms import RoomService


def rosters():
    """复制现有人工作战配置，避免污染其文件和会话。"""
    teams = []
    for name in ("1007A.json", "1007B.json"):
        team = json.loads((ROOT / name).read_text(encoding="utf-8"))["roster"]
        for item in team:
            item["skills"] = [{"name": skill} for skill in item["skills"]]
        teams.append(team)
    return teams


def room(active=0):
    """用两个稳定身份完成准备与首发确认。"""
    service = RoomService()
    battle_id = service.create_battle("audit-a", {"seed": 1007})["battle_id"]
    service.join_battle(battle_id, "audit-b")
    a, b = rosters()
    service.set_rosters(battle_id, "audit-a", {"roster": a, "active_index": active, "confirm": True})
    service.set_rosters(battle_id, "audit-b", {"roster": b, "active_index": 0, "confirm": True})
    return service, battle_id


def main():
    """将每个反例的预期、完整实际和通过的事务对照留档。"""
    configure_core_logging("")
    results = {}
    service, battle_id = room(active=4)
    before = service.public_state(battle_id, "audit-b")
    service.select_action(battle_id, "audit-a", {"action_key": "skill:slot=0", "request_id": "cute-a"})
    second = service.select_action(battle_id, "audit-b", {"action_key": "charge", "request_id": "cute-b"})
    events = service.battle_events(battle_id, "audit-b")["events"]
    after = service.public_state(battle_id, "audit-b")
    results["unrevealed_bench_events"] = {"expected": "从未上场精灵仍完全隐藏；其名称与状态不得经战报泄露", "before": before, "after": after, "events": events, "submit_result": second}

    battle = service.platform._get_battle(battle_id).episode.battle
    battle.devotion_a = {"飞断": 2, "假寐": 1}
    battle.devotion_b = {"虫茧": 4}
    results["devotion_visibility"] = {"expected": "己方有分布与总数；对方有总数且无分布", "views": {identity: service.public_state(battle_id, identity)["data"]["shared"]["devotion"] for identity in ("audit-a", "audit-b")}}

    # 直接构建拒绝与真实平台入口必须对照；禁止把局部拒绝当成端到端拒绝。
    platform = BattlePlatform()
    catalog = platform._catalog.catalog
    empty = []
    for name, record in catalog.pokemon.items():
        ability = record.get("ability")
        if ability and not catalog.get_ability_effects(ability):
            empty.append((name, ability))
    source = {"name": empty[0][0], "skills": [{"name": "火焰箭"}] * 4}
    direct = None
    try:
        platform._builder.build({"own_team": {"creatures": [source]}, "opponent_team": {"creatures": [source]}}, 1)
        direct = "accepted"
    except Exception as error:
        direct = {"type": type(error).__name__, "message": str(error)}
    test_id = platform.create_battle(mode="full", seed=1)["battle_id"]
    platform.set_roster(test_id, "own", {"creatures": [source]})
    response = platform.set_roster(test_id, "opponent", {"creatures": [source]})
    pokemon = platform._get_battle(test_id).episode.battle.team_a[0]
    results["unsupported_ability_bypass"] = {"source": source, "catalog_ability": empty[0][1], "affected_forms": len(empty), "direct_builder": direct, "platform_response": response, "actual_ability": pokemon.ability, "actual_effects": str(pokemon.ability_effects), "expected": "未实现机制应拒绝，不得静默移除特性"}

    # 在第二个提交已经完成写入、随后房间事件过滤故意失败处验证外层回滚。
    service, battle_id = room()
    first = service.select_action(battle_id, "audit-a", {"action_key": "charge", "request_id": "tx-a"})
    before_platform = copy.deepcopy(service.platform.export_battle(battle_id))
    before_room = copy.deepcopy(service.rooms[battle_id])
    caught = "not raised"
    with patch("nrc_platform.rooms._visible_event_count", side_effect=RuntimeError("audit rollback")):
        try:
            service.select_action(battle_id, "audit-b", {"action_key": "charge", "request_id": "tx-b"})
        except RuntimeError as error:
            caught = str(error)
    results["outer_transaction_rollback"] = {"expected": "核心、暂存、历史、请求缓存与房间都恢复到第二提交前", "caught": caught,
                                               "platform_equal": before_platform == service.platform.export_battle(battle_id), "room_equal": before_room == service.rooms[battle_id], "first_submission": first}
    retry = service.select_action(battle_id, "audit-b", {"action_key": "charge", "request_id": "tx-b"})
    snapshot = copy.deepcopy(service.platform.export_battle(battle_id))
    repeated = service.select_action(battle_id, "audit-b", {"action_key": "charge", "request_id": "tx-b"})
    results["room_idempotence"] = {"response_equal": retry == repeated, "state_equal": snapshot == service.platform.export_battle(battle_id)}
    for identity in ("audit-a", "audit-b"):
        full = service.battle_events(battle_id, identity)
        empty_result = service.battle_events(battle_id, identity, since=full["cursor"])
        results[f"cursor_{identity}"] = {"full_count": len(full["events"]), "cursor": full["cursor"], "empty_tail": empty_result["events"] == []}

    # 强制制造当前特性状态后比对三个公开预览入口，独立预期用固定威力+20。
    battle = service.platform._get_battle(battle_id).episode.battle
    battle.current_a = 4
    battle.skill_use_counts_a["状态"] = 2
    user, target = battle.team_a[4], battle.team_b[0]
    EffectExecutor.execute_ability(battle, user, target, Timing.ON_ENTER, user.ability_effects, "a")
    results["prediction_contract"] = {"expected": "同一状态和技能的显示与预测均包含拨浪鼓2层固定+20", "display": service.platform.get_display_info(battle_id, "own"), "query": service.platform.query_display_power(battle_id, "own", 1), "predict": service.platform.predict_damage(battle_id, "own", 1, 0)}

    service, battle_id = room()
    platform = service.platform
    platform.submit_selection(battle_id, "own", "charge", request_id="snapshot-pending")
    snapshot = platform.export_battle(battle_id)
    restored = BattlePlatform()
    restored.import_battle(copy.deepcopy(snapshot))
    restore_snapshot = restored.export_battle(battle_id)
    original_result = platform.submit_selection(battle_id, "opponent", "charge", request_id="snapshot-complete")
    restored_result = restored.submit_selection(battle_id, "opponent", "charge", request_id="snapshot-complete")
    results["snapshot_pending_roundtrip"] = {"snapshot_equal": snapshot == restore_snapshot, "result_equal": original_result == restored_result, "final_views_equal": all(platform.get_public_observation(battle_id, side) == restored.get_public_observation(battle_id, side) for side in ("own", "opponent"))}

    service, battle_id = room()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(service.select_action, battle_id, identity, {"action_key": "charge", "request_id": "concurrent-" + identity, "decision_index": 0}) for identity in ("audit-a", "audit-b")]
        responses = [future.result() for future in futures]
    results["simultaneous_submissions"] = {"resolved_count": sum(response["resolved"] for response in responses), "decision_index": service.platform.get_battle_status(battle_id)["decision_index"], "core_history_count": sum(row.get("source") == "core" for row in service.platform._get_battle(battle_id).history)}

    battle = service.platform._get_battle(battle_id)
    battle.episode.terminated = True
    battle.episode.phase = "terminal"
    battle.episode.players = ()
    for query in (service.actions, service.display, service.public_state):
        query(battle_id, "audit-a")
    try:
        service.select_action(battle_id, "audit-a", {"action_key": "charge", "request_id": "after-terminal"})
        result = "accepted"
    except Exception as error:
        result = {"type": type(error).__name__, "code": getattr(error, "code", ""), "message": str(error)}
    results["terminal_lock"] = {"actions": service.actions(battle_id, "audit-a")["actions"], "submit": result}

    (OUT / "probe_output.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    summary = {"unrevealed_events": [event for event in results["unrevealed_bench_events"]["events"] if event.get("type") == "state_change" and event.get("team") == "b"], "devotion": results["devotion_visibility"], "bypass": {key: results["unsupported_ability_bypass"][key] for key in ("catalog_ability", "actual_ability", "affected_forms", "direct_builder")}, "rollback": results["outer_transaction_rollback"], "idempotence": results["room_idempotence"], "prediction": results["prediction_contract"]}
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
