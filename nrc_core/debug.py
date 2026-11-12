"""Opt-in diagnostic logging for the deterministic battle core."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, TextIO

NRC_CORE_LOG = 'damage'

_ALL = "all"
_DEFAULT_CATEGORIES = {
    "turn",
    "display",
    "damage",
    "attributes",
    "skill",
    "status",
    "ability",
    "switch",
    "energy",
}
_categories: set[str] = set()
_stream: TextIO = sys.stdout


def configure_core_logging(spec: str | None = None, *, stream: TextIO | None = None) -> set[str]:
    """Configure console diagnostics; empty spec disables logging.

    ``spec`` accepts ``all``/``1`` or a comma-separated category list.  The
    environment variable ``NRC_CORE_LOG`` is used when ``spec`` is omitted.
    """
    global _categories, _stream
    raw = NRC_CORE_LOG if spec is None else str(spec)
    raw = raw.strip().lower()
    _categories = set(_DEFAULT_CATEGORIES) if raw in {"1", "true", "yes", _ALL} else {
        item.strip() for item in raw.split(",") if item.strip()
    }
    if stream is not None:
        _stream = stream
    return set(_categories)


def core_log(category: str, event: str, **fields: Any) -> None:
    if category not in _categories and _ALL not in _categories:
        return
    payload = {"event": event, **fields}
    print(f"[nrc_core:{category}] {json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)}", file=_stream, flush=True)


def core_logging_enabled(category: str) -> bool:
    return category in _categories or _ALL in _categories


configure_core_logging()

__all__ = ["configure_core_logging", "core_log", "core_logging_enabled"]
