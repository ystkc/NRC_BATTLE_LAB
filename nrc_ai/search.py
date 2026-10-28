"""Belief-tree search for simultaneous, partially observable decisions.

This is the first real search layer for the project. It uses exact core
transitions and samples hidden particles/opponent actions; it does not learn a
MuZero dynamics model yet. The tree is intentionally local to one planning
call, so a later implementation can add public-history transpositions without
changing the backend contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Any, Callable, Mapping

from .belief import ParticleBelief
from nrc_core.contracts import CoreBackend, LegalAction
from .opponent import OpponentPolicy


@dataclass
class EdgeStats:
    visits: int = 0
    value_sum: float = 0.0

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass
class SearchNode:
    visits: int = 0
    value_sum: float = 0.0
    edges: dict[str, EdgeStats] = field(default_factory=dict)
    children: dict[str, "SearchNode"] = field(default_factory=dict)

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass(frozen=True)
class SearchEstimate:
    action_key: str
    visits: int
    mean_value: float
    probability: float


@dataclass(frozen=True)
class SearchResult:
    action_key: str
    estimates: tuple[SearchEstimate, ...]
    simulations: int

    @property
    def policy(self) -> dict[str, float]:
        return {estimate.action_key: estimate.probability for estimate in self.estimates}


class BeliefTreeSearch:
    """POMCP-style sampled tree search over a backend's exact transitions."""

    def __init__(self, backend: CoreBackend, opponent_policy: OpponentPolicy, *, seed: int = 0, exploration: float = 1.4, discount: float = 0.99, leaf_value: Callable[[Any, int], float] | None = None) -> None:
        if exploration < 0.0:
            raise ValueError("exploration must be non-negative")
        if not 0.0 < discount <= 1.0:
            raise ValueError("discount must be in (0, 1]")
        self.backend = backend
        self.opponent_policy = opponent_policy
        self.rng = random.Random(seed)
        self.exploration = exploration
        self.discount = discount
        self.leaf_value = leaf_value or self._public_observation_value

    def plan(self, belief: ParticleBelief, *, player: int = 0, simulations: int = 128, horizon: int = 8) -> SearchResult:
        if not belief.particles:
            raise ValueError("planning requires a non-empty belief")
        if simulations <= 0 or horizon <= 0:
            raise ValueError("simulations and horizon must be positive")
        root_state = belief.particles[0].state
        decision = self.backend.decision(root_state)
        if decision.terminated or player not in decision.players:
            raise ValueError("player must be active at a non-terminal root decision")
        root_actions = self.backend.legal_actions(root_state, player)
        if not root_actions:
            raise ValueError("root player has no legal actions")
        root_action_keys = {action.key for action in root_actions}
        for particle in belief.particles:
            particle_keys = {action.key for action in self.backend.legal_actions(particle.state, player)}
            if particle_keys != root_action_keys:
                raise ValueError(
                    "belief particles disagree on the controlled player's legal "
                    "action set; keep own private state fixed and vary only hidden opponent state"
                )
        root = SearchNode(edges={action.key: EdgeStats() for action in root_actions})
        for _ in range(simulations):
            particle = belief.sample(self.rng)
            state = self.backend.clone(particle.state)
            root_action = self._select_action(root, root_actions)
            self._simulate(state, root, player, root_action, horizon, depth=0)
        total_visits = sum(edge.visits for edge in root.edges.values())
        estimates = tuple(
            SearchEstimate(key, edge.visits, edge.mean_value, edge.visits / total_visits if total_visits else 0.0)
            for key, edge in root.edges.items()
        )
        estimates = tuple(sorted(estimates, key=lambda item: (item.visits, item.mean_value), reverse=True))
        return SearchResult(estimates[0].action_key, estimates, simulations)

    def _select_action(self, node: SearchNode, legal_actions: tuple[LegalAction, ...]) -> str:
        for action in legal_actions:
            stats = node.edges.setdefault(action.key, EdgeStats())
            if stats.visits == 0:
                return action.key
        log_parent = math.log(max(1, node.visits))
        return max(
            (action.key for action in legal_actions),
            key=lambda key: node.edges[key].mean_value + self.exploration * math.sqrt(log_parent / node.edges[key].visits),
        )

    def _simulate(self, state: Any, node: SearchNode, player: int, forced_action: str | None, horizon: int, depth: int) -> float:
        decision = self.backend.decision(state)
        if decision.terminated:
            return self._terminal_value(decision.winner, player)
        if depth >= horizon:
            return self.leaf_value(state, player)
        actions: dict[int, str] = {}
        selected_key = "__wait__"
        if player in decision.players:
            legal = self.backend.legal_actions(state, player)
            if not legal:
                raise RuntimeError("backend returned no legal action for an active player")
            selected_key = forced_action if forced_action is not None else self._select_action(node, legal)
            if selected_key not in {action.key for action in legal}:
                raise ValueError(f"search selected illegal action {selected_key!r}")
            actions[player] = selected_key
        for other in decision.players:
            if other == player:
                continue
            legal = self.backend.legal_actions(state, other)
            if not legal:
                raise RuntimeError("backend returned no legal action for an active opponent")
            observation = self.backend.observe(state, other)
            actions[other] = self.opponent_policy.choose(observation, legal, self.rng)
        if not actions:
            raise RuntimeError("non-terminal backend decision has no players")
        transition = self.backend.advance(state, actions, self.rng.randrange(2**32))
        immediate = float(transition.rewards.get(player, 0.0))
        child = node.children.setdefault(selected_key, SearchNode())
        next_value = self._simulate(transition.state, child, player, None, horizon, depth + 1)
        value = immediate + self.discount * next_value
        node.visits += 1
        node.value_sum += value
        if selected_key != "__wait__":
            edge = node.edges.setdefault(selected_key, EdgeStats())
            edge.visits += 1
            edge.value_sum += value
        return value

    @staticmethod
    def _terminal_value(winner: int | None, player: int) -> float:
        if winner is None:
            return 0.0
        return 1.0 if winner == player else -1.0

    def _public_observation_value(self, state: Any, player: int) -> float:
        data = self.backend.observe(state, player).data
        own_team = data.get("own_team") or data.get("own") or []
        opponent_team = data.get("opponent_team") or data.get("opponent") or []

        def active_value(team: Any) -> tuple[float, float]:
            if isinstance(team, Mapping):
                team = [team]
            if not isinstance(team, (list, tuple)):
                return 0.0, 1.0
            active = next((item for item in team if isinstance(item, Mapping) and item.get("active")), None)
            active = active or next((item for item in team if isinstance(item, Mapping)), {})
            hp = float(active.get("hp", 0.0) or 0.0)
            max_hp = float(active.get("max_hp", hp or 1.0) or 1.0)
            energy = float(active.get("energy", 0.0) or 0.0)
            return hp / max_hp if max_hp > 0 else 0.0, energy / 10.0

        own_hp, own_energy = active_value(own_team)
        opponent_hp, opponent_energy = active_value(opponent_team)
        shared = data.get("shared", {}) if isinstance(data, Mapping) else {}
        mp = shared.get("mp", {}) or {}
        own_mp = float(mp.get("own", 0.0) or 0.0)
        opponent_mp = float(mp.get("opponent", 0.0) or 0.0)
        value = 0.55 * (own_hp - opponent_hp) + 0.15 * (own_energy - opponent_energy) + 0.30 * (own_mp - opponent_mp) / 4.0
        return max(-1.0, min(1.0, value))
