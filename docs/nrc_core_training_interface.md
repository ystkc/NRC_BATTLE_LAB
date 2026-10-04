# nrc_core 训练接口契约 v1

状态：核心训练后端已实现，接口细节仍待上层确认。本文与 `nrc_ai/contracts.py` 是双方交接边界；不要求保留旧的 `resolve_turn()` 接口。不要让规则内核依赖 PyTorch 或训练器。

## 1. 开发分工与最小交付

- 核心开发者：完整状态、规则推进、决策阶段、合法动作、观测可见性、可重复随机性、完整序列化、版本声明。建议提供 `nrc_core.training:create_backend` 工厂，可自行选择内部实现。
- 训练侧：历史编码、隐藏状态假设/先验、信念权重更新、对手策略、搜索、自博弈、轨迹、训练与评估。全部置于 `nrc_ai/`。
- P0 是第 2～7 节全部接口与验收。训练侧不会将现有带占位值的 `BattleRequest` 当完整状态，也不会用 `BattleResult.opponent.after` 直接训练演员。
- 优先交付一组**规则已核验**的小规模阵容和技能，明确不支持集合；血脉属性作为阵容/技能池输入但不参与属性克制，契约的形状需要 `metadata.gulu_ball`。选择技能、首领、道具/愿力和随机奉献等未实现机制在初始化时报 `UnsupportedMechanicError`，不得伪装成已执行。

## 2. Python 边界

以下类型在 `nrc_ai/contracts.py`；核心可通过一个轻量桥接模块实现相同结构，不必重写既有 schema。玩家标识固定为 `0/1`，不是请求中会改变的 own/opponent。

```python
class CoreBackend(Protocol):
    @property
    def manifest(self) -> CoreManifest: ...
    def new_game(self, setup: dict, seed: int) -> object: ...
    def clone(self, state: object) -> object: ...
    def decision(self, state: object) -> Decision: ...
    def observe(self, state: object, player: int) -> Observation: ...
    def legal_actions(self, state: object, player: int) -> tuple[LegalAction, ...]: ...
    def advance(self, state: object, actions: dict[int, str], seed: int) -> Transition: ...
    def export_state(self, state: object) -> dict: ...
    def import_state(self, snapshot: dict) -> object: ...
```

`object` 是完整物理状态，只能交给模拟器/信念采样器；演员 API 只接收 `HistoryFrame` 历史和己方 `LegalAction` 候选。初始化传入双方完整且合法配置用于自博弈。线上只有己方已知配置时，训练侧构造若干合法完整假设，再用 `new_game`/`import_state` 建立粒子，不能要求核心凭空推断唯一对手。

## 3. manifest 与版本

`CoreManifest`：`protocol_version="1"`、`rules_version`、`catalog_version`、`action_version`、`observation_version`、`environment`。版本应非空，机制/解释变更必须改变版本；规则版本建议取核验规则集合的内容哈希。environment 要区分 `nrc` 与测试环境。

CSV/DB 是同一份游戏内容，不重复统计。`data/回合顺序.md` 内雨天、灼烧等仍有待核验口径，力竭扣魔力的对象也要按实际游戏确认；不能由训练器任意挑一种文本解释。规则争议记录在版本化的核验清单。双属性按照 `data/属性克制表.md`：双克制 3 倍，双抵抗 0.25 倍，不套其他游戏的 4 倍。

## 4. 决策时序与动作

`Decision`：`index` 为严格递增的决策序号（不是回合号），`turn` 为游戏回合，`phase` 为 `turn_choice` / `replacement` 等字符串，`players` 为此刻必须提交动作的玩家元组，`terminated` 与 `winner` 描述真实终局。非终局至少有一个活动玩家；终局 players 为空，winner 为 0/1 或 None（平局）。

