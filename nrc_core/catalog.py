"""In-memory rule catalog supplied by an upper layer.

The core deliberately knows nothing about databases, files, or parsers.  A
platform builds this catalog from its own repositories and passes it into the
core before a battle starts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import Skill


def calc_combat_stats(
    base_hp: float,
    base_atk: float,
    base_spatk: float,
    base_def: float,
    base_spdef: float,
    base_speed: float,
    iv_config: Mapping[str, int] | None = None,
    nature_name: str = "",
) -> dict[str, int]:
    """Calculate stats from already-resolved catalog values."""
    iv = {key: int(value) for key, value in (iv_config or {}).items()}
    nature_bonus = {"hp": 0.0, "attack": 0.0, "defense": 0.0,
                    "sp_attack": 0.0, "sp_defense": 0.0, "speed": 0.0}
    try:
        from .pokemon_nature_table import get_nature_bonus
        raw_bonus = get_nature_bonus(nature_name)
        nature_bonus.update({
            "hp": raw_bonus.get("hp", 0.0),
            "attack": raw_bonus.get("atk", 0.0),
            "defense": raw_bonus.get("defense", 0.0),
            "sp_attack": raw_bonus.get("sp_atk", 0.0),
            "sp_defense": raw_bonus.get("sp_defense", 0.0),
            "speed": raw_bonus.get("speed", 0.0),
        })
    except (ImportError, KeyError):
        aliases = {
            "brave": ("attack", 0.2), "attack_up": ("attack", 0.2),
            "bold": ("defense", 0.2), "defense_up": ("defense", 0.2),
            "modest": ("sp_attack", 0.2), "sp_attack_up": ("sp_attack", 0.2),
            "calm": ("sp_defense", 0.2), "sp_defense_up": ("sp_defense", 0.2),
            "timid": ("speed", 0.2), "speed_up": ("speed", 0.2),
        }
        if nature_name in aliases:
            key, value = aliases[nature_name]
            nature_bonus[key] = value

    def rounded(value: float) -> int:
        return int(value + 0.5)

    def other(base: float, key: str, attribute: str) -> int:
        growth = base * 0.01 + iv.get(key, 0) * 0.005
        intermediate = rounded(10 + growth * 110)
        return rounded(intermediate * (1 + nature_bonus[attribute]) + 50)

    hp_growth = base_hp * 0.01 + iv.get("hp", 0) * 0.005
    hp_intermediate = rounded(70 + hp_growth * 170)
    return {
        "hp": rounded(hp_intermediate * (1 + nature_bonus["hp"]) + 100),
        "atk": other(base_atk, "atk", "attack"),
        "spatk": other(base_spatk, "spatk", "sp_attack"),
        "def": other(base_def, "def", "defense"),
        "spdef": other(base_spdef, "spdef", "sp_defense"),
        "speed": other(base_speed, "speed", "speed"),
    }


@dataclass(frozen=True)
class CoreCatalog:
    """Resolved, read-only catalog data required by the rules engine."""

    skills: Mapping[str, Skill] = field(default_factory=dict)
    pokemon: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    ability_effects: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)
    boss_forms: Mapping[str, tuple[Mapping[str, Any], ...]] = field(default_factory=dict)
    skill_descriptions: Mapping[str, str] = field(default_factory=dict)
    distributions: Mapping[tuple[str, str], tuple[Mapping[str, Any], ...]] = field(default_factory=dict)

    def get_skill(self, identifier: str | None) -> Skill | None:
        if not identifier:
            return None
        skill = self.skills.get(str(identifier))
        if skill is not None:
            return skill.copy()
        for candidate in self.skills.values():
            if str(getattr(candidate, "skill_id", "")) == str(identifier):
                return candidate.copy()
        return None

    def all_skills(self) -> dict[str, Skill]:
        return {name: skill.copy() for name, skill in self.skills.items()}

    def get_pokemon(self, name: str | None) -> Mapping[str, Any] | None:
        return self.pokemon.get(str(name)) if name else None

    def calc_combat_stats(self, *args: Any, **kwargs: Any) -> dict[str, int]:
        return calc_combat_stats(*args, **kwargs)

    def get_boss_forms(self, name: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.boss_forms.get(name, ()))

    def get_distribution(self, spirit_name: str, distribution_kind: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.distributions.get((spirit_name, distribution_kind), ()))

    def get_ability_effects(self, ability: str | None) -> list[Any]:
        if not ability:
            return []
        name = str(ability).split(":", 1)[0].split("：", 1)[0].strip()
        return list(self.ability_effects.get(name, ()))

    def get_skill_description(self, name: str | None) -> str:
        return str(self.skill_descriptions.get(str(name), "")) if name else ""

EMPTY_CATALOG = CoreCatalog()
