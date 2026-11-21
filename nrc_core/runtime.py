"""多回合战斗运行接口，负责状态推进、决策与快照。"""

from __future__ import annotations

import base64
import copy
import pickle
import random
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import (
    CoreBackend,
    CoreManifest,
    Decision,
    LegalAction,
    Observation,
    Transition,
)

from nrc_core.battle import (
    _apply_mark_on_enter,
    _apply_moisture_mark,
    _apply_turn_start_ability_logic,
    _trigger_battle_start_effects,
    check_outcome,
    check_winner,
)
from nrc_core.effect_models import Timing
from nrc_core.engine import EffectExecutor
from nrc_core.catalog import CoreCatalog
from nrc_core.models import BattleState, Pokemon
from nrc_core.rng import decision_rng, derive_subseed, rng_scope

from .codec import side_turn_from_dict
from .core import simulate_turn, skill_energy_cost, _turn_start_skill_display
from .rules_support import BattleRulesSupport


class UnsupportedMechanicError(ValueError):
    """Raised when a setup would require an unimplemented rule mechanism."""


class VersionMismatchError(ValueError):
    """Raised when a snapshot belongs to a different core contract."""


@dataclass
class BattleSession:
    """保存一次对战的完整状态与当前决策阶段。"""

    battle: BattleState
    manifest: CoreManifest
    decision_index: int = 0
    phase: str = "turn_choice"
    players: tuple[int, ...] = (0, 1)
    terminated: bool = False
    winner: int | None = None
    outcome: str | None = None
    seed: int = 0
    events: list[dict[str, Any]] | None = None


_RNG_LOCK = threading.RLock()


@contextmanager
def _isolated_rng(seed: int):
    """Run the legacy engine from a deterministic call-local RNG."""
    with _RNG_LOCK:
        with rng_scope(random.Random(int(seed))):
            yield


@contextmanager
def _decision_rng_scope(
    state: BattleSession,
    phase: str,
    side: str | int,
    *,
    decision_index: int | None = None,
):
    """按对局根 seed 和决策上下文建立稳定的随机作用域。"""
    index = state.decision_index if decision_index is None else decision_index
    with rng_scope(decision_rng(state.seed, index, phase, side)):
        yield


