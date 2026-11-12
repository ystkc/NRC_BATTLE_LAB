"""验证十一回合修复中易回归的迸发、应对和萌化边界。"""

import copy
import json
from pathlib import Path

import pytest

from nrc_core.core import simulate_turn, _turn_start_skill_display
from nrc_core.debug import configure_core_logging
from nrc_core.engine import EffectExecutor
from nrc_core.engine.handlers_field import _cute_add
from nrc_core.effect_models import Timing
from nrc_platform.platform import BattlePlatform
from nrc_platform.state import normalize_observation


@pytest.fixture(scope="module")
def initial_battle():
    """使用真实阵容和平台注入的数据，避免伪造进化数值。"""
    configure_core_logging("")
    platform = BattlePlatform()
    battle_id = platform.create_battle(mode="full", seed=1007)["battle_id"]
    root = Path(__file__).resolve().parents[1]
    for side, filename in (("own", "1007A.json"), ("opponent", "1007B.json")):
        roster = json.loads((root / filename).read_text(encoding="utf-8"))["roster"]
        for member in roster:
            member["skills"] = [{"name": name} for name in member["skills"]]
        platform.set_roster(battle_id, side, {"creatures": roster, "active_index": 0})
    return platform, platform._get_battle(battle_id).episode.battle


def test_burst_cost_matches_preview_legal_actions_and_payment(initial_battle):
    """首次行动只需一能量；面板、合法动作和结算一致，后续不重复减耗。"""
    platform, original = initial_battle
    battle = copy.deepcopy(original)
    battle.current_b = 3
    battle.team_b[3].energy = 1
    runtime = platform._backend
    session = runtime.new_game(battle, seed=1007)
    assert "skill:slot=0" in {action.key for action in runtime.legal_actions(session, 1)}
    panel = _turn_start_skill_display(session.battle, "b")
    assert panel["skills"][0]["display_energy_cost"] == 1
    result = simulate_turn(session.battle, (-1,), (0,), seed=1007)
    user = result.state.team_b[3]
    event = next(event for event in result.report if event.get("skill") == "超导")
    assert event["energy_cost"] == 1
    assert user.energy == 0
    assert user.skills[0].energy_cost == 3
    assert _turn_start_skill_display(result.state, "b")["skills"][0]["display_energy_cost"] == 3


@pytest.mark.parametrize("survives", [False, True])
def test_attack_counter_settles_before_status_skill(initial_battle, survives):
    """应对先结算；存活才能执行状态技能，应对也只能计数一次。"""
    _, original = initial_battle
    battle = copy.deepcopy(original)
    battle.current_a, battle.current_b = 2, 2
    if survives:
        battle.team_a[2].hp = battle.team_a[2].current_hp = 1000
    result = simulate_turn(battle, (0,), (0,), seed=1007)
    skills = [event["skill"] for event in result.report if event["type"] == "skill"]
    assert skills == (["暗突袭", "剧毒"] if survives else ["暗突袭"])
    assert result.state.counter_count_b == 1
    assert result.state.skill_use_counts_a.get("状态", 0) == int(survives)
    assert result.state.team_a[2].energy == (8 if survives else 10)


@pytest.mark.parametrize("current_hp", [200, 325])
def test_cute_keeps_hp_and_only_increases_powered_skills(initial_battle, current_hp):
    """退化保留当前生命并截断上限，永久威力加成跳过 -1 技能。"""
    _, original = initial_battle
    battle = copy.deepcopy(original)
    user, target = battle.team_a[4], battle.team_b[2]
    user.current_hp = current_hp
    assert user.devolution_forms[0]["name"] == "古钟蛇"
    clone = user.copy_state()
    clone.devolution_forms[0]["stats"]["hp"] = 1
    assert user.devolution_forms[0]["stats"]["hp"] == 294
    EffectExecutor.execute_skill(battle, user, target, user.skills[1], user.skills[1].effects, team="a")
    assert user.name == "古钟蛇"
    assert user.hp == 294
    assert user.current_hp == min(current_hp, 294)
    assert user.cute_stacks == 1
    assert [skill.power for skill in user.skills] == [-1, 40, -1, 25]
    assert user.ability_state["public_skill_modifiers"]["power"] == 10
    assert user.copy_state().cute_stacks == 1
    assert _cute_add(user, 1) == 0


