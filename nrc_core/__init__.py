"""NRC Battle Lab public core API."""

from .actions import ActionKind, ActionIntent, SideTurnInput
from .branching import BranchDimension, BranchKey, BranchOption
from .devotion import DevotionInput
from .schema import BattleRequest, BattleResult
from .core import TurnResult, simulate_turn


def __getattr__(name):
    if name == "BattleSimulator":
        from .simulator import BattleSimulator
        return BattleSimulator
    if name in {"NRCTrainingBackend", "UnsupportedMechanicError", "VersionMismatchError", "create_backend"}:
        from .training import NRCTrainingBackend, UnsupportedMechanicError, VersionMismatchError, create_backend
        return {
            "NRCTrainingBackend": NRCTrainingBackend,
            "UnsupportedMechanicError": UnsupportedMechanicError,
            "VersionMismatchError": VersionMismatchError,
            "create_backend": create_backend,
        }[name]
    raise AttributeError(name)

__all__ = [
    "ActionKind",
    "ActionIntent",
    "SideTurnInput",
    "BranchDimension",
    "BranchKey",
    "BranchOption",
    "DevotionInput",
    "BattleRequest",
    "BattleResult",
    "TurnResult",
    "simulate_turn",
    "BattleSimulator",
    "NRCTrainingBackend",
    "UnsupportedMechanicError",
    "VersionMismatchError",
    "create_backend",
]
