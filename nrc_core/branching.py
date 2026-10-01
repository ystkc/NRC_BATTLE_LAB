"""技能/特性分支的稳定协议。

BranchDimension 是核心与审计器共同约定的 enum；未知的新分支可以通过 ``custom`` 扩展，
不需要修改历史记录格式。一个技能的多个维度会做笛卡尔积，但有数量上限，避免属性分支爆炸。
"""

from dataclasses import dataclass, field
from enum import Enum
from itertools import product
from typing import Any, Iterable, Optional


class BranchDimension(str, Enum):
    PROBABILITY = "probability"
    GULU_BALL = "gulu_ball"
    COUNTER = "counter"
    SELF_ATTRIBUTE = "self_attribute"
    OPPONENT_ATTRIBUTE = "opponent_attribute"
    CONDITION = "condition"
    WEATHER = "weather"
    RANDOM_TARGET = "random_target"
    DEVOTION_EFFECT = "devotion_effect"
    REFRACTION = "refraction"
    CUSTOM = "custom"


class AuditStatus(str, Enum):
    PARSED = "parsed"
    MANUAL_REQUIRED = "manual_required"
    AUDITED = "audited"
    PARTIAL = "partial"


@dataclass(frozen=True)
class BranchKey:
    dimension: BranchDimension
    value: str
    label: str = ""

    @property
    def code(self) -> str:
        return f"{self.dimension.value}:{self.value}"

    def to_json(self) -> dict:
        return {
            "dimension": self.dimension.value,
            "value": self.value,
            "label": self.label or self.value,
            "code": self.code,
        }


@dataclass
class BranchOption:
    key: BranchKey
    probability: Optional[float] = None
    probability_low: Optional[float] = None
    probability_high: Optional[float] = None
    evidence: str = ""
    triggered_effects: list[str] = field(default_factory=list)
    audited: bool = False
    audit_note: str = ""

    def to_json(self) -> dict:
        return {
            "key": self.key.to_json(),
            "probability": self.probability,
            "probability_low": self.probability_low,
            "probability_high": self.probability_high,
            "evidence": self.evidence,
            "triggered_effects": self.triggered_effects,
            "audited": self.audited,
            "audit_note": self.audit_note,
        }


def expand_branch_dimensions(
    dimensions: Iterable[list[BranchOption]],
    max_branches: int = 128,
) -> tuple[list[list[BranchOption]], Optional[str]]:
    groups = [group for group in dimensions if group]
    if not groups:
        return [[]], None
    count = 1
    for group in groups:
        count *= len(group)
    if count > max_branches:
        return [], f"分支笛卡尔积为 {count}，超过上限 {max_branches}"
    return [list(items) for items in product(*groups)], None
