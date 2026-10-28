"""Single-turn NRC simulation core."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from nrc_core.battle import (
    DamageCalculator,
    _apply_moisture_mark,
    _apply_turn_start_ability_logic,
    _trigger_battle_start_effects,
    check_winner,
    execute_full_turn,
)
from nrc_core.models import BattleState, Pokemon, Skill, SkillCategory
from nrc_core.rng import rng_scope
from nrc_core.debug import core_log


@dataclass(frozen=True)
class TurnResult:
    state: BattleState
    winner: str | None
    report: tuple[dict[str, Any], ...]
    display_power: dict[str, Any]
    turn_start_skill_display: dict[str, Any]


def _action_view(state: BattleState, team: str, action: tuple[int, ...]) -> dict[str, Any]:
    team_list = state.team_a if team == "a" else state.team_b
    current_index = state.current_a if team == "a" else state.current_b
    current = team_list[current_index]
    if not action or action[0] < 0 or action[0] >= len(current.skills):
        return {"kind": "charge" if action and action[0] == -1 else "switch"}
    skill = current.skills[action[0]]
    return {"kind": "skill", "slot": action[0], "name": skill.name, "power": skill.power}


def _display_power(state: BattleState, team: str, action: tuple[int, ...]) -> dict[str, Any]:
    team_list = state.team_a if team == "a" else state.team_b
    enemy_list = state.team_b if team == "a" else state.team_a
    current_index = state.current_a if team == "a" else state.current_b
    enemy_index = state.current_b if team == "a" else state.current_a
    current = team_list[current_index]
    enemy = enemy_list[enemy_index]
    if not action or action[0] < 0 or action[0] >= len(current.skills):
        result = {"kind": "non_skill", "value": 0}
        core_log("display", "action", team=team, skill=None, result=result)
        return result
    skill = current.skills[action[0]]
    if skill.power <= 0:
        result = {"kind": "skill", "skill": skill.name, "value": 0}
        core_log("display", "action", team=team, skill=skill.name, result=result)
        return result
    value = DamageCalculator.calculate(current, enemy, skill, weather=state.weather)
    details = dict(current.ability_state.get("_last_damage_details", {}))
    result = {
        "kind": "skill",
        "skill": skill.name,
        "base_power": skill.power,
        "value": value,
        "display_power": details.get("effective_power", skill.power),
        "damage_per_hit": details.get("damage_per_hit", value),
        "hits": details.get("hits", max(1, skill.hit_count)),
        "type_effectiveness": current.ability_state.get("_last_effectiveness", 1.0),
    }
    core_log("display", "action", team=team, skill=skill.name, result=result)
    return result


def skill_energy_cost(current: Pokemon, skill: Skill) -> int:
    """返回技能面板与合法动作共用的当前单次能耗。"""
    from nrc_core.battle import _temporary_skill_cost_delta
    return max(0, int(skill.energy_cost + current.skill_cost_mod
                      + _temporary_skill_cost_delta(current, skill)))


def _turn_start_skill_display(state: BattleState, team: str) -> dict[str, Any]:
    """计算当前技能面板；只读调用方应传入状态副本。"""
    team_list = state.team_a if team == "a" else state.team_b
    active_index = state.current_a if team == "a" else state.current_b
    current = team_list[active_index]
    enemy_list = state.team_b if team == "a" else state.team_a
    enemy_index = state.current_b if team == "a" else state.current_a
    enemy = enemy_list[enemy_index]
    displayed_skills = []
    for index, skill in enumerate(current.skills):
        display_energy_cost = skill_energy_cost(current, skill)
        power = int((skill.power + current.skill_power_bonus + current.next_attack_power_bonus)
                    * (1 + current.skill_power_pct_mod + current.next_attack_power_pct))
        display_power = power
        display_damage_per_hit = None
        display_hits = max(1, int(skill.hit_count + current.hit_count_mod))
        type_effectiveness = None
        if skill.category in {SkillCategory.PHYSICAL, SkillCategory.MAGICAL} and skill.power > 0:
            previous_details = current.ability_state.get("_last_damage_details")
            previous_effectiveness = current.ability_state.get("_last_effectiveness")
            DamageCalculator.calculate(current, enemy, skill, power_override=power,
                                       hit_count_override=display_hits, weather=state.weather)
            details = current.ability_state.get("_last_damage_details", {})
            display_power = int(details.get("effective_power", skill.power))
            display_damage_per_hit = details.get("damage_per_hit")
            display_hits = details.get("hits", display_hits)
            type_effectiveness = current.ability_state.get("_last_effectiveness", 1.0)
            if previous_details is None:
                current.ability_state.pop("_last_damage_details", None)
            else:
                current.ability_state["_last_damage_details"] = previous_details
            if previous_effectiveness is None:
                current.ability_state.pop("_last_effectiveness", None)
            else:
                current.ability_state["_last_effectiveness"] = previous_effectiveness
        displayed_skills.append({
            "skill_slot": index,
            "skill_id": getattr(skill, "skill_id", skill.name),
            "name": skill.name,
            "display_energy_cost": display_energy_cost,
            "display_power": display_power,
            "display_damage_per_hit": display_damage_per_hit,
            "display_hits": int(display_hits),
            "display_priority": int(skill.priority_mod + current.priority_stage),
            "type_effectiveness": type_effectiveness,
        })
        core_log(
            "display",
            "skill",
            team=team,
            slot=index,
            skill=skill.name,
            display_power=display_power,
            display_energy_cost=display_energy_cost,
            display_hits=display_hits,
            type_effectiveness=type_effectiveness,
        )
    return {
        "active_index": active_index,
        "skills": displayed_skills,
    }

def simulate_turn(state: BattleState, action_a: tuple[int, ...], action_b: tuple[int, ...], *, seed: int, clone: bool = True) -> TurnResult:
    """Execute exactly one supplied turn; episode history belongs to platform."""
    next_state = state.copy_state() if clone else state
    core_log(
        "turn",
        "start",
        turn=next_state.turn,
        seed=seed,
        active_a=next_state.team_a[next_state.current_a].name,
        active_b=next_state.team_b[next_state.current_b].name,
        hp_a=next_state.team_a[next_state.current_a].current_hp,
        hp_b=next_state.team_b[next_state.current_b].current_hp,
        energy_a=next_state.team_a[next_state.current_a].energy,
        energy_b=next_state.team_b[next_state.current_b].energy,
        action_a=action_a,
        action_b=action_b,
    )
    if not getattr(next_state, "turn_start_prepared", False):
        _trigger_battle_start_effects(next_state)
        _apply_turn_start_ability_logic(next_state)
        _apply_moisture_mark(next_state)
        next_state.turn_start_prepared = True
    turn_start_skill_display = {
        "own": _turn_start_skill_display(next_state, "a"),
        "opponent": _turn_start_skill_display(next_state, "b"),
    }
    display_power = {"a": _display_power(next_state, "a", action_a), "b": _display_power(next_state, "b", action_b)}
    before = {
        "turn": next_state.turn,
        "active": {"a": next_state.team_a[next_state.current_a].name, "b": next_state.team_b[next_state.current_b].name},
        "actions": {"a": _action_view(next_state, "a", action_a), "b": _action_view(next_state, "b", action_b)},
        "hp": {"a": next_state.team_a[next_state.current_a].current_hp, "b": next_state.team_b[next_state.current_b].current_hp},
    }
    with rng_scope(random.Random(int(seed))):
        execute_full_turn(next_state, action_a, action_b, lambda *_: None, lambda *_: None, preserve_report=True)
    after = {
        "turn": next_state.turn,
        "active": {"a": next_state.team_a[next_state.current_a].name, "b": next_state.team_b[next_state.current_b].name},
        "hp": {"a": next_state.team_a[next_state.current_a].current_hp, "b": next_state.team_b[next_state.current_b].current_hp},
        "mp": {"a": next_state.mp_a, "b": next_state.mp_b},
    }
    report = tuple(next_state.turn_report) + ({"type": "turn", "before": before, "after": after},)
    next_state.turn_report = []
    core_log(
        "turn",
        "end",
        turn=before["turn"],
        next_turn=next_state.turn,
        active_a=after["active"]["a"],
        active_b=after["active"]["b"],
        hp_a=after["hp"]["a"],
        hp_b=after["hp"]["b"],
        mp_a=after["mp"]["a"],
        mp_b=after["mp"]["b"],
        report_events=len(report) - 1,
    )
    return TurnResult(next_state, check_winner(next_state), report, display_power, turn_start_skill_display)


__all__ = ["TurnResult", "simulate_turn"]
