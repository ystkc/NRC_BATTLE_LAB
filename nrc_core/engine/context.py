"""效果执行上下文。"""

from typing import Dict, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from nrc_core.models import Pokemon, Skill, BattleState, SkillCategory


class Ctx:
    """
    效果执行上下文 — 替代散落各处的参数传递。

    所有 handler 函数签名: (tag, ctx) -> None
    handler 可以读写 ctx 上的任意字段来传递信息。
    """
    __slots__ = (
        "state", "user", "target", "skill",
        "result", "is_first", "team",
        "enemy_skill", "damage", "execute_ability",
    )

    def __init__(
        self,
        state: "BattleState",
        user: "Pokemon",
        target: "Pokemon",
        skill: "Skill" = None,
        result: Dict = None,
        is_first: bool = False,
        team: str = "a",
        enemy_skill: "Skill" = None,
        damage: int = 0,
        execute_ability: Callable = None,
    ):
        self.state = state
        self.user = user
        self.target = target
        self.skill = skill
        self.result = result if result is not None else {}
        self.is_first = is_first
        self.team = team
        self.enemy_skill = enemy_skill
        self.damage = damage
        # 由执行器传入能力入口，避免伤害处理器反向依赖执行器。
        self.execute_ability = execute_ability