def _manifest(environment: str) -> CoreManifest:
    return CoreManifest("1", "injected", "injected", "1", "1", environment)


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
        "outcome": value.outcome,
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
        "electric_stacks": pokemon.electric_stacks,
        "cute_stacks": pokemon.cute_stacks,
        "entry_count": pokemon.entry_count,
    }
    if private:
        boost_fields = {
            "攻击提升": pokemon.atk_up, "攻击降低": pokemon.atk_down,
            "物防提升": pokemon.def_up, "物防降低": pokemon.def_down,
            "魔攻提升": pokemon.spatk_up, "魔攻降低": pokemon.spatk_down,
            "魔防提升": pokemon.spdef_up, "魔防降低": pokemon.spdef_down,
            "速度提升": pokemon.speed_up, "速度降低": pokemon.speed_down,
        }
        result.update({
            "ability": pokemon.ability,
            "skills": [_skill_json(skill, slot) for slot, skill in enumerate(pokemon.skills)],
            "boosts": {name: value for name, value in boost_fields.items() if value},
            "debuffs": BattleRulesSupport._snapshot_layers(pokemon, "down"),
            "statuses": BattleRulesSupport._snapshot_statuses(pokemon),
            "ability_states": BattleRulesSupport._snapshot_ability_states(pokemon),
            "conditions": {
                "poison": pokemon.poison_stacks,
                "burn": pokemon.burn_stacks,
                "freeze": pokemon.freeze_stacks,
                "leech": pokemon.leech_stacks,
                "electric": pokemon.electric_stacks,
                "meteor": pokemon.meteor_stacks,
                "cute": pokemon.cute_stacks,
            },
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
                value = state.sandstorm_original_costs.get(skill.skill_instance_id)
                if value is not None:
                    result.append((side, index, slot, int(value)))
    return result


def _restore_weather_backups(state: BattleState, values: list[tuple[str, int, int, int]]) -> None:
    state.sandstorm_original_costs.clear()
    for side, index, slot, value in values:
        team = state.team_a if side == "a" else state.team_b
        if 0 <= index < len(team) and 0 <= slot < len(team[index].skills):
            state.sandstorm_original_costs[team[index].skills[slot].skill_instance_id] = value


class BattleRuntime:
    """使用上层注入的规则目录推进完整对战。"""

    def __init__(self, *, catalog: CoreCatalog, environment: str = "nrc"):
        """绑定已经解析的规则目录，不读取数据库。"""
        if environment not in {"nrc", "test"}:
            raise ValueError("environment must be 'nrc' or 'test'")
        self.catalog = catalog
        self._manifest = _manifest(environment)
        self._simulator = BattleRulesSupport(catalog=self.catalog)

    @property
    def manifest(self) -> CoreManifest:
        return self._manifest

    def new_game(self, battle: BattleState, seed: int) -> BattleSession:
        """接收平台已解析的全知状态，创建独立对战会话。"""
        if not isinstance(battle, BattleState):
            raise TypeError("new_game requires a resolved BattleState")
        if not battle.team_a or not battle.team_b:
            raise ValueError("both teams must contain at least one creature")
        for team, active in ((battle.team_a, battle.current_a), (battle.team_b, battle.current_b)):
            if not 0 <= active < len(team):
                raise ValueError("active index is out of range")
            if any(not pokemon.skills for pokemon in team):
                raise ValueError("every creature must contain resolved skills")
        backups = _weather_backups(battle)
        # 规则目录是只读依赖，平台目录可能持有带锁的缓存。
        resolved = copy.deepcopy(battle, {id(battle.catalog): battle.catalog})
        _restore_weather_backups(resolved, backups)
        resolved.catalog = self.catalog
        state = BattleSession(resolved, self.manifest, seed=int(seed), events=[])
        self._prepare_decision(state, settle_start=True)
        return state

    def clone(self, state: object) -> BattleSession:
        """复制战斗会话并复用只读规则目录。"""
        current = self._check_state(state)
        backups = _weather_backups(current.battle)
        catalog = current.battle.catalog
        cloned = copy.deepcopy(current, {id(catalog): catalog})
        _restore_weather_backups(cloned.battle, backups)
        return cloned

    def _check_state(self, state: object) -> BattleSession:
        if not isinstance(state, BattleSession):
            raise TypeError("state is not an NRC BattleSession")
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

    def _prepare_decision(self, state: BattleSession, *, settle_start: bool = False) -> None:
        battle = state.battle
        if battle.turn_report:
            state.events.extend(battle.turn_report)
            battle.turn_report = []
        outcome = check_outcome(battle)
        if outcome:
            state.terminated = True
            state.outcome = outcome
            state.winner = 0 if outcome == "a_win" else 1 if outcome == "b_win" else None
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
            with _decision_rng_scope(state, "battle_start", "shared"):
                _trigger_battle_start_effects(battle)
            with _decision_rng_scope(state, "turn_start", "shared"):
                _apply_turn_start_ability_logic(battle)
                _apply_moisture_mark(battle)
            battle.turn_start_prepared = True
            # 入场/回合开始效果可能立即耗尽 MP 或令双方全队力竭，
            # 必须在返回可行动阶段前再次锁定终局。
            outcome = check_outcome(battle)
            if outcome:
                state.terminated = True
                state.outcome = outcome
                state.winner = 0 if outcome == "a_win" else 1 if outcome == "b_win" else None
                state.phase = "terminal"
                state.players = ()
                if battle.turn_report:
                    state.events.extend(battle.turn_report)
                    battle.turn_report = []
                return
        if battle.turn_report:
            state.events.extend(battle.turn_report)
            battle.turn_report = []

    def decision(self, state: object) -> Decision:
        current = self._check_state(state)
        return Decision(
            current.decision_index,
            current.battle.turn,
            current.phase,
            current.players,
            current.terminated,
            current.winner,
            current.outcome,
        )

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
        enemy_team = current.battle.team_b if player == 0 else current.battle.team_a
        enemy_index = current.battle.current_b if player == 0 else current.battle.current_a
        for index, skill in enumerate(active.skills):
            repetitions = max(1, int(getattr(skill, "use_count", 1) or 1))
            if active.ability_state.get("first_action_bonus"):
                repetitions += 1
            if active.energy < skill_energy_cost(active, skill, enemy_team[enemy_index]) * repetitions or active.get_skill_cooldown(index) > 0:
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

    def _with_resonance_actions(self, state: BattleSession, player: int, base: list[LegalAction]) -> tuple[LegalAction, ...]:
        team, active_index, side = self._team(state.battle, player)
        active = team[active_index]
        carried = state.battle.resonance_magic_a if side == "a" else state.battle.resonance_magic_b
        resonance_options = (carried,) if carried else ("willpower", "boss", "solar_heal")
        result = list(base)
        for action in base:
            primary = action.payload.get("primary", {})
            kind = primary.get("kind")
            if kind not in {"skill", "charge"}:
                continue
            for resonance in resonance_options:
                if resonance == "willpower":
                    uses = state.battle.resonance_uses_a if side == "a" else state.battle.resonance_uses_b
                    cooldown = state.battle.resonance_cooldown_a if side == "a" else state.battle.resonance_cooldown_b
                    if uses >= 2 or cooldown > 0 or active.energy < 2 or kind != "skill" or int(primary.get("skill_slot", -1)) != 0 or self._simulator._bloodline_type(active) is None:
                        continue
                elif resonance == "boss":
                    used = state.battle.resonance_evolution_used_a if side == "a" else state.battle.resonance_evolution_used_b
                    if used or not self._simulator._is_boss_bloodline(active):
                        continue
                elif resonance == "solar_heal":
                    used = state.battle.resonance_solar_heal_used_a if side == "a" else state.battle.resonance_solar_heal_used_b
                    if used:
                        continue
                payload = copy.deepcopy(action.payload)
                payload["items"] = [{"kind": "item", "item_kind": resonance, "item_payload": {}}]
                result.append(LegalAction(f"{action.key}|resonance={resonance}", payload))
        return tuple(result)

    def display(self, state: object, player: int) -> dict[str, Any]:
        """在副本上计算当前玩家技能面板，避免预览污染真实状态。"""
        snapshot = self.clone(state)
        _, _, side = self._team(snapshot.battle, player)
        return _turn_start_skill_display(snapshot.battle, side)

    def preview_damage(self, state: object, player: int, skill_slot: int) -> dict[str, Any]:
        """返回指定技能的当前伤害预览；不推进对战或推测隐藏状态。"""
        skills = self.display(state, player)["skills"]
        if not 0 <= skill_slot < len(skills):
            raise ValueError("skill_slot is out of range")
        return dict(skills[skill_slot])

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

    def _replacement(
        self,
        state: BattleSession,
        actions: Mapping[int, str],
        *,
        decision_index: int | None = None,
    ) -> None:
        for player in state.players:
            team, current_index, side = self._team(state.battle, player)
            with _decision_rng_scope(state, "replacement", side, decision_index=decision_index):
                legal = {item.key: item for item in self.legal_actions(state, player)}
                payload = legal[actions[player]].payload["primary"]
                chosen = int(payload["switch_index"])
                if chosen == current_index or team[chosen].is_fainted:
                    raise ValueError("illegal replacement target")
                if side == "a":
                    state.battle.current_a = chosen
                else:
                    state.battle.current_b = chosen
                pokemon = team[chosen]
                pokemon.entry_count += 1
                pokemon.ability_state["_burst_pending"] = True
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
        # ``seed`` 保留为兼容参数；对局随机性始终从新局 root seed 派生。
        int(seed)
        decision_index = current.decision_index
        next_state.decision_index += 1
        next_state.events = []
        if current.phase == "replacement":
            self._replacement(next_state, actions, decision_index=decision_index)
            self._prepare_decision(next_state, settle_start=True)
        else:
            payloads = {player: side_turn_from_dict(legal_by_player[player][actions[player]].payload) for player in current.players}
            before_state = self._report_state(next_state.battle)
            cleanups = []
            for player, side in ((0, "a"), (1, "b")):
                if player not in payloads:
                    continue
                items = payloads[player].items
                if not items:
                    continue
                field = "resonance_magic_a" if side == "a" else "resonance_magic_b"
                if getattr(next_state.battle, field) is None:
                    setattr(next_state.battle, field, items[0].item_kind.value)
            cleanups.extend(self._simulator._apply_resonance_items(
                next_state.battle, "a", payloads[0].items, next_state.battle.resonance_magic_a,
            ))
            cleanups.extend(self._simulator._apply_resonance_items(
                next_state.battle, "b", payloads[1].items, next_state.battle.resonance_magic_b,
            ))
            try:
                legacy_a = self._simulator._to_legacy_action(payloads[0].primary, next_state.battle, "a")
                legacy_b = self._simulator._to_legacy_action(payloads[1].primary, next_state.battle, "b")
                turn_seed = derive_subseed(current.seed, decision_index, "turn", "shared")
                turn_result = simulate_turn(next_state.battle, legacy_a, legacy_b, seed=turn_seed, clone=False)
            finally:
                self._simulator._restore_resonance_items(cleanups)
            next_state.events.extend(turn_result.report)
            after_state = self._report_state(next_state.battle)
            state_changes = self._simulator._state_change_events(before_state["a"], after_state["a"], "a")
            state_changes.extend(self._simulator._state_change_events(before_state["b"], after_state["b"], "b"))
            next_state.events.extend(state_changes)
            next_state.events.append({"type": "display_power", "value": turn_result.display_power})
            outcome = check_outcome(next_state.battle)
            if outcome:
                next_state.terminated = True
                next_state.outcome = outcome
                next_state.winner = 0 if outcome == "a_win" else 1 if outcome == "b_win" else None
                next_state.phase = "terminal"
                next_state.players = ()
            else:
                self._prepare_decision(next_state, settle_start=True)
        rewards = {0: 0.0, 1: 0.0}
        if next_state.terminated and next_state.winner is not None:
            rewards[next_state.winner] = 1.0
            rewards[1 - next_state.winner] = -1.0
        observations = {player: self.observe(next_state, player) for player in (0, 1)}
        return Transition(
            next_state,
            observations,
            rewards,
            next_state.terminated,
            next_state.winner,
            tuple(next_state.events or ()),
            next_state.outcome,
        )

    def _report_state(self, state: BattleState) -> dict[str, dict[str, Any]]:
        result = {}
        for team, creatures in (("a", state.team_a), ("b", state.team_b)):
            result[team] = {"creatures": []}
            for pokemon in creatures:
                result[team]["creatures"].append({
                    "name": pokemon.name,
                    "hp": pokemon.current_hp,
                    "energy": pokemon.energy,
                    "status": _status_name(pokemon.status),
                    "fainted": pokemon.is_fainted,
                    "statuses": self._simulator._snapshot_statuses(pokemon),
                    "buffs": self._simulator._snapshot_layers(pokemon, "up"),
                    "debuffs": self._simulator._snapshot_layers(pokemon, "down"),
                    "ability_states": self._simulator._snapshot_ability_states(pokemon),
                    "modifiers": dict(pokemon.ability_state.get("public_skill_modifiers", {})),
                    "_public_skill_modifier_deltas": [dict(item) for item in pokemon.ability_state.get("_public_skill_modifier_deltas", [])],
                    "skills": [
                        {"name": skill.name, "current_energy_cost": skill.energy_cost,
                         "current_power": skill.power, "current_hit_count": skill.hit_count,
                         "current_priority_mod": skill.priority_mod}
                        for skill in pokemon.skills
                    ],
                })
        return result

    def export_state(self, state: object) -> dict[str, Any]:
        current = self._check_state(state)
        snapshot = self.clone(current)
        backups = _weather_backups(snapshot.battle)
        snapshot.battle.sandstorm_original_costs.clear()
        payload = base64.b64encode(pickle.dumps(snapshot, protocol=5)).decode("ascii")
        return {
            "format": "nrc_core.runtime.pickle.v2",
            "manifest": _manifest_json(self.manifest),
            "weather_backups": backups,
            "payload": payload,
        }

    def import_state(self, snapshot: Mapping[str, Any]) -> BattleSession:
        if snapshot.get("format") != "nrc_core.runtime.pickle.v2":
            raise VersionMismatchError("unsupported state snapshot format; nrc_core.runtime.pickle.v2 required")
        if dict(snapshot.get("manifest") or {}) != _manifest_json(self.manifest):
            raise VersionMismatchError("snapshot manifest does not match backend manifest")
        try:
            state = pickle.loads(base64.b64decode(str(snapshot["payload"])))
        except Exception as exc:
            raise ValueError("invalid state snapshot payload") from exc
        current = self._check_state(state)
        _restore_weather_backups(current.battle, [tuple(item) for item in snapshot.get("weather_backups", [])])
        return current


def create_runtime(*, catalog: CoreCatalog, environment: str = "nrc") -> BattleRuntime:
    """通过明确注入的规则目录创建战斗运行器。"""
    return BattleRuntime(environment=environment, catalog=catalog)


__all__ = ["CoreBackend", "CoreManifest", "Decision", "LegalAction", "Observation", "Transition", "BattleRuntime", "BattleSession", "UnsupportedMechanicError", "VersionMismatchError", "create_runtime"]

