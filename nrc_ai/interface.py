"""Public observer-facing interface between ``nrc_platform`` and ``nrc_ai``.

The platform owns the battle state and visibility rules.  This module only
reads the two public observer views, asks the configured planner for action
estimates, and returns a serialisable recommendation.  It never advances a
battle or submits a selection by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
from typing import Any, Mapping, Sequence

from .belief import Particle, ParticleBelief
from .contracts import CoreBackend, LegalAction, Observation
from .opponent import OpponentPolicy, UniformOpponentPolicy
from .search import BeliefTreeSearch, SearchResult


Owner = str | Sequence[str]
_OWNERS = {"user", "ai"}


class AIInterfaceError(ValueError):
    """A stable error at the observer-facing AI boundary."""

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": copy.deepcopy(self.details)}


@dataclass(frozen=True)
class ObserverView:
    """One public view plus the legal operations visible from that view."""

    player: int
    owners: tuple[str, ...]
    observation: Observation
    legal_actions: tuple[LegalAction, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "owners": list(self.owners),
            "observation": {
                "player": self.observation.player,
                "decision_index": self.observation.decision_index,
                "turn": self.observation.turn,
                "phase": self.observation.phase,
                "data": copy.deepcopy(dict(self.observation.data)),
            },
            "legal_actions": [
                {"key": action.key, "payload": copy.deepcopy(dict(action.payload))}
                for action in self.legal_actions
            ],
        }


@dataclass(frozen=True)
class ModelActionEstimate:
    """A single model-ranked operation."""

    player: int
    action_key: str
    operation: Mapping[str, Any]
    probability: float
    confidence: float
    value: float
    visits: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "action_key": self.action_key,
            "operation": copy.deepcopy(dict(self.operation)),
            "probability": self.probability,
            "confidence": self.confidence,
            "value": self.value,
            "visits": self.visits,
        }


@dataclass(frozen=True)
class AIPrediction:
    """Result returned by :class:`NRCAIInterface`."""

    mode: str
    decision_index: int
    turn: int
    phase: str
    state_value: Mapping[int, float]
    views: Mapping[int, ObserverView]
    recommendations: tuple[ModelActionEstimate, ...]

    @property
    def operations(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.recommendations]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "decision_index": self.decision_index,
            "turn": self.turn,
            "phase": self.phase,
            "state_prediction": {
                "value": {str(player): value for player, value in self.state_value.items()},
                "observation_fingerprints": {
                    str(player): _observation_fingerprint(view.observation)
                    for player, view in self.views.items()
                },
            },
            "views": {str(player): view.to_dict() for player, view in self.views.items()},
            "operations": self.operations,
            "recommendations": self.operations,
        }


class NRCAIInterface:
    """Read platform observer views and produce AI operation candidates.

    ``owners`` maps observer/player ``0`` and ``1`` to ``"user"``, ``"ai"``
    or a sequence containing both.  A shared observer is therefore expressed
    as ``{0: ("user", "ai"), 1: "user"}`` and is reported as ``ai_assist``.

    The default planner is the existing exact-core belief-tree search.  A
    caller can inject ``model`` with a ``predict(observation, legal_actions)``
    method for a trained policy model; the model must return either a mapping
    of action keys to scores or an iterable of action records.
    """

    def __init__(
        self,
        platform: CoreBackend,
        *,
        owners: Mapping[int, Owner] | Sequence[Owner] | None = None,
        model: Any | None = None,
        opponent_policy: OpponentPolicy | None = None,
        seed: int = 0,
        simulations: int = 128,
        horizon: int = 8,
    ) -> None:
        if simulations <= 0 or horizon <= 0:
            raise ValueError("simulations and horizon must be positive")
        self.platform = platform
        self.owners = normalize_observer_owners(owners)
        self.model = model
        self.opponent_policy = opponent_policy or UniformOpponentPolicy()
        self.seed = int(seed)
        self.simulations = int(simulations)
        self.horizon = int(horizon)

    @property
    def mode(self) -> str:
        return observer_mode(self.owners)

    def observe(self, state: Any) -> dict[int, ObserverView]:
        """Read both observer views without changing platform state."""
        decision = self.platform.decision(state)
        views: dict[int, ObserverView] = {}
        for player in (0, 1):
            observation = self.platform.observe(state, player)
            legal = self.platform.legal_actions(state, player) if player in decision.players else ()
            views[player] = ObserverView(player, self.owners[player], observation, tuple(legal))
        return views

    def predict(self, state: Any) -> AIPrediction:
        """Predict AI-owned operations from the two public observer views.

        In a user-vs-user session no operation is recommended.  In a human-vs-
        AI session only the AI-owned observer is planned.  In an assist session
        the shared observer is planned, but the result remains advisory and no
        platform mutation occurs.
        """
        decision = self.platform.decision(state)
        views = self.observe(state)
        if decision.terminated:
            return AIPrediction(
                mode=self.mode,
                decision_index=decision.index,
                turn=decision.turn,
                phase=decision.phase,
                state_value={},
                views=views,
                recommendations=(),
            )

        recommendations: list[ModelActionEstimate] = []
        state_value: dict[int, float] = {}
        for player in decision.players:
            if "ai" not in self.owners[player]:
                continue
            view = views[player]
            if not view.legal_actions:
                continue
            estimates, value = self._predict_player(state, view)
            recommendations.extend(estimates)
            state_value[player] = value

        recommendations.sort(key=lambda item: (-item.confidence, -item.value, item.action_key))
        return AIPrediction(
            mode=self.mode,
            decision_index=decision.index,
            turn=decision.turn,
            phase=decision.phase,
            state_value=state_value,
            views=views,
            recommendations=tuple(recommendations),
        )

    def predict_battle(self, battle_id: str) -> AIPrediction:
        """Predict from a managed ``nrc_platform`` battle identifier.

        ``BattlePlatform`` deliberately exposes battle snapshots rather than
        its private session map.  The snapshot's core state is imported into
        the same platform instance, so observer filtering remains centralized
        in ``nrc_platform``/``nrc_core``.
        """
        exporter = getattr(self.platform, "export_battle", None)
        importer = getattr(self.platform, "import_state", None)
        if not callable(exporter) or not callable(importer):
            raise AIInterfaceError(
                "unsupported_platform",
                "platform must expose export_battle and import_state for battle prediction",
            )
        snapshot = exporter(battle_id)
        episode = snapshot.get("episode") if isinstance(snapshot, Mapping) else None
        if episode is None:
            raise AIInterfaceError("invalid_phase", "battle has no initialized core state", {"battle_id": battle_id})
        return self.predict(importer(episode))

    def _predict_player(self, state: Any, view: ObserverView) -> tuple[list[ModelActionEstimate], float]:
        if self.model is not None:
            custom = _call_model(self.model, view.observation, view.legal_actions)
            return _estimates_from_custom(view.player, view.legal_actions, custom)

        search = BeliefTreeSearch(
            self.platform,
            self.opponent_policy,
            seed=self.seed + view.player,
        )
        result = search.plan(
            ParticleBelief([Particle(self.platform.clone(state))]),
            player=view.player,
            simulations=self.simulations,
            horizon=self.horizon,
        )
        return _estimates_from_search(view.player, view.legal_actions, result)


def normalize_observer_owners(owners: Mapping[int, Owner] | Sequence[Owner] | None) -> dict[int, tuple[str, ...]]:
    """Normalize the two observer ownership declarations."""
    if owners is None:
        raw: Mapping[int, Owner] = {0: "user", 1: "user"}
    elif isinstance(owners, Mapping):
        raw = owners
    else:
        if len(owners) != 2:
            raise ValueError("owners must contain exactly two observer entries")
        raw = {0: owners[0], 1: owners[1]}

    result: dict[int, tuple[str, ...]] = {}
    for player in (0, 1):
        value = raw.get(player, raw.get("own" if player == 0 else "opponent"))
        if value is None:
            raise ValueError(f"missing observer owner for player {player}")
        if isinstance(value, str):
            values = ("user", "ai") if value in {"shared", "assist", "user+ai", "ai+user"} else (value,)
        else:
            values = tuple(value)
        if not values or any(item not in _OWNERS for item in values) or len(set(values)) != len(values):
            raise ValueError("observer owners must be user, ai, or a unique sequence of both")
        result[player] = tuple(values)
    return result


def observer_mode(owners: Mapping[int, Owner] | Sequence[Owner] | None) -> str:
    """Return the normalized session type for two observer views."""
    normalized = normalize_observer_owners(owners)
    if any(set(value) == _OWNERS for value in normalized.values()):
        return "ai_assist"
    if all(value == ("user",) for value in normalized.values()):
        return "user_vs_user"
    if all(value == ("ai",) for value in normalized.values()):
        return "ai_vs_ai"
    return "human_vs_ai"


AIInterface = NRCAIInterface
NrcAI = NRCAIInterface

def create_interface(platform: CoreBackend, **kwargs: Any) -> NRCAIInterface:
    """Construct the observer-facing AI interface."""
    return NRCAIInterface(platform, **kwargs)


def predict_operations(platform: CoreBackend, state: Any, **kwargs: Any) -> dict[str, Any]:
    """Convenience function returning a JSON-ready prediction dictionary."""
    return create_interface(platform, **kwargs).predict(state).to_dict()


def _call_model(model: Any, observation: Observation, legal_actions: tuple[LegalAction, ...]) -> Any:
    predictor = getattr(model, "predict", None)
    if not callable(predictor):
        predictor = model if callable(model) else None
    if predictor is None:
        raise AIInterfaceError("invalid_model", "model must be callable or expose predict")
    try:
        return predictor(observation, legal_actions)
    except TypeError:
        return predictor(observation.data, legal_actions)


def _estimates_from_search(player: int, legal_actions: tuple[LegalAction, ...], result: SearchResult) -> tuple[list[ModelActionEstimate], float]:
    by_key = {action.key: action for action in legal_actions}
    estimates = []
    for item in result.estimates:
        action = by_key.get(item.action_key)
        if action is None:
            continue
        estimates.append(
            ModelActionEstimate(
                player=player,
                action_key=item.action_key,
                operation={"key": action.key, "payload": copy.deepcopy(dict(action.payload))},
                probability=float(item.probability),
                confidence=float(item.probability),
                value=float(item.mean_value),
                visits=int(item.visits),
            )
        )
    value = next((item.value for item in estimates if item.action_key == result.action_key), 0.0)
    return estimates, float(value)


def _estimates_from_custom(player: int, legal_actions: tuple[LegalAction, ...], output: Any) -> tuple[list[ModelActionEstimate], float]:
    by_key = {action.key: action for action in legal_actions}
    rows: list[tuple[str, float, float, int]] = []
    if isinstance(output, Mapping):
        for key, value in output.items():
            if isinstance(value, Mapping):
                rows.append((str(key), float(value.get("probability", value.get("score", 0.0))), float(value.get("value", 0.0)), int(value.get("visits", 0))))
            else:
                rows.append((str(key), float(value), 0.0, 0))
    else:
        for item in output or ():
            if not isinstance(item, Mapping):
                continue
            key = item.get("action_key", item.get("key"))
            if key is not None:
                rows.append((str(key), float(item.get("probability", item.get("score", 0.0))), float(item.get("value", 0.0)), int(item.get("visits", 0))))
    rows = [(key, max(0.0, probability), value, visits) for key, probability, value, visits in rows if key in by_key]
    total = sum(item[1] for item in rows)
    if total <= 0 and rows:
        total = float(len(rows))
        rows = [(key, 1.0, value, visits) for key, _, value, visits in rows]
    estimates = []
    for key, probability, value, visits in rows:
        action = by_key[key]
        normalized = probability / total if total else 0.0
        estimates.append(ModelActionEstimate(player, key, {"key": key, "payload": copy.deepcopy(dict(action.payload))}, normalized, normalized, value, visits))
    estimates.sort(key=lambda item: (-item.confidence, item.action_key))
    return estimates, (estimates[0].value if estimates else 0.0)


def _observation_fingerprint(observation: Observation) -> str:
    payload = json.dumps(observation.data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "AIInterfaceError",
    "AIPrediction",
    "ModelActionEstimate",
    "NRCAIInterface",
    "AIInterface",
    "NrcAI",
    "ObserverView",
    "create_interface",
    "normalize_observer_owners",
    "observer_mode",
    "predict_operations",
]
