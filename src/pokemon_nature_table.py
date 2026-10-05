"""
洛克王国性格加成表

性格是战斗元素，对宠物的两项能力值产生的修正效果。
修正作用于宠物等级、天赋、努力值等要素计算后的最终能力值。

数据来源：百度百科 - 洛克王国性格
https://baike.baidu.com/item/性格/49946473
"""

from typing import TypedDict


class NatureBonus(TypedDict):
    """性格加成数据结构"""
    hp: float
    atk: float    # 攻击修正
    defense: float  # 防御修正
    sp_atk: float  # 魔攻修正
    sp_defense: float  # 魔抗修正
    speed: float  # 速度修正


# 性格加成表
# 格式：性格名 -> {atk, defense, sp_atk, sp_defense, speed}
# 正值表示 +20% 增益，负值表示 -10% 减益，0.0 表示无修正
NATURE_BONUSES: dict[str, NatureBonus] = {
    # ==================== 攻击型（+攻击）====================
    "孤僻": {
        "atk": 0.2,
        "defense": -0.1,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "固执": {
        "atk": 0.2,
        "defense": 0.0,
        "sp_atk": -0.1,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "调皮": {
        "atk": 0.2,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": -0.1,
        "speed": 0.0,
    },
    "勇敢": {
        "atk": 0.2,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": -0.1,
    },

    # ==================== 防御型（+防御）====================
    "大胆": {
        "atk": -0.1,
        "defense": 0.2,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "淘气": {
        "atk": 0.0,
        "defense": 0.2,
        "sp_atk": -0.1,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "无虑": {
        "atk": 0.0,
        "defense": 0.2,
        "sp_atk": 0.0,
        "sp_defense": -0.1,
        "speed": 0.0,
    },
    "悠闲": {
        "atk": 0.0,
        "defense": 0.2,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": -0.1,
    },

    # ==================== 魔攻型（+魔攻）====================
    "保守": {
        "atk": -0.1,
        "defense": 0.0,
        "sp_atk": 0.2,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "稳重": {
        "atk": 0.0,
        "defense": -0.1,
        "sp_atk": 0.2,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "马虎": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.2,
        "sp_defense": -0.1,
        "speed": 0.0,
    },
    "冷静": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.2,
        "sp_defense": 0.0,
        "speed": -0.1,
    },

    # ==================== 魔抗型（+魔抗）====================
    "沉着": {
        "atk": -0.1,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.2,
        "speed": 0.0,
    },
    "温顺": {
        "atk": 0.0,
        "defense": -0.1,
        "sp_atk": 0.0,
        "sp_defense": 0.2,
        "speed": 0.0,
    },
    "慎重": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": -0.1,
        "sp_defense": 0.2,
        "speed": 0.0,
    },
    "狂妄": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.2,
        "speed": -0.1,
    },

    # ==================== 速度型（+速度）====================
    "胆小": {
        "atk": -0.1,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.2,
    },
    "急躁": {
        "atk": 0.0,
        "defense": -0.1,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.2,
    },
    "开朗": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": -0.1,
        "sp_defense": 0.0,
        "speed": 0.2,
    },
    "天真": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": -0.1,
        "speed": 0.2,
    },

    # ==================== 平衡型（无修正）====================
    "坦率": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "害羞": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "认真": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "实干": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
    "浮躁": {
        "atk": 0.0,
        "defense": 0.0,
        "sp_atk": 0.0,
        "sp_defense": 0.0,
        "speed": 0.0,
    },
}