- 回合开始特性、传动、天气起始结算必须在 `observe()` 与 `legal_actions()` **之前**完成，不能选择后才重排技能。
- 通常双方同时选择：`players=(0,1)`，一次 `advance()` 收齐双方动作。返回前绝不把一方当前选择暴露给另一方。结算先后由核心判定，并非轮流选招。
- 强制换人/力竭后如规则允许选择：进入 `replacement`，只请求需换人者，不自动挑首个存活精灵。若双方同时换人，两方仍同时提交。一个回合可有多个决策节点，回合结束只结算一次。
- `advance` 只接收所有且仅有 `decision.players` 的动作；缺失、额外、非法、终局动作都抛 `ValueError`，不能自动聚能/pass。

`LegalAction`：`key` 是稳定的规范化字符串，`payload` 是既有 `SideTurnInput` 的 JSON 结构（primary + items）。例如 `skill:slot=0:choice=cleanse`、`charge`、`switch:index=2`、`skill:slot=1|willpower:target=0`。相同 action_version 内同一语义 key 稳定；顺序稳定；每个节点 key 唯一。技能传动后 slot 指当前已展示顺序。

选择技能需枚举所有合法 choice；附加道具需枚举允许组合/目标/次数，禁止不完整动作。mask 以候选列表为边界：列表内全合法，批处理补齐位置全非法，不强制定义涵盖所有全局技能的巨大整数空间。终局或非活动玩家返回空列表。己方合法动作不能根据己方不可见的对手信息改变；若实际存在可见限制，用观测体现。

## 5. 观测与安全边界

`Observation`：`player`、`decision_index`、`turn`、`phase`、`data`。data 仅含 `own`、`opponent`、`shared`、`events` 四个白名单区：

- own：该玩家可见的私有状态，包括本人技能/奉献效果等。
- opponent：本决策前已公开/已揭示的对手信息；未公开字段用现有 `Maybe` 语义，不存在≠未知≠0。未揭示技能、性格、契约/特性、奉献分配不得由图鉴或完整模拟状态自动补全。
- shared：回合、阶段、公共天气、已显示魔力等。敌方能量/后排生命是否可见由游戏 UI 核验，不能假定全可见。
- events：从上一决策到当前的**实际已发生且该玩家可见**事件，按结算顺序，带稳定事件 ID/类型、时点与来源。区分实际触发、规则推断、待审候选；只有前者作为确证。

禁止含 RNG/seed、完整快照、未来结果、当前未公开对手动作或审计器候选结论。事后补全对手技能不能回填早先时点的演员输入。自己的私有奉献可读，对手只能按 `data/奉献.md` 的可见规则读取。两名玩家观测必须分别生成。

观测值为有限 JSON 数据；对同一玩家可见历史完全相同但隐藏真值不同的两个状态，观测及该玩家合法动作必须相同。训练侧的结构检查不能替代核心的语义可见性验收。

## 6. 转移、随机性与奖励

`Transition`：`state`（独立下一完整状态）、`rewards`（长度 2）、`terminated`、`winner`。事件放入下一状态的各自 observe 中，不把全量审计事件广播给演员。

- `advance` 不修改输入；同一完整输入、动作、seed、版本产生相同结果。使用实例/调用本地 RNG，不调用进程级 `random.seed()`，支持多 worker。
- 同步选择下，对手模型不能条件化于尚未公开的己方当前动作。
- 随机分支真正影响下一状态：随机奉献一次抽取后跨回合/换人保留；新获取层数增量抽取；禁止每次搜索重新抽历史分配。柔软球、速度同值随机、随机目标等由 core 采样。应对、属性、已满足条件是确定性条件，不随便当独立随机事件相乘。
- 文本分支审计表不是归一化状态转移分布；不得用 `possible_branches` 标签替代可执行结果。P0 只需可采样的生成模型，不要求枚举全部随机分支。
- P0 奖励：非终局 (0,0)，终局胜方 +1、败方 -1、平局 (0,0)。默认 discount=1，不能用大量伤害奖励取代赢棋目标。如以后加 shaping 必须单独标记版本。
- 训练器达到决策预算是 truncated，不是真平局/真实终局，不能给这样的样本赋终局 0 标签。

