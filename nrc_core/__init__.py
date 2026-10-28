"""NRC Battle Lab public core API."""

from .actions import ActionKind, ActionIntent, SideTurnInput
from .devotion import DevotionInput
from .catalog import CoreCatalog
from .schema import BattleRequest
from .core import TurnResult, simulate_turn
from .debug import configure_core_logging, core_log


def __getattr__(name):
    if name in {"BattleRuntime", "BattleSession", "UnsupportedMechanicError", "VersionMismatchError", "create_runtime"}:
        from .runtime import BattleSession, BattleRuntime, UnsupportedMechanicError, VersionMismatchError, create_runtime
        return {
            "BattleRuntime": BattleRuntime,
            "BattleSession": BattleSession,
            "UnsupportedMechanicError": UnsupportedMechanicError,
            "VersionMismatchError": VersionMismatchError,
            "create_runtime": create_runtime,
        }[name]
    raise AttributeError(name)

__all__ = [
    "ActionKind",
    "ActionIntent",
    "SideTurnInput",
    "DevotionInput",
    "CoreCatalog",
    "BattleRequest",
    "TurnResult",
    "simulate_turn",
    "configure_core_logging",
    "core_log",
    "BattleRuntime",
    "BattleSession",
    "UnsupportedMechanicError",
    "VersionMismatchError",
    "create_runtime",
]
