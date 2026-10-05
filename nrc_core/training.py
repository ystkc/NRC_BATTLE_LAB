"""Training-facing stateful adapter for the NRC battle core.

The adapter deliberately exposes only exact action keys.  It does not provide
name matching, placeholder creatures, automatic replacement choices, or a toy
fallback when the requested rule is not implemented.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import pickle
import random
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from nrc_ai.contracts import (
    CoreManifest,
    Decision,
    LegalAction,
    Observation,
    Transition,
)

from src.battle import (
    _apply_mark_on_enter,
    _apply_moisture_mark,
    _apply_turn_start_ability_logic,
    _trigger_battle_start_effects,
    check_winner,
)
from src.effect_models import Timing
from src.engine._monolith import EffectExecutor
from src.models import BattleState, Pokemon
from src.pokemon_db import get_pokemon
from src.rng import rng_scope
from src.skill_db import get_all_skill_names, get_skill, load_ability_effects

from .codec import battle_request_from_dict, side_turn_from_dict
from .core import simulate_turn
from .schema import BattleRequest
from .simulator import BattleSimulator


class UnsupportedMechanicError(ValueError):
    """Raised when a setup would require an unimplemented rule mechanism."""


class VersionMismatchError(ValueError):
    """Raised when a snapshot belongs to a different core contract."""


class CoreBackend(Protocol):
    @property
    def manifest(self) -> CoreManifest: ...

    def new_game(self, setup: Mapping[str, Any], seed: int) -> object: ...
    def clone(self, state: object) -> object: ...
    def decision(self, state: object) -> Decision: ...
    def observe(self, state: object, player: int) -> Observation: ...
    def legal_actions(self, state: object, player: int) -> tuple[LegalAction, ...]: ...
    def advance(self, state: object, actions: Mapping[int, str], seed: int) -> Transition: ...
    def export_state(self, state: object) -> dict[str, Any]: ...
    def import_state(self, snapshot: Mapping[str, Any]) -> object: ...


@dataclass
class TrainingState:
    battle: BattleState
    manifest: CoreManifest
    decision_index: int = 0
    phase: str = "turn_choice"
    players: tuple[int, ...] = (0, 1)
    terminated: bool = False
    winner: int | None = None
    seed: int = 0
    events: list[dict[str, Any]] | None = None


_RNG_LOCK = threading.RLock()


@contextmanager
def _isolated_rng(seed: int):
    """Run the legacy engine from a deterministic call-local RNG."""
    with _RNG_LOCK:
        with rng_scope(random.Random(int(seed))):
            yield


def _hash_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _manifest(project_dir: Path, environment: str, data_dir: Path | None = None) -> CoreManifest:
    data_dir = data_dir or (project_dir / "data")
    rules = _hash_files([
        data_dir / "属性克制表.md",
        data_dir / "回合顺序.md",
        data_dir / "共鸣魔法.md",
        data_dir / "伤害数值计算.md",
        data_dir / "属性数值计算.md",
        data_dir / "wiki" / "game_descriptions.csv",
        project_dir / "src" / "battle.py",
        project_dir / "src" / "engine" / "_monolith.py",
        project_dir / "src" / "models.py",
        project_dir / "src" / "skill_db.py",
        project_dir / "src" / "effect_data.py",
        project_dir / "src" / "rng.py",
    ])
    catalog = _hash_files([data_dir / "nrc_wiki.db"])
    return CoreManifest("1", rules, catalog, "1", "1", environment)


def _manifest_json(value: CoreManifest) -> dict[str, str]:
    return {
        "protocol_version": value.protocol_version,
        "rules_version": value.rules_version,
        "catalog_version": value.catalog_version,
        "action_version": value.action_version,
        "observation_version": value.observation_version,
        "environment": value.environment,
    }


def _decision_json(value: Decision) -> dict[str, Any]:
    return {
        "index": value.index,
        "turn": value.turn,
        "phase": value.phase,
        "players": list(value.players),
        "terminated": value.terminated,
        "winner": value.winner,
    }


def _status_name(value: Any) -> str:
    return str(getattr(value, "value", value))


def _skill_json(skill: Any, index: int, private: bool = True) -> dict[str, Any]:
    result = {
        "index": index,
        "skill_id": getattr(skill, "skill_id", skill.name),
        "name": skill.name,
        "energy_cost": skill.energy_cost,
        "power": skill.power,
    }
    if private:
        result.update({
            "category": _status_name(skill.category),
            "type": _status_name(skill.skill_type),
            "hit_count": skill.hit_count,
        })
    return result


def _pokemon_json(pokemon: Pokemon, index: int, active: bool, private: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "index": index,
        "active": active,
        "name": pokemon.name,
        "types": [_status_name(value) for value in pokemon.pokemon_types],
        "hp": pokemon.current_hp,
        "max_hp": pokemon.hp,
        "energy": pokemon.energy,
        "status": _status_name(pokemon.status),
        "fainted": pokemon.is_fainted,
        "fatigue_turns": pokemon.fatigue_turns,
        "freeze_stacks": pokemon.freeze_stacks,
        "frostbite_damage": pokemon.frostbite_damage,
        "electric_stacks": pokemon.electric_stacks,
        "cute_stacks": pokemon.cute_stacks,
        "entry_count": pokemon.entry_count,
    }
    if private:
        result.update({
            "ability": pokemon.ability,
            "skills": [_skill_json(skill, slot) for slot, skill in enumerate(pokemon.skills)],
            "stats": {
                "hp": pokemon.hp,
                "attack": pokemon.attack,
                "defense": pokemon.defense,
                "sp_attack": pokemon.sp_attack,
                "sp_defense": pokemon.sp_defense,
                "speed": pokemon.speed,
            },
            "cooldowns": dict(pokemon.cooldowns),
            "ability_state": copy.deepcopy(pokemon.ability_state),
        })
    return result


def _weather_backups(state: BattleState) -> list[tuple[str, int, int, int]]:
    result = []
    for side, team in (("a", state.team_a), ("b", state.team_b)):
        for index, pokemon in enumerate(team):
            for slot, skill in enumerate(pokemon.skills):
                value = state.sandstorm_original_costs.get(id(skill))
                if value is not None:
                    result.append((side, index, slot, int(value)))
    return result


def _restore_weather_backups(state: BattleState, values: list[tuple[str, int, int, int]]) -> None:
    state.sandstorm_original_costs.clear()
    for side, index, slot, value in values:
        team = state.team_a if side == "a" else state.team_b
        if 0 <= index < len(team) and 0 <= slot < len(team[index].skills):
            state.sandstorm_original_costs[id(team[index].skills[slot])] = value


class NRCTrainingBackend:
    """Stateful adapter implementing the v1 training contract."""

    def __init__(self, *, environment: str = "nrc", data_dir: str | Path | None = None):
        if environment not in {"nrc", "test"}:
            raise ValueError("environment must be 'nrc' or 'test'")
        self.project_dir = Path(__file__).resolve().parents[1]
        self.data_dir = Path(data_dir) if data_dir else self.project_dir / "data"
        self._manifest = _manifest(self.project_dir, environment, self.data_dir)
        self._simulator = BattleSimulator(self.data_dir)
        self._skill_names: set[str] | None = None

    @property
    def manifest(self) -> CoreManifest:
        return self._manifest

    def _known_skill_names(self) -> set[str]:
        if self._skill_names is None:
            self._skill_names = set(get_all_skill_names())
        return self._skill_names

    def _validate_setup(self, request: BattleRequest) -> None:
        if not request.own_team.creatures or not request.opponent_team.creatures:
            raise ValueError("both teams must contain at least one creature")
        unsupported: list[str] = []
        for side, team in (("0", request.own_team), ("1", request.opponent_team)):
            resonance = self._simulator._canonical_resonance(team.resonance_magic.or_default(None))
            if resonance in {"flame_burst", "throttle"}:
                unsupported.append(f"player {side}: resonance {resonance}")
            elif resonance not in {None, "willpower", "boss", "solar_heal"}:
                unsupported.append(f"player {side}: unknown resonance {resonance}")
            active_index = int(team.active_index.or_default(0))
            if active_index < 0 or active_index >= len(team.creatures):
                raise ValueError(f"player {side} active_index is out of range")
            for index, creature in enumerate(team.creatures):
                name = creature.resolved_name(f"{side}_{index}")
                try:
                    db_record = get_pokemon(name)
                except Exception as exc:
                    raise ValueError(f"unknown creature {name!r}") from exc
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
                    if ability.split(":", 1)[0].split("：", 1)[0].strip() == "契约的形状":
                        ball = (creature.metadata or {}).get("gulu_ball")
                        if ball not in {"普通咕噜球", "高级咕噜球", "国王球", "美妙球", "好战球", "光合球", "网兜球", "暗星球", "调温球", "绝缘球", "淘沙球", "变幻球", "柔软咕噜球"}:
                            unsupported.append(f"{name}: contract mechanic requires valid gulu_ball")
                    if not load_ability_effects(ability):
                        unsupported.append(f"{name}: ability {ability}")
                if not creature.skills:
                    raise ValueError(f"{name} must provide all skill slots")
                for slot, skill in enumerate(creature.skills):
                    skill_name = skill.name.or_default(skill.skill_id.or_default(""))
                    if not skill_name or skill_name not in self._known_skill_names():
                        raise ValueError(f"unknown skill {skill_name!r} at {name}[{slot}]")
                    if skill_name == "愿力冲击":
                        unsupported.append(f"{name}[{slot}] 愿力冲击: resonance-only skill")
                    description = self._skill_description(skill_name)
                    parsed_skill = get_skill(skill_name)
                    if "选择" in description and len(getattr(parsed_skill, "choice_options", ())) != 2:
                        unsupported.append(f"{name}[{slot}] {skill_name}: choice skill must expose exactly two options")
                    if any(marker in description for marker in ("随机选择", "随机抽取")):
                        unsupported.append(f"{name}[{slot}] {skill_name}: random target/choice skill")
                for key in ("items", "contract", "random_skill"):
                    if (creature.metadata or {}).get(key):
                        unsupported.append(f"{name}: {key}")
        if unsupported:
            raise UnsupportedMechanicError("unsupported mechanics: " + "; ".join(unsupported))

    def _skill_description(self, name: str) -> str:
        database = self.data_dir / "nrc_wiki.db"
        with sqlite3.connect(database) as connection:
            row = connection.execute("SELECT description FROM skill_catalog WHERE name = ?", (name,)).fetchone()
        return (row[0] if row else "") or ""

    def new_game(self, setup: Mapping[str, Any], seed: int) -> TrainingState:
        raw = dict(setup)
        if "setup" in raw and isinstance(raw["setup"], Mapping):
            raw = dict(raw["setup"])
        request = battle_request_from_dict(raw)
        self._validate_setup(request)
        built = self._simulator._build_legacy(request)
        state = TrainingState(built.state, self.manifest, seed=int(seed), events=[])
        self._prepare_decision(state, settle_start=True)
        return state

    def clone(self, state: object) -> TrainingState:
        current = self._check_state(state)
        backups = _weather_backups(current.battle)
        cloned = copy.deepcopy(current)
        _restore_weather_backups(cloned.battle, backups)
        return cloned

    def _check_state(self, state: object) -> TrainingState:
        if not isinstance(state, TrainingState):
            raise TypeError("state is not an NRC TrainingState")
        if state.manifest != self.manifest:
            raise VersionMismatchError("state manifest does not match backend manifest")
        return state

    def _pending_players(self, battle: BattleState) -> tuple[int, ...]:
        pending = {0 if item.get("team") == "a" else 1 for item in battle.pending_switch_requests}
        if battle.team_a[battle.current_a].is_fainted and any(not item.is_fainted for item in battle.team_a):
            pending.add(0)
        if battle.team_b[battle.current_b].is_fainted and any(not item.is_fainted for item in battle.team_b):
            pending.add(1)
        return tuple(sorted(pending))

    def _prepare_decision(self, state: TrainingState, *, settle_start: bool = False) -> None:
        battle = state.battle
        winner = check_winner(battle)
        if winner:
            state.terminated = True
            state.winner = 0 if winner == "a" else 1
            state.phase = "terminal"
            state.players = ()
            return
        alive_a = any(not item.is_fainted for item in battle.team_a)
        alive_b = any(not item.is_fainted for item in battle.team_b)
        if not alive_a or not alive_b:
            state.terminated = True
            state.winner = 1 if alive_a and not alive_b else 0 if alive_b and not alive_a else None
            state.phase = "terminal"
            state.players = ()
            return
        pending = self._pending_players(battle)
        if pending:
            state.phase = "replacement"
            state.players = pending
            return
        state.phase = "turn_choice"
        state.players = (0, 1)
        if settle_start and not battle.turn_start_prepared:
            _trigger_battle_start_effects(battle)
            _apply_turn_start_ability_logic(battle)
            _apply_moisture_mark(battle)
            battle.turn_start_prepared = True

    def decision(self, state: object) -> Decision:
        current = self._check_state(state)
        return Decision(current.decision_index, current.battle.turn, current.phase, current.players, current.terminated, current.winner)

    def _team(self, battle: BattleState, player: int) -> tuple[list[Pokemon], int, str]:
        if player == 0:
            return battle.team_a, battle.current_a, "a"
        if player == 1:
            return battle.team_b, battle.current_b, "b"
        raise ValueError("player must be 0 or 1")

    def legal_actions(self, state: object, player: int) -> tuple[LegalAction, ...]:
        current = self._check_state(state)
        if current.terminated or player not in current.players:
            return ()
        team, active_index, _ = self._team(current.battle, player)
        active = team[active_index]
        result: list[LegalAction] = []
        if current.phase == "replacement":
            for index, pokemon in enumerate(team):
                if index == active_index or pokemon.is_fainted:
                    continue
                key = f"switch:index={index}"
                result.append(LegalAction(key, {"primary": {"kind": "switch", "switch_index": index}, "items": []}))
            return tuple(result)
        if active.is_fainted:
            return ()
        for index, skill in enumerate(active.skills):
            repetitions = max(1, int(getattr(skill, "use_count", 1) or 1))
            if active.ability_state.get("first_action_bonus"):
                repetitions += 1
            if active.energy < skill.energy_cost * repetitions or active.cooldowns.get(index, 0) > 0:
                continue
            options = tuple(getattr(skill, "choice_options", ()))
            if len(options) == 2:
                for option_index, option in enumerate(options):
                    key = f"skill:slot={index}:choice={option_index}"
                    result.append(LegalAction(key, {"primary": {"kind": "skill", "skill_slot": index, "skill_id": skill.skill_id, "skill_name": skill.name, "choice": option}, "items": []}))
            else:
                key = f"skill:slot={index}"
                result.append(LegalAction(key, {"primary": {"kind": "skill", "skill_slot": index, "skill_id": skill.skill_id, "skill_name": skill.name}, "items": []}))
        result.append(LegalAction("charge", {"primary": {"kind": "charge"}, "items": []}))
        for index, pokemon in enumerate(team):
            if index == active_index or pokemon.is_fainted:
                continue
            key = f"switch:index={index}"
            result.append(LegalAction(key, {"primary": {"kind": "switch", "switch_index": index}, "items": []}))
        return self._with_resonance_actions(current, player, result)

    def _with_resonance_actions(self, state: TrainingState, player: int, base: list[LegalAction]) -> tuple[LegalAction, ...]:
        team, active_index, side = self._team(state.battle, player)
        active = team[active_index]
        carried = state.battle.resonance_magic_a if side == "a" else state.battle.resonance_magic_b
        if not carried:
            return tuple(base)
        result = list(base)
        for action in base:
            primary = action.payload.get("primary", {})
            kind = primary.get("kind")
            if kind not in {"skill", "charge"}:
                continue
            if carried == "willpower":
                uses = state.battle.resonance_uses_a if side == "a" else state.battle.resonance_uses_b
                cooldown = state.battle.resonance_cooldown_a if side == "a" else state.battle.resonance_cooldown_b
                if uses >= 2 or cooldown > 0 or active.energy < 2:
                    continue
                if kind != "skill" or int(primary.get("skill_slot", -1)) != 0:
                    continue
                if self._simulator._bloodline_type(active) is None:
                    continue
            elif carried == "boss":
                used = state.battle.resonance_evolution_used_a if side == "a" else state.battle.resonance_evolution_used_b
                bloodline = active.ability_state.get("lab_metadata", {}).get("bloodline_attributes") or []
                if used or not any("首领" in str(value) for value in (bloodline if isinstance(bloodline, list) else [bloodline])):
                    continue
            elif carried == "solar_heal":
                used = state.battle.resonance_solar_heal_used_a if side == "a" else state.battle.resonance_solar_heal_used_b
                if used:
                    continue
            else:
                continue
            payload = copy.deepcopy(action.payload)
            payload["items"] = [{"kind": "item", "item_kind": carried, "item_payload": {}}]
            result.append(LegalAction(f"{action.key}|resonance={carried}", payload))
        return tuple(result)

    def observe(self, state: object, player: int) -> Observation:
        current = self._check_state(state)
        if player not in (0, 1):
            raise ValueError("player must be 0 or 1")
        own_team, own_index, _ = self._team(current.battle, player)
        other_team, other_index, _ = self._team(current.battle, 1 - player)
        data = {
            "manifest": _manifest_json(self.manifest),
            "decision": _decision_json(self.decision(current)),
            "shared": {
                "turn": current.battle.turn,
                "weather": current.battle.weather,
                "weather_turns": current.battle.weather_turns,
                "mp": {"own": current.battle.mp_a if player == 0 else current.battle.mp_b, "opponent": current.battle.mp_b if player == 0 else current.battle.mp_a},
                "marks": copy.deepcopy(current.battle.marks_a if player == 0 else current.battle.marks_b),
            },
            "own_team": [_pokemon_json(item, index, index == own_index, True) for index, item in enumerate(own_team)],
            "opponent_team": [_pokemon_json(item, index, index == other_index, False) for index, item in enumerate(other_team)],
            "legal_actions": [item.key for item in self.legal_actions(current, player)],
        }
        return Observation(player, current.decision_index, current.battle.turn, current.phase, data)

    def _replacement(self, state: TrainingState, actions: Mapping[int, str]) -> None:
        for player in state.players:
            legal = {item.key: item for item in self.legal_actions(state, player)}
            payload = legal[actions[player]].payload["primary"]
            team, current_index, side = self._team(state.battle, player)
            chosen = int(payload["switch_index"])
            if chosen == current_index or team[chosen].is_fainted:
                raise ValueError("illegal replacement target")
            if side == "a":
                state.battle.current_a = chosen
            else:
                state.battle.current_b = chosen
            pokemon = team[chosen]
            pokemon.entry_count += 1
            _apply_mark_on_enter(state.battle, side, pokemon)
            enemy = state.battle.team_b[state.battle.current_b] if side == "a" else state.battle.team_a[state.battle.current_a]
            if pokemon.ability_effects:
                EffectExecutor.execute_ability(state.battle, pokemon, enemy, Timing.ON_ENTER, pokemon.ability_effects, side)
            state.battle.pending_switch_requests = [item for item in state.battle.pending_switch_requests if item.get("team") != side]

    def advance(self, state: object, actions: Mapping[int, str], seed: int) -> Transition:
        current = self._check_state(state)
        if current.terminated:
            raise ValueError("cannot advance a terminal state")
        expected = set(current.players)
        if set(actions) != expected:
            raise ValueError(f"actions must contain exactly players {sorted(expected)}")
        legal_by_player = {player: {item.key: item for item in self.legal_actions(current, player)} for player in current.players}
        for player in current.players:
            if actions[player] not in legal_by_player[player]:
                raise ValueError(f"illegal action {actions[player]!r} for player {player}")
        next_state = self.clone(current)
        next_state.seed = int(seed)
        next_state.decision_index += 1
        next_state.events = []
        if current.phase == "replacement":
            self._replacement(next_state, actions)
            self._prepare_decision(next_state, settle_start=True)
        else:
            payloads = {player: side_turn_from_dict(legal_by_player[player][actions[player]].payload) for player in current.players}
            cleanups = []
            cleanups.extend(self._simulator._apply_resonance_items(
                next_state.battle, "a", payloads[0].items, next_state.battle.resonance_magic_a,
            ))
            cleanups.extend(self._simulator._apply_resonance_items(
                next_state.battle, "b", payloads[1].items, next_state.battle.resonance_magic_b,
            ))
            try:
                legacy_a = self._simulator._to_legacy_action(payloads[0].primary, next_state.battle, "a")
                legacy_b = self._simulator._to_legacy_action(payloads[1].primary, next_state.battle, "b")
                turn_result = simulate_turn(next_state.battle, legacy_a, legacy_b, seed=seed, clone=False)
            finally:
                self._simulator._restore_resonance_items(cleanups)
            next_state.events.extend(turn_result.report)
            next_state.events.append({"type": "display_power", "value": turn_result.display_power})
            winner = turn_result.winner or check_winner(next_state.battle)
            if winner:
                next_state.terminated = True
                next_state.winner = 0 if winner == "a" else 1
                next_state.phase = "terminal"
                next_state.players = ()
            else:
                self._prepare_decision(next_state, settle_start=True)
        rewards = {0: 0.0, 1: 0.0}
        if next_state.terminated and next_state.winner is not None:
            rewards[next_state.winner] = 1.0
            rewards[1 - next_state.winner] = -1.0
        observations = {player: self.observe(next_state, player) for player in (0, 1)}
        return Transition(next_state, observations, rewards, next_state.terminated, next_state.winner, tuple(next_state.events or ()))

    def export_state(self, state: object) -> dict[str, Any]:
        current = self._check_state(state)
        snapshot = self.clone(current)
        backups = _weather_backups(snapshot.battle)
        snapshot.battle.sandstorm_original_costs.clear()
        payload = base64.b64encode(pickle.dumps(snapshot, protocol=5)).decode("ascii")
        return {"format": "nrc_core.training.pickle.v1", "manifest": _manifest_json(self.manifest), "weather_backups": backups, "payload": payload}

    def import_state(self, snapshot: Mapping[str, Any]) -> TrainingState:
        if snapshot.get("format") != "nrc_core.training.pickle.v1":
            raise ValueError("unsupported state snapshot format")
        if dict(snapshot.get("manifest") or {}) != _manifest_json(self.manifest):
            raise VersionMismatchError("snapshot manifest does not match backend manifest")
        try:
            state = pickle.loads(base64.b64decode(str(snapshot["payload"])))
        except Exception as exc:
            raise ValueError("invalid state snapshot payload") from exc
        current = self._check_state(state)
        _restore_weather_backups(current.battle, [tuple(item) for item in snapshot.get("weather_backups", [])])
        return current


def create_backend(*, environment: str = "nrc", data_dir: str | Path | None = None) -> NRCTrainingBackend:
    """Factory used by the nrc_ai backend probe."""
    return NRCTrainingBackend(environment=environment, data_dir=data_dir)


__all__ = ["CoreBackend", "CoreManifest", "Decision", "LegalAction", "Observation", "Transition", "NRCTrainingBackend", "TrainingState", "UnsupportedMechanicError", "VersionMismatchError", "create_backend"]
