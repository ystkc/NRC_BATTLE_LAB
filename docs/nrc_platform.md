# NRC 对战平台层

## 分层职责

- `nrc_core.core.simulate_turn`：只执行一个回合的核心规则，输入完整 `BattleState` 和双方已解析动作，输出新的核心状态、胜负、战报事件和显示威力。
- `nrc_platform.BattlePlatform`：保存多回合决策序号、回合阶段、替补选择、终局和奖励；生成双方各自的观察；校验 action 是否属于当前合法动作。
- `nrc_core.training`：现阶段的训练协议适配器，内部调用单回合核心；平台接入优先使用 `nrc_platform.create_platform`。

## 核心输出

核心战报事件包含技能名称、应对是否成功、最终结算威力、实际能量消耗、最终伤害、是否力竭、攻击方是否换人以及目标是否换人。

显示威力与最终伤害分开：显示威力由核心预览计算，实际伤害还会受到应对、减伤和特性结算影响。平台层不重复计算这些数值，只负责按玩家可见范围展示。

## 当前入口

```python
from nrc_platform import create_platform

platform = create_platform()
state = platform.new_game(setup, seed=1)
observation = platform.observe(state, player=0)
transition = platform.advance(state, actions, seed=2)
```
