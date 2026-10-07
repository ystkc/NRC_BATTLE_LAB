"""Helpers for accepting compact creature input from user-facing clients."""

from __future__ import annotations

import re
from typing import Any, Mapping


STAT_ORDER = ("hp", "atk", "def", "spatk", "spdef", "speed")
_TOKEN_SPLIT = re.compile(r"[\s,\uFF0C]+")
_INTEGER = re.compile(r"^[0-9]+$")


def split_creature_spec(value: Any) -> tuple[str, dict[str, int]]:
    """Split ``name [hp]`` or ``name [hp atk def spatk spdef speed]``."""
    text = str(value or "").strip()
    if not text:
        return "", {}
    tokens = [token for token in _TOKEN_SPLIT.split(text) if token]
    numeric_start = len(tokens)
    while numeric_start and _INTEGER.fullmatch(tokens[numeric_start - 1]):
        numeric_start -= 1
    number_tokens = tokens[numeric_start:]
    if number_tokens and len(number_tokens) not in {1, 6}:
        raise ValueError("creature stats must contain either 1 HP value or 6 values")
    name = " ".join(tokens[:numeric_start]).strip()
    stats = {}
    if len(number_tokens) == 1:
        stats["hp"] = int(number_tokens[0])
    elif len(number_tokens) == 6:
        stats = {field: int(number) for field, number in zip(STAT_ORDER, number_tokens)}
    return name, stats


def merge_creature_spec(creature: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a creature mapping and move numeric suffixes into ``base.stats``."""
    result = dict(creature)
    raw_name = result.get("name") or result.get("display_name") or ""
    if isinstance(raw_name, Mapping):
        return result
    name, stats = split_creature_spec(raw_name)
    if name:
        result["name"] = name
    if stats:
        base = dict(result.get("base") or {})
        base["stats"] = {**dict(base.get("stats") or {}), **stats}
        result["base"] = base
    return result


__all__ = ["STAT_ORDER", "merge_creature_spec", "split_creature_spec"]
