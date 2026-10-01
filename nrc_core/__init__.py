"""NRC Battle Lab public core API."""

from .actions import ActionKind, ActionIntent, SideTurnInput
from .branching import BranchDimension, BranchKey, BranchOption
from .devotion import DevotionInput
from .schema import BattleRequest, BattleResult


def __getattr__(name):
    if name == "BattleSimulator":
        from .simulator import BattleSimulator
        return BattleSimulator
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
    "BattleSimulator",
]
