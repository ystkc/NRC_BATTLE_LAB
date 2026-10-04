"""Small, dependency-free boundary between nrc_core and training code."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class CoreManifest:
    protocol_version: str
    rules_version: str
    catalog_version: str
    action_version: str
    observation_version: str
    environment: str = "nrc"


@dataclass(frozen=True)
class LegalAction:
    key: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    index: int
    turn: int
    phase: str
    players: tuple[int, ...]
    terminated: bool = False
    winner: int | None = None


@dataclass(frozen=True)
class Observation:
    player: int
    decision_index: int
    turn: int
    phase: str
    data: Mapping[str, Any]


@dataclass(frozen=True)
class Transition:
    state: Any
    observations: Mapping[int, Observation]
    rewards: Mapping[int, float]
    terminated: bool
    winner: int | None = None
    events: tuple[Mapping[str, Any], ...] = ()


class CoreBackend(Protocol):
    @property
    def manifest(self) -> CoreManifest: ...
    def new_game(self, setup: Mapping[str, Any], seed: int) -> Any: ...
    def clone(self, state: Any) -> Any: ...
    def decision(self, state: Any) -> Decision: ...
    def observe(self, state: Any, player: int) -> Observation: ...
    def legal_actions(self, state: Any, player: int) -> tuple[LegalAction, ...]: ...
    def advance(self, state: Any, actions: Mapping[int, str], seed: int) -> Transition: ...
    def export_state(self, state: Any) -> Mapping[str, Any]: ...
    def import_state(self, snapshot: Mapping[str, Any]) -> Any: ...


def action_map(actions: Sequence[LegalAction]) -> dict[str, LegalAction]:
    result: dict[str, LegalAction] = {}
    for action in actions:
        if not action.key or action.key in result:
            raise ValueError(f"duplicate or empty action key: {action.key!r}")
        result[action.key] = action
    return result
