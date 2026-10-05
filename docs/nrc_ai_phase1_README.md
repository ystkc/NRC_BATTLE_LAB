# NRC AI 第一阶段 README

状态：第一版训练接口已完成，进入实际对战模拟准确性验证；第二阶段已开始实现在线信念更新。

日期：2026-10-04

## 1. 阶段目标

本阶段先把训练系统和 nrc_core 的边界固定下来，而不是急于声称已经有 MuZero 强度。当前系统可以：

- 对给定阵容和当前公开信息生成有限合法动作集合；
- 在对手隐藏信息存在时，用候选完整状态组成加权粒子信念；
- 用真实 nrc_core 转移进行局部 belief-tree search，输出下一步动作和访问分布；
- 生成普通自博弈轨迹、搜索教师轨迹，并训练一个带动作掩码的 GRU policy/value 模型；
- 在收到实际公共观测后，用已知己方动作和采样的对手动作更新粒子信念。

训练器不绕过规则模拟器。任何规则修补都应先更新核心适配器和 manifest，再重新生成轨迹和模型。

## 2. 使用条件

- Python 3.10 或更高版本；
- 在仓库根目录执行：pip install -e "[training]"；
- data/ 中的规则文档、CSV 和 data/nrc_wiki.db 可用；
- nrc_core.training:create_backend 可创建后端；
- 训练依赖为 NumPy 和 PyTorch；仅做接口烟测时，toy backend 不需要 NRC 数据库；
- pytest 是开发依赖，但当前环境未必已安装，不能把“pytest 不存在”误判为规则失败。

## 3. 保留产物

| 路径 | 作用 |
| --- | --- |
| nrc_core/training.py | 真实规则适配器、动作/观测/转移接口、版本 manifest |
| nrc_ai/contracts.py | 训练侧稳定协议和数据类 |
| nrc_ai/belief.py | 加权粒子信念和重采样 |
| nrc_ai/belief_setup.py | 从候选完整阵容构造初始信念 |
| nrc_ai/search.py | 基于精确规则转移的局部 belief-tree search |
| nrc_ai/online.py | 第二阶段在线观测更新和规划代理 |
| nrc_ai/selfplay.py | 普通自博弈与搜索教师自博弈 |
| nrc_ai/replay.py | 版本无关的 JSONL episode/step 轨迹 |
| nrc_ai/model.py、nrc_ai/training.py | GRU policy/value 和 warm-start 训练 |
| tests/test_nrc_ai_framework.py | toy backend、搜索、轨迹和在线更新测试 |
| tests/test_nrc_ai_real_integration.py | 真实后端集成测试 |
| tests/test_nrc_core_training_backend.py | 核心训练适配器测试 |
| docs/nrc_core_training_interface.md | 训练接口契约 |
| docs/nrc_core_training_interface_gaps.md | 当前未完成规则和待确认语义 |
| docs/nrc_ai_training.md | 训练框架技术说明；本文件是本阶段交接清单 |

## 4. 可复现命令

先准备一个符合当前 BattleRequest 的 setup.json。之后按以下顺序执行：

    python -m nrc_ai check --backend nrc_core.training:create_backend --setup setup.json
    python -m nrc_ai plan --setup setup.json --simulations 128 --horizon 8 --seed 0
    python -m nrc_ai plan-belief --setup setup.json --candidates candidates.json --simulations 128 --horizon 8 --seed 0
    python -m nrc_ai selfplay --setup setup.json --episodes 16 --max-decisions 128 --output data/replay/nrc.jsonl
    python -m nrc_ai search-selfplay --setup setup.json --episodes 16 --simulations 64 --horizon 8 --output data/replay/nrc-search.jsonl
    python -m nrc_ai build-action-keys --replay data/replay/nrc-search.jsonl --output data/replay/action_keys.json
    python -m nrc_ai train-replay --replay data/replay/nrc-search.jsonl --action-keys data/replay/action_keys.json --input-dim 256 --hidden-dim 128 --epochs 5

plan 使用单个完整状态，是 oracle teacher smoke test；plan-belief 使用候选隐藏状态；search-selfplay 把搜索访问分布写入 search_policy，训练时优先拟合该分布而不是只拟合实际采样动作。

当前命令输出的 manifest 必须保留。规则代码、规则 CSV、数据库或动作/观测协议变化后，旧轨迹和旧模型只能作为历史对照，不能直接混训。

