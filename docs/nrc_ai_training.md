# nrc_ai 第一版训练框架

## 范围

nrc_ai 是与正在开发的 nrc_core 解耦的训练侧骨架。当前版本完成：

- 核心适配器协议、版本清单、合法动作、观测和转移；
- 加权粒子信念和似然更新；
- 均匀、上下文计数型对手策略；
- 根动作蒙特卡洛采样基线；
- JSONL episode/step 轨迹；
- 确定性 JSON 编码和历史 GRU 策略/价值网络；
- toy backend、self-play 轨迹和 warm-start 训练命令。

这不是完整 POMCP、MuZero 或纳什均衡实现。它先固定核心接入边界和训练数据边界，避免用错误的隐藏信息训练出虚高结果。

## 运行

安装训练侧依赖：

    pip install -e ".[training]"

    python -m nrc_ai toy-rollout --simulations 32
    python -m nrc_ai toy-train --episodes 16 --epochs 2
    python -m nrc_ai check --backend nrc_ai.toy_backend:ToyBackend

真实 nrc_core 适配器实现后，使用：

    python -m nrc_ai check --backend nrc_core.training:create_backend --setup setup.json

    python -m nrc_ai plan --setup setup.json --simulations 128 --horizon 8
    python -m nrc_ai plan-belief --setup setup.json --candidates candidates.json --simulations 128 --horizon 8
    python -m nrc_ai selfplay --setup setup.json --episodes 16 --output data/replay/nrc.jsonl
    python -m nrc_ai search-selfplay --setup setup.json --episodes 16 --simulations 64 --output data/replay/nrc-search.jsonl

如果 backend 尚未存在，命令应明确失败；不能自动退回 toy backend。

plan 是 exact-transition、hidden-particle/opponent-policy 采样的第一版 belief-tree search；plan-belief 要求候选粒子保持己方私有状态和 shared state 一致，只改变隐藏对手假设。search-selfplay 用完整规则状态作为 teacher 粒子生成搜索分布，观测仍只保存己方可见信息；它是 AlphaZero 风格的搜索蒸馏数据，不是线上可见性证明。两种 self-play 的截断对局都会标记 truncated=true，不会伪造终局价值。

## 当前明确不做的事

1. 不把 toy 规则当作 NRC 规则；
2. 不把现有 BattleResult.opponent.after 直接喂给 actor；
3. 不把文本分支标签当成概率后继状态；
4. 不把根动作采样器称作完整 POMCP；
5. 不在 nrc_core 接口确认前训练真实游戏模型。

## 下一步

1. 为真实 backend 增加更多机制专项验收和观测可见性测试；
2. 从核心 Transition 生成只含公共观测的训练轨迹；
3. 将当前局部树搜索扩展为可复用 public-history POMCP/PUCT；
4. 用搜索分布、真实自博弈和人工记录训练对手模型；
5. 再接 MuZero 的 learned dynamics，不替换规则模拟器的真值测试。
