# 对战平台模块

`nrc_platform` 是多回合对战外壳，将 `nrc_core` 的单回合规则封装为供人工智能、回放和外部程序使用的稳定接口。

## 分层职责

- `nrc_core.core.simulate_turn`：只执行一个回合的核心规则，输入完整 `BattleState` 和双方已解析动作，输出新的核心状态、胜负、战报事件和显示威力。
- `nrc_platform.BattlePlatform`：保存多回合决策序号、回合阶段、替补选择、终局和奖励；生成双方各自的观测；校验动作是否属于当前合法动作。
- `nrc_core.training`：提供训练协议适配器，内部调用单回合核心；训练和搜索优先通过 `nrc_platform.create_platform` 接入多回合流程。

平台层不重复实现伤害、属性克制、技能效果或状态结算，这些规则统一由 `nrc_core` 提供。

## 平台状态

平台负责管理：

- 严格递增的决策序号和当前游戏回合。
- 普通行动、替补和终局等阶段。
- 当前需要提交动作的玩家集合。
- 双方各自可见的观测结果。
- 合法动作校验、回合转换、胜负和奖励。

通常双方同时选择动作。平台在收齐当前决策节点要求的动作后调用核心推进。强制换人应进入替补阶段，不能因为缺少动作而自动选择第一只存活的精灵或隐式跳过。

## 核心输出

战报事件可以包含技能名称、应对是否成功、最终结算威力、实际能量消耗、最终伤害、是否力竭、攻击方是否换人以及目标是否换人。

显示威力与最终伤害分开：显示威力来自核心预览，实际伤害还会受到应对、减伤和特性结算影响。平台只按玩家可见范围展示，不重复计算这些数值。

## 当前入口

```python
from nrc_platform import create_platform

platform = create_platform()
state = platform.new_game(setup, seed=1)
observation = platform.observe(state, player=0)
transition = platform.advance(state, actions, seed=2)
```

`setup` 应包含双方完整且合法的初始化配置。线上只有己方完整配置时，隐藏对手部分由 `nrc_ai` 构造候选粒子，平台本身不猜测唯一对手状态。