def test_devils_feast_keeps_whole_status_and_ability_description(initial_battle):
    """连续击败只累计晚宴层数，双方可见同一特性原文，普通中毒没有说明。"""
    platform, original = initial_battle
    runtime = platform._backend
    session = runtime.new_game(copy.deepcopy(original), seed=1007)
    battle = session.battle
    battle.current_b = 2
    user, target = battle.team_b[2], battle.team_a[0]
    for _ in range(2):
        EffectExecutor.execute_ability(battle, user, target, Timing.ON_KILL, user.ability_effects, "b")
    status = user.compound_statuses["恶魔的晚宴"]
    assert status.stacks == 10
    assert user.atk_up == user.spatk_up == 0
    assert user.calculation_modifier("atk_up") == pytest.approx(1)
    assert user.calculation_modifier("spatk_up") == pytest.approx(1)
    user.poison_stacks = 2
    catalog = platform._catalog.catalog
    for player, side in ((0, "opponent"), (1, "own")):
        observation = normalize_observation(runtime.observe(session, player), battle, catalog,
                                            revealed={0: set(range(5)), 1: set(range(6))})
        visible = observation.data[f"{side}_team"][2]
        feast = next(s for s in visible["statuses"] if s["name"] == "恶魔的晚宴")
        assert feast["description"] == catalog.ability_descriptions["恶魔的晚宴"]
        assert feast["description"] != feast["name"]
        assert not any(m["name"] in {"atk", "spatk"} for m in visible["modifiers"])
        assert "description" not in next(s for s in visible["statuses"] if s["name"] == "poison")
    clone = user.copy_state()
    clone.on_switch_out()
    assert not clone.compound_statuses
    assert user.compound_statuses["恶魔的晚宴"].stacks == 10


@pytest.mark.parametrize("side,index,slot,key", [("b", 4, 2, "冻土"), ("a", 4, 3, "拨浪鼓")])
def test_skill_ability_status_keeps_raw_power_and_preview_damage(initial_battle, side, index, slot, key):
    """技能加成保留完整来源；重复预览不污染技能，实际伤害仍与展开后的数值一致。"""
    from nrc_core.core import _display_power
    from nrc_core.battle import DamageCalculator

    platform, original = initial_battle
    session = platform._backend.new_game(copy.deepcopy(original), seed=1007)
    battle = session.battle
    if side == "a":
        battle.current_a = index
        battle.skill_use_counts_a["状态"] = 2
        user, target = battle.team_a[index], battle.team_b[0]
    else:
        battle.current_b = index
        user, target = battle.team_b[index], battle.team_a[0]
    raw_powers = [skill.power for skill in user.skills]
    EffectExecutor.execute_ability(battle, user, target, Timing.ON_ENTER, user.ability_effects, side)
    assert user.compound_statuses[key].stacks == 2
    assert [skill.power for skill in user.skills] == raw_powers
    skill = user.skills[slot]
    assert user.skill_modifier(skill, "power") or user.skill_modifier(skill, "power_pct")
    expanded = copy.deepcopy(user)
    expanded.skills[slot].power = int((skill.power + user.skill_modifier(skill, "power"))
                                     * (1 + user.skill_modifier(skill, "power_pct")))
    expanded.compound_statuses.clear()
    expected = DamageCalculator.calculate(expanded, target, expanded.skills[slot], weather=battle.weather)
    before = copy.deepcopy(user.compound_statuses)
    for _ in range(3):
        assert _display_power(battle, side, (slot,))["value"] == expected
        _turn_start_skill_display(battle, side)
    result = EffectExecutor.execute_skill(battle, user, target, skill, skill.effects, team=side)
    assert result["damage"] == expected
    assert user.compound_statuses == before
    assert [skill.power for skill in user.skills] == raw_powers

