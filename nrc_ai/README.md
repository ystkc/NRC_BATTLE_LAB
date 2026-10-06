# 人工智能训练模块

`nrc_ai` 是训练和搜索部分，依赖 `nrc_core` 提供真实规则推进。它负责隐藏信息信念、对手策略、局部搜索、自博弈、回放以及策略价值模型；不绕过规则模拟器，也不把测试后端当成正式游戏规则。

## 模块职责

- `contracts.py`：定义核心后端协议、版本清单、决策、观测、动作和转移数据。
- `belief.py`、`belief_setup.py`：管理候选状态组成的加权信念和重新采样。
- `opponent.py`、`population_prior.py`：提供均匀、上下文计数和先验型对手策略。
- `search.py`：基于精确核心转移执行局部信念树搜索。
- `selfplay.py`：执行普通自博弈和搜索教师自博弈。
- `replay.py`：保存逐局、逐步的 `JSONL` 回放轨迹。
- `model.py`、`training.py`：提供带动作掩码的循环策略价值模型和热启动训练。
- `online.py`：接收公共观测后更新粒子信念并继续规划。
- `cli.py`：提供命令行入口。

## 安装和快速检查

```bash
pip install -e ".[training]"
python -m nrc_ai toy-rollout --simulations 32
python -m nrc_ai toy-train --episodes 16 --epochs 2
python -m nrc_ai check --backend nrc_ai.toy_backend:ToyBackend
```

正式核心必须显式指定，正式任务失败时不能自动退回测试后端：

```bash
python -m nrc_ai check --backend nrc_core.training:create_backend --setup setup.json
```

## 搜索和训练

单命令版：

```bash
python -m nrc_ai phase1-wizard --setup setup.json --episodes 16 --simulations 64 --output data/replay/nrc.jsonl
```

拆分版：

```bash
python -m nrc_ai plan --setup setup.json --simulations 128 --horizon 8 --seed 0
python -m nrc_ai plan-belief --setup setup.json --candidates candidates.json --simulations 128 --horizon 8 --seed 0
python -m nrc_ai selfplay --setup setup.json --episodes 16 --output data/replay/nrc.jsonl
python -m nrc_ai search-selfplay --setup setup.json --episodes 16 --simulations 64 --output data/replay/nrc-search.jsonl
python -m nrc_ai build-action-keys --replay data/replay/nrc-search.jsonl --output data/replay/action_keys.json
python -m nrc_ai train-replay --replay data/replay/nrc-search.jsonl --action-keys data/replay/action_keys.json --input-dim 256 --hidden-dim 128 --epochs 5
```

`plan` 使用单个完整状态，适合规则和接口的对照检查；`plan-belief` 使用候选隐藏状态。`search-selfplay` 保存根动作访问分布 `search_policy`，训练时优先拟合该分布，而不是只拟合最终采样动作。截断对局必须标记 `truncated=true`，不能伪造终局价值。

## 信息边界

核心内部保留完整状态，模型输入只能使用己方可见的 `Observation.data` 和合法动作候选。一个粒子代表一个可能的完整规则状态，而不是文字猜测。初始信念可以由多个候选阵容及其权重构成；没有候选时的单粒子模式只用于对照调试。

收到真实公共观测后，应使用己方动作、采样的对手动作和新的观测更新粒子。不能直接把 `BattleResult.opponent.after` 提供给动作模型，也不能把隐藏信息伪装成观测。

## 当前范围

当前框架是信念粒子、根动作蒙特卡洛抽样、观测历史循环网络和搜索蒸馏，不是完整的部分可观测树搜索、策略改进树搜索、环境动力学学习模型或均衡求解器。对手策略可以使用均匀分布，也可以使用上下文计数策略。

任何核心规则修补都应先更新 `nrc_core`、版本清单和验收测试，再重新生成轨迹、动作字典和模型。版本不兼容的旧轨迹只能作为历史对照，不能直接混合训练。

## nrc_platform 观察者接口

`nrc_ai.interface.NRCAIInterface` 读取平台的两个观察者视角，并返回 JSON 可序列化的操作候选列表。接口只读平台状态，不会自动提交操作；真正提交仍由上层调用 `platform.submit_selection(...)` 完成。

```python
from nrc_ai.interface import NRCAIInterface

ai = NRCAIInterface(
    platform,
    owners={0: ("user", "ai"), 1: "user"},  # AI 与用户共用 0 号视角
    simulations=128,
    horizon=8,
)

prediction = ai.predict(state)
print(prediction.to_dict()["operations"])
# [{"player": 0, "action_key": "...", "operation": {...},
#   "probability": 0.7, "confidence": 0.7, ...}, ...]
```

视角角色约定：`{0: "user", 1: "user"}` 是 `user_vs_user`；一个视角为 `ai` 是 `human_vs_ai`；同一视角包含 `("user", "ai")` 是 `ai_assist`。`predict_battle(battle_id)` 可直接读取 `BattlePlatform` 的受控快照；`predict_operations(...)` 是返回字典的便捷函数。默认使用现有 `BeliefTreeSearch`，也可以注入实现 `predict(observation, legal_actions)` 的模型。
