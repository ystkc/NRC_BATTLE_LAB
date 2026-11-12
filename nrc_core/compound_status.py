"""保留完整身份的层状组合状态，计算时才展开属性修正。"""

from dataclasses import dataclass, field


def buff_modifiers(buff: dict[str, float]) -> dict[str, float]:
    """将规则中的属性缩写转换为可复用的每层修正定义。"""
    fields = {"atk": ("atk_up",), "spatk": ("spatk_up",),
              "all_atk": ("atk_up", "spatk_up"), "def": ("def_up",),
              "spdef": ("spdef_up",), "all_def": ("def_up", "spdef_up"), "speed": ("speed_up",)}
    modifiers = {}
    for name, amount in buff.items():
        for attribute in fields[name]:
            modifiers[attribute] = modifiers.get(attribute, 0.0) + amount
    return modifiers


@dataclass
class CompoundStatus:
    """层数与每层修正独立保存，不将派生值写回精灵。"""

    name: str
    stacks: int = 0
    modifiers: dict[str, float] = field(default_factory=dict)
    description: str = ""

    def modifier(self, attribute: str) -> float:
        """返回本次计算所需的派生值，不缓存、不消耗原始层数。"""
        return self.stacks * self.modifiers.get(attribute, 0.0)

    def observation(self, key: str) -> dict:
        """输出状态本身，避免向平台散发派生的普通增益。"""
        return {"name": key, "stacks": self.stacks, "unit": "层", "description": self.description}
