"""Online particle filtering and planning for partially observable play."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import random
from typing import Any, Mapping

from .belief import Particle, ParticleBelief
from nrc_core.contracts import CoreBackend, Observation
from .opponent import OpponentPolicy
from .search import BeliefTreeSearch, SearchResult


def _similarity(expected: Any, actual: Any) -> float:
    if type(expected) is not type(actual):
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            expected_number = float(expected)
            actual_number = float(actual)
            scale = max(1.0, abs(expected_number), abs(actual_number))
            return math.exp(-abs(expected_number - actual_number) / (0.1 * scale))
        return 0.0
    if isinstance(expected, Mapping):
        keys = set(expected) | set(actual)
        if not keys:
            return 1.0
        return sum(_similarity(expected.get(key), actual.get(key)) for key in keys) / len(keys)
    if isinstance(expected, (list, tuple)):
        if len(expected) != len(actual):
            return 0.0
        if not expected:
            return 1.0
        return sum(_similarity(left, right) for left, right in zip(expected, actual)) / len(expected)
    return 1.0 if expected == actual else 0.0


def observation_likelihood(expected: Observation, actual: Observation, *, exact: bool = False) -> float:
    """Score how well a predicted public observation explains an actual one."""
    if expected.player != actual.player or expected.phase != actual.phase:
        return 0.0
    if exact:
        expected_json = json.dumps(expected.data, sort_keys=True, ensure_ascii=False)
        actual_json = json.dumps(actual.data, sort_keys=True, ensure_ascii=False)
        return 1.0 if expected_json == actual_json else 0.0
    expected_decision = expected.data.get("decision", {})
    actual_decision = actual.data.get("decision", {})
    if expected_decision.get("index") != actual_decision.get("index"):
        return 0.0
    return max(0.0, min(1.0, _similarity(expected.data, actual.data)))


@dataclass(frozen=True)
class BeliefUpdateResult:
    belief: ParticleBelief
    attempted: int
    accepted: int
    effective_sample_size: float
    observed_player: int


class OnlineBeliefUpdater:
    """Advance hidden-state particles using known actions and one observation."""

    def __init__(self, backend: CoreBackend, opponent_policy: OpponentPolicy, *, seed: int = 0, samples_per_particle: int = 4, exact_observation: bool = False) -> None:
        if samples_per_particle <= 0:
            raise ValueError("samples_per_particle must be positive")
        self.backend = backend
        self.opponent_policy = opponent_policy
        self.rng = random.Random(seed)
        self.samples_per_particle = samples_per_particle
        self.exact_observation = exact_observation

    def update(self, belief: ParticleBelief, known_actions: Mapping[int, str], *, observing_player: int, observed: Observation) -> BeliefUpdateResult:
        if not belief.particles:
            raise ValueError("cannot update an empty belief")
        target_count = len(belief.particles)
        candidates: list[Particle] = []
        attempted = 0
        accepted = 0
        for particle in belief.particles:
            state = particle.state
            decision = self.backend.decision(state)
            if decision.terminated:
                continue
            if not set(known_actions).issubset(set(decision.players)):
                raise ValueError("known action contains a player who is not active")
            missing_players = [player for player in decision.players if player not in known_actions]
            if len(missing_players) > 1:
                raise ValueError("the updater supports at most one hidden simultaneous opponent")
            for _ in range(self.samples_per_particle):
                attempted += 1
                actions = dict(known_actions)
                for player in missing_players:
                    legal = self.backend.legal_actions(state, player)
                    if not legal:
                        continue
                    actions[player] = self.opponent_policy.choose(self.backend.observe(state, player), legal, self.rng)
                if set(actions) != set(decision.players):
                    continue
                transition = self.backend.advance(self.backend.clone(state), actions, self.rng.randrange(2**32))
                predicted = transition.observations[observing_player]
                likelihood = observation_likelihood(predicted, observed, exact=self.exact_observation)
                if likelihood <= 0.0:
                    continue
                accepted += 1
                metadata = dict(particle.metadata or {})
                metadata.update({"last_hidden_actions": {str(key): value for key, value in actions.items() if key not in known_actions}, "last_seed": getattr(transition.state, "seed", None)})
                candidates.append(Particle(transition.state, particle.weight * likelihood / self.samples_per_particle, metadata))
        updated = ParticleBelief(candidates)
        if updated.particles and len(updated.particles) > target_count:
            updated = ParticleBelief(updated.sample_many(target_count, self.rng, clone=self.backend.clone))
        return BeliefUpdateResult(updated, attempted, accepted, updated.effective_sample_size(), observing_player)


class OnlineBeliefAgent:
    """Search, act, then update a belief after the environment reveals a view."""

    def __init__(self, backend: CoreBackend, opponent_policy: OpponentPolicy, belief: ParticleBelief, *, player: int = 0, seed: int = 0, samples_per_particle: int = 4, simulations: int = 128, horizon: int = 8, exact_observation: bool = False) -> None:
        self.backend = backend
        self.opponent_policy = opponent_policy
        self.belief = belief
        self.player = player
        self.simulations = simulations
        self.horizon = horizon
        self.search = BeliefTreeSearch(backend, opponent_policy, seed=seed)
        self.updater = OnlineBeliefUpdater(backend, opponent_policy, seed=seed + 1, samples_per_particle=samples_per_particle, exact_observation=exact_observation)
        self.pending_action: str | None = None

    def plan(self) -> SearchResult:
        result = self.search.plan(self.belief, player=self.player, simulations=self.simulations, horizon=self.horizon)
        self.pending_action = result.action_key
        return result

    def observe(self, observation: Observation, *, known_actions: Mapping[int, str] | None = None) -> BeliefUpdateResult:
        actions = dict(known_actions or {})
        if not actions:
            if self.pending_action is None:
                raise ValueError("observe requires known_actions or a preceding plan call")
            actions[self.player] = self.pending_action
        result = self.updater.update(self.belief, actions, observing_player=self.player, observed=observation)
        self.belief = result.belief
        self.pending_action = None
        return result
