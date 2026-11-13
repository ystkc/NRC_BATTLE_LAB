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
MUL_BASE_HP = np.float32(1.7)
MUL_IV_HP = np.float32(0.85)
MUL_BASE_OTHER = np.float32(1.1)
MUL_IV_OTHER = np.float32(0.55)



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
    中间值严格使用float32，并保留两次四舍五入的顺序。"""
    required = ("hp", "atk", "spatk", "def", "spdef", "speed")
    if not isinstance(iv_config, Mapping):
        raise ValueError("iv_config必须提供六个维度的映射")
    missing = [key for key in required if key not in iv_config]
    if missing:
        raise ValueError(f"iv_config缺少维度: {', '.join(missing)}")

    try:
        iv = {
            key: np.float32(int(iv_config[key]) * PVP_APTITUDES_MULTIPLIER)
            for key in required
        }
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"资质维度必须是整数: {exc}") from exc
    for key, value in iv.items():
        if not np.isfinite(value):
            raise ValueError(f"资质维度{key}必须是有限数值")

    bases = {}
    for key, value in {
        "hp": base_hp,
        "atk": base_atk,
        "spatk": base_spatk,
        "def": base_def,
        "spdef": base_spdef,
        "speed": base_speed,
    }.items():
        try:
            converted = np.float32(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"种族值维度{key}必须是数值: {exc}") from exc
        if not np.isfinite(converted):
            raise ValueError(f"种族值维度{key}必须是有限数值")
        bases[key] = converted

    logger.info("individual value: %s", iv)
    if str(nature_name).strip().lower() in {"neutral", "中性", "无修正"}:
        nature_bonus = {key: np.float32(0.0) for key in required}
    else:
        nature_bonus = get_nature_bonus(nature_name)
    one = np.float32(1.0)

    def rounded(value: np.float32) -> int:
        return int(np.floor(np.float32(value) + np.float32(0.5)))

    def other(key: str) -> int:
        base_value = bases[key]
        first = np.float32(MUL_BASE_OTHER * base_value + MUL_IV_OTHER * iv[key] + np.float32(10.0))
        result = rounded(np.float32(rounded(first)) * np.float32(one + np.float32(nature_bonus[key]))) + 50
        return result

    hp_first = np.float32(MUL_BASE_HP * bases["hp"] + MUL_IV_HP * iv["hp"] + np.float32(70.0))
    hp_result = rounded(np.float32(rounded(hp_first)) * np.float32(one + np.float32(nature_bonus["hp"]))) + 100
    return {
        "hp": hp_result,
        "atk": other("atk"),
        "spatk": other("spatk"),
        "def": other("def"),
        "spdef": other("spdef"),
        "speed": other("speed"),
    }


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
    # 平台解析后一次注入的辅助目录；核心不反查数据库或文件。
    skill_pools: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    evolution_previous: Mapping[str, str] = field(default_factory=dict)
    evolution_next: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    nature_modifiers: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    weight_ranges: Mapping[str, tuple[float, float] | None] = field(default_factory=dict)
    source_snapshots: Mapping[str, Any] = field(default_factory=dict)
    resident_boss_ids: tuple[int, ...] = ()

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

    def get_skill_pool(self, spirit_name: str) -> tuple[str, ...]:
        """读取平台预解析的精灵技能池。"""
        return tuple(self.skill_pools.get(spirit_name, ()))

    def get_weight_range(self, spirit_name: str) -> tuple[float, float] | None:
        """读取平台预解析的体重范围。"""
        value = self.weight_ranges.get(spirit_name)
        return tuple(value) if value is not None else None

    def get_nature_modifiers(self) -> Mapping[str, Mapping[str, float]]:
        """读取平台注入的性格修正快照。"""
        return self.nature_modifiers

    def get_ability_effects(self, ability: str | None) -> list[Any]:
        if not ability:
            return []
        name = str(ability).split(":", 1)[0].split("：", 1)[0].strip()
        return list(self.ability_effects.get(name, ()))

    def get_skill_description(self, name: str | None) -> str:
        return str(self.skill_descriptions.get(str(name), "")) if name else ""

EMPTY_CATALOG = CoreCatalog()
