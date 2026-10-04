"""Call-scoped random source used by the battle engine.

The legacy engine used the process-global random module directly.  Keeping the
source in a ContextVar makes seeded simulations reproducible and independent
across threads without changing the public battle API.
"""

from __future__ import annotations

import random
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterable, TypeVar


_T = TypeVar("_T")
_current: ContextVar[random.Random | None] = ContextVar("nrc_rng", default=None)


def get_rng() -> random.Random:
    return _current.get() or random


@contextmanager
def rng_scope(rng: random.Random):
    token = _current.set(rng)
    try:
        yield rng
    finally:
        _current.reset(token)


def choice(values: Iterable[_T]) -> _T:
    return get_rng().choice(tuple(values))


def shuffle(values: list[_T]) -> None:
    get_rng().shuffle(values)


def randrange(*args: int) -> int:
    return get_rng().randrange(*args)

