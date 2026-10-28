"""战斗运行器共享的协议、动作、观测与转移数据。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from .models import BattleState


@dataclass(frozen=True)
class CoreManifest:
    """运行协议与规则目录版本。"""

    protocol_version: str
    rules_version: str
    catalog_version: str
    action_version: str
    observation_version: str
    environment: str = "nrc"


@dataclass(frozen=True)
class LegalAction:
    """合法动作键与解析后的动作内容。"""

    key: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """当前决策阶段与需要提交操作的玩家。"""

    index: int
    turn: int
    phase: str
    players: tuple[int, ...]
    terminated: bool = False
    winner: int | None = None


@dataclass(frozen=True)
class Observation:
    """面向指定玩家的结构化观测。"""

    player: int
    decision_index: int
    turn: int
    phase: str
    data: Mapping[str, Any]


@dataclass(frozen=True)
class Transition:
    """一次推进后的状态、观测与战斗事件。"""

    state: Any
    observations: Mapping[int, Observation]
    rewards: Mapping[int, float]
    terminated: bool
    winner: int | None = None
    events: tuple[Mapping[str, Any], ...] = ()


class CoreBackend(Protocol):
    """战斗运行器的结构化调用协议。"""

    @property
    def manifest(self) -> CoreManifest: ...
    def new_game(self, setup: BattleState, seed: int) -> Any: ...
    def clone(self, state: Any) -> Any: ...
    def decision(self, state: Any) -> Decision: ...
    def observe(self, state: Any, player: int) -> Observation: ...
    def legal_actions(self, state: Any, player: int) -> tuple[LegalAction, ...]: ...
    def advance(self, state: Any, actions: Mapping[int, str], seed: int) -> Transition: ...
    def export_state(self, state: Any) -> Mapping[str, Any]: ...
    def import_state(self, snapshot: Mapping[str, Any]) -> Any: ...


def action_map(actions: Sequence[LegalAction]) -> dict[str, LegalAction]:
    """校验动作键并建立索引。"""
    result: dict[str, LegalAction] = {}
    for action in actions:
        if not action.key or action.key in result:
            raise ValueError(f"duplicate or empty action key: {action.key!r}")
        result[action.key] = action
    return result

