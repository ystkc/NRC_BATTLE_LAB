"""统一动作协议。

主动作互斥：技能、聚能、换人三者只能选一个；道具动作独立挂载，允许和主动作同时发生。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionKind(str, Enum):
    SKILL = "skill"
    CHARGE = "charge"
    SWITCH = "switch"
    ITEM = "item"
    PASS = "pass"


class ItemKind(str, Enum):
    WILLPOWER = "willpower"
    BOSS = "boss"
    UNKNOWN = "unknown"


@dataclass
class ActionIntent:
    kind: ActionKind
    skill_id: Optional[str] = None
    skill_name: Optional[str] = None
    skill_slot: Optional[int] = None
    switch_index: Optional[int] = None
    item_kind: Optional[ItemKind] = None
    item_payload: dict[str, Any] = field(default_factory=dict)
    source: str = "manual"

    @classmethod
    def skill(cls, name: str = "", slot: Optional[int] = None, skill_id: Optional[str] = None) -> "ActionIntent":
        return cls(ActionKind.SKILL, skill_id=skill_id, skill_name=name or None, skill_slot=slot)

    @classmethod
    def charge(cls) -> "ActionIntent":
        return cls(ActionKind.CHARGE)

    @classmethod
    def switch(cls, index: int) -> "ActionIntent":
        return cls(ActionKind.SWITCH, switch_index=index)

    @classmethod
    def item(cls, item_kind: ItemKind, payload: Optional[dict] = None) -> "ActionIntent":
        return cls(ActionKind.ITEM, item_kind=item_kind, item_payload=payload or {})

    def validate_primary(self) -> list[str]:
        errors: list[str] = []
        if self.kind == ActionKind.SKILL and not (self.skill_id or self.skill_name or self.skill_slot is not None):
            errors.append("技能动作必须提供 skill_name 或 skill_slot")
        if self.kind == ActionKind.SWITCH and self.switch_index is None:
            errors.append("换人动作必须提供 switch_index")
        if self.kind == ActionKind.ITEM:
            errors.append("道具只能放在 items 中，不能作为主动作")
        return errors

    def to_json(self) -> dict:
        return {
            "kind": self.kind.value,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "skill_slot": self.skill_slot,
            "switch_index": self.switch_index,
            "item_kind": self.item_kind.value if self.item_kind else None,
            "item_payload": self.item_payload,
            "source": self.source,
        }


@dataclass
class SideTurnInput:
    primary: ActionIntent
    items: list[ActionIntent] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors = self.primary.validate_primary()
        for item in self.items:
            if item.kind != ActionKind.ITEM:
                errors.append("items 中只能出现 item 动作")
        return errors
