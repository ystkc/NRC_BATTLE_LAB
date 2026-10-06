from __future__ import annotations

from nrc_platform import create_platform


def _creature(name: str, skills: list[str], hp: int, *, bloodline: str | None = None, boss_form: str | None = None) -> dict:
    creature = {
        "name": name,
        "skills": [{"name": skill} for skill in skills],
        "state": {"hp": hp, "max_hp": hp, "energy": 10},
    }
    if bloodline:
        creature["base"] = {"bloodline_attributes": [bloodline]}
    if boss_form:
        creature["metadata"] = {"boss_form": boss_form}
    return creature


def _submit(platform, battle_id: str, side: str, selection: dict, request: str):
    return platform.submit_selection(battle_id, side, selection, request_id=request)


def test_manual_1002_platform_flow_reaches_replacement_and_resonance():
    platform = create_platform()
    battle = platform.create_battle(mode="full", seed=1002)
    battle_id = battle.battle_id

    own = {
        "active_index": 0,
        "creatures": [
            _creature("画间沉铁兽", ["连续爪击", "反击拳", "幻象", "鼓劲"], 490),
            _creature("蹦蹦花（短毛球形态）", ["毒誓", "见招拆招", "反击拳", "蜡质膜"], 426),
            _creature("尖嘴狐仙", ["火焰箭", "暴风雪", "晒太阳", "防御"], 406),
            _creature("深渊蛙", ["沉溺", "叠浪", "网缚", "三连破"], 403),
            _creature("晶石蜗（火山琉璃的样子）", ["连续爪击", "反击拳", "幻象", "防御"], 376),
            _creature("巨灵石", ["跺地", "穿膛", "晒太阳", "吓退"], 426),
        ],
    }
    opponent = {
        "active_index": 0,
        "resonance_magic": "boss",
        "creatures": [
            _creature("恶魔狼", ["力量增效", "贪婪", "一拳", "斩断"], 100, bloodline="boss"),
            _creature("海豹船长", ["一拳", "斩断", "水幕冲击", "月蚀"], 100),
            _creature("银月狼王", ["月蚀", "贪婪", "斩断", "一拳"], 100),
        ],
    }
    assert platform.set_roster(battle_id, "own", own).initialized is False
    assert platform.set_roster(battle_id, "opponent", opponent).phase == "turn_choice"
    display = platform.get_display_info(battle_id, "own")
    assert len(display.skills) == 4
    assert all("display_power" in skill and "display_energy_cost" in skill for skill in display.skills)
    prediction = platform.predict_damage(platform._battles[battle_id].episode, "own", 1, 0.25)
    assert prediction.damage_after_reduction >= 0
    assert prediction.hits >= 1

    first = _submit(platform, battle_id, "own", {"skill_slot": 3}, "r1-own")
    assert first.resolved is False
    second = _submit(
        platform,
        battle_id,
        "opponent",
        {"skill_slot": 0, "resonance_magic": "boss"},
        "r1-opponent",
    )
    assert second.resolved is True
    observation = platform.get_public_observation(battle_id, "own")
    assert observation.data["opponent_team"][0]["name"] == "恶魔狼王"

    # The next turn keeps the recorded action shape and demonstrates a manual switch.
    _submit(platform, battle_id, "own", {"skill_slot": 1}, "r2-own")
    r2 = _submit(platform, battle_id, "opponent", {"skill_slot": 1}, "r2-opponent")
    assert r2.resolved is True

    switch = _submit(platform, battle_id, "opponent", {"switch_index": 1, "kind": "switch"}, "r3-opponent")
    assert switch.resolved is False
    platform._battles[battle_id].episode.battle.team_b[1].current_hp = 1
    r3 = _submit(platform, battle_id, "own", {"skill_slot": 1}, "r3-own")
    assert r3.resolved is True
    assert r3.phase == "replacement"
    replacement = _submit(platform, battle_id, "opponent", {"switch_index": 2, "kind": "switch"}, "r4-opponent")
    assert replacement.resolved is True
    assert replacement.phase == "turn_choice"


def test_partial_selection_survives_opponent_roster_completion():
    platform = create_platform()
    battle_id = platform.create_battle(mode="partial", seed=1002).battle_id
    own = {"creatures": [_creature("画间沉铁兽", ["连续爪击", "反击拳", "幻象", "鼓劲"], 490)]}
    assert platform.set_roster(battle_id, "own", own).initialized is False
    platform.set_roster(battle_id, "opponent", {"creatures": [{"name": {"known": False}}]})

    waiting = _submit(platform, battle_id, "own", {"skill_slot": 3}, "partial-own")
    assert waiting.resolved is False
    assert waiting.next_required == ["opponent"]

    opponent = {"creatures": [{"name": "恶魔狼"}]}
    completed = platform.set_roster(battle_id, "opponent", opponent)
    assert completed.initialized is True
    resolved = _submit(platform, battle_id, "opponent", {"skill_slot": 0}, "partial-opponent")
    assert resolved.resolved is True
