# 核心规则模块

`nrc_core` 是全知规则核心，只消费已经解析的规则目录、战斗状态和动作，不查库、不搜索名称、不推测隐藏信息。

## 公开入口

- `simulate_turn`：单回合结算。
- `BattleRuntime(catalog=...)`：多回合推进、合法动作、决策、显示和快照。
- `BattleSession`：一场对战的完整运行状态。
- `CoreCatalog`：由平台构造并注入的已解析规则目录。
- `contracts.py`：共享协议、决策、合法动作、观测与转移数据。

```python
from nrc_core.runtime import create_runtime

runtime = create_runtime(catalog=resolved_catalog)
session = runtime.new_game(resolved_battle_state, seed=17)
decision = runtime.decision(session)
actions = runtime.legal_actions(session, player=0)
display = runtime.display(session, player=0)
preview = runtime.preview_damage(session, player=0, skill_slot=0)
transition = runtime.advance(session, {0: own_action_key, 1: opponent_action_key}, seed=18)
session = transition.state
```

`advance` 仅接受当前决策阶段要求的全部合法动作，不自动补操作。强制换人进入替补决策阶段。`clone` 深拷贝完整会话；`display` 和 `preview_damage` 在副本上计算，不污染真实状态。合法动作与技能面板共用当前能耗计算。

`observe` 是核心结构化观测，正式用户可见范围仍由平台按规则遮蔽。`BattleSession` 与伤害预览属于全知数据，不应直接发送给对手或动作模型。

旧单回合适配器的预测分支、未知推测与审计输出协议已删除。原输入构造、物种数值与特性补全、性格及资质分布、输入别名及 Maybe 字段解析均由 `nrc_platform.builder.BattleBuilder` 完成。核心初始化只接收完整 `BattleState`；`rules_support.py` 仅提供共鸣、动作槽位映射和状态快照规则，不搜索名称或解析技能描述。

## 快照

`export_state` / `import_state` 使用 `nrc_core.runtime.pickle.v1` 格式，校验版本清单，仅供受信任的同版本 Python 进程内部使用。禁止导入用户上传或其他不可信来源的 pickle 快照。旧训练快照不兼容。

旧 `nrc_core.training`、`NRCTrainingBackend`、`TrainingState`、`create_backend` 和全局查库兼容门面已移除。AI 搜索与训练尚未实现。

## 规则模块

- `core.py`、`battle.py`：伤害、回合阶段与终局。
- `engine/`：按职责分组的效果处理器和阶段分发。
- `models.py`、`schema.py`、`actions.py`：状态、请求、动作与结果。
- `effect_data.py`、`effect_models.py`：硬编码效果与原语。
- `rng.py`：可复现的作用域随机数。

规则以 `data/*.md` 为首要依据。未实现机制抛出 `UnsupportedMechanicError`，不静默替换。生成文件 `skill_effects_generated.py` 不要手改。

## 验证与诊断

```bash
python scripts/check_runtime_migration.py
python -m compileall -q nrc_core nrc_ai
python scripts/generate_skill_effects.py
```

迁移验证脚本从固定的迁移前提交临时加载旧实现，以固定种子比较三回合聚能的决策、双方观测、合法动作及事件，并检查新快照往返。

核心默认不输出诊断日志。设置环境变量 `NRC_CORE_LOG` 为 `all`，或逗号分隔的 `turn,display,damage,attributes,skill,status,ability,switch,energy` 可启用对应分类。