## 5. 训练原理

### 5.1 状态、观测、动作分离

后端内部保留完整状态；训练侧只把 Observation.data 作为己方输入。己方可以看到完整己方队伍，对手只输出当前规则允许公开的战斗状态。动作使用稳定字符串键，例如 skill:slot=0、charge、switch:index=1，模型输出再经过合法动作掩码。

### 5.2 隐藏信息用信念而非伪造观测

一个粒子是“可能的完整规则状态”，不是一段猜测文字。初始阶段可由候选阵容 JSON 给出多个粒子及权重；没有候选时的单粒子模式只用于 oracle 调试，不代表真实在线能力。规划时从信念按权重采样，再从对手策略分布采样隐藏动作，最后调用 backend.advance。

### 5.3 搜索目标是策略分布

搜索树对每个根动作统计访问次数和回报，根访问次数归一化成为 search_policy。这比只保存最终动作更适合蒸馏，也保留“第二选择”和不确定性。当前叶节点价值是公共观测启发式，不是已训练 MuZero value；终局使用胜负值。

### 5.4 截断轨迹不伪造终局价值

达到 max_decisions 的 episode 标记 truncated=true。这类轨迹仍可用于策略监督，但不写入假终局胜负值；只有真实终局且 winner 为 0 或 1 时才启用终局 value target。

### 5.5 在线粒子更新

第二阶段的 OnlineBeliefUpdater 接收己方已知动作、观测玩家和实际公共观测。每个粒子采样隐藏对手动作及随机种子，推进一次真实后端，再以预测观测对实际观测的 likelihood 加权。默认使用软匹配以容纳随机路径和少量数值差异；契约测试可设置 exact_observation=True。若所有粒子都被过滤，调用方必须记录“信念耗尽”，不能静默回退到全知状态。

## 6. 能力范围与明确限制

当前真实后端已经支持并通过基础验证的方向包括：普通技能/蓄力/切换、巧变、魔术帽、时间特性、血脉属性输入、愿力强化、进化之力、光合治愈，以及部分契约 metadata。当前适配器仍会明确拒绝或暂不承诺：选择型/随机技能、未上线共鸣魔法、道具和随机奉献等尚未完成契约的机制。

规则层面仍需志愿者和核心开发者协同确认：随机路径是否全部进入 src.rng、强制换人路径、回合开始结算时机、MP 归零与全队倒下的终局优先级、冻结后的换人时机，以及选择技能的正式 schema。详见 docs/nrc_core_training_interface_gaps.md。

当前搜索不是完整 POMCP、PUCT 或 Nash equilibrium 求解；对手策略默认均匀分布，也可用 EmpiricalOpponentPolicy 做上下文计数。当前模型不是 MuZero dynamics model，不能把搜索结果解释为已经学会规则。

## 7. 核心修补后的快速重训

1. 运行 python -m py_compile nrc_ai/*.py nrc_core/*.py tests/*.py。
2. 运行 check，确认 protocol_version、rules_version、catalog_version 和动作键没有意外变化。
3. 运行真实后端集成测试；若环境有 pytest，再运行 python -m pytest tests/test_nrc_ai_framework.py tests/test_nrc_ai_real_integration.py tests/test_nrc_core_training_backend.py -q。
4. 用志愿者已确认的最小阵容重跑 plan、selfplay 和 search-selfplay，检查终局、换人、随机技能和观测可见性。
5. 用 build-action-keys 从新轨迹生成动作字典，不手工复用旧动作列表。
6. 重新训练并保存 manifest、setup/candidate 文件、命令参数、随机种子和数据时间范围。
7. 对比修补前后的胜率、动作分布、合法动作拒绝率、终局一致率和公共观测一致率；任何提升都必须先排除规则变化造成的分布变化。

## 8. 下一阶段入口

当前已开始第二阶段：在线信念更新和“规划—执行—接收观测—更新信念”闭环。下一步应优先做真实后端的公共观测轨迹回放、粒子耗尽诊断、随机种子覆盖率和 public-history transposition；之后再把搜索访问分布与真实对战记录结合，用于对手模型和下一阶段阵容推荐。MuZero 的 learned representation/dynamics/prediction 应放在这些验证稳定后接入，不能替代规则模拟器的准确性测试。
