from __future__ import annotations

import sqlite3
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from pypinyin import Style, lazy_pinyin
except ImportError:  # pragma: no cover - exercised only in minimal installs
    Style = None
    lazy_pinyin = None


def normalize_query(value: str) -> str:
    return re.sub(r"['\u2019\uFF07]", "", str(value or "")).strip().lower()


def initials(value: str) -> str:
    """Return searchable initials for Chinese text.

    ``pypinyin`` is optional so the recorder can still start in a minimal
    checkout. Without it, ASCII words remain searchable and Chinese input is
    matched by its literal prefix.
    """
    if not value:
        return ""
    if lazy_pinyin is None:
        return "".join(character.lower() for character in value if character.isascii())
    return "".join(lazy_pinyin(value, style=Style.FIRST_LETTER, errors="default")).lower()


def pinyin(value: str) -> str:
    if not value:
        return ""
    if lazy_pinyin is None:
        return "".join(character.lower() for character in value if character.isascii())
    return "".join(lazy_pinyin(value, errors="default")).lower()


@dataclass(frozen=True)
class Candidate:
    name: str
    initials: str
    pinyin: str
    kind: str
    meta: dict

    def to_json(self) -> dict:
        return {"name": self.name, "initials": self.initials, "kind": self.kind, **self.meta}


class _TrieNode:
    __slots__ = ("children", "values")

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.values: list[Candidate] = []


class PrefixIndex:
    """Trie-backed prefix search plus a bounded subsequence fallback."""

    def __init__(self, candidates: Iterable[Candidate]) -> None:
        self.candidates = list(candidates)
        self.root = _TrieNode()
        for candidate in self.candidates:
            node = self.root
            for character in candidate.initials:
                node = node.children.setdefault(character, _TrieNode())
                if len(node.values) < 80:
                    node.values.append(candidate)

    def search(self, query: str, limit: int = 12) -> list[Candidate]:
        normalized = normalize_query(query)
        if not normalized:
            return self.candidates[:limit]

        prefix_matches: list[Candidate] = []
        node = self.root
        for character in normalized:
            node = node.children.get(character)
            if node is None:
                break
        else:
            prefix_matches = list(node.values)

        scored: list[tuple[int, str, Candidate]] = []
        seen: set[str] = set()
        for candidate in prefix_matches:
            if candidate.name in seen:
                continue
            seen.add(candidate.name)
            scored.append((0, candidate.name, candidate))

        for candidate in self.candidates:
            if candidate.name in seen:
                continue
            score = self._score(candidate, normalized)
            if score is not None:
                scored.append((score, candidate.name, candidate))
                seen.add(candidate.name)
        scored.sort(key=lambda item: (item[0], len(item[1]), item[1]))
        return [item[2] for item in scored[:limit]]

    @staticmethod
    def _score(candidate: Candidate, query: str) -> int | None:
        initials_value = candidate.initials
        pinyin_value = candidate.pinyin
        name = candidate.name.lower()
        if query in initials_value:
            return 10 + initials_value.index(query)
        if query in pinyin_value:
            return 15 + pinyin_value.index(query)
        if query in name:
            return 20 + name.index(query)
        position = 0
        for character in query:
            position = initials_value.find(character, position)
            if position < 0:
                return None
            position += 1
        return 40 + position


