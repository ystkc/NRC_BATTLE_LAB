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
    def __init__(self, db_path: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self.db_path = Path(db_path) if db_path else project_root / "data" / "nrc.db"
        self.pokemon: list[Candidate] = []
        self.skills: list[Candidate] = []
        self._load()
        self.pokemon_index = PrefixIndex(self.pokemon)
        self.skill_index = PrefixIndex(self.skills)

    def _load(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            pokemon_rows = connection.execute(
                "SELECT * FROM pokemon ORDER BY id"
            ).fetchall()
            skill_rows = connection.execute(
                "SELECT id, name, element, category, power, energy_cost FROM skill ORDER BY name"
            ).fetchall()
        pokemon_rows_by_form: dict[str, list[sqlite3.Row]] = {}
        for row in pokemon_rows:
            pokemon_rows_by_form.setdefault(self._form_key(row), []).append(row)
        for forms in pokemon_rows_by_form.values():
            forms.sort(key=self._form_order)
        self.pokemon = [
            Candidate(
                name=row["name"],
                initials=initials(row["name"]),
                pinyin=pinyin(row["name"]),
                kind="pokemon",
                meta={
                    "id": row["id"],
                    "element": row["element"],
                    "ability": row["ability"] or "",
                    "icon_url": self._spirit_icon(row["spirit_no"], row["name"]),
                    "base_name": re.sub(
                        r"[（(].*?[）)]", "", pokemon_rows_by_form[self._form_key(row)][0]["name"]
                    ).strip(),
                    "forms": [
                        {
                            "id": form["id"],
                            "name": form["name"],
                            "element": form["element"],
                            "ability": form["ability"] or "",
                            "icon_url": self._spirit_icon(form["spirit_no"], form["name"]),
                            "portrait_url": self._portrait(form),
                        }
                        for form in pokemon_rows_by_form[self._form_key(row)]
                    ],
                },
            )
            for row in pokemon_rows
        ]
        self.skills = [
            Candidate(
                name=row["name"],
                initials=initials(row["name"]),
                pinyin=pinyin(row["name"]),
                kind="skill",
                meta={
                    "id": row["id"],
                    "element": row["element"],
                    "category": row["category"],
                    "power": row["power"] or 0,
                    "energy_cost": row["energy_cost"] or 0,
                    "icon_url": self._skill_icon(row["name"]),
                },
            )
            for row in skill_rows
        ]

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
        seen = set()
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
        return str(row["spirit_no"] or re.sub(r"[（(].*?[）)]", "", row["name"]).strip())

    @staticmethod
    def _form_order(row: sqlite3.Row) -> tuple[int, int, int]:
        form = row["wiki_form"] if "wiki_form" in row.keys() else ""
        name = row["name"]
        basic = any(label in (form or "") + name for label in ("基本", "基础", "本来的样子"))
        return (0 if basic else 1, 1 if "（" in name or "(" in name else 0, row["id"])

    @staticmethod
    def _portrait(row: sqlite3.Row) -> str | None:
        if "portrait_path" in row.keys() and row["portrait_path"]:
            project_root = Path(__file__).resolve().parents[1]
            candidate = (project_root / row["portrait_path"]).resolve()
            asset_root = (project_root / "data").resolve()
            if asset_root in candidate.parents and candidate.is_file():
                return "/assets/" + candidate.relative_to(asset_root).as_posix()
        return Catalog._spirit_icon(row["spirit_no"], row["name"])

    @staticmethod
    def _spirit_icon(spirit_no: str | None, name: str) -> str | None:
        if not spirit_no:
            return None
        safe_name = re.sub(r"[^\w\u4e00-\u9fff]", "_", name)
        filename = f"{str(spirit_no).replace('.', '')}_{safe_name}.png"
        project_root = Path(__file__).resolve().parents[1]
        if (project_root / "data" / "spirit_icons" / filename).exists():
            return f"/assets/spirit_icons/{filename}"
        return None

    @staticmethod
    def _skill_icon(name: str) -> str | None:
        safe_name = re.sub(r"[^\w\u4e00-\u9fff.-]", "_", name).strip("._") or "asset"
        filename = f"{safe_name}.png"
        project_root = Path(__file__).resolve().parents[1]
        if (project_root / "data" / "skill_icons" / filename).exists():
            return f"/assets/skill_icons/{filename}"
        return None
