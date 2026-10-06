"""Population priors extracted from PvP usage distributions.

Nature and blood are categorical distributions and sum to one. Skill and
talent are inclusion marginals and sum approximately to the number of
selected slots: four skills and at most three talents.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import math
from pathlib import Path
import random
import sqlite3
from typing import Any, Mapping


def _percentage(value: object) -> float:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0.0
    if text.endswith("%"):
        text = text[:-1]
        scale = 0.01
    else:
        try:
            number = float(text)
        except ValueError:
            return 0.0
        scale = 1.0 if number <= 1.0 else 0.01
    try:
        return max(0.0, min(1.0, float(text) * scale))
    except ValueError:
        return 0.0


def _sample_cardinality(expected_count: float, maximum: int, rng: random.Random) -> int:
    """Sample a bounded count whose expectation is approximately expected_count."""
    expected_count = max(0.0, min(float(maximum), expected_count))
    if expected_count <= 1e-9:
        return 0
    if expected_count >= maximum - 1e-9:
        return maximum
    low = -20.0
    high = 20.0
    for _ in range(80):
        midpoint = (low + high) / 2.0
        weights = [math.exp(midpoint * count) for count in range(maximum + 1)]
        normalizer = sum(weights)
        mean = sum(count * weight for count, weight in enumerate(weights)) / normalizer
        if mean < expected_count:
            low = midpoint
        else:
            high = midpoint
    weights = [math.exp(((low + high) / 2.0) * count) for count in range(maximum + 1)]
    return rng.choices(list(range(maximum + 1)), weights=weights, k=1)[0]


def _sample_fixed_cardinality(probabilities: Mapping[str, float], count: int, rng: random.Random, *, epsilon: float = 1e-5) -> tuple[str, ...]:
    """Sample exactly count items from inclusion marginals.

    The conditional-Bernoulli product-of-odds distribution respects the fixed
    cardinality constraint without treating six talent dimensions as six
    mutually exclusive categories.
    """
    items = list(probabilities)
    if count <= 0 or not items:
        return ()
    count = min(count, len(items))
    odds = []
    for item in items:
        probability = max(epsilon, min(1.0 - epsilon, float(probabilities[item])))
        odds.append(probability / (1.0 - probability))
    suffix = [[0.0] * (count + 1) for _ in range(len(items) + 1)]
    suffix[-1][0] = 1.0
    for index in range(len(items) - 1, -1, -1):
        suffix[index][0] = suffix[index + 1][0]
        for selected in range(1, count + 1):
            suffix[index][selected] = suffix[index + 1][selected] + odds[index] * suffix[index + 1][selected - 1]
    selected_items: list[str] = []
    remaining = count
    for index, item in enumerate(items):
        if remaining == 0:
            break
        include_mass = odds[index] * suffix[index + 1][remaining - 1]
        exclude_mass = suffix[index + 1][remaining]
        total = include_mass + exclude_mass
        include_probability = include_mass / total if total > 0.0 else 0.0
        if rng.random() < include_probability:
            selected_items.append(item)
            remaining -= 1
    if remaining:
        for item in sorted(items, key=lambda value: probabilities[value], reverse=True):
            if item not in selected_items:
                selected_items.append(item)
                remaining -= 1
                if remaining == 0:
                    break
    return tuple(selected_items)


def _sample_categorical(probabilities: Mapping[str, float], rng: random.Random, *, temperature: float = 1.0) -> str | None:
    if not probabilities:
        return None
    temperature = max(0.05, float(temperature))
    items = list(probabilities)
    weights = [max(1e-6, float(probabilities[item])) ** (1.0 / temperature) for item in items]
    return rng.choices(items, weights=weights, k=1)[0]


@dataclass(frozen=True)
class PopulationBuild:
    skills: tuple[str, ...]
    personality: str | None
    bloodline: str | None
    aptitudes: tuple[str, ...]
    aptitude_values: Mapping[str, int]
    log_score: float


class PopulationPrior:
    """PvP prior with deterministic top-K builds and optional sampling helpers."""

    def __init__(self, records: Mapping[str, Mapping[str, Mapping[str, float]]], *, source: str, source_digest: str, nature_tail_floor: float = 1e-4) -> None:
        self.records = {spirit: {kind: dict(values) for kind, values in kinds.items()} for spirit, kinds in records.items()}
        self.source = source
        self.source_digest = source_digest
        nature_universe = {item for kinds in self.records.values() for item in kinds.get("nature", {})}
        if nature_tail_floor < 0.0 or nature_tail_floor * len(nature_universe) >= 1.0:
            raise ValueError("nature_tail_floor must leave positive probability mass")
        for kinds in self.records.values():
            observed = kinds.get("nature")
            if not observed:
                continue
            missing = nature_universe - set(observed)
            observed_total = sum(observed.values())
            if observed_total <= 0.0:
                continue
            missing_mass = nature_tail_floor * len(missing)
            scale = max(0.0, 1.0 - missing_mass) / observed_total
            kinds["nature"] = {**{item: value * scale for item, value in observed.items()}, **{item: nature_tail_floor for item in missing}}

    @classmethod
    def from_database(cls, database: str | Path, *, nature_tail_floor: float = 1e-4) -> "PopulationPrior":
        path = Path(database)
        records: dict[str, dict[str, dict[str, float]]] = {}
        with sqlite3.connect(path) as connection:
            rows = connection.execute("SELECT distribution_kind, spirit_name, item_name, percentage FROM distribution_records ORDER BY spirit_name, distribution_kind, position, item_name").fetchall()
        for kind, spirit, item, percentage in rows:
            records.setdefault(str(spirit), {}).setdefault(str(kind), {})[str(item)] = _percentage(percentage)
        return cls(records, source=str(path), source_digest=hashlib.sha256(path.read_bytes()).hexdigest()[:16], nature_tail_floor=nature_tail_floor)

    @classmethod
    def from_csv_directory(cls, directory: str | Path, *, nature_tail_floor: float = 1e-4) -> "PopulationPrior":
        import csv
        directory = Path(directory)
        file_names = {"skill": "skill_distributions.csv", "nature": "personality_distributions.csv", "blood": "bloodline_distributions.csv", "talent": "talent_distributions.csv"}
        records: dict[str, dict[str, dict[str, float]]] = {}
        digest = hashlib.sha256()
        for kind, filename in file_names.items():
            path = directory / filename
            digest.update(path.read_bytes())
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    spirit = str(row.get("精灵", "")).strip()
                    item = str(row.get("名称", "")).strip()
                    if spirit and item:
                        records.setdefault(spirit, {}).setdefault(kind, {})[item] = _percentage(row.get("百分比"))
        return cls(records, source=str(directory), source_digest=digest.hexdigest()[:16], nature_tail_floor=nature_tail_floor)

    def spirits(self) -> tuple[str, ...]:
        return tuple(sorted(self.records))

    def distribution(self, spirit: str, kind: str) -> dict[str, float]:
        return dict(self.records.get(spirit, {}).get(kind, {}))

    def summary(self, spirit: str | None = None) -> dict[str, Any]:
        names = [spirit] if spirit else list(self.spirits())
        result: dict[str, Any] = {"source": self.source, "source_digest": self.source_digest, "spirits": {}}
        for name in names:
            if name not in self.records:
                continue
            result["spirits"][name] = {
                "skill_count": len(self.distribution(name, "skill")),
                "skill_inclusion_sum": round(sum(self.distribution(name, "skill").values()), 6),
                "personality_count": len(self.distribution(name, "nature")),
                "bloodline_count": len(self.distribution(name, "blood")),
                "aptitude_count": len(self.distribution(name, "talent")),
                "aptitude_inclusion_sum": round(sum(self.distribution(name, "talent").values()), 6),
            }
        return result

    def sample_build(self, spirit: str, rng: random.Random, *, skill_count: int = 4, aptitude_count: int | None = None, aptitude_iv: int = 54, categorical_temperature: float = 1.0) -> PopulationBuild:
        skills = self.distribution(spirit, "skill")
        personalities = self.distribution(spirit, "nature")
        bloodlines = self.distribution(spirit, "blood")
        aptitudes = self.distribution(spirit, "talent")
        selected_skills = _sample_fixed_cardinality(skills, skill_count, rng)
        if aptitude_count is None:
            selected_aptitude_count = _sample_cardinality(sum(aptitudes.values()), 3, rng)
        else:
            selected_aptitude_count = min(3, max(0, aptitude_count))
        selected_aptitudes = _sample_fixed_cardinality(aptitudes, selected_aptitude_count, rng)
        if not 0 <= aptitude_iv <= 60:
            raise ValueError("aptitude_iv must be between 0 and 60")
        aptitude_values = {item: aptitude_iv for item in selected_aptitudes}
        personality = _sample_categorical(personalities, rng, temperature=categorical_temperature)
        bloodline = _sample_categorical(bloodlines, rng, temperature=categorical_temperature)
        score_parts = [skills.get(item, 1e-6) for item in selected_skills]
        score_parts.extend(aptitudes.get(item, 1e-6) for item in selected_aptitudes)
        if personality:
            score_parts.append(personalities.get(personality, 1e-6))
        if bloodline:
            score_parts.append(bloodlines.get(bloodline, 1e-6))
        score = sum(math.log(max(1e-6, value)) for value in score_parts)
        return PopulationBuild(selected_skills, personality, bloodline, selected_aptitudes, aptitude_values, score)

    @staticmethod
    def _top_items(probabilities: Mapping[str, float], count: int) -> tuple[str, ...]:
        """Select by probability, preserving source order for exact ties."""
        ranked = sorted(enumerate(probabilities.items()), key=lambda pair: (-float(pair[1][1]), pair[0]))
        return tuple(item for _, (item, _) in ranked[:max(0, count)])

    def top_build(self, spirit: str, *, skill_count: int = 4, aptitude_count: int = 3, aptitude_iv: int = 60) -> PopulationBuild:
        """Build the deterministic population representative used in phase one.

        Aptitude rows are inclusion probabilities, not six-way categories. The
        representative therefore selects exactly the three highest dimensions
        and assigns grade 10 (the core equivalent is IV 60) to them.
        """
        if not 0 <= aptitude_iv <= 60:
            raise ValueError("aptitude_iv must be between 0 and 60")
        skills = self.distribution(spirit, "skill")
        personalities = self.distribution(spirit, "nature")
        bloodlines = self.distribution(spirit, "blood")
        aptitudes = self.distribution(spirit, "talent")
        selected_skills = self._top_items(skills, skill_count)
        selected_aptitudes = self._top_items(aptitudes, min(3, aptitude_count))
        personality_items = self._top_items(personalities, 1)
        bloodline_items = self._top_items(bloodlines, 1)
        personality = personality_items[0] if personality_items else None
        bloodline = bloodline_items[0] if bloodline_items else None
        score_parts = [skills.get(item, 1e-6) for item in selected_skills]
        score_parts.extend(aptitudes.get(item, 1e-6) for item in selected_aptitudes)
        if personality:
            score_parts.append(personalities.get(personality, 1e-6))
        if bloodline:
            score_parts.append(bloodlines.get(bloodline, 1e-6))
        score = sum(math.log(max(1e-6, value)) for value in score_parts)
        return PopulationBuild(
            selected_skills,
            personality,
            bloodline,
            selected_aptitudes,
            {item: aptitude_iv for item in selected_aptitudes},
            score,
        )

    @staticmethod
    def _value(raw: Any) -> Any:
        if isinstance(raw, Mapping) and "value" in raw:
            return raw["value"]
        return raw

    def candidate_setups(self, root_setup: Mapping[str, Any], *, count: int = 1, seed: int = 0, aptitude_count: int | None = 3, aptitude_iv: int = 60, categorical_temperature: float = 1.0) -> list[dict[str, Any]]:
        if count <= 0:
            raise ValueError("count must be positive")
        candidates: list[dict[str, Any]] = []
        for _ in range(count):
            setup = copy.deepcopy(dict(root_setup))
            candidate_score = 0.0
            opponent_team = setup.get("opponent_team") or {}
            for creature in opponent_team.get("creatures") or []:
                spirit = str(self._value(creature.get("name")) or "") if isinstance(creature, Mapping) else ""
                if not spirit or spirit not in self.records:
                    continue
                build = self.top_build(spirit, aptitude_count=3 if aptitude_count is None else aptitude_count, aptitude_iv=aptitude_iv)
                candidate_score += build.log_score
                creature["skills"] = [{"name": {"known": True, "exists": True, "value": skill}, "source": "population_prior"} for skill in build.skills]
                base = creature.setdefault("base", {})
                if build.personality:
                    base["nature"] = {"known": True, "exists": True, "value": build.personality}
                if build.bloodline:
                    base["bloodline_attributes"] = {"known": True, "exists": True, "value": [build.bloodline]}
                raw_stats = base.get("stats")
                has_explicit_stats = bool(raw_stats) and not (isinstance(raw_stats, Mapping) and "known" in raw_stats and (not raw_stats.get("known") or not raw_stats.get("exists", True)))
                if build.aptitudes and not has_explicit_stats:
                    from nrc_core.pokemon_db import calc_combat_stats, get_pokemon
                    species = get_pokemon(spirit)
                    if species:
                        iv_config = {"hp": 0, "atk": 0, "spatk": 0, "def": 0, "spdef": 0, "speed": 0}
                        for aptitude in build.aptitudes:
                            stat_key = {"生命": "hp", "物攻": "atk", "魔攻": "spatk", "物防": "def", "魔防": "spdef", "速度": "speed"}.get(aptitude)
                            stat_key = {"\u751f\u547d": "hp", "\u7269\u653b": "atk", "\u9b54\u653b": "spatk", "\u7269\u9632": "def", "\u9b54\u9632": "spdef", "\u901f\u5ea6": "speed"}.get(aptitude, stat_key)
                            if stat_key:
                                iv_config[stat_key] = aptitude_iv
                        computed = calc_combat_stats(
                            species["base_hp"], species["base_attack"], species["base_magic_attack"],
                            species["base_defense"], species["base_magic_defense"], species["base_speed"],
                            iv_config=iv_config, nature_name=build.personality or "坦率",
                        )
                        base["stats"] = {"known": True, "exists": True, "value": computed}
                metadata = dict(creature.get("metadata") or {})
                metadata["population_prior"] = {"source": self.source, "source_digest": self.source_digest, "selection_mode": "deterministic-top-k", "skill_count": len(build.skills), "aptitude_count": len(build.aptitudes), "aptitude_grade": 10, "aptitude_selection": list(build.aptitudes), "aptitude_iv_assumption": aptitude_iv, "aptitude_values": dict(build.aptitude_values), "log_score": build.log_score}
                creature["metadata"] = metadata
            candidates.append({"setup": setup, "weight": 1.0})
        return candidates


__all__ = ["PopulationBuild", "PopulationPrior"]