## 7. 完整状态快照与错误

`export_state` / `import_state` 要包含 manifest，拒绝版本不兼容；恢复后决策、观测、候选和任意 seed 下的后继一致。覆盖技能顺序、永久改写/冷却、入场次数、疲劳、增减益/印记持续时长、天气备份、使用/应对计数、奉献分配、待换人队列、阶段和回合开始已结算标记。不要用只含可见字段的 `BattleRequest` 代替完整快照。

`clone` 不共享可变嵌套对象，也不能丢待处理换人；尤其检查原内核按对象 id 保存的技能天气备份，复制后必须重映射或使用稳定实体 ID。错误路径也不得改变输入/RNG。未知实体、未实现机制、不合法阵容、版本不匹配应拒绝，不用中性数值占位。

## 8. P1 扩展（不阻塞 P0）

- 提供版本化阵容 setup 校验、技能归属/选择上限、契约球与血脉技能池的正式约束。
- 提供规则一致的观测似然辅助，用于粒子滤波；观测可能有 OCR/手录噪声，要把测量不确定性与游戏随机性分开。
- 提供公开事件中真正已展示的动作及能耗区间，训练側用来缩小候选，而不是读取 oracle。
- 提供有限概率分支枚举/批量模拟/状态哈希以加速，未知概率不能自动均匀。

## 9. 交付验收

1. 初始化 → 选择 → 强制换人 → 新回合 → 终局的最小真实规则用例。
2. action key 唯一/顺序稳定、非法/多余/缺失动作拒绝、非法选择项与道具组合拒绝。
3. 回合开始传动已体现在观测及槽位，不能重复结算。
4. 相同 seed 复现，输入不变，全局 RNG 不变，clone/快照恢复后后继一致。
5. 隐藏敌方技能/奉献/性格不同但公共证据相同：己方观测和候选严格相同；己方自己的私有信息正确可见。
6. 揭示后下一观测更新，先前观测快照不变；对手当前同时选择不提前揭示。
7. 真实终局零和奖励、平局、魔力扣减对象、强制换人节点均有测试。
8. 柔软球/同速随机真实改变后继，概率有依据；随机奉献在未支持前必须拒绝，不得伪造历史分配。
9. 未实现机制初始化失败，不产生可进入训练集的伪结果。

通用接口探针：`python -m nrc_ai check --backend nrc_core.training:create_backend --setup path/to/setup.json`。真实 backend 已提供；不能偷偷退回 toy。该探针只验机械契约，真实可见性/概率/规则正确性还需上述专项用例。

## 10. 战报与当前记录器衔接

保留 `manual_input/recorder.py` 的 request/observed_after。新训练轨迹另存 JSONL，包含 manifest、episode/来源时间、双方按时点的独立观测、当时完整合法候选、实际己方动作、每步奖励、terminated/truncated。自博弈另有搜索分布；人工动作不能伪装成搜索最优标签。

现有 BattleRequest 往往已含本回合对手动作，observed_after 又含预测与实测，不能自动整包导入训练。需要恢复**动作前**可见状态、去除未来/事后补全、验证 actual、补齐终局和版本。缺少合法候选或可信终局者先用于审计/对手行为数据，不能作为本版价值监督样本。

## 11. 第一版训练框架的明确范围

实现的是信念粒子 + 根动作 Monte Carlo rollout、观测历史 GRU 的策略/价值监督、自博弈轨迹与按对局拆分评估。不是完整 POMCP/PUCT、不是 MuZero 的 learned dynamics、不是纳什均衡保证；不能把 toy 上的训练曲线当游戏胜率。后续在此契约稳定后加入观测分支树搜索、对手池、latent dynamics，以及近期对战阵容优化。
