# 核心规则模块

`nrc_core` 是项目的战斗规则核心。原 `src/` 目录中的实现已经归并到这里。

## 模块职责

- `battle.py`、`simulator.py`：执行回合、计算伤害、处理状态和终局。
- `models.py`、`schema.py`、`actions.py`：定义战斗状态、动作以及输入输出数据结构。
- `effect_models.py`、`effect_data.py`、`engine/`：处理技能、特性、状态和效果。
- `pokemon_db.py`、`skill_db.py`：访问数据库和规则目录。
- `rng.py`：提供可复现的作用域随机数。
- `training.py`：提供训练系统使用的核心适配接口。

训练系统只能接收 `Observation`、`Decision`、`LegalAction` 和 `Transition` 等接口对象，不能把完整的隐藏状态直接提供给动作模型。

## 训练接口

训练适配器应提供以下能力：

```python
backend.manifest
backend.new_game(setup, seed)
backend.clone(state)
backend.decision(state)
backend.observe(state, player)
backend.legal_actions(state, player)
backend.advance(state, actions, seed)
backend.export_state(state)
backend.import_state(snapshot)
```

`Decision.index` 是严格递增的决策序号，`turn` 是游戏回合，`phase` 用于区分普通选择和替补等阶段。

`advance()` 只能接收当前决策节点要求的全部动作。动作缺失、动作额外、动作非法或游戏已经结束时，应直接报错，不能自动跳过或自动聚能。

通常双方同时提交动作。回合开始的特性、传动和天气结算必须在 `observe()` 与 `legal_actions()` 之前完成。强制换人应进入明确的替补决策节点，不能自动选择第一只存活的精灵。

## 版本和可见性

`CoreManifest` 至少包含以下版本信息：

- `protocol_version`
- `rules_version`
- `catalog_version`
- `action_version`
- `observation_version`
- `environment`

规则、数据库、动作或观测语义发生变化时，必须更新相应版本。快照必须携带版本校验信息；当前快照只适用于受信任的同版本 Python 进程。

己方观测可以包含己方完整运行状态；对手观测只能包含规则允许公开的队伍和战斗状态，不得泄露对手技能、特性、能力状态或完整隐藏属性。

## 规则约束

- 双属性克制以 `data/属性克制表.md` 为准，双克制为 `3x`，双抵抗为 `0.25x`。
- 血脉属性可以作为阵容和技能池输入，但不参与属性克制计算。
- 随机技能、特性、目标选择和同速判定必须使用作用域随机数。
- 选择类技能、未完成的共鸣魔法、随机奉献及部分强制换人路径，在接口明确前应抛出 `UnsupportedMechanicError`。
- 力竭扣减、魔力归零与全队倒下的终局优先级、冻结后的换人时机等规则仍需专项验收。

## 生成技能效果

```bash
python nrc_core/generate_skill_effects.py
```

该命令生成 `skill_effects_generated.py`。生成文件不要手工修改。

## 验证

```bash
python -m nrc_ai check --backend nrc_core.training:create_backend --setup setup.json
python -m pytest tests/test_nrc_core_training_backend.py -q
```

修正规则后，应重新生成轨迹和模型，并保存配置文件、版本清单、随机种子、命令参数及数据时间范围。
