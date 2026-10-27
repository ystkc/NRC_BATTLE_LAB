# 平台状态分类

依据 `data/状态分类.md`。`BattlePlatform.observe`、`advance` 返回的观测和 Web `/state` 共用 `state.py` 的适配器。

| 类别 | 对外字段 | 绑定对象 | 数值约定 |
| --- | --- | --- | --- |
| 增益减益 | `own_team[i].modifiers[]` | 精灵实例 | `name / stacks / unit`，允许负数 |
| 状态 | `own_team[i].statuses[]` | 精灵实例 | 同上，只输出正数；可为负的特性计数拆为原名和 `_negative` 状态 |
| 技能状态（能力状态） | `own_team[i].skills[j].skill_states` | 精灵实例的技能槽 | `power_delta / energy_cost_delta / hit_count_delta / cooldown`，零值省略 |
| 印记 | `shared.marks.own / opponent` | 阵营 | 印记名到层数的映射，随观察者视角翻转 |

双方的增减益、状态和阵营印记公开；未公开的技能、特性和完整属性仍保持隐藏。冻结只记录 `freeze` 层数，侵蚀比例由前端按每层 5% 计算，不存储或传递侵蚀生命值。`shared.devotion` 中己方包含总层数与具体分配，对方仅包含总层数。

## 原字段的关系和去向

- `boosts`：原来同时包含提升和降低；与 `debuffs` 重复，合并为 `modifiers`。属性以每层 10% 表示，正负层分别保留。核心允许提升和降低同时存在，不做净值抵消，也不改变结算。
- `debuffs`、`buffs`：从外部观测移除；使用实时精灵属性生成增减益，不再把输入时的层记录当作实时值。
- `conditions`、顶层 `*_stacks`、`status`：合并到 `statuses`，同名状态只显示一次。`fainted` 仍是生命周期标记。
- `ability_states`：原先只是运行时字典中布尔值/数值的扫描结果，并不代表技能状态。实际状态计数、免疫等按 `state.py` 的显式白名单进入 `statuses`；全精灵修正进入 `modifiers`。时间戳、触发历史、配置和缓存不是状态层，不直接展示。
- `ability_state.layered_state`：输入层记录，不能和实时状态重复输出。原始 `ability_state` 整体从对外观测移除；内部特性运行时、回放快照仍由核心保存。
- `cooldowns`：移入对应技能槽的 `skill_states.cooldown`。技能增减值以目录中的基础技能为参照，来自该精灵实际携带的技能实例，不建立按技能名称共享的状态表。

## 容易混淆的边界

1. 中毒状态 `poison` 与中毒印记 `poison_mark` 是两种机制；星陨状态 `meteor` 与星陨印记 `meteor_mark` 也是两种机制。前者留在精灵的状态中，后者读取核心 `marks_a / marks_b`；换人不改变印记的阵营归属，不能按名称将二者相加。
2. `hit_count_mod` 等对该精灵所有技能生效的修正属于精灵的增减益；技能实例自身的 `hit_count` 变化才属于技能槽。全技能威力、能耗修正同理。
3. `skill_states` 是技能实例修正和冷却的观测，不是最终显示威力/能耗预测；天气、印记和条件性特性等影响继续通过平台的技能显示接口计算。
4. 绑定对象与下场是否清除是不同问题。是否清除、衰减和触发仍按现有核心规则执行，本次平台合并不改写战斗机制。

新增特性状态需在 `_ABILITY_STATUSES` 中显式登记，避免再次将内部运行时字典直接作为 UI 协议。内部训练后端的旧字段和核心输入格式保持原契约；本文件描述平台对外观测。
