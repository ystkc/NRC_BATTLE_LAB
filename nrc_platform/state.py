"""Observer-facing state categories; core runtime dictionaries are never a UI API."""

from __future__ import annotations

import copy

from nrc_core.contracts import Observation
from nrc_core.catalog import CoreCatalog
from nrc_core.models import BattleState, Pokemon


_LEGACY = {
    "boosts", "buffs", "debuffs", "conditions", "ability_states", "ability_state",
    "cooldowns", "status", "freeze_stacks", "electric_stacks",
    "cute_stacks", "poison_stacks", "burn_stacks", "leech_stacks", "meteor_stacks",
}
_STATUSES = (
    ("poison", "poison_stacks", "层"), ("burn", "burn_stacks", "层"),
    ("freeze", "freeze_stacks", "层"),
    ("leech", "leech_stacks", "层"), ("electric", "electric_stacks", "层"),
    ("meteor", "meteor_stacks", "层"), ("cute", "cute_stacks", "层"),
)

# Publicly meaningful counters/flags, not timestamps, input caches or object references.
_ABILITY_STATUSES = {
    "guard_counters", "undying_revive_in", "double_damage_next", "first_action_bonus",
    "turn_end_repeat", "turn_end_skip", "freeze_immune", "burn_immune",
    "poison_immune", "meteor_immune", "debuff_immune", "energy_immune",
    "cute_no_cap", "energy_no_cap", "extra_poison_tick", "half_meteor_full_damage",
}

_SKILL_MODIFIERS = {
    "energy_cost": ("skill_cost", "能量"),
    "power": ("skill_power", "威力"),
    "hit_count": ("combo", "层"),
    "priority_mod": ("priority", "层"),
}
_PUBLIC_SKILL_MODIFIERS = {**_SKILL_MODIFIERS, "power_pct": ("skill_power_pct", "%")}


def creature_effects(pokemon: Pokemon) -> tuple[list[dict], list[dict]]:
    # Up and down layers coexist in the rules: do not cancel them into a net value.
    modifiers = []
    for stat in ("atk", "def", "spatk", "spdef", "speed"):
        for direction, sign in (("up", 1), ("down", -1)):
            value = getattr(pokemon, f"{stat}_{direction}")
            if value:
                modifiers.append({"name": stat, "stacks": round(sign * value * 10, 10), "unit": "10%"})
    for name, value, unit in (
        ("combo", pokemon.hit_count_mod, "层"),
        ("priority", pokemon.priority_stage, "层"),
        ("action_speed", pokemon.ability_state.get("action_speed_bonus_layers", 0), "+5"),
        ("skill_power", pokemon.skill_power_bonus, "威力"),
        ("skill_power_pct", pokemon.skill_power_pct_mod * 100, "%"),
        ("skill_cost", pokemon.skill_cost_mod, "能量"),
        ("power_multiplier", (pokemon.power_multiplier - 1) * 100, "%"),
        ("life_drain", pokemon.life_drain_mod * 100, "%"),
        ("next_attack_power", pokemon.next_attack_power_bonus, "威力"),
        ("next_attack_power_pct", pokemon.next_attack_power_pct * 100, "%"),
    ):
        if value:
            modifiers.append({"name": name, "stacks": value, "unit": unit})
    statuses = [
        {"name": name, "stacks": getattr(pokemon, field), "unit": unit}
        for name, field, unit in _STATUSES if getattr(pokemon, field) > 0
    ]
    for field, value in pokemon.ability_state.get("public_skill_modifiers", {}).items():
        if field in _PUBLIC_SKILL_MODIFIERS and value:
            name, unit = _PUBLIC_SKILL_MODIFIERS[field]
            modifiers.append({"name": name, "stacks": value, "unit": unit})
    for mod in pokemon.ability_state.get("temporary_skill_cost_mods", []):
        if mod.get("filter", "all") == "all" and mod.get("amount"):
            amount = mod["amount"]
            if pokemon.ability_state.get("cost_invert"):
                amount = -amount
            if pokemon.ability_state.get("cost_change_double"):
                amount *= 2
            modifiers.append({"name": "skill_cost", "stacks": amount, "unit": "能量"})
    status = str(getattr(pokemon.status, "value", pokemon.status))
    if status not in {"normal", "正常", "fainted", "力竭"} and not any(s["name"] == status for s in statuses):
        statuses.append({"name": status, "stacks": 1, "unit": "层"})
    for key in sorted(_ABILITY_STATUSES):
        value = pokemon.ability_state.get(key, 0)
        if isinstance(value, (int, float)) and value:
            # Signed trait counters are two distinct nonnegative statuses.
            statuses.append({"name": key if value > 0 else f"{key}_negative",
                             "stacks": abs(value), "unit": "层"})
    return modifiers, statuses


def normalize_observation(observation: Observation, battle: BattleState, catalog: CoreCatalog, *, revealed: dict[int, set[int]]) -> Observation:
    """Expose public effects while preserving private loadout information."""
    data = copy.deepcopy(dict(observation.data))
    own_a = observation.player == 0
    sides = (("own", battle.team_a if own_a else battle.team_b),
             ("opponent", battle.team_b if own_a else battle.team_a))
    for side, team in sides:
        for item, pokemon in zip(data.get(f"{side}_team", []), team):
            known = side == "own" or item["index"] in revealed[1 - observation.player]
            if not known:
                index = item["index"]
                item.clear()
                item.update(index=index, name="未知精灵", known=False, active=False,
                            fainted=False, types=[], modifiers=[], statuses=[])
                continue
            item["known"] = True
            metadata = pokemon.ability_state.get("lab_metadata", {})
            for field in ("bloodline_attributes", "form", "bossified", "drive_form"):
                if field in metadata:
                    item[field] = copy.deepcopy(metadata[field])
            item["ability"] = pokemon.ability
            item["hp_percent"] = max(0, min(100, round(pokemon.current_hp / pokemon.hp * 100))) if pokemon.hp else 0
            private = side == "own" and "skills" in item
            for key in _LEGACY:
                item.pop(key, None)
            modifiers, statuses = creature_effects(pokemon)
            item["modifiers"] = modifiers
            item["statuses"] = statuses
            if not private:
                for skill_data in item.get("skills", []):
                    skill_data.pop("skill_states", None)
            if private:
                for skill_data in item["skills"]:
                    slot = skill_data["index"]
                    skill = pokemon.skills[slot]
                    base = catalog.get_skill(skill.name)
                    states = {"cooldown": pokemon.cooldowns.get(slot, 0)}
                    if base is not None:
                        public_deltas = pokemon.ability_state.get("_public_skill_modifier_deltas", [])
                        public = public_deltas[slot] if slot < len(public_deltas) else {}
                        for field in _SKILL_MODIFIERS:
                            states[f"{field}_delta"] = (
                                getattr(skill, field) - getattr(base, field) - public.get(field, 0)
                            )
                    skill_data["skill_states"] = {k: v for k, v in states.items() if v}
    data["shared"]["marks"] = {
        "own": copy.deepcopy(battle.marks_a if own_a else battle.marks_b),
        "opponent": copy.deepcopy(battle.marks_b if own_a else battle.marks_a),
    }
    own_devotion = battle.devotion_a if own_a else battle.devotion_b
    opponent_devotion = battle.devotion_b if own_a else battle.devotion_a
    data["shared"]["devotion"] = {
        "own": {"total": sum(own_devotion.values()), "distribution": copy.deepcopy(own_devotion)},
    }
    return Observation(observation.player, observation.decision_index, observation.turn,
                       observation.phase, data)
