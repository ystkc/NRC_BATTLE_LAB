import numpy as np

# 数值规则要求所有中间值保持单精度，避免半精度在边界处提前舍入。
NATURE_BONUS = np.float32(0.2)
NATURE_FAIL = np.float32(-0.1)
NATURE_BALANCE = np.float32(0.0)

PVP_APTITUDES_MULTIPLIER = 6 # PVP平衡为5星，成长资质为基础成长资质6倍
