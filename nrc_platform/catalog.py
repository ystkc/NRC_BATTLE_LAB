"""Build the resolved in-memory catalog consumed by ``nrc_core``."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidTag

from nrc_core.catalog import CoreCatalog
from nrc_core.effect_data import ABILITY_EFFECTS, SKILL_EFFECTS
from nrc_core.models import Skill, SkillCategory, Type
from nrc_core.pokemon_nature_table import NATURE_BONUSES
from wiki_crawler.distribution_cache import DEFAULT_CACHE, DEFAULT_DATABASE, DistributionCache

try:
    from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
except ImportError:
    SKILL_EFFECTS_GENERATED = {}


_TYPE_ALIASES = {
    "normal": Type.NORMAL, "普通": Type.NORMAL, "普通系": Type.NORMAL,
    "fire": Type.FIRE, "火": Type.FIRE, "火系": Type.FIRE,
    "water": Type.WATER, "水": Type.WATER, "水系": Type.WATER,
    "grass": Type.GRASS, "草": Type.GRASS, "草系": Type.GRASS,
    "electric": Type.ELECTRIC, "电": Type.ELECTRIC, "电系": Type.ELECTRIC,
    "ice": Type.ICE, "冰": Type.ICE, "冰系": Type.ICE,
    "fighting": Type.FIGHTING, "martial": Type.FIGHTING, "武": Type.FIGHTING, "武系": Type.FIGHTING,
    "poison": Type.POISON, "毒": Type.POISON, "毒系": Type.POISON,
    "ground": Type.GROUND, "地": Type.GROUND, "地系": Type.GROUND,
    "flying": Type.FLYING, "wing": Type.FLYING, "翼": Type.FLYING, "翼系": Type.FLYING,
    "psychic": Type.PSYCHIC, "幻": Type.PSYCHIC, "幻系": Type.PSYCHIC,
    "bug": Type.BUG, "insect": Type.BUG, "虫": Type.BUG, "虫系": Type.BUG,
    "ghost": Type.GHOST, "幽": Type.GHOST, "幽系": Type.GHOST,
    "dragon": Type.DRAGON, "龙": Type.DRAGON, "龙系": Type.DRAGON,
    "dark": Type.DARK, "devil": Type.DARK, "恶": Type.DARK, "恶系": Type.DARK,
    "steel": Type.STEEL, "machinery": Type.STEEL, "机械": Type.STEEL, "机械系": Type.STEEL,
    "fairy": Type.FAIRY, "cute": Type.FAIRY, "萌": Type.FAIRY, "萌系": Type.FAIRY,
    "light": Type.LIGHT, "光": Type.LIGHT, "光系": Type.LIGHT,
}

_CATEGORY_ALIASES = {
    "physical": SkillCategory.PHYSICAL, "物理": SkillCategory.PHYSICAL, "物攻": SkillCategory.PHYSICAL,
    "magical": SkillCategory.MAGICAL, "magic": SkillCategory.MAGICAL, "魔法": SkillCategory.MAGICAL, "魔攻": SkillCategory.MAGICAL,
    "defense": SkillCategory.DEFENSE, "防御": SkillCategory.DEFENSE,
    "status": SkillCategory.STATUS, "变化": SkillCategory.STATUS, "状态": SkillCategory.STATUS,
}

_DIMO_BOSS_FORMS = ("圣光迪莫", "圣水迪莫", "圣火迪莫", "圣草迪莫")
_REQUIRED_COLUMNS = {
    "elements": {"id", "name"},
    "ability_catalog": {"id", "name", "description", "source_url"},
    "skill_catalog": {"id", "name", "wiki_id", "element_id", "category", "energy_cost", "power", "description"},
    "spirit_forms": {
        "id", "name", "catalog_number", "evolution_stage", "is_lord", "ability_id",
        "base_hp", "base_speed", "base_attack", "base_magic_attack", "base_defense", "base_magic_defense",
        "ability_description", "weight_text", "weight_sort_value", "source_url",
    },
    "spirit_skills": {"spirit_name", "skill_name"},
    "evolution_links": {"from_name", "to_name", "from_number", "to_number", "from_stage", "to_stage"},
}


class CatalogDataError(ValueError):
    """目录结构或枚举值不满足核心契约。"""


def _validate_schema(connection: sqlite3.Connection) -> None:
    for table, required in _REQUIRED_COLUMNS.items():
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        actual = {str(row[1]) for row in rows}
        missing = sorted(required - actual)
        if missing:
            raise CatalogDataError(f"目录表 {table} 缺少字段: {', '.join(missing)}")


def _enum_value(mapping: dict[str, Any], raw: Any, *, field: str, record: str, default: Any) -> Any:
    text = str(raw or "").strip().lower()
    if not text:
        return default
    value = mapping.get(text)
    if value is None:
        raise CatalogDataError(f"目录字段 {field}={raw!r} 未知（记录 {record}）")
    return value


def _weight_range(text: Any, fallback: Any = None) -> tuple[float, float] | None:
    value = str(text or "").strip().replace("ＫＧ", "KG").replace("kg", "")
    numbers = re.findall(r"\d+(?:\.\d+)?", value)
    if len(numbers) >= 2:
        low, high = float(numbers[0]), float(numbers[1])
        if low <= high:
            return low, high
    if fallback not in (None, ""):
        try:
            point = float(fallback)
            return point, point
        except (TypeError, ValueError):
            pass
    return None


def _lookup(mapping: dict[str, Any], raw: Any, default: Any, *, field: str = "", record: str = "") -> Any:
    return _enum_value(mapping, raw, field=field, record=record, default=default)


def _skill_effects() -> dict[str, list[Any]]:
    effects = {name: list(value) for name, value in SKILL_EFFECTS_GENERATED.items() if value}
    effects.update({name: list(value) for name, value in SKILL_EFFECTS.items()})
    return effects


def _choice_options(description: str) -> tuple[str, ...]:
    match = re.search(r"选择[:：]?\s*([^。；;]+)", description or "")
    if not match:
        return ()
    options = tuple(item.strip() for item in re.split(r"或|/|、", match.group(1)) if item.strip())
    return options if len(options) == 2 else ()


@dataclass(frozen=True)
class PlatformCatalog(CoreCatalog):
    """在平台侧把目录中的精灵身份连接到培养分布缓存。"""

    distribution_cache: DistributionCache = field(default=DEFAULT_CACHE, repr=False, compare=False)

    def get_distribution(self, spirit_name: str, distribution_kind: str) -> tuple[Mapping[str, Any], ...]:
        """按精灵名称获取指定分布。"""
        return self.get_distributions(spirit_name, (distribution_kind,))[distribution_kind]

    def get_distributions(self, spirit_name: str, kinds: tuple[str, ...], *, allow_fetch: bool = True) -> dict[str, tuple[Mapping[str, Any], ...]]:
        """查询培养分布，Wiki 暂不可用时继续提供本地数据。"""
        record = self.get_pokemon(spirit_name)
        if allow_fetch and record is not None:
            try:
                return self.distribution_cache.get_distributions(spirit_name, kinds, source_url=record.get("source_url", ""))
            except (OSError, ValueError, KeyError, TypeError, InvalidTag) as error:
                logging.getLogger(__name__).warning("%s 培养统计暂不可用：%s", spirit_name, error)
        return self.distribution_cache.get_distributions(spirit_name, kinds, allow_fetch=False)


def load_catalog(data_dir: str | Path | None = None) -> PlatformCatalog:
    """从 SQLite 载入规则目录，并接入同一数据库的分布缓存。"""
    root = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data"
    database = root / "nrc_wiki.db"
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        _validate_schema(connection)
        element_names = {int(row["id"]): str(row["name"] or "") for row in connection.execute("SELECT id, name FROM elements")}
        ability_rows = list(connection.execute("SELECT id, name, source_url FROM ability_catalog"))
        ability_names = {int(row["id"]): str(row["name"] or "") for row in ability_rows}
        ability_sources = {int(row["id"]): str(row["source_url"] or "") for row in ability_rows}
        descriptions = {
            str(row["name"]): str(row["description"] or "")
            for row in connection.execute("SELECT name, description FROM skill_catalog")
        }
        ability_descriptions = {
            str(row["name"]): str(row["description"] or "")
            for row in connection.execute("SELECT name, description FROM ability_catalog")
        }
        skills_by_spirit: dict[str, list[str]] = {}
        for row in connection.execute("SELECT spirit_name, skill_name FROM spirit_skills ORDER BY id"):
            skills_by_spirit.setdefault(str(row[0]), []).append(str(row[1]))
        spirit_elements: dict[int, list[str]] = {}
        for row in connection.execute(
            "SELECT spirit_id, element_id FROM spirit_elements ORDER BY spirit_id, position"
        ):
            spirit_elements.setdefault(int(row[0]), []).append(element_names.get(int(row[1]), ""))
        pokemon: dict[str, dict[str, Any]] = {}
        for row in connection.execute("SELECT * FROM spirit_forms"):
            item = dict(row)
            name = str(item["name"])
            pokemon[name] = {
                "id": item["id"],
                "name": name,
                "catalog_number": item.get("catalog_number"),
                "types": spirit_elements.get(int(item["id"]), []),
                "ability": ability_names.get(int(item["ability_id"]), "") if item.get("ability_id") else "",
                "ability_source_url": ability_sources.get(int(item["ability_id"]), "") if item.get("ability_id") else "",
                "ability_description": item.get("ability_description") or "",
                "evolution_stage": item.get("evolution_stage"),
                "is_lord": bool(item.get("is_lord")),
                "base_hp": item.get("base_hp") or 0,
                "base_attack": item.get("base_attack") or 0,
                "base_magic_attack": item.get("base_magic_attack") or 0,
                "base_defense": item.get("base_defense") or 0,
                "base_magic_defense": item.get("base_magic_defense") or 0,
                "base_speed": item.get("base_speed") or 0,
                "skills": tuple(skills_by_spirit.get(name, ())),
                "skill_pool": tuple(skills_by_spirit.get(name, ())),
                "weight_range": _weight_range(item.get("weight_text"), item.get("weight_sort_value")),
                "source_url": str(item.get("source_url") or ""),
                "nature_modifiers": {key: dict(value) for key, value in NATURE_BONUSES.items()},
            }
        for record in pokemon.values():
            record["previous_forms"] = []
        evolution_previous: dict[str, str] = {}
        for row in connection.execute("SELECT DISTINCT from_name, to_name FROM evolution_links"):
            previous, evolved = str(row[0]), str(row[1])
            if previous in pokemon and evolved in pokemon:
                if evolved in evolution_previous and evolution_previous[evolved] != previous:
                    raise CatalogDataError(f"形态 {evolved} 存在多个前阶")
                evolution_previous[evolved] = previous
                pokemon[evolved]["previous_forms"].append(previous)
                pokemon[previous].setdefault("next_forms", []).append(evolved)
        for start in evolution_previous:
            seen: set[str] = set()
            current = start
            while current in evolution_previous:
                if current in seen:
                    raise CatalogDataError(f"进化图包含循环: {current}")
                seen.add(current)
                current = evolution_previous[current]
        for name, record in pokemon.items():
            record.setdefault("next_forms", [])
            if record["skills"]:
                continue
            base_name = str(name).split("（", 1)[0]
            inherited = skills_by_spirit.get(base_name, ())
            if inherited:
                record["skills"] = tuple(inherited)
        skill_effects = _skill_effects()
        skills: dict[str, Skill] = {}
        for row in connection.execute("SELECT * FROM skill_catalog ORDER BY id"):
            name = str(row["name"])
            description = str(row["description"] or "")
            hit_match = re.search(r"(?:([0-9]+)\s*(?:连击|杩炲嚮))", description)
            hit_count = int(hit_match.group(1)) if hit_match else 1
            skill = Skill(
                name=name,
                skill_type=_lookup(_TYPE_ALIASES, element_names.get(row["element_id"], ""), Type.NORMAL, field="element", record=name),
                category=_lookup(_CATEGORY_ALIASES, row["category"], SkillCategory.STATUS, field="category", record=name),
                power=int(row["power"] or 0),
                energy_cost=int(row["energy_cost"] or 0),
                hit_count=max(1, hit_count),
                skill_id=str(row["wiki_id"] or row["id"]),
            )
            skill.description = description
            skill.source_url = str(row["source_url"] or "")
            skill.effects = list(skill_effects.get(name, ()))
            skill.choice_options = _choice_options(description)
            skill._base_energy_cost = skill.energy_cost
            skill.burst = "迸发" in description
            skill.devotion_affected = "奉献" in description
            skills[name] = skill

    forms_by_number: dict[Any, list[dict[str, Any]]] = {}
    for record in pokemon.values():
        number = record.get("catalog_number")
        if number is not None and record.get("is_lord"):
            forms_by_number.setdefault(number, []).append(record)
    boss_forms = {
        name: tuple(forms_by_number.get(record.get("catalog_number"), ()))
        for name, record in pokemon.items()
        if not record.get("is_lord") and len(forms_by_number.get(record.get("catalog_number"), ())) == 1
    }
    dimo = pokemon.get("迪莫")
    resident_file = root / "resident_boss_ids.json"
    resident_ids: list[int] | None = None
    if resident_file.exists():
        try:
            resident_data = json.loads(resident_file.read_text(encoding="utf-8"))
            resident_ids = [int(value) for value in resident_data.get("迪莫", [])]
        except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            raise CatalogDataError(f"常驻首领映射文件无效: {resident_file}") from exc
    if resident_ids is not None:
        resident_records = [record for record in pokemon.values() if int(record.get("id", -1)) in resident_ids]
        resident_names = {str(record.get("name")) for record in resident_records}
        if len(resident_ids) != 4 or len(resident_records) != 4 or resident_names != set(_DIMO_BOSS_FORMS):
            raise CatalogDataError("常驻首领映射必须恰好包含四个迪莫首领形态")
        if any(not record.get("is_lord") for record in resident_records):
            raise CatalogDataError("常驻首领映射包含非首领形态")
        boss_forms["迪莫"] = tuple(pokemon[name] for name in _DIMO_BOSS_FORMS)
    missing = [name for name in _DIMO_BOSS_FORMS if name not in pokemon]
    invalid = [name for name in _DIMO_BOSS_FORMS if name in pokemon and not pokemon[name].get("is_lord")]
    if dimo is None:
        missing.insert(0, "迪莫")
    if invalid or missing:
        details = []
        if missing:
            details.append("缺失=" + ",".join(missing))
        if invalid:
            details.append("非首领=" + ",".join(invalid))
        raise CatalogDataError("迪莫首领映射无效: " + "; ".join(details))
    boss_forms["迪莫"] = tuple(pokemon[name] for name in _DIMO_BOSS_FORMS)
    ability_effects = {name: tuple(value) for name, value in ABILITY_EFFECTS.items()}
    evolution_next = {
        name: tuple(record.get("next_forms", ()))
        for name, record in pokemon.items()
    }
    weight_ranges = {name: record.get("weight_range") for name, record in pokemon.items()}
    source_snapshots = {
        "pokemon": {name: record.get("source_url", "") for name, record in pokemon.items()},
        "skills": {name: getattr(skill, "source_url", "") for name, skill in skills.items()},
        "abilities": {name: ability_sources.get(ability_id, "") for ability_id, name in ability_names.items()},
    }
    return PlatformCatalog(
        skills=skills,
        pokemon=pokemon,
        ability_effects=ability_effects,
        boss_forms=boss_forms,
        skill_descriptions=descriptions,
        ability_descriptions=ability_descriptions,
        distribution_cache=DEFAULT_CACHE if database.resolve() == DEFAULT_DATABASE else DistributionCache(database),
        skill_pools={name: tuple(values) for name, values in skills_by_spirit.items()},
        evolution_previous=dict(evolution_previous),
        evolution_next=evolution_next,
        nature_modifiers={name: dict(values) for name, values in NATURE_BONUSES.items()},
        weight_ranges=weight_ranges,
        source_snapshots=source_snapshots,
        resident_boss_ids=tuple(resident_ids or ()),
    )


__all__ = ["CatalogDataError", "load_catalog"]
