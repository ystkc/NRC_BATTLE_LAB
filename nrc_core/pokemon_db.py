"""Compatibility facade for a platform-provided in-memory creature catalog."""

from __future__ import annotations

from typing import Any, Mapping

from .catalog import CoreCatalog, EMPTY_CATALOG, calc_combat_stats

_catalog: CoreCatalog = EMPTY_CATALOG


def configure_catalog(catalog: CoreCatalog) -> None:
    global _catalog
    _catalog = catalog


def get_pokemon(name: str) -> Mapping[str, Any] | None:
    return _catalog.get_pokemon(name)


def get_boss_form(name: str) -> list[Mapping[str, Any]]:
    return list(_catalog.get_boss_forms(name))


def count_pokemon() -> int:
    return len(_catalog.pokemon)


def get_pokemon_skills(name: str) -> list[dict[str, Any]]:
    record = get_pokemon(name)
    if not record:
        return []
    result = []
    for skill_name in record.get("skills", ()):
        skill = _catalog.get_skill(str(skill_name))
        if skill is None:
            continue
        result.append({
            "name": skill.name,
            "wiki_id": getattr(skill, "skill_id", skill.name),
            "energy_cost": skill.energy_cost,
            "power": skill.power,
        })
    return result


def search_pokemon(query: str) -> list[Mapping[str, Any]]:
    text = str(query or "").strip()
    return [record for name, record in _catalog.pokemon.items() if text in name or name in text]


__all__ = ["configure_catalog", "get_pokemon", "get_boss_form", "get_pokemon_skills", "search_pokemon", "count_pokemon", "calc_combat_stats"]
