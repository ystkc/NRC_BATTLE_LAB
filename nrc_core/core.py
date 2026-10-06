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
from nrc_core.models import BattleState, SkillCategory
from nrc_core.rng import rng_scope


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
        return {"kind": "non_skill", "value": 0}
    skill = current.skills[action[0]]
    if skill.power <= 0:
        return {"kind": "skill", "skill": skill.name, "value": 0}
    value = DamageCalculator.calculate(current, enemy, skill, weather=state.weather)
    details = dict(current.ability_state.get("_last_damage_details", {}))
    return {
        "kind": "skill",
        "skill": skill.name,
        "base_power": skill.power,
        "value": value,
        "display_power": details.get("effective_power", skill.power),
        "damage_per_hit": details.get("damage_per_hit", value),
        "hits": details.get("hits", max(1, skill.hit_count)),
        "type_effectiveness": current.ability_state.get("_last_effectiveness", 1.0),
    }


def _turn_start_skill_display(state: BattleState, team: str) -> dict[str, Any]:
    team_list = state.team_a if team == "a" else state.team_b
    active_index = state.current_a if team == "a" else state.current_b
    current = team_list[active_index]
    enemy_list = state.team_b if team == "a" else state.team_a
    enemy_index = state.current_b if team == "a" else state.current_a
    enemy = enemy_list[enemy_index]
    displayed_skills = []
    for index, skill in enumerate(current.skills):
        display_power = int(skill.power)
        display_damage_per_hit = None
        display_hits = max(1, int(skill.hit_count))
        type_effectiveness = None
        if skill.category in {SkillCategory.PHYSICAL, SkillCategory.MAGICAL} and skill.power > 0:
            previous_details = current.ability_state.get("_last_damage_details")
            previous_effectiveness = current.ability_state.get("_last_effectiveness")
            DamageCalculator.calculate(current, enemy, skill, weather=state.weather)
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
            "display_energy_cost": int(skill.energy_cost),
            "display_power": display_power,
            "display_damage_per_hit": display_damage_per_hit,
            "display_hits": int(display_hits),
            "type_effectiveness": type_effectiveness,
        })
    return {
        "active_index": active_index,
        "skills": displayed_skills,
    }

def simulate_turn(state: BattleState, action_a: tuple[int, ...], action_b: tuple[int, ...], *, seed: int, clone: bool = True) -> TurnResult:
    """Execute exactly one supplied turn; episode history belongs to platform."""
    next_state = state.copy_state() if clone else state
    next_state.turn_skill_use_counts_a.clear()
    next_state.turn_skill_use_counts_b.clear()
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
        execute_full_turn(next_state, action_a, action_b, lambda *_: None, lambda *_: None)
    after = {
        "turn": next_state.turn,
        "active": {"a": next_state.team_a[next_state.current_a].name, "b": next_state.team_b[next_state.current_b].name},
        "hp": {"a": next_state.team_a[next_state.current_a].current_hp, "b": next_state.team_b[next_state.current_b].current_hp},
        "mp": {"a": next_state.mp_a, "b": next_state.mp_b},
    }
    report = tuple(next_state.turn_report) + ({"type": "turn", "before": before, "after": after},)
    return TurnResult(next_state, check_winner(next_state), report, display_power, turn_start_skill_display)


__all__ = ["TurnResult", "simulate_turn"]
