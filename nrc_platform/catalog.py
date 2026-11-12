"""Build the resolved in-memory catalog consumed by ``nrc_core``."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from nrc_core.catalog import CoreCatalog
from nrc_core.effect_data import ABILITY_EFFECTS, SKILL_EFFECTS
from nrc_core.models import Skill, SkillCategory, Type

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


def _lookup(mapping: dict[str, Any], raw: Any, default: Any) -> Any:
    text = str(raw or "").strip().lower()
    if text in mapping:
        return mapping[text]
    for key, value in mapping.items():
        if key and key in text:
            return value
    return default


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


def load_catalog(data_dir: str | Path | None = None) -> CoreCatalog:
    root = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data"
    database = root / "nrc_wiki.db"
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        element_names = {int(row["id"]): str(row["name"] or "") for row in connection.execute("SELECT id, name FROM elements")}
        ability_names = {int(row["id"]): str(row["name"] or "") for row in connection.execute("SELECT id, name FROM ability_catalog")}
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
        distributions: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in connection.execute("SELECT spirit_name, distribution_kind, item_name, percentage, position FROM distribution_records"):
            key = (str(row[0]), str(row[1]))
            distributions.setdefault(key, []).append({
                "item": str(row[2]),
                "percentage": float(str(row[3] or 0).replace("%", "")),
                "position": int(row[4] or 0),
            })
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
            }
        for record in pokemon.values():
            record["previous_forms"] = []
        for row in connection.execute("SELECT DISTINCT from_name, to_name FROM evolution_links"):
            previous, evolved = str(row[0]), str(row[1])
            if previous in pokemon and evolved in pokemon:
                pokemon[evolved]["previous_forms"].append(previous)
        for name, record in pokemon.items():
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
                skill_type=_lookup(_TYPE_ALIASES, element_names.get(row["element_id"], ""), Type.NORMAL),
                category=_lookup(_CATEGORY_ALIASES, row["category"], SkillCategory.STATUS),
                power=int(row["power"] or 0),
                energy_cost=int(row["energy_cost"] or 0),
                hit_count=max(1, hit_count),
                skill_id=str(row["wiki_id"] or row["id"]),
            )
            skill.description = description
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
    frozen_distributions = {key: tuple(sorted(value, key=lambda item: (-item["percentage"], item["position"]))) for key, value in distributions.items()}
    ability_effects = {name: tuple(value) for name, value in ABILITY_EFFECTS.items()}
    return CoreCatalog(
        skills=skills,
        pokemon=pokemon,
        ability_effects=ability_effects,
        boss_forms=boss_forms,
        skill_descriptions=descriptions,
        ability_descriptions=ability_descriptions,
        distributions=frozen_distributions,
    )


__all__ = ["load_catalog"]
