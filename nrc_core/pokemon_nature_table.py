"""
洛克王国性格加成表

性格是战斗元素，对宠物的两项能力值产生的修正效果。
修正作用于宠物等级、天赋、努力值等要素计算后的最终能力值。
# NRC PvP 性格表以 data/属性数值计算.md 为准。

"""

from typing import TypedDict
from .constant import NATURE_BONUS as NB, NATURE_FAIL as NF, NATURE_BALANCE as N0


class NatureBonus(TypedDict):
    """性格加成数据结构"""
    NatureBonus = TypedDict ("NatureBonus", {
        "hp": float,
        "atk": float,
        "def": float,
        "spatk": float,
        "spdef": float,
        "speed": float,
    })


# 性格加成表
# 格式：性格名 -> {atk, def, spatk, spdef, speed}
# 正值表示 +20% 增益，负值表示 -10% 减益，N0 表示无修正
NATURE_BONUSES: dict[str, NatureBonus] = {
    "逞强": {"hp": NF, "atk": NB, "def": N0, "spatk": N0, "spdef": N0, "speed": N0},
    "理性": {"hp": NF, "atk": N0, "def": N0, "spatk": NB, "spdef": N0, "speed": N0},
    "坦率": {"hp": NF, "atk": N0, "def": NB, "spatk": N0, "spdef": N0, "speed": N0},
    "焦虑": {"hp": NF, "atk": N0, "def": N0, "spatk": N0, "spdef": NB, "speed": N0},
    "热情": {"hp": NF, "atk": N0, "def": N0, "spatk": N0, "spdef": N0, "speed": NB},
    "沉默": {"hp": NB, "atk": NF, "def": N0, "spatk": N0, "spdef": N0, "speed": N0},
    "聪明": {"hp": N0, "atk": NF, "def": N0, "spatk": NB, "spdef": N0, "speed": N0},
    "稳重": {"hp": N0, "atk": NF, "def": NB, "spatk": N0, "spdef": N0, "speed": N0},
    "警惕": {"hp": N0, "atk": NF, "def": N0, "spatk": N0, "spdef": NB, "speed": N0},
    "胆小": {"hp": N0, "atk": NF, "def": N0, "spatk": N0, "spdef": N0, "speed": NB},
    "平和": {"hp": NB, "atk": N0, "def": N0, "spatk": NF, "spdef": N0, "speed": N0},
    "固执": {"hp": N0, "atk": NB, "def": N0, "spatk": NF, "spdef": N0, "speed": N0},
    "天真": {"hp": N0, "atk": N0, "def": NB, "spatk": NF, "spdef": N0, "speed": N0},
    "害羞": {"hp": N0, "atk": N0, "def": N0, "spatk": NF, "spdef": NB, "speed": N0},
    "开朗": {"hp": N0, "atk": N0, "def": N0, "spatk": NF, "spdef": N0, "speed": NB},
    "忧郁": {"hp": NB, "atk": N0, "def": NF, "spatk": N0, "spdef": N0, "speed": N0},
    "大胆": {"hp": N0, "atk": NB, "def": NF, "spatk": N0, "spdef": N0, "speed": N0},
    "专注": {"hp": N0, "atk": N0, "def": NF, "spatk": NB, "spdef": N0, "speed": N0},
    "温顺": {"hp": N0, "atk": N0, "def": NF, "spatk": N0, "spdef": NB, "speed": N0},
    "急躁": {"hp": N0, "atk": N0, "def": NF, "spatk": N0, "spdef": N0, "speed": NB},
    "粗心": {"hp": NB, "atk": N0, "def": N0, "spatk": N0, "spdef": NF, "speed": N0},
    "调皮": {"hp": N0, "atk": NB, "def": N0, "spatk": N0, "spdef": NF, "speed": N0},
    "偏执": {"hp": N0, "atk": N0, "def": N0, "spatk": NB, "spdef": NF, "speed": N0},
    "懒散": {"hp": N0, "atk": N0, "def": NB, "spatk": N0, "spdef": NF, "speed": N0},
    "莽撞": {"hp": N0, "atk": N0, "def": N0, "spatk": N0, "spdef": NF, "speed": NB},
    "踏实": {"hp": NB, "atk": N0, "def": N0, "spatk": N0, "spdef": N0, "speed": NF},
    "勇敢": {"hp": N0, "atk": NB, "def": N0, "spatk": N0, "spdef": N0, "speed": NF},
    "冷静": {"hp": N0, "atk": N0, "def": N0, "spatk": NB, "spdef": N0, "speed": NF},
    "悠闲": {"hp": N0, "atk": N0, "def": NB, "spatk": N0, "spdef": N0, "speed": NF},
    "慎重": {"hp": N0, "atk": N0, "def": N0, "spatk": N0, "spdef": NB, "speed": NF},
}

# 所有性格名称列表（按分类）
NATURES_BY_CATEGORY = {"nrc": list(NATURE_BONUSES)}

# 所有性格名称（平铺列表）
ALL_NATURES = list(NATURE_BONUSES)


def get_nature_bonus(nature: str) -> NatureBonus:
    """
    根据性格名称获取对应的加成效果。

    Args:
        nature: 性格名称（如 "固执", "胆小" 等）

    Returns:
        NatureBonus 字典，包含 atk, def, spatk, spdef, speed 的修正值

    Raises:
        KeyError: 如果性格名称不存在
    """
    if nature not in NATURE_BONUSES:
        raise KeyError(f"未知的性格：{nature}")
    return NATURE_BONUSES[nature]


def is_neutral_nature(nature: str) -> bool:
    """
    判断是否为平衡型性格（无修正）。

    Args:
        nature: 性格名称

    Returns:
        True 如果是平衡型性格，否则 False
    """
    return nature in NATURE_BONUSES and all(
        v == N0 for v in NATURE_BONUSES[nature].values()
    )
