"""Public multi-turn battle-platform boundary for NRC."""

from .platform import BattlePlatform, PlatformError, PlatformResult, create_platform

__all__ = ["BattlePlatform", "PlatformError", "PlatformResult", "create_platform"]
