"""已解析战斗状态使用的共鸣、动作与快照规则帮助实现。"""

from __future__ import annotations

from typing import Any, Mapping
from nrc_core.actions import ActionIntent, ActionKind
from nrc_core.catalog import CoreCatalog, calc_combat_stats
from nrc_core.models import BattleState, Pokemon, Type
from nrc_core.effect_models import Timing
from nrc_core.engine import EffectExecutor

_STAT_LAYER_ALIASES = {
    "atk": "atk", "attack": "atk",
    "def": "def", "defense": "def",
    "spatk": "spatk", "sp_attack": "spatk",
    "spdef": "spdef", "sp_defense": "spdef",
    "speed": "speed",
    "物攻": "atk", "物攻强化": "atk", "物防": "def", "物防强化": "def",
    "魔攻": "spatk", "魔攻强化": "spatk", "魔防": "spdef", "魔防强化": "spdef",
    "攻击": "atk", "攻击强化": "atk", "防御": "def", "防御强化": "def",
    "魔攻": "spatk", "魔攻强化": "spatk", "魔防": "spdef", "魔防强化": "spdef",
    "速度": "speed", "速度强化": "speed",
}

_STATUS_LAYER_FIELDS = {
    "poison": "poison_stacks", "burn": "burn_stacks",
    "freeze": "freeze_stacks",
    "leech": "leech_stacks", "electric": "electric_stacks",
    "meteor": "meteor_stacks", "cute": "cute_stacks",
    "combo": "hit_count_mod",
}

_STATUS_LAYER_ALIASES = {
    "中毒": "poison", "灼烧": "burn", "冻结": "freeze", "寄生": "leech",
    "引电": "electric", "星陨": "meteor", "萌化": "cute", "连击": "combo",
}

