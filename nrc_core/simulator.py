"""纯核心战斗模拟器适配层。

旧项目的规则内核仍负责实际结算；本层负责：

* 接受可带未知字段的稳定输入协议；
* 将协议映射到旧的 BattleState；
* 统一主动作与道具动作；
* 输出双方完整回合后的可审计快照；
* 将技能文本解析得到的可能分支附加到结果中。

这使 人工采集器和未来 MuZero 都只依赖 nrc_core，而不直接依赖旧内部对象。
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any, Optional

from nrc_core.battle import (
    _skill_has_counter_for,
)
from nrc_core.effect_models import Timing
from nrc_core.engine._monolith import EffectExecutor
from nrc_core.catalog import CoreCatalog, EMPTY_CATALOG
from nrc_core.models import BattleState, Pokemon, SkillCategory, Type, get_type_effectiveness
from nrc_core.catalog import calc_combat_stats
from nrc_core.rng import rng_scope
from nrc_core.debug import core_log

from .actions import ActionIntent, ActionKind, SideTurnInput
from .branching import AuditStatus, BranchDimension, BranchKey, BranchOption
from .codec import battle_request_from_dict
from .core import simulate_turn
from .devotion import RANDOM_DEVOTION_CAPS
from .schema import (
    BattleRequest,
    BattleResult,
    CreatureInput,
    ResolutionBranch,
    SideResult,
    TeamInput,
)


def get_pokemon(_name: str):
    return None


def get_skill(_name: str):
    return None


LEGACY_DEVOTION_KEYS = {
    "cost_reduce": "\u5047\u5be5",
    "power_bonus": "\u98de\u65ad",
    "life_drain": "\u866b\u8327",
    "enemy_poison": "\u6346\u7f1a",
    "hit_count_bonus": "\u866b\u7fa4\u8fc7\u5883",
}
CANONICAL_DEVOTION_KEYS = {value: key for key, value in LEGACY_DEVOTION_KEYS.items()}


TYPE_MAP = {
    "普通": Type.NORMAL, "普通系": Type.NORMAL,
    "火": Type.FIRE, "火系": Type.FIRE,
    "水": Type.WATER, "水系": Type.WATER,
    "草": Type.GRASS, "草系": Type.GRASS,
    "电": Type.ELECTRIC, "电系": Type.ELECTRIC,
    "冰": Type.ICE, "冰系": Type.ICE,
    "武": Type.FIGHTING, "武系": Type.FIGHTING,
    "毒": Type.POISON, "毒系": Type.POISON,
    "地": Type.GROUND, "地系": Type.GROUND,
    "翼": Type.FLYING, "翼系": Type.FLYING,
    "幻": Type.PSYCHIC, "幻系": Type.PSYCHIC,
    "虫": Type.BUG, "虫系": Type.BUG,
    "幽": Type.GHOST, "幽系": Type.GHOST,
    "龙": Type.DRAGON, "龙系": Type.DRAGON,
    "恶": Type.DARK, "恶系": Type.DARK,
    "机械": Type.STEEL, "机械系": Type.STEEL, "机": Type.STEEL, "机系": Type.STEEL,
    "萌": Type.FAIRY, "萌系": Type.FAIRY,
    "光": Type.LIGHT, "光系": Type.LIGHT,
}


TYPE_LABELS = {
    Type.NORMAL: "normal",
    Type.FIRE: "fire",
    Type.WATER: "water",
    Type.ELECTRIC: "electric",
    Type.GRASS: "grass",
    Type.ICE: "ice",
    Type.FIGHTING: "martial",
    Type.POISON: "poison",
    Type.GROUND: "ground",
    Type.FLYING: "wing",
    Type.PSYCHIC: "psychic",
    Type.BUG: "insect",
    Type.GHOST: "ghost",
    Type.DRAGON: "dragon",
    Type.DARK: "devil",
    Type.STEEL: "machinery",
    Type.FAIRY: "cute",
    Type.LIGHT: "light",
}

def _type_label(value: Type) -> str:
    return TYPE_LABELS.get(value, "unknown")

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
    "freeze": "freeze_stacks", "frostbite_damage": "frostbite_damage",
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

@dataclass
class _LegacyBuild:
    state: BattleState
    own_names: list[str]
    opponent_names: list[str]
    warnings: list[str]
    unknowns: list[str]


class BattleSimulator:
    """面向采集器的纯核心入口。"""

    def __init__(self, data_dir=None, *, catalog: CoreCatalog | None = None):
        if catalog is None and data_dir is not None:
            from nrc_platform.catalog import load_catalog
            try:
                catalog = load_catalog(data_dir)
            except FileNotFoundError:
                catalog = None
        self.catalog = catalog or EMPTY_CATALOG

    def resolve_turn(self, request: BattleRequest | dict[str, Any]) -> BattleResult:
        if isinstance(request, dict):
            request = battle_request_from_dict(request)
        errors = self._validate_request(request)
        if errors:
            raise ValueError("; ".join(errors))
        seed = request.seed if request.seed is not None else random.SystemRandom().randrange(2**32)
        with rng_scope(random.Random(seed)):
            built = self._build_legacy(request)
            before_own = self._snapshot_side(built.state, "a", request.own_team, built.own_names)
            before_opponent = self._snapshot_side(built.state, "b", request.opponent_team, built.opponent_names)
            shared_before = self._snapshot_shared(built.state)
            cleanups = []
            cleanups.extend(self._apply_resonance_items(
                built.state, "a", request.own_turn.items, built.state.resonance_magic_a,
            ))
            cleanups.extend(self._apply_resonance_items(
                built.state, "b", request.opponent_turn.items, built.state.resonance_magic_b,
            ))
            type_effectiveness_a = self._effectiveness_for_action(built.state, "a", request.own_turn.primary)
            type_effectiveness_b = self._effectiveness_for_action(built.state, "b", request.opponent_turn.primary)
            try:
                action_a = self._to_legacy_action(request.own_turn.primary, built.state, "a")
                action_b = self._to_legacy_action(request.opponent_turn.primary, built.state, "b")
                turn_result = simulate_turn(built.state, action_a, action_b, seed=seed, clone=False)
            finally:
                self._restore_resonance_items(cleanups)
            built.state = turn_result.state

        after_own = self._snapshot_side(built.state, "a", request.own_team, built.own_names)
        after_opponent = self._snapshot_side(built.state, "b", request.opponent_team, built.opponent_names)
        shared_after = self._snapshot_shared(built.state)
        own_events, own_warnings = self._side_events(request.own_turn, request.opponent_turn, built.state, "a")
        opponent_events, opponent_warnings = self._side_events(request.opponent_turn, request.own_turn, built.state, "b")
        branches = self._possible_branches(request, built.state)
        latent_uncertainties = self._latent_uncertainties(request, built.state)
        debug = {
            "attribute_calculation": {
                "own": [pokemon.ability_state.get("lab_metadata", {}).get("attribute_calculation") for pokemon in built.state.team_a],
                "opponent": [pokemon.ability_state.get("lab_metadata", {}).get("attribute_calculation") for pokemon in built.state.team_b],
            },
            "damage_calculation": {
                "own": [event.get("debug", {}).get("damage_calculation") for event in turn_result.report if event.get("type") == "skill" and event.get("team") == "a" and event.get("debug")],
                "opponent": [event.get("debug", {}).get("damage_calculation") for event in turn_result.report if event.get("type") == "skill" and event.get("team") == "b" and event.get("debug")],
            },
        }

        events = [
            {"type": "seed", "value": seed},
            {"type": "action", "team": "own", "value": request.own_turn.primary.to_json()},
            {"type": "action", "team": "opponent", "value": request.opponent_turn.primary.to_json()},
            *turn_result.report,
            {"type": "display_power", "value": turn_result.display_power},
            *own_events,
            {"type": "turn_start_skill_display", "value": turn_result.turn_start_skill_display},
            *opponent_events,
        ]
        return BattleResult(
            own=SideResult(
                before=before_own,
                after=after_own,
                triggered_abilities=[event["id"] for event in own_events if event["type"] == "ability_candidate"],
                triggered_weather=[event["id"] for event in own_events if event["type"] == "weather_candidate"],
                triggered_counters=[event["id"] for event in own_events if event["type"] == "counter_candidate"],
                type_effectiveness=type_effectiveness_a,
                unsupported_actions=own_warnings,
            ),
            opponent=SideResult(
                before=before_opponent,
                after=after_opponent,
                triggered_abilities=[event["id"] for event in opponent_events if event["type"] == "ability_candidate"],
                triggered_weather=[event["id"] for event in opponent_events if event["type"] == "weather_candidate"],
                triggered_counters=[event["id"] for event in opponent_events if event["type"] == "counter_candidate"],
                type_effectiveness=type_effectiveness_b,
                unsupported_actions=opponent_warnings,
            ),
            shared_before=shared_before,
            shared_after=shared_after,
            turn_start_skill_display=turn_result.turn_start_skill_display,
            possible_branches=branches,
            observed_branch_id=None if len(branches) > 1 else (branches[0].branch_id if branches else None),
            events=events,
            warnings=built.warnings,
            debug=debug,
            input_unknowns=built.unknowns,
            latent_uncertainties=latent_uncertainties,
        )

    def _validate_request(self, request: BattleRequest) -> list[str]:
        errors: list[str] = []
        if not request.own_team.creatures or not request.opponent_team.creatures:
            errors.append("双方队伍至少需要一个精灵")
        if request.own_turn is None or request.opponent_turn is None:
            errors.append("own_turn 和 opponent_turn 都必须提供")
        else:
            errors.extend(f"own_turn: {error}" for error in request.own_turn.validate())
            errors.extend(f"opponent_turn: {error}" for error in request.opponent_turn.validate())
        return errors

    def _build_legacy(self, request: BattleRequest) -> _LegacyBuild:
        warnings: list[str] = []
        unknowns: list[str] = []
        own_names: list[str] = []
        opponent_names: list[str] = []
        team_a = [self._creature_to_legacy(item, f"own_{index}", warnings, unknowns) for index, item in enumerate(request.own_team.creatures)]
        team_b = [self._creature_to_legacy(item, f"opponent_{index}", warnings, unknowns) for index, item in enumerate(request.opponent_team.creatures)]
        own_names.extend(item.resolved_name(f"own_{index}") for index, item in enumerate(request.own_team.creatures))
        opponent_names.extend(item.resolved_name(f"opponent_{index}") for index, item in enumerate(request.opponent_team.creatures))
        state = BattleState(
            team_a=team_a,
            team_b=team_b,
            catalog=self.catalog,
            current_a=request.own_team.active_index.or_default(0),
            current_b=request.opponent_team.active_index.or_default(0),
            turn=request.shared.turn.or_default(1),
            weather=request.shared.weather.value if request.shared.weather.known and request.shared.weather.exists else None,
            mp_a=int(request.shared.mp.get("own").or_default(4)),
            mp_b=int(request.shared.mp.get("opponent").or_default(4)),
            resonance_magic_a=self._canonical_resonance(request.own_team.resonance_magic.or_default(None)),
            resonance_magic_b=self._canonical_resonance(request.opponent_team.resonance_magic.or_default(None)),
        )
        battle_context = dict(request.shared.metadata)
        for field_name in ("system_time", "weekend", "bypass"):
            field = getattr(request.shared, field_name)
            if field.known and field.exists:
                battle_context[field_name] = field.value
        for pokemon in state.team_a + state.team_b:
            pokemon.ability_state["battle_context"] = dict(battle_context)
        self._apply_devotion_input(state, request.own_team, "a")
        self._apply_devotion_input(state, request.opponent_team, "b")
        for team_id, source in (("a", request.own_team), ("b", request.opponent_team)):
            active_index = source.active_index.or_default(0)
            team_list = state.team_a if team_id == "a" else state.team_b
            if 0 <= active_index < len(team_list) and team_list[active_index].entry_count <= 0:
                team_list[active_index].entry_count = 1
        if request.shared.weather_turns.known and request.shared.weather_turns.exists:
            state.weather_turns = int(request.shared.weather_turns.value)
        for team, source, marks in (("a", request.own_team, state.marks_a), ("b", request.opponent_team, state.marks_b)):
            active = source.active_index.or_default(0)
            if 0 <= active < len(source.creatures):
                raw_marks = source.creatures[active].state.marks
                if raw_marks.known and raw_marks.exists:
                    for entry in _layer_entries(raw_marks.value):
                        mark_name = _layer_name(entry)
                        marks[mark_name] = marks.get(mark_name, 0) + _layer_stacks(entry)
        return _LegacyBuild(state, own_names, opponent_names, warnings, unknowns)

    @staticmethod
    def _canonical_resonance(value: Any) -> str | None:
        if not value:
            return None
        aliases = {
            "愿力": "willpower",
            "愿力强化": "willpower",
            "willpower": "willpower",
            "进化之力": "boss",
            "首领化": "boss",
            "boss": "boss",
            "光合治愈": "solar_heal",
            "solar_heal": "solar_heal",
            "闪焰爆发": "flame_burst",
            "节流术": "throttle",
        }
        return aliases.get(str(value), str(value))

    @staticmethod
    def _bloodline_values(pokemon: Pokemon) -> list[str]:
        metadata = pokemon.ability_state.get("lab_metadata", {})
        values = metadata.get("bloodline_attributes") or []
        if isinstance(values, str):
            values = [part.strip() for part in values.replace("/", "|").split("|") if part.strip()]
        return [str(value).strip() for value in values if str(value).strip()]

    @classmethod
    def _is_boss_bloodline(cls, pokemon: Pokemon) -> bool:
        values = cls._bloodline_values(pokemon)
        return any(
            text.lower() in {"boss", "lord", "leader"}
            or any(marker in text for marker in ("首领", "首領"))
            for text in values
        )

    @classmethod
    def _bloodline_type(cls, pokemon: Pokemon) -> Type | None:
        values = cls._bloodline_values(pokemon)
        special = ("首领", "首領", "奇异", "奇異", "污染", "boss", "lord", "leader")
        for raw in values:
            text = str(raw)
            if any(marker in text for marker in special):
                continue
            for name, type_value in TYPE_MAP.items():
                if name and name in text:
                    return type_value
        return None

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

    @staticmethod
    def _canonical_devotion_key(value: str) -> str:
        aliases = {
            "power_bonus": "power_bonus",
            "cost_reduce": "cost_reduce",
            "hit_count_bonus": "hit_count_bonus",
            "life_drain": "life_drain",
            "enemy_poison": "enemy_poison",
            "\u5047\u5be5": "cost_reduce",
            "\u98de\u65ad": "power_bonus",
            "\u866b\u8327": "life_drain",
            "\u6346\u7f1a": "enemy_poison",
            "\u866b\u7fa4\u8fc7\u5883": "hit_count_bonus",
        }
        return aliases.get(str(value), str(value))

    def _normalize_devotion_counts(self, raw: dict[str, Any]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for key, value in (raw or {}).items():
            canonical = self._canonical_devotion_key(key)
            if canonical in RANDOM_DEVOTION_CAPS:
                normalized[canonical] = max(0, int(value))
        return normalized

    def _apply_devotion_input(self, state: BattleState, team: TeamInput, side: str) -> None:
        specified = team.devotion.specified_counts
        random_counts = team.devotion.random_counts
        known: dict[str, int] = {}
        specified_known: dict[str, int] = {}
        if specified.known and specified.exists and isinstance(specified.value, dict):
            specified_known = self._normalize_devotion_counts(specified.value)
            known.update(specified_known)
        if random_counts.known and random_counts.exists and isinstance(random_counts.value, dict):
            for key, value in self._normalize_devotion_counts(random_counts.value).items():
                known[key] = known.get(key, 0) + min(value, RANDOM_DEVOTION_CAPS[key])
        legacy_known = {LEGACY_DEVOTION_KEYS[key]: value for key, value in known.items()}
        legacy_specified = {LEGACY_DEVOTION_KEYS[key]: value for key, value in specified_known.items()}
        legacy_random = {
            LEGACY_DEVOTION_KEYS[key]: value
            for key, value in self._normalize_devotion_counts(random_counts.value or {}).items()
        }
        draws = int(team.devotion.random_draws.or_default(0))
        if draws > 0 and not random_counts.known:
            from nrc_core.engine._monolith import DEVOTION_TYPES
            sampled: dict[str, int] = {}
            for _ in range(draws):
                chosen = rng_choice(DEVOTION_TYPES)
                canonical = self._canonical_devotion_key(chosen)
                sampled[canonical] = sampled.get(canonical, 0) + 1
            for key, value in sampled.items():
                capped = min(value, RANDOM_DEVOTION_CAPS[key])
                known[key] = known.get(key, 0) + capped
                legacy_known[LEGACY_DEVOTION_KEYS[key]] = legacy_known.get(LEGACY_DEVOTION_KEYS[key], 0) + capped
            legacy_random = {
                LEGACY_DEVOTION_KEYS[key]: value
                for key, value in sampled.items()
            }
            draws = 0
        elif random_counts.known:
            draws = 0
        if side == "a":
            state.devotion_a = legacy_known
            state.specified_devotion_a = legacy_specified
            state.random_devotion_draws_a = draws
            state.random_devotion_counts_a = legacy_random if legacy_random else {}
        else:
            state.devotion_b = legacy_known
            state.specified_devotion_b = legacy_specified
            state.random_devotion_draws_b = draws
            state.random_devotion_counts_b = legacy_random if legacy_random else {}

    def _distribution_rows(self, spirit_name: str, distribution_kind: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.catalog.get_distribution(spirit_name, distribution_kind)]
    @staticmethod
    def _normalize_individual_values(raw: Any) -> dict[str, int]:
        aliases = {
            "hp": "hp", "生命": "hp", "生命值": "hp",
            "atk": "atk", "attack": "atk", "物攻": "atk",
            "spatk": "spatk", "sp_attack": "spatk", "魔攻": "spatk",
            "def": "def", "defense": "def", "物防": "def",
            "spdef": "spdef", "sp_defense": "spdef", "魔防": "spdef",
            "speed": "speed", "速度": "speed",
        }
        result = {key: 0 for key in ("hp", "atk", "spatk", "def", "spdef", "speed")}
        items = raw.items() if isinstance(raw, dict) else ()
        for key, value in items:
            text = str(key).strip()
            normalized = aliases.get(text.lower(), aliases.get(text))
            if normalized is None:
                continue
            try:
                result[normalized] = max(0, min(60, int(value)))
            except (TypeError, ValueError):
                continue
        return result

    def _resolve_combat_config(
        self,
        item: CreatureInput,
        name: str,
        provided_stats: bool,
    ) -> tuple[str, dict[str, int], dict[str, Any]]:
        metadata = item.metadata if isinstance(item.metadata, dict) else {}
        mode = str(metadata.get("attribute_assumption", "database") or "database").lower()
        nature_rows = self._distribution_rows(name, "nature")
        talent_rows = self._distribution_rows(name, "talent")
        nature_explicit = item.base.nature.known and item.base.nature.exists and bool(item.base.nature.value)
        if nature_explicit:
            nature_name = str(item.base.nature.value)
            nature_source = "input"
        elif mode in {"neutral", "zero", "all_zero"}:
            nature_name = "坦率"
            nature_source = "assumption:neutral"
        elif nature_rows:
            nature_name = nature_rows[0]["item"]
            nature_source = "catalog.distribution"
        else:
            nature_name = "坦率"
            nature_source = "fallback:neutral"

        iv_explicit = item.base.individual_values.known and item.base.individual_values.exists
        if iv_explicit:
            iv_config = self._normalize_individual_values(item.base.individual_values.value)
            iv_source = "input"
        elif mode in {"neutral", "zero", "all_zero"} or provided_stats:
            iv_config = self._normalize_individual_values({})
            iv_source = "assumption:zero" if not provided_stats else "not_used:provided_stats"
        else:
            talent_map = {
                "生命": "hp", "物攻": "atk", "魔攻": "spatk",
                "物防": "def", "魔防": "spdef", "速度": "speed",
            }
            selected = [row for row in talent_rows if row["item"] in talent_map][:3]
            iv_config = self._normalize_individual_values({talent_map[row["item"]]: 60 for row in selected})
            iv_source = "catalog.distribution" if talent_rows else "fallback:zero"

        assumption = {
            "mode": mode,
            "nature": nature_name,
            "nature_source": nature_source,
            "individual_values": dict(iv_config),
            "individual_values_source": iv_source,
            "nature_distribution": nature_rows,
            "talent_distribution": talent_rows,
        }
        return nature_name, iv_config, assumption

    def _creature_to_legacy(self, item: CreatureInput, fallback: str, warnings: list[str], unknowns: list[str]) -> Pokemon:
        name = item.resolved_name(fallback)
        db_record = None
        try:
            db_record = self.catalog.get_pokemon(name)
        except Exception:
            db_record = None
        provided_stats = item.base.stats.known and item.base.stats.exists and bool(item.base.stats.value)
        stats = item.base.stats.value if provided_stats else None
        nature_name, iv_config, attribute_assumption = self._resolve_combat_config(item, name, provided_stats)
        if not stats:
            if db_record:
                stats = calc_combat_stats(
                    db_record["base_hp"], db_record["base_attack"], db_record["base_magic_attack"],
                    db_record["base_defense"], db_record["base_magic_defense"], db_record["base_speed"],
                    iv_config=iv_config,
                    nature_name=nature_name,
                )
            else:
                stats = {"hp": 100, "atk": 100, "def": 100, "spatk": 100, "spdef": 100, "speed": 100}
                warnings.append(f"{name}: 未找到六维数据，使用中性占位值")
        type_value = item.base.attributes.or_default(None)
        if not type_value and db_record:
            type_value = db_record.get("types", [])
        if isinstance(type_value, str):
            type_value = [part.strip() for part in type_value.replace("|", "/").split("/") if part.strip()]
        type_value = type_value or ["普通"]
        pokemon_types = [TYPE_MAP.get(value, Type.NORMAL) for value in type_value]
        pokemon_type = pokemon_types[0]
        ability_name = item.ability.name.or_default(db_record.get("ability", "") if db_record else "")
        ability_names = [ability_name] if ability_name else []
        ability_names.extend(
            ability.name.value
            for ability in item.abilities
            if ability.name.known and ability.name.exists and ability.name.value
        )
        skill_slots = item.skills or []
        skills = []
        for index in range(max(4, len(skill_slots))):
            slot = skill_slots[index] if index < len(skill_slots) else None
            skill_name = slot.name.or_default("") if slot else ""
            skill_id = slot.skill_id.or_default(skill_name) if slot else skill_name
            if not skill_name and skill_id:
                skill_name = skill_id
            if not skill_name:
                skill_name = f"__unknown_skill_{index}"
                unknowns.append(f"{name}.skills[{index}]")
            if skill_name == "愿力冲击":
                raise ValueError("愿力冲击不能作为精灵携带技能，只能由愿力强化临时提供")
            skill = self.catalog.get_skill(skill_name)
            if skill is None:
                skill = get_skill(skill_name)
            if skill is None:
                skill = Skill(skill_name, Type.NORMAL, SkillCategory.STATUS, 0, 0)
            skill.skill_id = skill_id or skill.name
            if slot:
                if slot.current_energy_cost.known and slot.current_energy_cost.exists:
                    skill.energy_cost = int(slot.current_energy_cost.value)
                if slot.current_power.known and slot.current_power.exists:
                    skill.power = int(slot.current_power.value)
                skill.use_count = max(1, int(slot.use_count.or_default(1) or 1))
            skills.append(skill)
        state = item.state
        max_hp = int(state.max_hp.or_default(stats.get("hp", 100)))
        current_hp = int(state.hp.or_default(max_hp))
        energy = int(state.energy.or_default(10))
        pokemon = Pokemon(
            name=name,
            pokemon_type=pokemon_type,
            hp=max_hp,
            attack=int(stats.get("atk", 100)),
            defense=int(stats.get("def", 100)),
            sp_attack=int(stats.get("spatk", 100)),
            sp_defense=int(stats.get("spdef", 100)),
            speed=int(stats.get("speed", 100)),
            pokemon_types=pokemon_types,
            ability=ability_name,
            skills=skills,
            current_hp=current_hp,
            energy=energy,
            entry_count=int(item.entry_count.or_default(0)),
            fatigue_turns=int(state.fatigue_turns.or_default(0)),
            nature=nature_name,
            iv_hp=iv_config["hp"],
            iv_atk=iv_config["atk"],
            iv_spatk=iv_config["spatk"],
            iv_def=iv_config["def"],
            iv_spdef=iv_config["spdef"],
            iv_speed=iv_config["speed"],
        )
        core_log("attributes", "resolved", pokemon=name,
                 source="input" if provided_stats else "catalog_or_fallback",
                 base_stats={
                     "hp": db_record.get("base_hp") if db_record else None,
                     "atk": db_record.get("base_attack") if db_record else None,
                     "spatk": db_record.get("base_magic_attack") if db_record else None,
                     "def": db_record.get("base_defense") if db_record else None,
                     "spdef": db_record.get("base_magic_defense") if db_record else None,
                     "speed": db_record.get("base_speed") if db_record else None,
                 },
                 stats={"hp": pokemon.hp, "atk": pokemon.attack,
                        "spatk": pokemon.sp_attack, "def": pokemon.defense,
                        "spdef": pokemon.sp_defense, "speed": pokemon.speed},
                 nature=nature_name, iv=iv_config,
                 types=[item.value for item in pokemon.pokemon_types],
                 ability=ability_name)
        layered_state = {"buffs": [], "debuffs": [], "statuses": []}
        for direction, raw in (("up", state.buffs.or_default([])), ("down", state.debuffs.or_default([]))):
            entries = _layer_entries(raw)
            bucket = "buffs" if direction == "up" else "debuffs"
            layered_state[bucket] = [
                {"name": _layer_name(entry), "unit": str(entry.get("unit", "legacy")), "stacks": _layer_stacks(entry)}
                for entry in entries
            ]
            for entry in entries:
                stat = _stat_layer_key(_layer_name(entry))
                if stat:
                    value = (float(entry.get("stacks", 0)) / 10.0) if entry.get("_legacy") else _layer_unit_value(entry.get("unit")) * _layer_stacks(entry)
                    setattr(pokemon, f"{stat}_{direction}", max(0.0, value))
        status_fields = {
            "poison": "poison_stacks", "burn": "burn_stacks", "freeze": "freeze_stacks",
            "frostbite_damage": "frostbite_damage", "leech": "leech_stacks",
            "electric": "electric_stacks",
            "meteor": "meteor_stacks", "cute": "cute_stacks", "combo": "hit_count_mod",
        }
        raw_statuses = state.statuses.or_default(None)
        status_entries = _layer_entries(raw_statuses if raw_statuses is not None else item.metadata.get("status_stacks", {}))
        layered_state["statuses"] = [
            {"name": _layer_name(entry), "unit": str(entry.get("unit", _layer_name(entry))), "stacks": _layer_stacks(entry)}
            for entry in status_entries
        ]
        for entry in status_entries:
            key = _status_layer_key(_layer_name(entry))
            if key in status_fields:
                current = getattr(pokemon, status_fields[key])
                setattr(pokemon, status_fields[key], max(0, int(current) + _layer_stacks(entry)))
        pokemon.ability_state["layered_state"] = layered_state
        if pokemon.freeze_stacks and not pokemon.frostbite_damage:
            pokemon.frostbite_damage = max(1, round(pokemon.hp * 0.05 * pokemon.freeze_stacks))
            if pokemon.current_hp <= pokemon.frostbite_damage:
                pokemon.current_hp = 0
        pokemon.ability_effects = [
            effect
            for name in dict.fromkeys(ability_names)
            for effect in self.catalog.get_ability_effects(name)
        ]
        pokemon.ability_state["lab_metadata"] = {
            "creature_id": item.creature_id.value if item.creature_id.known else None,
            "evolution_stage": item.evolution_stage.value if item.evolution_stage.known else None,
            "bossified": item.bossified.value if item.bossified.known else None,
            "bloodline_attributes": item.base.bloodline_attributes.value if item.base.bloodline_attributes.known else None,
            "combat_attributes": list(type_value),
            "attribute_calculation": {
                "formula": "provided_stats" if provided_stats else "hp: intermediate=round_half_up(70 + growth * 170); final=round_half_up(intermediate * (1 + nature_bonus) + 100); other: intermediate=round_half_up(10 + growth * 110); final=round_half_up(intermediate * (1 + nature_bonus) + 50)",
                "growth_formula": "growth = base * 0.01 + iv * 0.005",
                "rounding": "floor(value + 0.5)",
                "provided_stats": bool(provided_stats),
                "nature": nature_name,
                "individual_values": dict(iv_config),
                "assumption": attribute_assumption,
                "base_stats": {key: db_record[key] for key in ("base_hp", "base_attack", "base_magic_attack", "base_defense", "base_magic_defense", "base_speed") } if db_record else None,
                "result": dict(stats),
            },
            "skill_pool": item.skill_pool.value if item.skill_pool.known else None,
            "gulu_ball": item.metadata.get("gulu_ball"),
            "boss_form": item.metadata.get("boss_form") or item.metadata.get("boss_name"),
        }
        for field_name, field in (("hp", state.hp), ("energy", state.energy), ("ability", item.ability.name)):
            if not field.known:
                unknowns.append(f"{name}.{field_name}")
        return pokemon

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
        for index, skill in enumerate(current.skills):
            if skill.name == action.skill_name or getattr(skill, "skill_id", "") == action.skill_id:
                skill.selected_choice = action.choice or ""
                return (index,)
        raise ValueError(f"{team} 当前精灵没有技能: {action.skill_name or action.skill_id}")

    def _possible_branches(self, request: BattleRequest, state: BattleState) -> list[ResolutionBranch]:
        return [ResolutionBranch(
            "base",
            1.0,
            [BranchOption(BranchKey(BranchDimension.CONDITION, "base", "base"), 1.0)],
        )]
        parsed_rules = []
        for team, side in (("a", request.own_turn), ("b", request.opponent_turn)):
            if not side or side.primary.kind != ActionKind.SKILL:
                continue
            skill_name = side.primary.skill_name
            if skill_name is None and side.primary.skill_slot is not None:
                current = state.get_current(team)
                if 0 <= side.primary.skill_slot < len(current.skills):
                    skill_name = current.skills[side.primary.skill_slot].name
            if skill_name is None and side.primary.skill_id:
                current = state.get_current(team)
                skill_name = next(
                    (skill.name for skill in current.skills if getattr(skill, "skill_id", "") == side.primary.skill_id),
                    None,
                )
        if not parsed_rules:
            branches = [ResolutionBranch("base", 1.0, [BranchOption(BranchKey(BranchDimension.CONDITION, "base", "无条件分支"), 1.0)])]
        else:
            combinations = [[]]
            for rule in parsed_rules:
                rule_branches = (
                    [[option] for option in rule.options]
                    if not rule.branches or rule.branches == [[]]
                    else rule.branches
                )
                combinations = [prefix + branch for prefix in combinations for branch in rule_branches]
                if len(combinations) > 128:
                    return [ResolutionBranch(
                        "manual_required", None, [], AuditStatus.MANUAL_REQUIRED,
                        "双方技能分支组合超过 128，需人工拆分或指定观测分支",
                    )]
            branches = []
            for options in combinations:
                code = "__".join(option.key.code for option in options) or "condition:base"
                probability_values = [option.probability for option in options if option.probability is not None]
                probability = 1.0 if probability_values else None
                for value in probability_values:
                    probability *= value
                status = AuditStatus.PARSED if probability is not None else AuditStatus.MANUAL_REQUIRED
                branches.append(ResolutionBranch(code, probability, options, status))
        for uncertainty in self._latent_uncertainties(request, state):
            option = BranchOption(
                key=BranchKey(BranchDimension.DEVOTION_EFFECT, "latent", "随机奉献潜变量"),
                evidence=f"{uncertainty['side']}:{uncertainty['skill_id']}",
            )
            branches.append(ResolutionBranch(
                f"devotion:{uncertainty['side']}:latent",
                None,
                [option],
                AuditStatus.PARTIAL,
                "奉献随机状态采用紧凑潜变量，不展开五类效果和层数组合",
            ))
        return branches

    def _latent_uncertainties(self, request: BattleRequest, state: BattleState) -> list[dict[str, Any]]:
        uncertainties: list[dict[str, Any]] = []
        for side_name, side_id in (("own", "a"), ("opponent", "b")):
            draws = state.random_devotion_draws_a if side_id == "a" else state.random_devotion_draws_b
            if draws <= 0:
                continue
            current = state.get_current(side_id)
            action = request.own_turn if side_id == "a" else request.opponent_turn
            active_skill = None
            if action and action.primary.kind == ActionKind.SKILL:
                index = action.primary.skill_slot
                if index is None and action.primary.skill_name:
                    index = next((i for i, item in enumerate(current.skills) if item.name == action.primary.skill_name), None)
                if index is not None and 0 <= index < len(current.skills):
                    active_skill = current.skills[index]
            if active_skill is None or not getattr(active_skill, "devotion_affected", False):
                continue
            uncertainties.append({
                "type": "random_devotion_latent",
                "side": side_name,
                "draws": draws,
                "skill_id": getattr(active_skill, "skill_id", active_skill.name),
                "effect_ranges": {
                    "power_bonus": [0, min(RANDOM_DEVOTION_CAPS["power_bonus"], draws) * 20],
                    "cost_reduce": [0, min(RANDOM_DEVOTION_CAPS["cost_reduce"], draws) * 2],
                    "hit_count_bonus": [0, min(RANDOM_DEVOTION_CAPS["hit_count_bonus"], draws)],
                    "life_drain": [0.0, min(RANDOM_DEVOTION_CAPS["life_drain"], draws) * 0.1],
                    "enemy_poison": [0, min(RANDOM_DEVOTION_CAPS["enemy_poison"], draws) * 2],
                },
                "update": "replace random_counts after observing an affected skill",
            })
        return uncertainties

    @staticmethod
    def _skill_for_action(action: ActionIntent, pokemon: Pokemon):
        if action.skill_slot is not None and 0 <= action.skill_slot < len(pokemon.skills):
            return pokemon.skills[action.skill_slot]
        return next(
            (
                skill for skill in pokemon.skills
                if skill.name == action.skill_name
                or getattr(skill, "skill_id", "") == action.skill_id
            ),
            None,
        )

    def _effectiveness_for_action(self, state: BattleState, team: str, action: ActionIntent) -> list[dict[str, Any]]:
        """返回供审计模块使用的属性关系，不把它当作游戏可见事实。"""
        if action.kind != ActionKind.SKILL:
            return []
        attacker = state.get_current(team)
        defender = state.get_current("b" if team == "a" else "a")
        skill = self._skill_for_action(action, attacker)
        if skill is None:
            return []
        if skill.category not in {SkillCategory.PHYSICAL, SkillCategory.MAGICAL}:
            return []
        multiplier = get_type_effectiveness(skill.skill_type, defender.pokemon_types)
        return [{
            "role": "type_effectiveness",
            "respondent": attacker.name,
            "respondee": defender.name,
            "skill_id": getattr(skill, "skill_id", "") or skill.name,
            "skill_name": skill.name,
            "skill_type": _type_label(skill.skill_type),
            "skill_category": skill.category.value,
            "applies_to_damage": skill.category in {SkillCategory.PHYSICAL, SkillCategory.MAGICAL},
            "type_multiplier": multiplier,
            "is_super_effective": multiplier > 1.0,
            "is_resisted": 0.0 < multiplier < 1.0,
            "is_immune": multiplier == 0.0,
            "known": True,
            "source": "type_chart_for_audit",
        }]

    def _side_events(self, own_turn: SideTurnInput, enemy_turn: SideTurnInput, state: BattleState, team: str) -> tuple[list[dict], list[str]]:
        events: list[dict] = []
        warnings: list[str] = []
        action = own_turn.primary
        for item in own_turn.items:
            if item.item_kind is not None and item.item_kind.value not in {"willpower", "boss", "solar_heal"}:
                warnings.append(f"道具暂未接入规则内核: {item.item_kind.value if item.item_kind else 'unknown'}")
        current = state.get_current(team)
        enemy = state.get_current("b" if team == "a" else "a")
        if current.ability_effects:
            for effect in current.ability_effects:
                events.append({
                    "type": "ability_candidate",
                    "id": f"{current.ability or current.name}:{effect.timing.name}",
                    "certainty": "engine_timing_executed",
                })
        if state.weather:
            events.append({"type": "weather_candidate", "id": f"weather:{state.weather}", "certainty": "shared_state"})
        if action.kind == ActionKind.SKILL:
            skill = self._skill_for_action(action, current)
            enemy_skill = None
            if enemy_turn.primary.kind == ActionKind.SKILL:
                enemy_skill = next(
                    (
                        item for item in enemy.skills
                        if item.name == enemy_turn.primary.skill_name
                        or getattr(item, "skill_id", "") == enemy_turn.primary.skill_id
                    ),
                    None,
                )
            if skill and enemy_skill and _skill_has_counter_for(skill, enemy_skill):
                events.append({"type": "counter_candidate", "id": "counter:success-or-failure", "certainty": "requires_audit"})
        return events, warnings

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
        fields = (("poison", "poison_stacks"), ("burn", "burn_stacks"), ("freeze", "freeze_stacks"), ("frostbite_damage", "frostbite_damage"), ("leech", "leech_stacks"), ("electric", "electric_stacks"), ("meteor", "meteor_stacks"), ("cute", "cute_stacks"), ("combo", "hit_count_mod"))
        return [{"name": name, "unit": name, "stacks": max(0, int(getattr(pokemon, field, 0)))} for name, field in fields if int(getattr(pokemon, field, 0)) > 0]

    @staticmethod
    def _snapshot_marks(marks: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"name": str(name), "unit": str(name), "stacks": max(0, int(round(float(value))))} for name, value in marks.items() if isinstance(value, (int, float)) and value > 0]

    def _snapshot_side(self, state: BattleState, team: str, source: TeamInput, names: list[str]) -> dict[str, Any]:
        team_list = state.team_a if team == "a" else state.team_b
        active_index = state.current_a if team == "a" else state.current_b
        marks = state.marks_a if team == "a" else state.marks_b
        return {
            "team_name": source.team_name,
            "active_index": active_index,
            "team_marks": self._snapshot_marks(marks),
            "devotion": self._snapshot_devotion(state, source, team),
            "creatures": [
                {
                    "index": index,
                    "name": pokemon.name,
                    "hp": pokemon.current_hp,
                    "max_hp": pokemon.hp,
                    "energy": pokemon.energy,
                    "fainted": pokemon.is_fainted,
                    "entry_count": getattr(pokemon, "entry_count", 0),
                    "fatigue_turns": getattr(pokemon, "fatigue_turns", 0),
                    "ability": pokemon.ability,
                    "attributes": [_type_label(type_value) for type_value in pokemon.pokemon_types],
                    "bloodline_attributes": pokemon.ability_state.get("lab_metadata", {}).get("bloodline_attributes"),
                    "stats": {
                        "atk": pokemon.attack, "def": pokemon.defense,
                        "spatk": pokemon.sp_attack, "spdef": pokemon.sp_defense,
                        "speed": pokemon.speed,
                    },
                    "buffs": self._snapshot_layers(pokemon, "up"),
                    "debuffs": self._snapshot_layers(pokemon, "down"),
                    "statuses": self._snapshot_statuses(pokemon),
                    "skills": [
                        {
                            "skill_id": getattr(skill, "skill_id", skill.name),
                            "name": skill.name,
                            "current_energy_cost": skill.energy_cost,
                            "current_power": skill.power,
                            "use_count": int((state.turn_skill_use_counts_a if team == "a" else state.turn_skill_use_counts_b).get(str(index) + ":" + str(slot), 0)),
                            "planned_use_count": max(1, int(getattr(skill, "use_count", 1) or 1)),
                        }
                        for slot, skill in enumerate(pokemon.skills)
                    ],
                }
                for index, pokemon in enumerate(team_list)
            ],
        }

    def _snapshot_devotion(self, state: BattleState, source: TeamInput, team: str) -> dict[str, Any]:
        specified = {
            CANONICAL_DEVOTION_KEYS.get(key, key): value
            for key, value in (state.specified_devotion_a if team == "a" else state.specified_devotion_b).items()
        }
        draws = state.random_devotion_draws_a if team == "a" else state.random_devotion_draws_b
        counts = {
            CANONICAL_DEVOTION_KEYS.get(key, key): value
            for key, value in (state.random_devotion_counts_a if team == "a" else state.random_devotion_counts_b).items()
        }
        visible = team == "a" or source.devotion.visible_to_observer
        return {
            "specified": specified,
            "random": {
                "status": "resolved" if draws == 0 else "unresolved",
                "draws": draws,
                "counts": counts if visible else None,
                "visible_to_observer": visible,
            },
        }

    def _snapshot_shared(self, state: BattleState) -> dict[str, Any]:
        return {
            "turn": state.turn,
            "weather": state.weather,
            "weather_turns": state.weather_turns,
            "mp": {"own": state.mp_a, "opponent": state.mp_b},
        }
