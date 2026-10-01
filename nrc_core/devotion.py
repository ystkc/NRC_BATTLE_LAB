"""奉献状态的协议层定义。

随机奉献不直接展开为所有层数分配，而是保留一个紧凑的潜变量状态。
这样可以把战斗模拟和观测更新分开，避免在 MuZero 训练前就产生组合爆炸。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .unknown import Maybe


RANDOM_DEVOTION_EFFECTS = (
    "power_bonus",
    "cost_reduce",
    "hit_count_bonus",
    "life_drain",
    "enemy_poison",
)

RANDOM_DEVOTION_CAPS = {
    "power_bonus": 5,
    "cost_reduce": 10,
    "hit_count_bonus": 10,
    "life_drain": 10,
    "enemy_poison": 10,
}


@dataclass
class DevotionInput:
    """一方的奉献状态。

    ``specified_counts`` 是已经确定的指定奉献；``random_counts`` 是已经
    通过观测或己方信息确认的随机奉献分配。只有 ``random_draws`` 已知而
    ``random_counts`` 未知时，才表示“随机状态”，模拟器不会强行猜测其
    具体分配，而会返回潜变量分支。
    """

    specified_counts: Maybe[dict[str, int]] = field(default_factory=lambda: Maybe.from_value({}))
    random_draws: Maybe[int] = field(default_factory=lambda: Maybe.from_value(0))
    random_counts: Maybe[dict[str, int]] = field(default_factory=lambda: Maybe.unknown("random devotion unresolved"))
    visible_to_observer: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "specified_counts": self.specified_counts.to_json(),
            "random_draws": self.random_draws.to_json(),
            "random_counts": self.random_counts.to_json(),
            "visible_to_observer": self.visible_to_observer,
        }

    @property
    def random_is_unresolved(self) -> bool:
        return (
            self.random_draws.known
            and self.random_draws.exists
            and int(self.random_draws.value or 0) > 0
            and not (self.random_counts.known and self.random_counts.exists)
        )