def _layer_entries(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [{"name": str(name), "unit": "legacy", "stacks": value, "_legacy": True} for name, value in raw.items()]
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append({"name": item, "unit": item, "stacks": 1})
        elif isinstance(item, dict):
            result.append(dict(item))
    return result

def _layer_name(entry: dict[str, Any]) -> str:
    return str(entry.get("name") or entry.get("status") or entry.get("stat") or "unknown")

def _layer_stacks(entry: dict[str, Any]) -> int:
    try:
        return max(0, int(round(float(entry.get("stacks", entry.get("count", 0))))))
    except (TypeError, ValueError):
        return 0

def _layer_unit_value(unit: Any) -> float:
    if isinstance(unit, (int, float)):
        return float(unit)
    text = str(unit or "").strip().replace("％", "%")
    value = float(text.replace("%", "") or 0)
    return value / 100.0

def _stat_layer_key(name: str) -> str | None:
    normalized = name.lower().replace("_up", "").replace("_down", "")
    return _STAT_LAYER_ALIASES.get(normalized) or _STAT_LAYER_ALIASES.get(name)

def _status_layer_key(name: str) -> str:
    normalized = name.lower().replace("_stacks", "")
    return _STATUS_LAYER_ALIASES.get(normalized, normalized)

class BattleRulesSupport:
    """仅操作完整战斗对象，不补全原始观测输入。"""

    def __init__(self, *, catalog: CoreCatalog):
        """绑定已解析的共鸣形态和技能映射。"""
        self.catalog = catalog

    @staticmethod
    def _is_boss_bloodline(pokemon: Pokemon) -> bool:
        """读取平台已规范化的首领血脉标记。"""
        return bool(pokemon.ability_state.get("lab_metadata", {}).get("resolved_boss_bloodline"))

    @staticmethod
    def _bloodline_type(pokemon: Pokemon) -> Type | None:
        """读取平台已解析的系别血脉。"""
        value = pokemon.ability_state.get("lab_metadata", {}).get("resolved_bloodline_type")
        return value if isinstance(value, Type) else None

    def _apply_boss_resonance(self, state: BattleState, team: str) -> None:
        used_name = "resonance_evolution_used_a" if team == "a" else "resonance_evolution_used_b"
        if getattr(state, used_name):
            raise ValueError("进化之力每场战斗只能使用一次")
        active = state.get_current(team)
        if not self._is_boss_bloodline(active):
            raise ValueError("进化之力只能对首领血脉精灵使用")
        metadata = active.ability_state.get("lab_metadata", {})
        boss_name = metadata.get("boss_form") or metadata.get("boss_name")
        candidates = [self.catalog.get_pokemon(boss_name)] if boss_name else list(self.catalog.get_boss_forms(active.name))
        candidates = [item for item in candidates if item]
        if len(candidates) != 1:
            raise ValueError("当前精灵缺少唯一的首领形态映射，请通过 metadata.boss_form 指定")
        record = candidates[0]
        old_hp = max(1, active.hp)
        hp_ratio = max(0.0, min(1.0, active.current_hp / old_hp))
        stats = calc_combat_stats(
            record["base_hp"], record["base_attack"], record["base_magic_attack"],
            record["base_defense"], record["base_magic_defense"], record["base_speed"],
            iv_config={
                "hp": active.iv_hp,
                "atk": active.iv_atk,
                "spatk": active.iv_spatk,
                "def": active.iv_def,
                "spdef": active.iv_spdef,
                "speed": active.iv_speed,
            },
            nature_name=active.nature,
        )
        active.name = record["name"]
        active.hp = int(stats["hp"])
        active.attack = int(stats["atk"])
        active.defense = int(stats["def"])
        active.sp_attack = int(stats["spatk"])
        active.sp_defense = int(stats["spdef"])
        active.speed = int(stats["speed"])
        active.current_hp = min(active.hp, max(0, round(active.hp * hp_ratio)))
        active.ability = record.get("ability", "")
        active.ability_effects = self.catalog.get_ability_effects(active.ability)
        active.ability_state["lab_metadata"]["bossified"] = True
        enemy = state.get_current("b" if team == "a" else "a")
        if active.ability_effects:
            EffectExecutor.execute_ability(state, active, enemy, Timing.ON_ENTER, active.ability_effects, team)
        setattr(state, used_name, True)

    def _apply_resonance_items(self, state: BattleState, team: str, items: list[ActionIntent], carried: str | None) -> list[tuple[Pokemon, Any]]:
        cleanups: list[tuple[Pokemon, Any]] = []
        if not items:
            return cleanups
        if len(items) > 1:
            raise ValueError("每回合最多使用一种共鸣魔法")
        item = items[0]
        kind = item.item_kind.value if item.item_kind else ""
        if kind != carried:
            raise ValueError("使用的共鸣魔法不是本方携带的共鸣魔法")
        active = state.get_current(team)
        if active.is_fainted:
            raise ValueError("倒下的精灵不能使用共鸣魔法")
        if kind == "willpower":
            uses_name = "resonance_uses_a" if team == "a" else "resonance_uses_b"
            cooldown_name = "resonance_cooldown_a" if team == "a" else "resonance_cooldown_b"
            if getattr(state, uses_name) >= 2 or getattr(state, cooldown_name) > 0:
                raise ValueError("愿力强化当前不可用")
            bloodline_type = self._bloodline_type(active)
            if bloodline_type is None:
                raise ValueError("愿力强化只能对系别血脉精灵使用")
            replacement = self.catalog.get_skill("愿力冲击")
            replacement.skill_id = "resonance:willpower_strike"
            replacement.skill_type = bloodline_type
            replacement._resonance_dual_path = True
            replacement.description = "基础威力80，能耗2，造成物理/魔法伤害；应对状态时威力提高150%"
            original = active.skills[0]
            active.skills[0] = replacement
            cleanups.append((active, original))
            setattr(state, uses_name, getattr(state, uses_name) + 1)
            setattr(state, cooldown_name, 3)
        elif kind == "boss":
            self._apply_boss_resonance(state, team)
        elif kind == "solar_heal":
            used_name = "resonance_solar_heal_used_a" if team == "a" else "resonance_solar_heal_used_b"
            if getattr(state, used_name):
                raise ValueError("光合治愈每场战斗只能使用一次")
            active.ability_state["resonance_solar_heal_remaining"] = 3
            heal = max(1, round(active.hp * 0.15))
            active.current_hp = min(active.hp, active.current_hp + heal)
            setattr(state, used_name, True)
        else:
            raise ValueError(f"共鸣魔法尚未上线: {kind}")
        return cleanups

    @staticmethod
    def _restore_resonance_items(cleanups: list[tuple[Pokemon, Any]]) -> None:
        for pokemon, original in cleanups:
            pokemon.skills[0] = original

    def _to_legacy_action(self, action: ActionIntent, state: BattleState, team: str) -> tuple[int, ...]:
        if action.kind == ActionKind.CHARGE or action.kind == ActionKind.PASS:
            return (-1,)
        if action.kind == ActionKind.SWITCH:
            if action.switch_index is None:
                raise ValueError("换人动作缺少 switch_index")
            return (-2, int(action.switch_index))
        if action.kind != ActionKind.SKILL:
            return (-1,)
        current = state.get_current(team)
        if action.skill_slot is not None:
            if not 0 <= int(action.skill_slot) < len(current.skills):
                raise ValueError(f"{team} skill_slot out of range")
            current.skills[int(action.skill_slot)].selected_choice = action.choice or ""
            return (int(action.skill_slot),)
        raise ValueError(f"{team}: 核心技能动作必须提供 skill_slot")

    @staticmethod
    def _snapshot_layers(pokemon: Pokemon, direction: str) -> list[dict[str, Any]]:
        stored = pokemon.ability_state.get("layered_state", {}).get("buffs" if direction == "up" else "debuffs", [])
        if stored:
            result = []
            for item in stored:
                name = str(item.get("name"))
                unit = str(item.get("unit"))
                stacks = max(0, int(item.get("stacks", 0)))
                stat = _stat_layer_key(name)
                if stat and unit != "legacy":
                    unit_value = _layer_unit_value(unit)
                    if unit_value > 0:
                        stacks = max(0, int(round(float(getattr(pokemon, f"{stat}_{direction}", 0.0)) / unit_value)))
                result.append({"name": name, "unit": unit, "stacks": stacks})
            action_speed_layers = int(pokemon.ability_state.get("action_speed_bonus_layers", 0))
            if direction == "up" and action_speed_layers > 0:
                result.append({"name": "变形活画速度", "unit": "+5", "stacks": action_speed_layers})
            return result
        result = []
        for stat in ("atk", "def", "spatk", "spdef", "speed"):
            value = max(0.0, float(getattr(pokemon, f"{stat}_{direction}", 0.0)))
            if value:
                result.append({"name": f"{stat}_{direction}", "unit": "+10%", "stacks": int(round(value * 10))})
        action_speed_layers = int(pokemon.ability_state.get("action_speed_bonus_layers", 0))
        if direction == "up" and action_speed_layers > 0:
            result.append({"name": "变形活画速度", "unit": "+5", "stacks": action_speed_layers})
        return result

    @staticmethod
    def _snapshot_statuses(pokemon: Pokemon) -> list[dict[str, Any]]:
        stored = pokemon.ability_state.get("layered_state", {}).get("statuses", [])
        if stored:
            result = []
            for item in stored:
                name = str(item.get("name"))
                key = _status_layer_key(name)
                field = _STATUS_LAYER_FIELDS.get(key)
                stacks = max(0, int(getattr(pokemon, field, 0))) if field else max(0, int(item.get("stacks", 0)))
                result.append({"name": name, "unit": str(item.get("unit")), "stacks": stacks})
            return result
        fields = (("poison", "poison_stacks"), ("burn", "burn_stacks"), ("freeze", "freeze_stacks"), ("leech", "leech_stacks"), ("electric", "electric_stacks"), ("meteor", "meteor_stacks"), ("cute", "cute_stacks"), ("combo", "hit_count_mod"))
        return [{"name": name, "unit": name, "stacks": max(0, int(getattr(pokemon, field, 0)))} for name, field in fields if int(getattr(pokemon, field, 0)) > 0]

    @staticmethod
    def _snapshot_marks(marks: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"name": str(name), "unit": str(name), "stacks": max(0, int(round(float(value))))} for name, value in marks.items() if isinstance(value, (int, float)) and value > 0]

    @staticmethod
    def _snapshot_ability_states(pokemon: Pokemon) -> list[dict[str, Any]]:
        runtime = pokemon.ability_state or {}
        result: list[dict[str, Any]] = []
        for key, value in runtime.items():
            if key in {"layered_state", "lab_metadata", "battle_context", "last_skill_cost", "last_skill_turn", "faint_processed"} or str(key).startswith("_"):
                continue
            if isinstance(value, bool) and value:
                result.append({"kind": "ability", "name": str(key), "stacks": 1})
            elif isinstance(value, (int, float)) and value:
                result.append({"kind": "ability", "name": str(key), "stacks": value})
        return result

    @staticmethod
    def _state_change_events(before: Mapping[str, Any], after: Mapping[str, Any], team: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        before_creatures = before.get("creatures") or []
        after_creatures = after.get("creatures") or []
        for index, current in enumerate(after_creatures):
            previous = before_creatures[index] if index < len(before_creatures) else {}
            changes: list[dict[str, Any]] = []
            private_changes: list[dict[str, Any]] = []
            old_modifiers = previous.get("modifiers") or {}
            new_modifiers = current.get("modifiers") or {}
            for name in sorted(set(old_modifiers) | set(new_modifiers)):
                if old_modifiers.get(name, 0) != new_modifiers.get(name, 0):
                    changes.append({"kind": "modifier", "name": name,
                                    "before": old_modifiers.get(name, 0), "after": new_modifiers.get(name, 0)})
            for field, label in (("hp", "hp"), ("energy", "energy"), ("status", "status"), ("fainted", "fainted")):
                old_value = previous.get(field)
                new_value = current.get(field)
                if old_value != new_value:
                    changes.append({"kind": label, "before": old_value, "after": new_value})
            for field, kind in (("statuses", "status"), ("buffs", "buff"), ("debuffs", "debuff"), ("ability_states", "ability"), ("skills", "skill")):
                old_items = previous.get(field) or []
                new_items = current.get(field) or []
                if field == "skills":
                    old_public = previous.get("_public_skill_modifier_deltas") or []
                    new_public = current.get("_public_skill_modifier_deltas") or []
                    for slot, item in enumerate(new_items):
                        if slot >= len(old_items):
                            continue
                        old_item = old_items[slot]
                        for key in ("energy_cost", "power", "hit_count", "priority_mod"):
                            snapshot_key = "current_" + key
                            old_value, new_value = old_item.get(snapshot_key), item.get(snapshot_key)
                            if old_value is None or new_value is None:
                                continue
                            old_global = old_public[slot].get(key, 0) if slot < len(old_public) else 0
                            new_global = new_public[slot].get(key, 0) if slot < len(new_public) else 0
                            delta = new_value - old_value - (new_global - old_global)
                            if delta:
                                private_changes.append({"kind": "skill", "name": str(item.get("name")), "field": key,
                                                        "before": old_value, "after": old_value + delta})
                    continue
                old_map = {str(item.get("name")): item for item in old_items if isinstance(item, dict)}
                new_map = {str(item.get("name")): item for item in new_items if isinstance(item, dict)}
                for name in sorted(set(old_map) | set(new_map)):
                    old_item = old_map.get(name, {})
                    new_item = new_map.get(name, {})
                    old_stacks = old_item.get("stacks", 0)
                    new_stacks = new_item.get("stacks", 0)
                    if old_stacks != new_stacks:
                        changes.append({"kind": kind, "name": name, "unit": new_item.get("unit") or old_item.get("unit"), "before": old_stacks, "after": new_stacks})
            if changes:
                events.append({"type": "state_change", "team": team, "pokemon": current.get("name"), "changes": changes})
            if private_changes:
                events.append({"type": "state_change", "team": team, "pokemon": current.get("name"),
                               "private": True, "visibility": "owner", "owner_team": team, "changes": private_changes})
        return events
