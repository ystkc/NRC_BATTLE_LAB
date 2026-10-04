"""Root-action Monte Carlo baseline while the real backend is being developed."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

from .belief import ParticleBelief
from .contracts import CoreBackend
from .opponent import OpponentPolicy


@dataclass(frozen=True)
class ActionEstimate:
    action_key: str
    visits: int
    mean_value: float
    win_rate: float


class RootActionEvaluator:
    """Sample hidden states and opponent actions for each root action.

    This is deliberately not called POMCP yet: it has no tree reuse or history
    nodes. It is the integration seam for the future search implementation.
    """

    def __init__(self, backend: CoreBackend, opponent_policy: OpponentPolicy, *, seed: int = 0) -> None:
        self.backend = backend
        self.opponent_policy = opponent_policy
        self.rng = random.Random(seed)

    def evaluate(self, belief: ParticleBelief, *, player: int = 0, simulations_per_action: int = 32, horizon: int = 8) -> tuple[ActionEstimate, ...]:
        if not belief.particles:
            raise ValueError("root evaluation requires a non-empty belief")
        actions = self.backend.legal_actions(belief.particles[0].state, player)
        estimates = []
        for action in actions:
            values = []
            wins = []
            for _ in range(simulations_per_action):
                particle = belief.sample(self.rng)
                value, winner = self._rollout(self.backend.clone(particle.state), player, action.key, horizon)
                values.append(value)
                wins.append(1.0 if winner == player else 0.0)
            estimates.append(ActionEstimate(action.key, len(values), sum(values) / len(values), sum(wins) / len(wins)))
        return tuple(sorted(estimates, key=lambda item: (item.mean_value, item.win_rate), reverse=True))

    def _rollout(self, state: Any, player: int, own_action: str, horizon: int) -> tuple[float, int | None]:
        total = 0.0
        discount = 1.0
        for _ in range(horizon):
            decision = self.backend.decision(state)
            if decision.terminated:
                return total, decision.winner
            actions = {}
            if player in decision.players:
                actions[player] = own_action
            for other in decision.players:
                if other == player:
                    continue
                observation = self.backend.observe(state, other)
                legal = self.backend.legal_actions(state, other)
                actions[other] = self.opponent_policy.choose(observation, legal, self.rng)
            transition = self.backend.advance(state, actions, self.rng.randrange(2**32))
            total += discount * float(transition.rewards.get(player, 0.0))
            discount *= 0.99
            state = transition.state
            if transition.terminated:
                return total, transition.winner
            if player in self.backend.decision(state).players:
                legal = self.backend.legal_actions(state, player)
                if not legal:
                    raise RuntimeError("backend returned no legal action for an active player")
                own_action = self.rng.choice(legal).key
        decision = self.backend.decision(state)
        return total, decision.winner if decision.terminated else None
