"""Stateful public battle platform around the NRC single-turn core."""

from __future__ import annotations

import copy
import math
import random
import re
import uuid
import threading
from functools import wraps
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
import logging

from pypinyin import Style, lazy_pinyin

from nrc_core.contracts import CoreManifest, Decision, LegalAction, Observation, Transition
from nrc_core.battle import DamageCalculator
from nrc_core.models import SkillCategory, Type, get_type_effectiveness
from nrc_core.runtime import BattleRuntime, BattleSession

from .catalog import load_catalog
from .builder import BattleBuilder, BuildResult
from .input import merge_creature_spec
from .state import normalize_observation
from nrc_core.codec import creature_from_dict


DAMAGE_CATEGORIES = {SkillCategory.PHYSICAL, SkillCategory.MAGICAL}
RELATION_RANK = {"super_effective": 5, "effective": 4, "very_resistant": 3, "resistant": 2, "normal": 1}


class PlatformError(ValueError):
    """A structured error at the platform boundary."""

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}


class PlatformResult(dict[str, Any]):
    """Dict result that also supports attribute access in examples."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self))


@dataclass
class _ManagedBattle:
    battle_id: str
    mode: str
    seed: int
    manifest: CoreManifest
    own_roster: dict[str, Any] | None = None
    opponent_roster: dict[str, Any] | None = None
    episode: BattleSession | None = None
    pending: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    requests: dict[str, PlatformResult] = field(default_factory=dict)
    lock: Any = field(default_factory=threading.RLock, repr=False)
    revealed: dict[int, set[int]] = field(default_factory=lambda: {0: set(), 1: set()})

    @property
    def phase(self) -> str:
        """阶段从唯一核心状态读取。"""
        return self.episode.phase if self.episode else "setup"

    @property
    def decision_index(self) -> int:
        """当前决策序号。"""
        return self.episode.decision_index if self.episode else 0

    @property
    def terminal(self) -> bool:
        """终局由核心判定。"""
        return bool(self.episode and self.episode.terminated)

    @property
    def winner(self) -> int | None:
        """胜方由核心判定。"""
        return self.episode.winner if self.episode else None

    @property
    def outcome(self) -> str | None:
        """终局结果；平局也有明确的 draw 值。"""
        return self.episode.outcome if self.episode else None


class _Catalog:
    """All catalog lookup and user-input normalization lives in the platform."""

    def __init__(self, catalog):
        self.catalog = catalog

    @staticmethod
    def _base_name(name: str) -> str:
        return re.split(r"[\(\uff08]", str(name), maxsplit=1)[0].strip()

    @classmethod
    def _aliases(cls, name: str) -> set[str]:
        base = cls._base_name(name)
        return {
            str(name).casefold(),
            base.casefold(),
            "".join(lazy_pinyin(base)).casefold(),
            "".join(lazy_pinyin(base, style=Style.FIRST_LETTER)).casefold(),
        }

    def resolve_pokemon(self, value: Any) -> Mapping[str, Any] | None:
        text = str(value or "").strip()
        if not text:
            return None
        direct = self.catalog.get_pokemon(text)
        if direct:
            return direct
        raise PlatformError("invalid_roster", f"unknown creature {text!r}")

    def normalize_team(self, raw: Any, *, allow_unknown: bool) -> dict[str, Any]:
        if isinstance(raw, Mapping):
            team = copy.deepcopy(dict(raw))
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            team = {"creatures": copy.deepcopy(list(raw))}
        else:
            raise PlatformError("invalid_roster", "roster must be a mapping or creature sequence")
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(team.get("creatures") or []):
            creature = {"name": item} if isinstance(item, str) else copy.deepcopy(dict(item)) if isinstance(item, Mapping) else None
            if creature is None:
                raise PlatformError("invalid_roster", "creature must be a mapping or name", {"index": index})
            self._normalize_creature(creature, index, allow_unknown)
            normalized.append(creature)
        team["creatures"] = normalized
        team.setdefault("active_index", 0)
        return team

    def _normalize_creature(self, creature: dict[str, Any], index: int, allow_unknown: bool) -> None:
        creature.update(merge_creature_spec(creature))
        name = _known_value(creature.get("display_name")) or _known_value(creature.get("name"))
        if not name:
            if not allow_unknown:
                raise PlatformError("unknown_required_field", "creature name is required", {"index": index})
            return
        record = self.resolve_pokemon(name)
        if record is None:
            if not allow_unknown:
                raise PlatformError("invalid_roster", f"unknown creature {name!r}", {"index": index})
            return
        canonical_name = str(record.get("name") or name)
        creature["name"] = canonical_name
        ability_name = str(record.get("ability") or "")
        if ability_name and not self.catalog.get_ability_effects(ability_name):
            creature.setdefault("ability", {
                "name": {"known": True, "exists": True, "value": ""},
            })
        if not creature.get("skills"):
            creature["skills"] = [
                {"name": str(skill_name)}
                for skill_name in self.catalog.get_pokemon(canonical_name).get("skills", ())[:4]
            ]



def _serialized(method):
    """同局请求串行化，异常时恢复暂存与历史。"""
    @wraps(method)
    def call(self, battle_id, *args, **kwargs):
        battle = self._get_battle(battle_id)
        with battle.lock:
            # 展示查询只读；避免每个 API 都克隆整场核心状态，导致串行轮询秒级延迟。
            mutable = method.__name__ in {"set_roster", "submit_selection", "select_action", "reset_battle"}
            before = None
            if mutable:
                before = {key: copy.deepcopy(value) for key, value in vars(battle).items() if key not in {"lock", "episode"}}
                before["episode"] = self._backend.clone(battle.episode) if battle.episode else None
            try:
                return method(self, battle_id, *args, **kwargs)
            except Exception:
                if before is not None:
                    for key, value in before.items():
                        setattr(battle, key, value)
                raise
    return call


def _build_error(result: BuildResult) -> PlatformError:
    """将构建器诊断完整桥接到平台错误，避免丢失输入路径。"""
    diagnostics = result.diagnostics.to_json()
    first = (result.diagnostics.issues or result.diagnostics.warnings or [None])[0]
    if first is None:
        return PlatformError("build_failed", "battle state construction failed", {"diagnostics": diagnostics})
    details = {
        "path": first.path,
        "reason": first.reason,
        "issues": diagnostics.get("issues", []),
        "warnings": diagnostics.get("warnings", []),
        "diagnostics": diagnostics,
    }
    return PlatformError(first.code, first.reason, details)


class BattlePlatform:
    """持有双人对局，统一提交、历史和玩家视角。"""

    def __init__(self, *, environment: str = "nrc", data_dir: str | Path | None = None):
        catalog = load_catalog(data_dir)
        self._backend = BattleRuntime(environment=environment, catalog=catalog)
        self._catalog = _Catalog(catalog)
        self._builder = BattleBuilder(catalog=catalog)
        self._battles: dict[str, _ManagedBattle] = {}
        self.logger = logging.getLogger(__name__)

    @property
    def manifest(self) -> CoreManifest:
        return self._backend.manifest

    @_serialized
    def get_battle_status(self, battle_id: str) -> PlatformResult:
        """供房间编排读取唯一核心状态与提交进度。"""
        battle = self._get_battle(battle_id)
        return PlatformResult(battle_id=battle_id, turn=self._current_turn(battle),
                              phase=battle.phase, decision_index=battle.decision_index,
                              pending=list(battle.pending), terminal=battle.terminal,
                              winner=battle.winner, outcome=battle.outcome,
                              initialized=battle.episode is not None)

    def resolve_pokemon(self, value: Any) -> Mapping[str, Any] | None:
        """Resolve a canonical creature record or a pinyin alias."""
        return self._catalog.resolve_pokemon(value)

    def create_battle(self, *, mode: str, seed: int | None = None, rules_version: str | None = None) -> PlatformResult:
        if mode != "full":
            raise PlatformError("invalid_mode", "only two-player full mode is supported")
        if rules_version is not None and rules_version != self.manifest.rules_version:
            raise PlatformError("version_mismatch", "requested rules version does not match active backend")
        chosen_seed = int(seed if seed is not None else random.SystemRandom().randrange(2**32))
        battle_id = f"nrc-{uuid.uuid4().hex}"
        battle = _ManagedBattle(battle_id, mode, chosen_seed, self.manifest)
        self._battles[battle_id] = battle
        return PlatformResult(
            battle_id=battle_id,
            mode=mode,
            decision_index=0,
            turn=1,
            phase="setup",
            manifest=_manifest_dict(self.manifest),
        )

    @_serialized
    def set_roster(self, battle_id: str, side: str, roster: Any, *, request_id: str | None = None) -> PlatformResult:
        battle = self._get_battle(battle_id)
        self._ensure_mutable(battle)
        if side not in {"own", "opponent"}:
            raise PlatformError("invalid_side", "side must be 'own' or 'opponent'")
        if request_id:
            request_id = f"roster:{side}:{request_id}"
        if request_id and request_id in battle.requests:
            return battle.requests[request_id]
        if battle.episode is not None:
            raise PlatformError("invalid_phase", "rosters are fixed after battle initialization")
        normalized = self._catalog.normalize_team(roster, allow_unknown=False)
        if side == "own":
            battle.own_roster = normalized
        else:
            battle.opponent_roster = normalized
        self._try_initialize(battle)
        self._resolve_pending_actions(battle)
        result = PlatformResult(
            battle_id=battle_id,
            accepted=True,
            initialized=battle.episode is not None,
            events=copy.deepcopy(battle.episode.events) if battle.episode is not None else [],
            decision_index=battle.decision_index,
            phase=battle.phase,
            warnings=[] if battle.episode is not None else ["waiting_for_complete_rosters"],
        )
        if request_id:
            battle.requests[request_id] = result
        return result

    @_serialized
    def submit_selection(self, battle_id: str, side: str, selection: Mapping[str, Any] | str, *, request_id: str, decision_index: int | None = None) -> PlatformResult:
        battle = self._get_battle(battle_id)
        request_id = f"{side}:{request_id}"
        if request_id in battle.requests:
            return battle.requests[request_id]
        self._ensure_mutable(battle)
        if decision_index is not None and decision_index != battle.decision_index:
            raise PlatformError("stale_decision", "decision index is no longer current", {
                "expected": battle.decision_index, "received": decision_index,
            })
        if side in battle.pending:
            raise PlatformError("already_submitted", "player already submitted this decision")
        if side not in {"own", "opponent"}:
            raise PlatformError("invalid_side", "side must be 'own' or 'opponent'")
        if battle.episode is None:
            raise PlatformError("invalid_phase", "both sides need enough roster information before selecting")
        player = 0 if side == "own" else 1
        raw_selection = {"action_key": selection} if isinstance(selection, str) else copy.deepcopy(dict(selection))
        action_key = self._resolve_action_key(battle.episode, player, raw_selection)
        battle.pending[side] = {"selection": raw_selection, "action_key": action_key, "request_id": request_id}

        decision = self._backend.decision(battle.episode)
        required_sides = {"own" if item == 0 else "opponent" for item in decision.players}
        if not required_sides.issubset(battle.pending):
            result = PlatformResult(
                battle_id=battle_id,
                accepted=True,
                decision_index=battle.decision_index,
                phase=decision.phase,
                resolved=False,
                next_required=sorted(required_sides - battle.pending.keys()),
                result=None,
                warnings=[],
            )
            battle.requests[request_id] = result
            return result

        actions = {
            player: battle.pending["own" if player == 0 else "opponent"]["action_key"]
            for player in decision.players
        }
        transition = self._backend.advance(battle.episode, actions, battle.seed + battle.decision_index)
        battle.episode = transition.state
        self._record_revealed(battle)
        battle.pending.clear()
        decision_after = self._backend.decision(battle.episode)
        events = [dict(event) for event in transition.events]
        battle.history.append({
            "decision_index": battle.decision_index,
            "turn": decision_after.turn,
            "actions": copy.deepcopy(actions),
            "events": events,
            "source": "core",
        })
        result = PlatformResult(
            battle_id=battle_id,
            accepted=True,
            decision_index=battle.decision_index,
            phase=decision_after.phase,
            resolved=True,
            result={
                "events": events,
                "state_delta": self._state_delta(events),
                "display": self._display_from_events(events),
                "branches": [],
            },
            next_required=["own" if item == 0 else "opponent" for item in decision_after.players],
            terminated=transition.terminated,
            winner=transition.winner,
            outcome=transition.outcome,
            warnings=[],
        )
        battle.requests[request_id] = result
        return result

    @_serialized
    def get_display_info(self, battle_id: str, side: str, *, include_damage_preview: bool = True) -> PlatformResult:
        battle = self._get_battle(battle_id)
        if side not in {"own", "opponent"}:
            raise PlatformError("invalid_side", "side must be 'own' or 'opponent'")
        if battle.episode is None:
            team = battle.own_roster if side == "own" else battle.opponent_roster
            return PlatformResult(
                battle_id=battle_id,
                side=side,
                turn=self._current_turn(battle),
                phase=battle.phase,
                active_index=int((team or {}).get("active_index", 0)),
                skills=self._static_display_info(team),
                assumptions=[],
                warnings=["core_state_not_initialized"],
            )
        display = self._backend.display(battle.episode, 0 if side == "own" else 1)
        skills = []
        for item in display.get("skills", []):
            row = dict(item)
            row["effect_indicator"] = _indicator_for_multiplier(row.get("type_effectiveness"))
            if not include_damage_preview:
                row.pop("display_damage_per_hit", None)
            skills.append(row)
        return PlatformResult(
            battle_id=battle_id,
            side=side,
            turn=self._current_turn(battle),
            phase=battle.phase,
            active_index=display.get("active_index", 0),
            skills=skills,
            assumptions=[],
            warnings=[],
        )

    @_serialized
    def get_matchup_relations(self, battle_id: str, side: str) -> PlatformResult:
        """Rate every creature on one side by its best damaging skill against the opposing active creature."""
        battle = self._get_battle(battle_id)
        if side not in {"own", "opponent"}:
            raise PlatformError("invalid_side", "side must be 'own' or 'opponent'")
        if battle.episode is None:
            return PlatformResult(battle_id=battle_id, side=side, target=None, relations=[], warnings=["core_state_not_initialized"])
        team, target = _team_and_target(battle.episode, _side_code(side))
        relations = []
        for index, creature in enumerate(team):
            best: dict[str, Any] | None = None
            for skill in creature.skills:
                if skill.category not in DAMAGE_CATEGORIES or skill.power <= 0:
                    continue
                multiplier = get_type_effectiveness(skill.skill_type, target.pokemon_types)
                indicator = _indicator_for_multiplier(multiplier)
                if best is None or RELATION_RANK.get(indicator, 0) > RELATION_RANK.get(best["indicator"], 0):
                    best = {"skill_name": skill.name, "indicator": indicator, "multiplier": float(multiplier)}
            relations.append({"index": index, **(best or {"skill_name": None, "indicator": None, "multiplier": None})})
        return PlatformResult(
            battle_id=battle_id,
            side=side,
            target=target.name,
            relations=relations,
            warnings=[],
        )

    def preview_creature(self, creature: Mapping[str, Any]) -> PlatformResult:
        """Resolve one roster entry with the same combat-attribute path as battles."""
        self.logger.info("Provided_infos: %s", creature.__str__())
        raw = merge_creature_spec(copy.deepcopy(dict(creature)))
        name = str(raw.get("name") or raw.get("display_name") or "").strip()
        if not name:
            raise PlatformError("invalid_roster", "creature name is required")
        record = self._catalog.resolve_pokemon(name)
        if record is None:
            raise PlatformError("invalid_roster", f"unknown creature {name!r}")
        name = str(record.get("name") or name)
        raw["name"] = name
        if not raw.get("skills"):
            raw["skills"] = [{"name": str(skill)} for skill in list(record.get("skills", ()))[:4]]
        parsed = creature_from_dict(raw)
        warnings: list[str] = []
        unknowns: list[str] = []
        pokemon = self._builder._creature_to_legacy(parsed, name, warnings, unknowns)
        metadata = pokemon.ability_state.get("lab_metadata", {})
        bloodline = metadata.get("bloodline_attributes") or []
        if isinstance(bloodline, str):
            bloodline = [bloodline]
        self.logger.info("Pokemon info; %s", pokemon.__str__())
        stats = {
            "hp": int(pokemon.hp),
            "atk": int(pokemon.attack),
            "def": int(pokemon.defense),
            "spatk": int(pokemon.sp_attack),
            "spdef": int(pokemon.sp_defense),
            "speed": int(pokemon.speed),
        }
        base = raw.get("base") or {}
        stats_input_values = dict(base.get("stats") or {})
        stats_input = bool(stats_input_values)
        single_hp_input = set(stats_input_values) == {"hp"}
        nature_known = bool(base.get("nature"))
        individual_values_known = bool(base.get("individual_values"))
        return PlatformResult(
            name=pokemon.name,
            hp=int(pokemon.hp),
            stats=stats,
            stats_known={key: (True if single_hp_input else (key in stats_input_values if stats_input else True)) for key in stats},
            nature=pokemon.nature if nature_known or not stats_input else None,
            individual_values=copy.deepcopy(base.get("individual_values")) if individual_values_known else None,
            nature_known=nature_known or not stats_input,
            individual_values_known=individual_values_known,
            stats_input=stats_input,
            bloodline_attributes=list(bloodline),
            warnings=warnings,
            unknowns=unknowns,
        )

    @_serialized
    def get_legal_actions(self, battle_id: str, side: str) -> PlatformResult:
        """Return the exact action keys currently accepted by the core."""
        battle = self._get_battle(battle_id)
        if side not in {"own", "opponent"}:
            raise PlatformError("invalid_side", "side must be 'own' or 'opponent'")
        if battle.episode is None:
            return PlatformResult(battle_id=battle_id, side=side, phase=battle.phase, actions=[], warnings=["core_state_not_initialized"])
        player = 0 if side == "own" else 1
        actions = self._backend.legal_actions(battle.episode, player)
        return PlatformResult(
            battle_id=battle_id,
            side=side,
            phase=battle.phase,
            actions=[{"key": item.key, "payload": copy.deepcopy(dict(item.payload))} for item in actions],
            warnings=[],
        )

    @_serialized
    def get_public_observation(self, battle_id: str, side: str = "own") -> PlatformResult:
        """Return the observer-scoped snapshot used by upper-layer clients."""
        battle = self._get_battle(battle_id)
        if side not in {"own", "opponent"}:
            raise PlatformError("invalid_side", "side must be 'own' or 'opponent'")
        if battle.episode is None:
            return PlatformResult(battle_id=battle_id, side=side, data={}, warnings=["core_state_not_initialized"])
        player = 0 if side == "own" else 1
        observation = normalize_observation(self._backend.observe(battle.episode, player), battle.episode.battle, self._catalog.catalog, revealed=battle.revealed)
        return PlatformResult(
            battle_id=battle_id,
            side=side,
            decision_index=observation.decision_index,
            turn=observation.turn,
            phase=observation.phase,
            data=copy.deepcopy(dict(observation.data)),
            warnings=[],
        )

    @_serialized
    def export_battle(self, battle_id: str) -> Mapping[str, Any]:
        battle = self._get_battle(battle_id)
        snapshot: dict[str, Any] = {
            "format": "nrc_platform.session.v2",
            "battle_id": battle.battle_id,
            "mode": battle.mode,
            "seed": battle.seed,
            "manifest": _manifest_dict(battle.manifest),
            "own_roster": copy.deepcopy(battle.own_roster),
            "opponent_roster": copy.deepcopy(battle.opponent_roster),
            "pending": copy.deepcopy(battle.pending),
            "history": copy.deepcopy(battle.history),
            "revealed": {str(k): sorted(v) for k, v in battle.revealed.items()},
            "requests": copy.deepcopy(battle.requests),
            "phase": battle.phase,
            "decision_index": battle.decision_index,
            "terminal": battle.terminal,
            "winner": battle.winner,
            "outcome": battle.outcome,
        }
        if battle.episode is not None:
            snapshot["episode"] = self._backend.export_state(battle.episode)
        return snapshot

    def import_battle(self, snapshot: Mapping[str, Any]) -> PlatformResult:
        if not isinstance(snapshot, Mapping):
            raise PlatformError("invalid_snapshot", "snapshot must be an object", {"path": "snapshot"})
        if snapshot.get("format") != "nrc_platform.session.v2":
            raise PlatformError("version_mismatch", "unsupported platform snapshot format", {"path": "format"})
        manifest = snapshot.get("manifest")
        if not isinstance(manifest, Mapping):
            raise PlatformError("invalid_snapshot", "snapshot manifest must be an object", {"path": "manifest"})
        if dict(manifest) != _manifest_dict(self.manifest):
            raise PlatformError("version_mismatch", "snapshot manifest does not match active backend")
        battle_id = str(snapshot.get("battle_id") or "")
        if not battle_id:
            raise PlatformError("invalid_snapshot", "snapshot is missing battle_id")
        try:
            revealed = snapshot.get("revealed", {})
            requests = snapshot.get("requests", {})
            pending = snapshot.get("pending", {})
            history = snapshot.get("history", [])
            own_roster = snapshot.get("own_roster")
            opponent_roster = snapshot.get("opponent_roster")
            if revealed is None:
                revealed = {}
            if requests is None:
                requests = {}
            if pending is None:
                pending = {}
            if history is None:
                history = []
            if not isinstance(revealed, Mapping) or not isinstance(requests, Mapping):
                raise TypeError("revealed and requests must be objects")
            if not isinstance(pending, Mapping):
                raise TypeError("pending must be an object")
            if not isinstance(history, list):
                raise TypeError("history must be an array")
            if own_roster is not None and not isinstance(own_roster, Mapping):
                raise TypeError("own_roster must be an object or null")
            if opponent_roster is not None and not isinstance(opponent_roster, Mapping):
                raise TypeError("opponent_roster must be an object or null")
            if any(not isinstance(value, Mapping) for value in requests.values()):
                raise TypeError("requests values must be objects")
            for player in (0, 1):
                visible = revealed.get(str(player), [])
                if visible is None:
                    continue
                if isinstance(visible, (str, bytes)) or not isinstance(visible, (list, tuple, set, frozenset)):
                    raise TypeError(f"revealed[{player}] must be an array")
            battle = _ManagedBattle(
                battle_id=battle_id,
                mode=str(snapshot.get("mode", "full")),
                seed=int(snapshot.get("seed", 0)),
                manifest=self.manifest,
                own_roster=copy.deepcopy(own_roster),
                opponent_roster=copy.deepcopy(opponent_roster),
                pending=copy.deepcopy(pending),
                history=copy.deepcopy(history),
                revealed={p: set(revealed.get(str(p), [])) for p in (0, 1)},
                requests={k: PlatformResult(v) for k, v in requests.items()},
            )
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise PlatformError("invalid_snapshot", "snapshot metadata is invalid", {
                "path": "snapshot", "reason": str(exc),
            }) from exc
        # winner/outcome 从核心快照恢复；旧平台快照仍保留兼容字段。
        if snapshot.get("episode") is not None:
            try:
                battle.episode = self._backend.import_state(snapshot["episode"])
            except Exception as exc:
                raise PlatformError("invalid_snapshot", "snapshot core state is invalid", {
                    "path": "episode", "reason": str(exc),
                }) from exc
        self._battles[battle_id] = battle
        return PlatformResult(
            battle_id=battle_id,
            mode=battle.mode,
            decision_index=battle.decision_index,
            turn=self._current_turn(battle),
            phase=battle.phase,
            manifest=_manifest_dict(self.manifest),
            terminal=battle.terminal,
            winner=battle.winner,
            outcome=battle.outcome,
        )

    def query_display_power(self, state: Any, side: str, skill: Any, *, context: Mapping[str, Any] | None = None) -> PlatformResult:
        episode = self._coerce_episode(state)
        code = _side_code(side)
        view = self._backend.display(episode, 0 if code == "a" else 1)
        slot = _find_skill_slot(episode, code, skill)
        if slot is None or slot >= len(view.get("skills", [])):
            raise PlatformError("invalid_action", "skill does not exist on the active creature")
        result = dict(view["skills"][slot])
        result["effect_indicator"] = _indicator_for_multiplier(result.get("type_effectiveness"))
        result["certainty"] = "exact"
        result["assumptions"] = []
        result["warnings"] = []
        return PlatformResult(result)

    def predict_damage(
        self,
        state: Any,
        attacker: str,
        skill: Any,
        damage_reduction: float,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> PlatformResult:
        if not math.isfinite(float(damage_reduction)) or not 0 <= damage_reduction <= 1:
            raise PlatformError("invalid_damage_reduction", "damage_reduction must be in [0, 1]")
        episode = self._coerce_episode(state)
        code = _side_code(attacker)
        slot = _find_skill_slot(episode, code, skill)
        if slot is None:
            raise PlatformError("invalid_action", "skill does not exist on the active creature")
        isolated = self._backend.clone(episode)
        isolated_attacker, isolated_defender = _active_pair(isolated, code)
        isolated_skill = isolated_attacker.skills[slot]
        raw_damage = DamageCalculator.calculate(isolated_attacker, isolated_defender, isolated_skill, weather=isolated.battle.weather)
        details = dict(isolated_attacker.ability_state.get("_last_damage_details", {}))
        hits = max(1, int(details.get("hits", getattr(isolated_skill, "hit_count", 1))))
        raw_per_hit = int(details.get("damage_per_hit", max(1, raw_damage // hits)))
        after_per_hit = int(raw_per_hit * (1.0 - float(damage_reduction)))
        total = int(raw_damage * (1.0 - float(damage_reduction)))
        if damage_reduction >= 1:
            after_per_hit = total = 0
        return PlatformResult(
            skill_id=getattr(isolated_skill, "skill_id", isolated_skill.name),
            display_power=int(details.get("effective_power", isolated_skill.power)),
            raw_damage=int(raw_damage),
            damage_reduction=float(damage_reduction),
            damage_after_reduction=total,
            damage_per_hit=after_per_hit,
            hits=hits,
            total_damage=total,
            type_effectiveness=details.get("effectiveness", 1.0),
            certainty="exact",
            assumptions=[],
            warnings=[],
        )

    @staticmethod
    def query_type_effectiveness(attack_type: Any, defense_types: Sequence[Any]) -> PlatformResult:
        attack = _resolve_type(attack_type)
        defenses = [_resolve_type(value) for value in defense_types]
        per_type = [{"defense_type": item.value, "multiplier": _single_type_multiplier(attack, item)} for item in defenses]
        multiplier = get_type_effectiveness(attack, defenses)
        return PlatformResult(
            attack_type=attack.value,
            defense_types=[item.value for item in defenses],
            per_type=per_type,
            multiplier=multiplier,
            indicator=_indicator_for_multiplier(multiplier),
            certainty="exact",
        )

    @staticmethod
    def _record_revealed(battle: _ManagedBattle) -> None:
        """只在实际初始化或推进成功后登记上场，不由查询写入。"""
        state = battle.episode.battle
        for player, team, active in ((0, state.team_a, state.current_a), (1, state.team_b, state.current_b)):
            battle.revealed[player].add(active)
            battle.revealed[player].update(i for i, pokemon in enumerate(team) if pokemon.entry_count > 0)

    def _get_battle(self, battle_id: str) -> _ManagedBattle:
        try:
            return self._battles[battle_id]
        except KeyError as exc:
            raise PlatformError("battle_not_found", f"battle {battle_id!r} does not exist") from exc

    @staticmethod
    def _ensure_mutable(battle: _ManagedBattle) -> None:
        if battle.terminal:
            raise PlatformError("battle_terminated", "battle is already terminal")

    def _try_initialize(self, battle: _ManagedBattle) -> None:
        if battle.own_roster is None or battle.opponent_roster is None or battle.episode is not None:
            return
        if not battle.own_roster.get("creatures") or not battle.opponent_roster.get("creatures"):
            return
        setup = {
            "own_team": copy.deepcopy(battle.own_roster),
            "opponent_team": copy.deepcopy(battle.opponent_roster),
            "shared": {"turn": 1, "mp": {"own": 4, "opponent": 4}},
        }
        result = self._builder.build_result(setup, battle.seed)
        if not result.ok:
            raise _build_error(result)
        try:
            episode = self._backend.new_game(result.state, battle.seed)
        except Exception as exc:
            raise PlatformError("core_initialization_failed", "core battle initialization failed", {
                "path": "setup", "reason": str(exc),
            }) from exc
        battle.episode = episode
        self._record_revealed(battle)

    def _resolve_pending_actions(self, battle: _ManagedBattle) -> None:
        if battle.episode is None:
            return
        decision = self._backend.decision(battle.episode)
        required = set(decision.players)
        for side, pending in battle.pending.items():
            player = 0 if side == "own" else 1
            if player not in required or pending.get("action_key") is not None:
                continue
            pending["action_key"] = self._resolve_action_key(battle.episode, player, pending["selection"])

    def _resolve_action_key(self, episode: BattleSession, player: int, selection: Mapping[str, Any]) -> str:
        legal = {item.key: item for item in self._backend.legal_actions(episode, player)}
        direct = selection.get("action_key")
        if direct:
            if direct not in legal:
                raise PlatformError("invalid_action", f"illegal action {direct!r}", {"player": player})
            return str(direct)
        primary = selection.get("primary") or selection
        kind = str(primary.get("kind", "skill"))
        if kind == "charge":
            base = "charge"
        elif kind == "switch":
            base = f"switch:index={int(primary.get('switch_index', selection.get('switch_to')))}"
        elif kind == "skill":
            slot = primary.get("skill_slot")
            if slot is None:
                reference = _known_value(primary.get("skill_id")) or _known_value(primary.get("skill_name"))
                slot = _find_skill_slot(episode, "a" if player == 0 else "b", reference)
            if slot is None:
                raise PlatformError("invalid_action", "skill_slot or skill reference is required")
            base = f"skill:slot={int(slot)}"
            choice = primary.get("choice")
            if choice is not None:
                base = next((key for key, item in legal.items() if key.startswith(base + ":choice=") and item.payload.get("primary", {}).get("choice") == choice), base)
        else:
            raise PlatformError("invalid_action", f"unsupported action kind {kind!r}")
        resonance = selection.get("resonance_magic")
        if isinstance(resonance, Mapping):
            resonance = resonance.get("name") if resonance.get("enabled", True) else None
        if resonance:
            match = next((key for key in legal if key.startswith(f"{base}|resonance=") and key.rsplit("|resonance=", 1)[1] == str(resonance)), None)
            if match:
                return match
        if base not in legal:
            raise PlatformError("invalid_action", f"illegal action {base!r}", {"player": player})
        return base

    def _coerce_episode(self, state: Any) -> BattleSession:
        if isinstance(state, BattleSession):
            return state
        if isinstance(state, str):
            battle = self._get_battle(state)
            if battle.episode is None:
                raise PlatformError("invalid_phase", f"battle {state!r} has no complete core state")
            return battle.episode
        raise PlatformError("invalid_state", "state must be a battle id or BattleSession")

    @staticmethod
    def _current_turn(battle: _ManagedBattle) -> int:
        return int(battle.episode.battle.turn) if battle.episode is not None else 1

    @staticmethod
    def _state_delta(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        turns = [event for event in events if event.get("type") == "turn"]
        return dict(turns[-1].get("after") or {}) if turns else {}

    @staticmethod
    def _display_from_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        for event in events:
            if event.get("type") == "display_power":
                return copy.deepcopy(event.get("value") or {})
        return {}

    def _static_display_info(self, team: Mapping[str, Any] | None) -> list[dict[str, Any]]:
        if not team:
            return []
        creatures = team.get("creatures") or []
        active_index = int(team.get("active_index", 0))
        if not 0 <= active_index < len(creatures):
            return []
        result = []
        for slot, raw in enumerate(creatures[active_index].get("skills") or []):
            name = _known_value(raw.get("name")) if isinstance(raw, Mapping) else str(raw)
            if not name:
                result.append({"skill_slot": slot, "display_power": None, "display_energy_cost": None, "certainty": "unknown"})
                continue
            skill = self._catalog.catalog.get_skill(str(name))
            result.append({
                "skill_slot": slot,
                "skill_id": getattr(skill, "skill_id", skill.name),
                "name": skill.name,
                "display_power": int(skill.power),
                "display_energy_cost": int(skill.energy_cost),
                "display_hits": max(1, int(skill.hit_count)),
                "type_effectiveness": None,
                "effect_indicator": "unknown",
                "certainty": "conditional",
            })
        return result


def _known_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "known" in value:
        return value.get("value") if value.get("known") and value.get("exists", True) else None
    return value


def _manifest_dict(manifest: CoreManifest) -> dict[str, Any]:
    return {
        "protocol_version": manifest.protocol_version,
        "rules_version": manifest.rules_version,
        "catalog_version": manifest.catalog_version,
        "action_version": manifest.action_version,
        "observation_version": manifest.observation_version,
        "environment": manifest.environment,
    }


def _side_code(side: str) -> str:
    if side in {"own", "a", "0", 0}:
        return "a"
    if side in {"opponent", "b", "1", 1}:
        return "b"
    raise PlatformError("invalid_side", "side must be own/opponent")


def _active_pair(episode: BattleSession, code: str):
    if code == "a":
        return episode.battle.team_a[episode.battle.current_a], episode.battle.team_b[episode.battle.current_b]
    return episode.battle.team_b[episode.battle.current_b], episode.battle.team_a[episode.battle.current_a]


def _find_skill_slot(episode: BattleSession, code: str, reference: Any) -> int | None:
    active, _ = _active_pair(episode, code)
    if isinstance(reference, Mapping):
        if reference.get("skill_slot") is not None:
            return int(reference["skill_slot"])
        reference = _known_value(reference.get("skill_id")) or _known_value(reference.get("skill_name")) or _known_value(reference.get("name"))
    if isinstance(reference, int):
        return reference
    if reference is None:
        return None
    text = str(reference)
    for index, skill in enumerate(active.skills):
        if text in {str(skill.name), str(getattr(skill, "skill_id", ""))}:
            return index
    return None


def _team_and_target(episode: BattleSession, code: str):
    battle = episode.battle
    if code == "a":
        return battle.team_a, battle.team_b[battle.current_b]
    return battle.team_b, battle.team_a[battle.current_a]


def _resolve_type(value: Any) -> Type:
    if isinstance(value, Type):
        return value
    try:
        return Type(str(value).strip().lower())
    except ValueError as exc:
        raise PlatformError("invalid_type", f"unknown type {value!r}") from exc


def _single_type_multiplier(attack: Type, defense: Type) -> float:
    from nrc_core.models import TYPE_CHART

    return float(TYPE_CHART.get(attack.value, {}).get(defense.value, 1.0))


def _indicator_for_multiplier(multiplier: Any) -> str:
    if multiplier is None:
        return "unknown"
    multiplier = float(multiplier)
    if multiplier == 0:
        return "immune"
    if multiplier < 0.5:
        return "very_resistant"
    if multiplier < 1:
        return "resistant"
    if multiplier == 1:
        return "normal"
    if multiplier <= 2:
        return "effective"
    return "super_effective"


def create_platform(*, environment: str = "nrc", data_dir: str | Path | None = None) -> BattlePlatform:
    return BattlePlatform(environment=environment, data_dir=data_dir)


__all__ = ["BattlePlatform", "PlatformError", "PlatformResult", "create_platform"]
