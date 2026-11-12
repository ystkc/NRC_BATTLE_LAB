"""In-memory rule catalog supplied by an upper layer.

The core deliberately knows nothing about databases, files, or parsers.  A
platform builds this catalog from its own repositories and passes it into the
core before a battle starts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
import numpy as np
import logging
logger = logging.getLogger(__name__)


from .models import Skill
from .pokemon_nature_table import get_nature_bonus
from .constant import PVP_APTITUDES_MULTIPLIER
MUL_BASE_HP = np.float16(1.7)
MUL_IV_HP = np.float16(0.85)
MUL_BASE_OTHER = np.float16(1.1)
MUL_IV_OTHER = np.float16(0.55)



def calc_combat_stats(
    base_hp: float,
    base_atk: float,
    base_spatk: float,
    base_def: float,
    base_spdef: float,
    base_speed: float,
    iv_config: Mapping[str, int] | None = None, # Individual value，忽略资质等直接输入个体特值
    nature_name: str = "",
) -> dict[str, int]:
    """Calculate stats from already-resolved catalog values.
    生命=四舍五入[1.7×种族值+个体资质值×0.85+70]×四舍五入（1+性格修正）+100
其他=四舍五入[1.1×种族值+个体资质值×0.55+10]×四舍五入（1+性格修正）+50
为了在极端边界条件下（例如种族值105，个体资质值0，无性格修正）保持和游戏内计算结果一致，需要严格使用float16类型"""
    try:
        iv = {key: int(value) * PVP_APTITUDES_MULTIPLIER for key, value in (iv_config or {}).items()}
        logger.info("individual value: %s", iv)
        nature_bonus = get_nature_bonus(nature_name)

        def rounded(value: float) -> int:
            return int(value + 0.5)

        def other(base: float, key: str) -> int:
            result = rounded(rounded(MUL_BASE_OTHER * base + MUL_IV_OTHER * iv[key] + 10) * (1 + nature_bonus[key])) + 50
            return result
        
        hp_result = rounded(rounded(MUL_BASE_HP * base_hp + MUL_IV_HP * iv["hp"] + 70) * (1 + nature_bonus["hp"])) + 100
        return {
            "hp": hp_result,
            "atk": other(base_atk, "atk"),
            "spatk": other(base_spatk, "spatk"),
            "def": other(base_def, "def"),
            "spdef": other(base_spdef, "spdef"),
            "speed": other(base_speed, "speed"),
        }
    except Exception:
        import traceback
        traceback.print_exc()


@dataclass(frozen=True)
class CoreCatalog:
    """Resolved, read-only catalog data required by the rules engine."""

    skills: Mapping[str, Skill] = field(default_factory=dict)
    pokemon: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    ability_effects: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)
    boss_forms: Mapping[str, tuple[Mapping[str, Any], ...]] = field(default_factory=dict)
    skill_descriptions: Mapping[str, str] = field(default_factory=dict)
    ability_descriptions: Mapping[str, str] = field(default_factory=dict)
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