# NRC PvP 性格表以 data/属性数值计算.md 为准。旧版表格保留在上方仅供
# 历史数据读取；这里覆盖为当前六维表（+20%/-10%）。
NATURE_BONUSES = {
    "逞强": {"hp": -0.1, "atk": 0.2, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.0},
    "理性": {"hp": -0.1, "atk": 0.0, "defense": 0.0, "sp_atk": 0.2, "sp_defense": 0.0, "speed": 0.0},
    "坦率": {"hp": -0.1, "atk": 0.0, "defense": 0.2, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.0},
    "焦虑": {"hp": -0.1, "atk": 0.0, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.2, "speed": 0.0},
    "热情": {"hp": -0.1, "atk": 0.0, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.2},
    "沉默": {"hp": 0.2, "atk": -0.1, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.0},
    "聪明": {"hp": 0.0, "atk": -0.1, "defense": 0.0, "sp_atk": 0.2, "sp_defense": 0.0, "speed": 0.0},
    "稳重": {"hp": 0.0, "atk": -0.1, "defense": 0.2, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.0},
    "警惕": {"hp": 0.0, "atk": -0.1, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.2, "speed": 0.0},
    "胆小": {"hp": 0.0, "atk": -0.1, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.2},
    "平和": {"hp": 0.2, "atk": 0.0, "defense": 0.0, "sp_atk": -0.1, "sp_defense": 0.0, "speed": 0.0},
    "固执": {"hp": 0.0, "atk": 0.2, "defense": 0.0, "sp_atk": -0.1, "sp_defense": 0.0, "speed": 0.0},
    "天真": {"hp": 0.0, "atk": 0.0, "defense": 0.2, "sp_atk": -0.1, "sp_defense": 0.0, "speed": 0.0},
    "害羞": {"hp": 0.0, "atk": 0.0, "defense": 0.0, "sp_atk": -0.1, "sp_defense": 0.2, "speed": 0.0},
    "开朗": {"hp": 0.0, "atk": 0.0, "defense": 0.0, "sp_atk": -0.1, "sp_defense": 0.0, "speed": 0.2},
    "忧郁": {"hp": 0.2, "atk": 0.0, "defense": -0.1, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.0},
    "大胆": {"hp": 0.0, "atk": 0.2, "defense": -0.1, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.0},
    "专注": {"hp": 0.0, "atk": 0.0, "defense": -0.1, "sp_atk": 0.2, "sp_defense": 0.0, "speed": 0.0},
    "温顺": {"hp": 0.0, "atk": 0.0, "defense": -0.1, "sp_atk": 0.0, "sp_defense": 0.2, "speed": 0.0},
    "急躁": {"hp": 0.0, "atk": 0.0, "defense": -0.1, "sp_atk": 0.0, "sp_defense": 0.0, "speed": 0.2},
    "粗心": {"hp": 0.2, "atk": 0.0, "defense": 0.0, "sp_atk": 0.0, "sp_defense": -0.1, "speed": 0.0},
    "调皮": {"hp": 0.0, "atk": 0.2, "defense": 0.0, "sp_atk": 0.0, "sp_defense": -0.1, "speed": 0.0},
    "偏执": {"hp": 0.0, "atk": 0.0, "defense": 0.0, "sp_atk": 0.2, "sp_defense": -0.1, "speed": 0.0},
    "懒散": {"hp": 0.0, "atk": 0.0, "defense": 0.2, "sp_atk": 0.0, "sp_defense": -0.1, "speed": 0.0},
    "莽撞": {"hp": 0.0, "atk": 0.0, "defense": 0.0, "sp_atk": 0.0, "sp_defense": -0.1, "speed": 0.2},
    "踏实": {"hp": 0.2, "atk": 0.0, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.0, "speed": -0.1},
    "勇敢": {"hp": 0.0, "atk": 0.2, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.0, "speed": -0.1},
    "冷静": {"hp": 0.0, "atk": 0.0, "defense": 0.0, "sp_atk": 0.2, "sp_defense": 0.0, "speed": -0.1},
    "悠闲": {"hp": 0.0, "atk": 0.0, "defense": 0.2, "sp_atk": 0.0, "sp_defense": 0.0, "speed": -0.1},
    "慎重": {"hp": 0.0, "atk": 0.0, "defense": 0.0, "sp_atk": 0.0, "sp_defense": 0.2, "speed": -0.1},
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
        NatureBonus 字典，包含 atk, defense, sp_atk, sp_defense, speed 的修正值

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
        v == 0.0 for v in NATURE_BONUSES[nature].values()
    )