class Catalog:
    """Read the normalized wiki database used by the simulator."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self.db_path = Path(db_path) if db_path else project_root / "data" / "nrc_wiki.db"
        self.asset_root = project_root / "data"
        self.pokemon: list[Candidate] = []
        self.skills: list[Candidate] = []
        self._load()
        self.pokemon_index = PrefixIndex(self.pokemon)
        self.skill_index = PrefixIndex(self.skills)

    def _load(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            pokemon_rows = connection.execute(
                """
                SELECT
                    sp.*,
                    COALESCE((
                        SELECT group_concat(e.name, ' / ')
                        FROM spirit_elements se JOIN elements e ON e.id = se.element_id
                        WHERE se.spirit_id = sp.id ORDER BY se.position
                    ), '') AS element_name,
                    COALESCE(a.name, '') AS ability_name,
                    COALESCE(av.path, '') AS avatar_path,
                    COALESCE(po.path, '') AS portrait_path
                FROM spirit_forms sp
                LEFT JOIN ability_catalog a ON a.id = sp.ability_id
                LEFT JOIN assets av ON av.id = sp.avatar_asset_id
                LEFT JOIN (
                    SELECT spirit_id, MIN(asset_id) AS asset_id
                    FROM spirit_portraits GROUP BY spirit_id
                ) portrait ON portrait.spirit_id = sp.id
                LEFT JOIN assets po ON po.id = portrait.asset_id
                ORDER BY sp.id
                """
            ).fetchall()
            skill_rows = connection.execute(
                """
                SELECT s.*, e.name AS element_name, COALESCE(a.path, '') AS skill_path
                FROM skill_catalog s
                LEFT JOIN elements e ON e.id = s.element_id
                LEFT JOIN assets a ON a.id = s.icon_asset_id
                ORDER BY s.id
                """
            ).fetchall()

        groups: dict[str, list[sqlite3.Row]] = {}
        for row in pokemon_rows:
            groups.setdefault(self._form_key(row), []).append(row)
        for forms in groups.values():
            forms.sort(key=self._form_order)

        self.pokemon = []
        for row in pokemon_rows:
            forms = groups[self._form_key(row)]
            base = forms[0]
            self.pokemon.append(Candidate(
                name=str(row["name"] or ""),
                initials=initials(str(row["name"] or "")),
                pinyin=pinyin(str(row["name"] or "")),
                kind="pokemon",
                meta={
                    "id": row["id"],
                    "element": row["element_name"] or "",
                    "ability": row["ability_name"] or row["ability_description"] or "",
                    "icon_url": self._asset_url(row["avatar_path"]),
                    "base_name": str(base["name"] or ""),
                    "forms": [self._form_json(form) for form in forms],
                },
            ))

        self.skills = []
        for row in skill_rows:
            name = str(row["name"] or "")
            self.skills.append(Candidate(
                name=name,
                initials=initials(name),
                pinyin=pinyin(name),
                kind="skill",
                meta={
                    "id": row["id"],
                    "element": row["element_name"] or "",
                    "category": row["category"] or "",
                    "power": row["power"] or 0,
                    "energy_cost": row["energy_cost"] or 0,
                    "icon_url": self._asset_url(row["skill_path"]),
                },
            ))

    def _form_json(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "element": row["element_name"] or "",
            "ability": row["ability_name"] or row["ability_description"] or "",
            "icon_url": self._asset_url(row["avatar_path"]),
            "portrait_url": self._asset_url(row["portrait_path"]) or self._asset_url(row["avatar_path"]),
            "catalog_number": row["catalog_number"] or "",
            "evolution_stage": row["evolution_stage"],
        }

    def search(self, kind: str, query: str, limit: int = 12) -> list[dict]:
        if kind == "weather":
            choices = [
                {"id": "", "name": "无天气", "aliases": "none no"},
                {"id": "rain", "name": "雨天", "aliases": "rain yt"},
                {"id": "snow", "name": "雪天", "aliases": "snow xt"},
                {"id": "sandstorm", "name": "沙暴", "aliases": "sandstorm sb"},
                {"id": "sunny", "name": "晴天", "aliases": "sunny qt"},
                {"id": "hail", "name": "冰雹", "aliases": "hail bb"},
            ]
            normalized = normalize_query(query)
            return [item for item in choices if not normalized or normalized in
                    normalize_query(item["name"] + " " + item["aliases"] + " " + pinyin(item["name"]))][:limit]
        index = self.pokemon_index if kind == "pokemon" else self.skill_index
        if kind != "pokemon":
            return [candidate.to_json() for candidate in index.search(query, limit)]
        result = []
        seen: set[int] = set()
        for candidate in index.search(query, len(self.pokemon)):
            item = candidate.to_json()
            base = item["forms"][0]
            if base["id"] in seen:
                continue
            seen.add(base["id"])
            result.append({**item, **base, "name": item["base_name"]})
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _form_key(row: sqlite3.Row) -> str:
        return str(row["catalog_number"] or row["wiki_id"] or row["name"])

    @staticmethod
    def _form_order(row: sqlite3.Row) -> tuple[int, int, int]:
        stage = row["evolution_stage"] if row["evolution_stage"] is not None else 999
        return (0 if stage == 1 else 1, int(stage), int(row["id"]))

    def _asset_url(self, relative_path: str | None) -> str | None:
        relative_path = str(relative_path or "").replace(chr(92), "/").lstrip("/")
        if not relative_path:
            return None
        candidate = (self.asset_root / relative_path).resolve()
        root = self.asset_root.resolve()
        if root not in candidate.parents or not candidate.is_file():
            return None
        return "/assets/" + candidate.relative_to(root).as_posix()
