"""Opponent-facing NRC platform around the single-turn core."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from nrc_ai.contracts import CoreManifest, Decision, LegalAction, Observation, Transition
from nrc_core.training import NRCTrainingBackend, TrainingState


@dataclass
class PlatformState:
    """Multi-turn decision/history record owned by the platform."""

    episode: TrainingState


class BattlePlatform:
    """Hide opponent information and reject illegal public actions."""

    def __init__(self, *, environment: str = "nrc", data_dir: str | Path | None = None):
        self._backend = NRCTrainingBackend(environment=environment, data_dir=data_dir)

    @property
    def manifest(self) -> CoreManifest:
        return self._backend.manifest

    def new_game(self, setup: Mapping[str, Any], seed: int) -> PlatformState:
        return PlatformState(self._backend.new_game(setup, seed))

    def clone(self, state: PlatformState) -> PlatformState:
        return PlatformState(self._backend.clone(state.episode))

    def decision(self, state: PlatformState) -> Decision:
        return self._backend.decision(state.episode)

    def observe(self, state: PlatformState, player: int) -> Observation:
        return self._backend.observe(state.episode, player)

    def legal_actions(self, state: PlatformState, player: int) -> tuple[LegalAction, ...]:
        return self._backend.legal_actions(state.episode, player)

    def advance(self, state: PlatformState, actions: Mapping[int, str], seed: int) -> Transition:
        transition = self._backend.advance(state.episode, actions, seed)
        return Transition(PlatformState(transition.state), transition.observations, transition.rewards, transition.terminated, transition.winner, transition.events)

    def export_state(self, state: PlatformState) -> Mapping[str, Any]:
        return self._backend.export_state(state.episode)

    def import_state(self, snapshot: Mapping[str, Any]) -> PlatformState:
        return PlatformState(self._backend.import_state(snapshot))


def create_platform(*, environment: str = "nrc", data_dir: str | Path | None = None) -> BattlePlatform:
    return BattlePlatform(environment=environment, data_dir=data_dir)


__all__ = ["BattlePlatform", "PlatformState", "create_platform"]
