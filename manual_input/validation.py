from __future__ import annotations

from typing import Any


def _known(value: Any) -> bool:
    return isinstance(value, dict) and value.get("known") is True and value.get("exists", True)


def _value(field: Any, default: Any = None) -> Any:
    return field.get("value", default) if _known(field) else default


def validate_request(request: dict[str, Any], require_round: bool = True) -> list[str]:
    """Validate the fields needed by ``nrc_core.BattleSimulator``.

    Unknown passive fields are allowed, but the recorder never silently drops
    them: every unknown is represented by the core ``Maybe`` protocol.
    """
    errors: list[str] = []
    skip_opponent = bool((request.get("shared") or {}).get("metadata", {}).get("skip_opponent_lineup"))
    for side in ("own_team", "opponent_team"):
        team = request.get(side) or {}
        creatures = team.get("creatures") or []
        if len(creatures) != 6:
            errors.append(f"{side}.creatures must contain exactly 6 entries")
        active = _value(team.get("active_index"), None)
        if not isinstance(active, int) or not 0 <= active < max(len(creatures), 1):
            errors.append(f"{side}.active_index is invalid")
        for index, creature in enumerate(creatures):
            prefix = f"{side}.creatures[{index}]"
            if not _known(creature.get("name")) or not _value(creature.get("name")):
                if side == "opponent_team" and skip_opponent:
                    continue
                errors.append(f"{prefix}.name is required")
            state = creature.get("state") or {}
            for field in ("hp", "max_hp", "energy"):
                if not _known(state.get(field)):
                    if side == "opponent_team" and skip_opponent:
                        continue
                    errors.append(f"{prefix}.state.{field} is required")
            skills = creature.get("skills") or []
            if len(skills) != 4:
                errors.append(f"{prefix}.skills must contain exactly 4 slots")
            for skill_index, skill in enumerate(skills):
                if not isinstance(skill, dict):
                    errors.append(f"{prefix}.skills[{skill_index}] is invalid")
                    continue
                skill_name = skill.get("name")
                if _known(skill_name) and _value(skill_name):
                    if not _known(skill.get("current_energy_cost")):
                        errors.append(f"{prefix}.skills[{skill_index}].current_energy_cost is required")
                    if not _known(skill.get("current_power")):
                        errors.append(f"{prefix}.skills[{skill_index}].current_power is required")

    shared = request.get("shared") or {}
    for field in ("turn",):
        if not _known(shared.get(field)):
            errors.append(f"shared.{field} is required")
    for field in ("own", "opponent"):
        if not _known((shared.get("mp") or {}).get(field)):
            errors.append(f"shared.mp.{field} is required")

    if require_round:
        for side, team_name in (("own_turn", "own"), ("opponent_turn", "opponent")):
            turn = request.get(side) or {}
            primary = turn.get("primary") or {}
            kind = primary.get("kind")
            if kind not in {"skill", "charge", "switch", "pass"}:
                errors.append(f"{side}.primary.kind is required")
            if kind == "skill" and primary.get("skill_slot") is None and not primary.get("skill_name"):
                errors.append(f"{side}.primary must select a skill")
            if kind == "skill":
                team = request.get(f"{team_name}_team") or {}
                creatures = team.get("creatures") or []
                active = _value(team.get("active_index"), None)
                slot = primary.get("skill_slot")
                selected = None
                if isinstance(active, int) and 0 <= active < len(creatures):
                    skills = creatures[active].get("skills") or []
                    if isinstance(slot, int) and 0 <= slot < len(skills):
                        selected = skills[slot]
                if selected is None:
                    errors.append(f"{side}.primary skill_slot is invalid")
                elif not _known(selected.get("name")) or not _value(selected.get("name")):
                    errors.append(f"{side}.primary selects an unrecorded skill")
                elif not _known(selected.get("current_energy_cost")) or not _known(selected.get("current_power")):
                    errors.append(f"{side}.primary selected skill needs cost and power")
            if kind == "switch" and primary.get("switch_index") is None:
                errors.append(f"{side}.primary must select a switch target")
    return errors
