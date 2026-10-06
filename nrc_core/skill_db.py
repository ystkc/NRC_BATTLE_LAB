"""Compatibility facade for a platform-provided in-memory skill catalog.

The old module queried SQLite and parsed descriptions.  Both responsibilities
belong to the platform now; callers must configure a resolved ``CoreCatalog``.
"""

from __future__ import annotations

from .catalog import CoreCatalog, EMPTY_CATALOG
from .effect_data import ABILITY_EFFECTS
from .models import Skill, TYPE_NAME_MAP, Type

_TYPE_MAP = {name: value for name, value in TYPE_NAME_MAP.items()}
_TYPE_MAP.update({value.value: value for value in Type})

_catalog: CoreCatalog = EMPTY_CATALOG


def configure_catalog(catalog: CoreCatalog) -> None:
    global _catalog
    _catalog = catalog


def load_skills() -> dict[str, Skill]:
    return _catalog.all_skills()


def get_skill(name: str) -> Skill | None:
    return _catalog.get_skill(name)


def get_all_skills() -> dict[str, Skill]:
    return _catalog.all_skills()


def get_all_skill_names() -> list[str]:
    return list(_catalog.skills)


def load_ability_effects(ability_str: str) -> list:
    if not ability_str:
        return []
    name = str(ability_str).split(":", 1)[0].split("：", 1)[0].strip()
    configured = _catalog.get_ability_effects(name)
    return configured or list(ABILITY_EFFECTS.get(name, ()))


__all__ = [
    "configure_catalog",
    "load_skills",
    "get_skill",
    "get_all_skills",
    "get_all_skill_names",
    "load_ability_effects",
]
