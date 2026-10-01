"""显式表达“未知”和“不存在”的字段。

采集场景不能把未知值和空值混在一起。这个模块不要求调用方使用复杂的类型：
``Maybe.from_value(3)`` 表示已知值，``Maybe.unknown()`` 表示暂时未知，
``Maybe.absent()`` 表示已确认不存在。
"""

from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class Maybe(Generic[T]):
    known: bool = False
    exists: bool = True
    value: Optional[T] = None
    reason: str = ""

    @classmethod
    def from_value(cls, value: T) -> "Maybe[T]":
        return cls(known=True, exists=True, value=value)

    @classmethod
    def unknown(cls, reason: str = "") -> "Maybe[T]":
        return cls(known=False, exists=True, value=None, reason=reason)

    @classmethod
    def absent(cls, reason: str = "") -> "Maybe[T]":
        return cls(known=True, exists=False, value=None, reason=reason)

    @classmethod
    def from_json(cls, raw: Any) -> "Maybe[T]":
        if isinstance(raw, Maybe):
            return raw
        if isinstance(raw, dict) and "known" in raw:
            return cls(
                known=bool(raw.get("known")),
                exists=bool(raw.get("exists", True)),
                value=raw.get("value"),
                reason=str(raw.get("reason", "")),
            )
        if raw is None:
            return cls.unknown("输入未提供")
        return cls.from_value(raw)

    def to_json(self) -> dict:
        return {
            "known": self.known,
            "exists": self.exists,
            "value": self.value if self.known and self.exists else None,
            "reason": self.reason,
        }

    def or_default(self, default: T) -> T:
        return self.value if self.known and self.exists else default

