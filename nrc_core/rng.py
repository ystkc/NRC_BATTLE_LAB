"""Call-scoped random source used by the battle engine.

The legacy engine used the process-global random module directly.  Keeping the
source in a ContextVar makes seeded simulations reproducible and independent
across threads without changing the public battle API.
"""

from __future__ import annotations

import random
import hashlib
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


def derive_subseed(
    root_seed: int,
    decision_index: int,
    phase: str,
    side: str | int,
) -> int:
    """从对局根 seed 派生稳定的决策/阶段/侧别子 seed。

    使用版本化 SHA-256 编码，避免依赖 Python 的 hash 随机化；该函数只
    派生整数，不会读取或改变当前 ``rng_scope`` 中的随机源。
    """
    if isinstance(root_seed, bool) or not isinstance(root_seed, int):
        raise TypeError("root_seed must be an integer")
    if isinstance(decision_index, bool) or not isinstance(decision_index, int):
        raise TypeError("decision_index must be an integer")
    if not isinstance(phase, str) or not phase:
        raise ValueError("phase must be a non-empty string")
    if isinstance(side, bool) or not isinstance(side, (str, int)):
        raise TypeError("side must be a string or integer")
    payload = "|".join(
        ("nrc-battle-lab.rng.v1", str(root_seed), str(decision_index), phase, str(side))
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def derive_decision_seed(
    root_seed: int,
    decision_index: int,
    phase: str,
    side: str | int,
) -> int:
    """兼容性别名：派生一个决策阶段和侧别专属 seed。"""
    return derive_subseed(root_seed, decision_index, phase, side)


def decision_rng(
    root_seed: int,
    decision_index: int,
    phase: str,
    side: str | int,
) -> random.Random:
    """创建独立的决策子随机源，不改变当前全局/上下文随机源。"""
    return random.Random(derive_subseed(root_seed, decision_index, phase, side))

