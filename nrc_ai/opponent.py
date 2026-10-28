"""Opponent-policy baselines used by belief search and self-play."""

from __future__ import annotations

from collections import defaultdict
import random
from typing import Mapping, Protocol

from nrc_core.contracts import LegalAction, Observation


class OpponentPolicy(Protocol):
    def distribution(self, observation: Observation, legal_actions: tuple[LegalAction, ...]) -> Mapping[str, float]: ...
    def choose(self, observation: Observation, legal_actions: tuple[LegalAction, ...], rng: random.Random) -> str: ...


def _uniform(actions: tuple[LegalAction, ...]) -> dict[str, float]:
    if not actions:
        raise ValueError("opponent has no legal action")
    probability = 1.0 / len(actions)
    return {action.key: probability for action in actions}


class UniformOpponentPolicy:
    def distribution(self, observation: Observation, legal_actions: tuple[LegalAction, ...]) -> Mapping[str, float]:
        return _uniform(legal_actions)

    def choose(self, observation: Observation, legal_actions: tuple[LegalAction, ...], rng: random.Random) -> str:
        return rng.choice(legal_actions).key


class EmpiricalOpponentPolicy:
    def __init__(self, *, prior: float = 1.0) -> None:
        self.prior = float(prior)
        self.counts: dict[str, dict[str, float]] = defaultdict(dict)

    @staticmethod
    def context(observation: Observation) -> str:
        data = observation.data
        shared = data.get("shared", {}) if isinstance(data, Mapping) else {}
        return f"{observation.phase}|turn_bucket={min(observation.turn, 10)}|weather={shared.get('weather', '?')}"

    def observe(self, observation: Observation, action_key: str, weight: float = 1.0) -> None:
        context = self.context(observation)
        self.counts[context][action_key] = self.counts[context].get(action_key, 0.0) + weight

    def distribution(self, observation: Observation, legal_actions: tuple[LegalAction, ...]) -> Mapping[str, float]:
        context_counts = self.counts.get(self.context(observation), {})
        values = {action.key: self.prior + context_counts.get(action.key, 0.0) for action in legal_actions}
        total = sum(values.values())
        return {key: value / total for key, value in values.items()}

    def choose(self, observation: Observation, legal_actions: tuple[LegalAction, ...], rng: random.Random) -> str:
        distribution = self.distribution(observation, legal_actions)
        return rng.choices(list(distribution), weights=list(distribution.values()), k=1)[0]
