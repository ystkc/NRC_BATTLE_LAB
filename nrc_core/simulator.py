"""纯核心战斗模拟器适配层。

旧项目的规则内核仍负责实际结算；本层负责：

* 接受可带未知字段的稳定输入协议；
* 将协议映射到旧的 BattleState；
* 统一主动作与道具动作；
* 输出双方完整回合后的可审计快照；
* 将技能文本解析得到的可能分支附加到结果中。

这使 mitmproxy、人工采集器和未来 MuZero 都只依赖 nrc_core，而不直接依赖旧内部对象。
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from collector.parsing.skill_description import SkillDescriptionParser
from src.battle import (
    _skill_has_counter_for,
    auto_switch,
    execute_full_turn,
)
from src.effect_models import Timing
from src.models import BattleState, Pokemon, SkillCategory, Type, get_type_effectiveness
from src.pokemon_db import calc_combat_stats, get_pokemon
from src.skill_db import get_skill, load_ability_effects

from .actions import ActionIntent, ActionKind, SideTurnInput
from .branching import AuditStatus, BranchDimension, BranchKey, BranchOption
from .codec import battle_request_from_dict
from .devotion import RANDOM_DEVOTION_CAPS
from .schema import (
    BattleRequest,
    BattleResult,
    CreatureInput,
    ResolutionBranch,
    SideResult,
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


@dataclass
class _LegacyBuild:
    state: BattleState
    own_names: list[str]
    opponent_names: list[str]
    warnings: list[str]
    unknowns: list[str]


class BattleSimulator:
    """面向采集器的纯核心入口。"""

    def __init__(self, data_dir: str | Path | None = None):
        self.project_dir = Path(__file__).resolve().parents[1]
        self.data_dir = Path(data_dir) if data_dir else self.project_dir / "data"
        self._skill_descriptions: dict[str, str] = {}
        self._skill_parser = SkillDescriptionParser()
        self._load_skill_descriptions()

    def resolve_turn(self, request: BattleRequest | dict[str, Any]) -> BattleResult:
        if isinstance(request, dict):
            request = battle_request_from_dict(request)
        errors = self._validate_request(request)
        if errors:
            raise ValueError("; ".join(errors))
        built = self._build_legacy(request)
        before_own = self._snapshot_side(built.state, "a", request.own_team, built.own_names)
        before_opponent = self._snapshot_side(built.state, "b", request.opponent_team, built.opponent_names)
        shared_before = self._snapshot_shared(built.state)

        seed = request.seed if request.seed is not None else random.randrange(2**32)
        effectiveness_a = self._effectiveness_for_action(built.state, "a", request.own_turn.primary)
        effectiveness_b = self._effectiveness_for_action(built.state, "b", request.opponent_turn.primary)
        random_state = random.getstate()
        random.seed(seed)
        try:
            action_a = self._to_legacy_action(request.own_turn.primary, built.state, "a")
            action_b = self._to_legacy_action(request.opponent_turn.primary, built.state, "b")
            execute_full_turn(built.state, action_a, action_b)
            auto_switch(built.state)
        finally:
            random.setstate(random_state)

        after_own = self._snapshot_side(built.state, "a", request.own_team, built.own_names)
        after_opponent = self._snapshot_side(built.state, "b", request.opponent_team, built.opponent_names)
        shared_after = self._snapshot_shared(built.state)
        own_events, own_warnings = self._side_events(request.own_turn, request.opponent_turn, built.state, "a")
        opponent_events, opponent_warnings = self._side_events(request.opponent_turn, request.own_turn, built.state, "b")
        branches = self._possible_branches(request, built.state)
        latent_uncertainties = self._latent_uncertainties(request, built.state)

        events = [
            {"type": "seed", "value": seed},
            {"type": "action", "team": "own", "value": request.own_turn.primary.to_json()},
            {"type": "action", "team": "opponent", "value": request.opponent_turn.primary.to_json()},
            *own_events,
            *opponent_events,
        ]
        return BattleResult(
            own=SideResult(
                before=before_own,
                after=after_own,
                triggered_abilities=[event["id"] for event in own_events if event["type"] == "ability_candidate"],
                triggered_weather=[event["id"] for event in own_events if event["type"] == "weather_candidate"],
                triggered_counters=[event["id"] for event in own_events if event["type"] == "counter_candidate"],
                effectiveness=effectiveness_a,
                unsupported_actions=own_warnings,
            ),
            opponent=SideResult(
                before=before_opponent,
                after=after_opponent,
                triggered_abilities=[event["id"] for event in opponent_events if event["type"] == "ability_candidate"],
                triggered_weather=[event["id"] for event in opponent_events if event["type"] == "weather_candidate"],
                triggered_counters=[event["id"] for event in opponent_events if event["type"] == "counter_candidate"],
                effectiveness=effectiveness_b,
                unsupported_actions=opponent_warnings,
            ),
            shared_before=shared_before,
            shared_after=shared_after,
            possible_branches=branches,
            observed_branch_id=None if len(branches) > 1 else (branches[0].branch_id if branches else None),
            events=events,
            warnings=built.warnings,
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
            current_a=request.own_team.active_index.or_default(0),
            current_b=request.opponent_team.active_index.or_default(0),
            turn=request.shared.turn.or_default(1),
            weather=request.shared.weather.value if request.shared.weather.known and request.shared.weather.exists else None,
            mp_a=int(request.shared.mp.get("own").or_default(4)),
            mp_b=int(request.shared.mp.get("opponent").or_default(4)),
        )
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
                if raw_marks.known and raw_marks.exists and isinstance(raw_marks.value, dict):
                    marks.update({str(key): float(value) for key, value in raw_marks.value.items()})
        return _LegacyBuild(state, own_names, opponent_names, warnings, unknowns)

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
        if side == "a":
            state.devotion_a = legacy_known
            state.specified_devotion_a = legacy_specified
            state.random_devotion_draws_a = draws if not random_counts.known else 0
            state.random_devotion_counts_a = legacy_random if random_counts.known and random_counts.exists else {}
        else:
            state.devotion_b = legacy_known
            state.specified_devotion_b = legacy_specified
            state.random_devotion_draws_b = draws if not random_counts.known else 0
            state.random_devotion_counts_b = legacy_random if random_counts.known and random_counts.exists else {}

    def _creature_to_legacy(self, item: CreatureInput, fallback: str, warnings: list[str], unknowns: list[str]) -> Pokemon:
        name = item.resolved_name(fallback)
        stats = item.base.stats.value if item.base.stats.known and item.base.stats.exists else None
        if not stats:
            db_record = None
            try:
                db_record = get_pokemon(name)
            except Exception:
                db_record = None
            if db_record:
                stats = calc_combat_stats(
                    db_record["生命种族值"], db_record["物攻种族值"], db_record["魔攻种族值"],
                    db_record["物防种族值"], db_record["魔防种族值"], db_record["速度种族值"],
                    nature_name=item.base.nature.or_default("坦率"),
                )
            else:
                stats = {"hp": 100, "atk": 100, "def": 100, "spatk": 100, "spdef": 100, "speed": 100}
                warnings.append(f"{name}: 未找到六维数据，使用中性占位值")
        type_value = item.base.attributes.or_default(["普通"])
        pokemon_type = TYPE_MAP.get(type_value[0] if type_value else "普通", Type.NORMAL)
        ability_name = item.ability.name.or_default("")
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
            skill = get_skill(skill_name)
            skill.skill_id = skill_id or skill.name
            if slot:
                if slot.current_energy_cost.known and slot.current_energy_cost.exists:
                    skill.energy_cost = int(slot.current_energy_cost.value)
                if slot.current_power.known and slot.current_power.exists:
                    skill.power = int(slot.current_power.value)
                skill.use_count = int(slot.use_count.or_default(0))
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
            ability=ability_name,
            skills=skills,
            current_hp=current_hp,
            energy=energy,
            entry_count=int(item.entry_count.or_default(0)),
            fatigue_turns=int(state.fatigue_turns.or_default(0)),
            nature=item.base.nature.or_default("坦率"),
        )
        for direction, modifiers in (("up", state.buffs), ("down", state.debuffs)):
            for stat, value in modifiers.or_default({}).items():
                if stat in {"atk", "def", "spatk", "spdef", "speed"}:
                    setattr(pokemon, f"{stat}_{direction}", max(0.0, float(value)))
        status_fields = {
            "poison": "poison_stacks", "burn": "burn_stacks", "freeze": "freeze_stacks",
            "frostbite_damage": "frostbite_damage", "leech": "leech_stacks",
            "meteor": "meteor_stacks", "cute": "cute_stacks", "combo": "hit_count_mod",
        }
        for key, value in item.metadata.get("status_stacks", {}).items():
            if key in status_fields:
                setattr(pokemon, status_fields[key], max(0, int(value)))
        pokemon.ability_effects = [
            effect
            for name in dict.fromkeys(ability_names)
            for effect in load_ability_effects(name)
        ]
        pokemon.ability_state["lab_metadata"] = {
            "creature_id": item.creature_id.value if item.creature_id.known else None,
            "evolution_stage": item.evolution_stage.value if item.evolution_stage.known else None,
            "bossified": item.bossified.value if item.bossified.known else None,
            "bloodline_attributes": item.base.bloodline_attributes.value if item.base.bloodline_attributes.known else None,
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
            return (int(action.skill_slot),)
        for index, skill in enumerate(current.skills):
            if skill.name == action.skill_name or getattr(skill, "skill_id", "") == action.skill_id:
                return (index,)
        raise ValueError(f"{team} 当前精灵没有技能: {action.skill_name or action.skill_id}")

    def _load_skill_descriptions(self) -> None:
        path = self.data_dir / "skills_all.csv"
        if not path.exists():
            return
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("技能名") or "").strip()
                self._skill_descriptions[name] = (row.get("效果描述") or "").strip()

    def _possible_branches(self, request: BattleRequest, state: BattleState) -> list[ResolutionBranch]:
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
            if skill_name:
                description = self._skill_descriptions.get(skill_name, "")
                parsed_rules.append(self._skill_parser.parse(skill_name, description))
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
        multiplier = get_type_effectiveness(skill.skill_type, defender.pokemon_type)
        return [{
            "role": "dealt",
            "attacker": attacker.name,
            "defender": defender.name,
            "skill_id": getattr(skill, "skill_id", "") or skill.name,
            "skill_name": skill.name,
            "skill_type": skill.skill_type.value,
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

    def _snapshot_side(self, state: BattleState, team: str, source: TeamInput, names: list[str]) -> dict[str, Any]:
        team_list = state.team_a if team == "a" else state.team_b
        active_index = state.current_a if team == "a" else state.current_b
        marks = state.marks_a if team == "a" else state.marks_b
        return {
            "team_name": source.team_name,
            "active_index": active_index,
            "team_marks": dict(marks),
            "devotion": self._snapshot_devotion(state, source, team),
            "creatures": [
                {
                    "index": index,
                    "name": names[index] if index < len(names) else pokemon.name,
                    "hp": pokemon.current_hp,
                    "max_hp": pokemon.hp,
                    "energy": pokemon.energy,
                    "fainted": pokemon.is_fainted,
                    "entry_count": getattr(pokemon, "entry_count", 0),
                    "fatigue_turns": getattr(pokemon, "fatigue_turns", 0),
                    "ability": pokemon.ability,
                    "stats": {
                        "atk": pokemon.attack, "def": pokemon.defense,
                        "spatk": pokemon.sp_attack, "spdef": pokemon.sp_defense,
                        "speed": pokemon.speed,
                    },
                    "modifiers": {
                        "atk_up": pokemon.atk_up, "atk_down": pokemon.atk_down,
                        "def_up": pokemon.def_up, "def_down": pokemon.def_down,
                        "spatk_up": pokemon.spatk_up, "spatk_down": pokemon.spatk_down,
                        "spdef_up": pokemon.spdef_up, "spdef_down": pokemon.spdef_down,
                        "speed_up": pokemon.speed_up, "speed_down": pokemon.speed_down,
                    },
                    "statuses": {
                        "poison": pokemon.poison_stacks,
                        "burn": pokemon.burn_stacks,
                        "freeze": pokemon.freeze_stacks,
                        "frostbite_damage": pokemon.frostbite_damage,
                        "leech": pokemon.leech_stacks,
                        "meteor": pokemon.meteor_stacks,
                        "cute": pokemon.cute_stacks,
                        "combo": pokemon.hit_count_mod,
                    },
                    "skills": [
                        {
                            "skill_id": getattr(skill, "skill_id", skill.name),
                            "name": skill.name,
                            "current_energy_cost": skill.energy_cost,
                            "current_power": skill.power,
                            "use_count": getattr(skill, "use_count", 0),
                        }
                        for skill in pokemon.skills
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
