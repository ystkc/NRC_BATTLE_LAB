"""平台完整输入解析、目录补全与核心战斗状态构造。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import logging

from nrc_core.effect_models import Timing
from nrc_core.engine import EffectExecutor
from nrc_core.catalog import CoreCatalog, EMPTY_CATALOG
from nrc_core.models import BattleState, Pokemon, Type
from nrc_core.catalog import calc_combat_stats
from nrc_core.debug import core_log
from nrc_core.rules_support import BattleRulesSupport
from nrc_core.codec import battle_request_from_dict
from nrc_core.devotion import RANDOM_DEVOTION_CAPS
from nrc_core.rng import choice as rng_choice, rng_scope
from nrc_core.runtime import UnsupportedMechanicError
import random

from nrc_core.actions import ActionIntent, ActionKind
from nrc_core.schema import (
    BattleRequest,
    CreatureInput,
    TeamInput,
)


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

@dataclass
class _LegacyBuild:
    state: BattleState
    own_names: list[str]
    opponent_names: list[str]
    warnings: list[str]
    unknowns: list[str]


class BattleBuilder(BattleRulesSupport):
    """构造完整战斗状态，并提供共鸣与状态快照帮助方法。"""

    def __init__(self, *, catalog: CoreCatalog | None = None):
        """接收已解析目录，不从核心反向调用平台查库。"""
        self.catalog = catalog or EMPTY_CATALOG
        self.logger = logging.getLogger(__name__)

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
        for pokemon in state.team_a + state.team_b:
            metadata = pokemon.ability_state.setdefault("lab_metadata", {})
            metadata["resolved_boss_bloodline"] = self._is_boss_bloodline(pokemon)
            metadata["resolved_bloodline_type"] = self._bloodline_type(pokemon)
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
            from nrc_core.engine.handlers_field import DEVOTION_TYPES
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
        db_record = self.catalog.get_pokemon(name)
        if db_record is None:
            raise ValueError(f"unknown creature {name!r}")
        provided_stats = item.base.stats.known and item.base.stats.exists and bool(item.base.stats.value)
        stats = dict(item.base.stats.value) if provided_stats else None
        partial_stats = provided_stats and set(stats) == {"hp"}
        if partial_stats:
            item.metadata = {**(item.metadata or {}), "attribute_assumption": "neutral"}
        nature_name, iv_config, attribute_assumption = self._resolve_combat_config(item, name, provided_stats)
        if partial_stats:
            if db_record:
                self.logger.info("Database record: %s", db_record.__str__())
                default_stats = calc_combat_stats(
                    db_record["base_hp"], db_record["base_attack"], db_record["base_magic_attack"],
                    db_record["base_defense"], db_record["base_magic_defense"], db_record["base_speed"],
                    iv_config=iv_config,
                    nature_name=nature_name,
                )
            stats = {**default_stats, **stats}
        elif not stats:
            if db_record:
                stats = calc_combat_stats(
                    db_record["base_hp"], db_record["base_attack"], db_record["base_magic_attack"],
                    db_record["base_defense"], db_record["base_magic_defense"], db_record["base_speed"],
                    iv_config=iv_config,
                    nature_name=nature_name,
                )
        if not stats or set(stats) != {"hp", "atk", "def", "spatk", "spdef", "speed"}:
            raise ValueError(f"{name}: 必须提供完整六维数据")
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
        if not skill_slots:
            raise ValueError(f"{name}: 必须提供技能")
        for index, slot in enumerate(skill_slots):
            skill_name = slot.name.or_default("") if slot else ""
            skill_id = slot.skill_id.or_default(skill_name) if slot else skill_name
            if not skill_name and skill_id:
                skill_name = skill_id
            if not skill_name:
                raise ValueError(f"{name}.skills[{index}]: 必须提供已知技能")
            if skill_name == "愿力冲击":
                raise ValueError("愿力冲击不能作为精灵携带技能，只能由愿力强化临时提供")
            skill = self.catalog.get_skill(skill_name)
            if skill is None:
                raise ValueError(f"unknown skill {skill_name!r}")
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
            "leech": "leech_stacks",
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
        if pokemon.freeze_stacks and pokemon.current_hp <= pokemon.freeze_threshold:
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

    def _known_skill_names(self) -> set[str]:
        return set(self.catalog.skills)

    def _validate_setup(self, request: BattleRequest) -> None:
        if not request.own_team.creatures or not request.opponent_team.creatures:
            raise ValueError("both teams must contain at least one creature")
        unsupported: list[str] = []
        for side, team in (("0", request.own_team), ("1", request.opponent_team)):
            resonance = self._canonical_resonance(team.resonance_magic.or_default(None))
            if resonance in {"flame_burst", "throttle"}:
                unsupported.append(f"player {side}: resonance {resonance}")
            elif resonance not in {None, "willpower", "boss", "solar_heal"}:
                unsupported.append(f"player {side}: unknown resonance {resonance}")
            active_index = int(team.active_index.or_default(0))
            if active_index < 0 or active_index >= len(team.creatures):
                raise ValueError(f"player {side} active_index is out of range")
            for index, creature in enumerate(team.creatures):
                name = creature.resolved_name(f"{side}_{index}")
                db_record = self.catalog.get_pokemon(name)
                if not db_record:
                    raise ValueError(f"unknown creature {name!r}")
                if creature.bossified.known and creature.bossified.or_default(False):
                    unsupported.append(f"{name}: boss mechanics")
                ability_names = []
                if creature.ability.name.known and creature.ability.name.exists:
                    ability_names.append(str(creature.ability.name.value))
                elif db_record.get("ability"):
                    ability_names.append(str(db_record["ability"]))
                ability_names.extend(
                    str(item.name.value)
                    for item in creature.abilities
                    if item.name.known and item.name.exists
                )
                for ability in ability_names:
                    if not ability:
                        continue
                    if ability.split(":", 1)[0].split("：", 1)[0].strip() == "契约的形状":
                        ball = (creature.metadata or {}).get("gulu_ball")
                        if ball not in {"普通咕噜球", "高级咕噜球", "国王球", "美妙球", "好战球", "光合球", "网兜球", "暗星球", "调温球", "绝缘球", "淘沙球", "变幻球", "柔软咕噜球"}:
                            unsupported.append(f"{name}: contract mechanic requires valid gulu_ball")
                    if not self.catalog.get_ability_effects(ability):
                        unsupported.append(f"{name}: ability {ability}")
                if not creature.skills:
                    raise ValueError(f"{name} must provide all skill slots")
                for slot, skill in enumerate(creature.skills):
                    skill_name = skill.name.or_default(skill.skill_id.or_default(""))
                    if not skill_name or skill_name not in self._known_skill_names():
                        raise ValueError(f"unknown skill {skill_name!r} at {name}[{slot}]")
                    if skill_name == "愿力冲击":
                        unsupported.append(f"{name}[{slot}] 愿力冲击: resonance-only skill")
                    parsed_skill = self.catalog.get_skill(skill_name)
                    if parsed_skill is None:
                        raise ValueError(f"unknown skill {skill_name!r} at {name}[{slot}]")
                    if parsed_skill.choice_options and len(parsed_skill.choice_options) != 2:
                        unsupported.append(f"{name}[{slot}] {skill_name}: choice skill must expose exactly two options")
                    if parsed_skill.random_source:
                        unsupported.append(f"{name}[{slot}] {skill_name}: random target/choice skill")
                for key in ("items", "contract", "random_skill"):
                    if (creature.metadata or {}).get(key):
                        unsupported.append(f"{name}: {key}")
        if unsupported:
            raise UnsupportedMechanicError("unsupported mechanics: " + "; ".join(unsupported))


    def build(self, setup: Mapping[str, Any], seed: int = 0) -> BattleState:
        """校验并解析平台输入，返回不含未知占位的全知状态。"""
        raw = dict(setup)
        if "setup" in raw and isinstance(raw["setup"], Mapping):
            raw = dict(raw["setup"])
        request = battle_request_from_dict(raw)
        self._validate_setup(request)
        with rng_scope(random.Random(int(seed))):
            battle = self._build_legacy(request).state
        return battle
