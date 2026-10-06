# `nrc_platform` 对战状态管理器

`nrc_platform` 是 `nrc_core` 之上的多回合对战状态管理层。它负责收集数据库和规则目录中的全部必要资料，保存阵容、历史、当前状态、可见信息和用户操作，再把规范化请求交给核心模拟器。

核心模拟器只负责规则计算：它接收已经解析好的 ID、名称、原语和显式未知值，不负责查询数据库、补全技能/精灵资料或维护跨回合会话。所有数据库访问、候选生成、未知字段保留和历史合并都必须在本模块完成。

本 README 是平台层的目标接口契约，供 `nrc_core`、`nrc_ai`、UI、机器人和回放工具共同遵守。接口名称可以在实现时调整，但输入输出语义、未知值规则和时序不能随意改变。

## 1. 解决的问题

平台必须同时支持两种模式：

| 模式 | 信息范围 | 平台行为 |
| --- | --- | --- |
| `full` 全知模拟 | 双方阵容、属性、技能、状态和本回合操作均已知 | 平台查询并规范化全部资料，直接调用核心，得到唯一回合结果；随机规则由 `seed` 决定 |
| `partial` 有限信息预测 | 我方信息完整；对方只有已观测到的部分信息 | 平台查询可用资料，保留剩余未知，根据约束补全对手候选状态，调用核心进行多分支预测 |

两种模式使用同一套核心字段和回合时序。差异只在于：`full` 在送入核心前必须解析为一个完整状态，`partial` 可以保留 `unknown`，由平台的状态推断层生成一个或多个核心可执行状态。

## 2. 分层职责

### 2.1 平台层 `nrc_platform`

- 创建和销毁对局，生成稳定的 `battle_id`。
- 访问并缓存 `data/`、技能目录、精灵目录、属性表等数据库信息；核心不得承担这些查询。
- 将用户输入的名称、技能槽、ID 和显示字段解析为核心可消费的规范化资料。
- 持有对局的唯一可变记录：阵容、当前状态、历史操作、历史战报、观测校准和推断候选。
- 管理回合编号、提交状态、强制换人阶段、终局状态和版本信息。注意有可能模拟后有精灵力竭，那么回合不能直接结束，而是严格按照data下的流程模拟后再次等待用户传入操作，新精灵入场特效又可能导致对方力竭，总之只要有精灵力竭就不能开始下一回合。
- 维护有限信息模式下的对手候选状态，并在新观测到来后过滤或重加权候选。
- 按观察者权限生成显示信息，不能把对手隐藏字段泄露给上层。
- 调用下层接口完成显示威力查询、伤害预测、属性克制查询和回合结算。

### 2.2 核心层 `nrc_core`

- 执行一回合的确定性规则：先后手、应对、技能效果、伤害、状态、能耗、入场效果和终局。
- 接收平台已经解析的技能/精灵 ID 或名称、原语数值和显式未知值。核心只应该通过硬编码的ID、名称、规则原语模拟，不应该查询数据库或即时解析技能描述。
- 返回回合后的状态、事件、显示威力、效果指示器。
- 通过log在控制台输出模拟过程，包括详细的显示威力计算、伤害计算（例如伤害数值，多少连击，克制还是抵抗，然后还有状态伤害，特性伤害，对方是否力竭这些），触发特性等

核心不负责保存跨回合的用户会话，也不负责猜测唯一的对手资质、性格或操作。平台不得在本层之外另写一套伤害或状态规则。

### 2.3 上层调用方

上层只负责展示和收集输入，原则上不持久化战斗状态。上层提交的内容包括阵容、技能选择、共鸣魔法、选择类技能选项、换人选择和可见的血量校准；平台将这些内容与内部历史合并后再调用核心。

## 3. 数据库边界和规范化流程

数据库查询必须在平台完成，流程固定为：

1. 接收上层输入的 ID、名称、技能槽或用户可见文本。
2. 在平台查询精灵、技能、属性克制、特性、共鸣魔法和规则版本等资料。
3. 将查询结果转换成稳定的内部 DTO；保留来源、目录版本和查询失败原因。
4. 对没有查到或用户没有提供的字段构造显式 `unknown`，不能在平台入口用默认值掩盖。
5. 在 `full` 模式校验核心必需字段是否齐全；在 `partial` 模式把未知字段和候选约束一起传给推断器。
6. 只有平台完成规范化和未知值封装后，才构造核心请求。核心不应出现数据库连接、技能名模糊搜索或“根据名称补全对象”的行为。

平台需要缓存查询结果，但缓存必须带 `catalog_version` 和 `rules_version`。同一个名字在不同目录版本下解析出的技能、属性或数值可能不同，不能跨版本复用。

## 4. 基本术语

- **对局状态**：当前双方阵容、出场精灵、血量、能量、状态、属性修正、印记、天气、共鸣魔法和回合元数据。
- **历史**：已经提交的选择、实际观测到的结果、核心战报、用户校准和平台对未知字段的推断记录。
- **显示威力**：技能在当前状态和已有历史影响下展示给用户的威力，不等于最终实际伤害。
- **伤害预测**：在指定减伤值下计算技能可能造成的伤害。减伤值通常来自对方本回合的应对操作，因此不能假设为已知。
- **观测值**：用户明确看到或明确输入的事实，例如对方本回合剩余血量百分比。
- **未知值**：当前没有足够证据确定的字段。未知不是 `0`、空字符串或默认性格。
- **候选状态**：在有限信息模式下满足当前全部历史和观测约束的一种完整对手状态。
- **分支**：由未知属性、未知性格、随机效果、对手操作或多段伤害等因素产生的一个可能结果。

## 5. 未知值协议

核心和平台都使用显式未知值。推荐 JSON 形式如下：

```json
{
  "known": false,
  "exists": true,
  "value": null,
  "reason": "opponent nature has not been observed"
}
```

已知值：

```json
{"known": true, "exists": true, "value": 120, "reason": ""}
```

明确不存在或不适用：

```json
{"known": true, "exists": false, "value": null, "reason": "this creature has no secondary type"}
```

规则：

1. `known=false` 表示不知道，不能当作 `0`、`1.0`、满血或默认性格。
2. `exists=false` 表示已经确定该字段不适用；例如没有第二属性、没有异常状态。
3. 缺省字段、JSON `null` 和未知值在平台入口处统一规范化为 `unknown`，但输出时必须保留原因。
4. 平台可以返回 `value_range`、`candidates`、`distribution` 或 `branches`，但不能把推断结果伪装成 `known=true` 的事实。
5. 如果一个结果依赖未知字段，返回值必须标记 `certainty="conditional"` 或 `certainty="range"`，并在 `assumptions` 中列出使用的补全条件。

对手的未知信息至少覆盖：种族/精灵名称、属性、血脉属性、技能池、技能槽、特性、资质、性格、基础属性、当前状态、剩余能量和本回合操作。已观测到的信息可以逐字段升级为已知；不能因为某次推断采用了一个候选，就永久覆盖事实层。

## 6. 平台内部状态

实现可以使用 dataclass、数据库或内存对象，但逻辑上必须等价于以下结构：

```text
PlatformBattleState
├── battle_id: str
├── mode: "full" | "partial"
├── schema_version / rules_version / catalog_version
├── decision_index: int          # 每次接受一个平台操作后严格递增
├── turn: int                    # 核心回合号
├── phase: setup | turn_choice | replacement | terminal
├── own_team: TeamState
├── opponent_team: TeamState | OpponentBelief
├── shared: SharedBattleState
├── pending_selection: SelectionState
├── history: BattleHistory
├── display_cache: DisplayCache
├── terminal: bool
└── winner: own | opponent | draw | unknown
```

`TeamState` 的每个精灵至少需要能够表达：

- 身份和基础资料：名称、唯一 ID、战斗属性、血脉属性、进化/强化状态。
- 战斗属性：最大血量、当前血量、物攻、物防、魔攻、魔防、速度。
- 资质和性格：IV、性格及其修正；有限信息模式可以是未知、候选集或区间。
- 技能：技能 ID、名称、槽位、基础能耗、基础威力、当前能耗、当前显示威力、使用次数和选择项。
- 战斗状态：能量、异常状态、增减益、属性等级、印记、冷却、疲劳和入场次数。
- 阵容状态：是否存活、是否当前出场、是否需要换人。

平台状态必须包含足够的历史，才能解释同一个技能为什么在不同回合显示不同威力。至少记录：

- 每回合双方提交的动作及动作来源：用户输入、观测、推断或自动分支。
- 共鸣魔法选择、使用次数、冷却和是否已经触发。
- 选择类技能的选项、选项来源和生效回合。
- 每次技能使用前后的能耗、血量、状态和印记变化。
- 核心返回的事件、`observed_branch_id`、候选分支权重和警告。
- 用户后续提供的血量校准及其对应的回合、精灵和观测时间点。

## 7. 下层接口契约

下层接口是平台调用 `nrc_core` 或规则目录的稳定适配边界。数据库和规则目录查询由平台的 catalog/repository 适配器完成；下层规则接口只接收平台已解析的 DTO、ID/名称、原语数值和显式未知值。接口返回值建议使用可序列化字典或不可变 DTO；不得返回只能在当前 Python 进程中解释的临时对象。

### 7.1 查询当前显示威力

```python
query_display_power(
    state: CoreState,
    side: Literal["own", "opponent"],
    skill: SkillRef,
    *,
    context: DisplayContext | None = None,
) -> DisplayPowerResult
```

`SkillRef` 至少支持 `skill_id`、`skill_name` 或 `skill_slot` 之一；平台应在调用前完成名称到 ID、技能槽到技能对象的解析。`context` 用于明确查询的是哪一个候选状态、哪一个选择项以及是否模拟本回合开始结算。

返回结构：

```json
{
  "skill_id": "skill:counter",
  "name": "反击",
  "skill_slot": 1,
  "kind": "skill",
  "base_power": 20,
  "display_power": 31,
  "display_energy_cost": 2,
  "hits": 2,
  "type_effectiveness": 1.0,
  "certainty": "exact",
  "assumptions": [],
  "warnings": []
}
```

约束：

- 显示威力必须基于传入的**当前状态和历史**计算，不能只读技能目录中的静态威力。
- 应包含已生效的属性修正、状态、印记、天气、入场效果、技能使用次数、共鸣魔法和前置选择。
- “显示威力”与“最终伤害”分离。显示威力不应把对方本回合尚未确定的应对减伤直接折入。
- 非攻击技能的 `display_power` 可以为 `0`，但必须通过 `kind` 或 `is_damage_skill=false` 说明这是规则结果，不是查询失败。
- 对手属性或特性未知时，返回 `certainty="range"` 或 `branches`；全知模式下同样输入应返回 `certainty="exact"`。
- 查询不得改变对局状态。核心若使用临时缓存，平台必须在查询结束后恢复缓存。

### 7.2 查询指定减伤下的伤害

```python
predict_damage(
    state: CoreState,
    attacker: Literal["own", "opponent"],
    skill: SkillRef,
    damage_reduction: DamageReduction,
    *,
    context: DamageContext | None = None,
) -> DamagePrediction
```

`damage_reduction` 是本次被动方或应对技能已经确定的减伤比例，取值范围为 `[0, 1]`：

- `0`：不减伤。
- `0.7`：减伤 70%，最终伤害乘以 `0.3`。
- `1`：完全免伤，最终直接为 `0`。

推荐返回：

```json
{
  "skill_id": "skill:slash",
  "display_power": 60,
  "raw_damage": 187,
  "damage_reduction": 0.7,
  "damage_after_reduction": 56,
  "damage_per_hit": 56,
  "hits": 2,
  "total_damage": 112,
  "type_effectiveness": 2.0,
  "certainty": "conditional",
  "assumptions": ["opponent_defense=known", "counter_reduction=0.7"],
  "warnings": []
}
```

约束：

1. 该接口只预测，不扣血、不扣能量、不触发状态，也不写入历史。
2. 减伤值必须是显式参数；不能从“对方可能使用防御技能”自动猜一个值后返回单一数字。
3. 如果技能是多段攻击，应同时返回单段伤害、段数和总伤害。随机段数或随机伤害应返回分支或区间。
4. 返回中要区分 `raw_damage`、减伤后的单段伤害和总伤害，避免上层把显示威力误当成伤害。
5. 若对方属性、物防/魔防、特性或状态未知，返回候选伤害集合或上下界，并列出造成范围扩大的字段。
6. 对于不造成直接伤害的技能，返回 `total_damage=0`，并在 `effects` 或 `warnings` 中描述其状态效果，而不是报“没有伤害数据”。

### 7.3 查询属性克制和抵抗关系

```python
query_type_effectiveness(
    attack_type: TypeRef,
    defense_types: Sequence[TypeRef],
) -> TypeEffectivenessResult
```

返回：

```json
{
  "attack_type": "fire",
  "defense_types": ["grass", "bug"],
  "per_type": [
    {"defense_type": "grass", "multiplier": 2.0},
    {"defense_type": "bug", "multiplier": 2.0}
  ],
  "multiplier": 3.0,
  "indicator": "super_effective",
  "certainty": "exact"
}
```

属性表是平台规则目录的单一事实来源。未列出的组合默认为 `1.0`；双属性均为 `2.0` 时按项目规则合并为 `3.0`，其他双属性按乘法合并；血脉属性不参与战斗属性克制。建议 `indicator` 使用稳定枚举：`immune`、`very_resistant`、`resistant`、`normal`、`effective`、`super_effective`、`unknown`。UI 的中文文案由上层映射，不能把文案当作协议值。

### 7.4 计算并更新一个回合

```python
resolve_turn(
    state: CoreState,
    actions: Mapping[Literal["own", "opponent"], TurnAction],
    *,
    seed: int,
    mode: Literal["full", "partial"] = "full",
) -> CoreTurnResult
```

`TurnAction` 至少要能表达：

```json
{
  "primary": {
    "kind": "skill",
    "skill_id": "skill:counter",
    "skill_slot": 1,
    "choice": null
  },
  "items": [],
  "resonance_magic": null,
  "source": "user"
}
```

允许的主动作包括 `skill`、`charge`、`switch`、`pass`；道具或共鸣魔法等独立动作通过对应字段表达，不能偷偷改写成普通技能。动作必须携带选择类技能的选项；缺少选项时应返回可定位的校验错误。

`CoreTurnResult` 至少包含：

```text
state_after                 # 下一回合开始前的完整核心状态
winner                      # own / opponent / None
events[]                    # 有序、可回放的战报事件
display_power              # 双方本回合技能的显示威力
turn_start_skill_display   # 回合开始时可展示的技能信息
branches[]                 # 未知或随机导致的候选分支
observed_branch_id         # 已被观测确认的分支，可为空
warnings[]
input_unknowns[]
latent_uncertainties[]
```

#### 回合结算时序

除规则版本明确覆盖外，统一按以下阶段执行。若一个阶段双方都需要处理，按同一阶段的先后顺序规则交错执行：

1. 接收并校验双方选择；校验技能、能量、换人对象和选择项。
2. 结算本回合共鸣魔法选择及其资源消耗。
3. 结算换人和入场效果，包括特性、迅捷技能、天气和印记。
4. 确定双方技能的显示威力、显示能耗和克制关系。
5. 结算应对成功的技能。
6. 按先手值、技能优先级和同速随机结果结算剩余技能；技能附带的状态在本阶段记录，但需要延后的效果不得提前触发。
7. 结算伤害、能量、吸血、反伤、扣能量、属性等级、印记和技能冷却。
8. 结算回合结束效果，例如中毒、燃烧、冻伤、持续伤害、回复和临时修正。
9. 处理力竭和终局；未终局时为每个需要换人的一方生成明确的 `replacement` 决策节点。
10. 更新战报和回合号。回合号只在完整回合结算结束后加一，替补选择本身不应重复推进回合。

如果入场效果导致另一方力竭，另一方也必须进入换人流程；不能自动选第一只存活精灵，也不能静默跳过缺少的换人操作。

#### 未知状态下的结算

`partial` 模式下不得把对手未知值直接送入只接受实数的核心字段。平台必须：

1. 用已知观测、阵容约束、技能目录和历史建立候选集合。
2. 对每个候选补全一个完整核心状态，并调用 `resolve_turn`。
3. 按观测过滤不可能分支，并保留候选来源和权重。
4. 合并状态：确定相同的字段升级为已知，不同字段保留候选、范围或未知。
5. 对上层返回“可能结果”，而不是伪造一个唯一结果。

如果候选状态超过平台配置的计算上限，必须返回截断标记、采样数量和未覆盖的不确定性，不能删除不确定性后返回精确结果。

## 8. 上层接口契约

以下接口是面向 UI、机器人或人工对战工具的逻辑 API。调用方不应直接修改 `PlatformBattleState`。

### 8.1 创建新对局

```python
create_battle(
    *,
    mode: Literal["full", "partial"],
    seed: int | None = None,
    rules_version: str | None = None,
) -> CreateBattleResult
```

返回：

```json
{
  "battle_id": "nrc-20261006-000001",
  "mode": "partial",
  "decision_index": 0,
  "turn": 1,
  "phase": "setup",
  "manifest": {
    "protocol_version": "...",
    "rules_version": "...",
    "catalog_version": "..."
  }
}
```

`battle_id` 是后续所有接口的主键。创建成功后，平台即拥有该对局的状态；上层只保存 ID 和展示缓存即可。重复提交同一个客户端请求 ID 时应幂等返回同一个对局，而不是创建两个状态。

### 8.2 传入阵容

```python
set_roster(
    battle_id: str,
    side: Literal["own", "opponent"],
    roster: RosterInput,
    *,
    request_id: str | None = None,
) -> RosterResult
```

`full` 模式要求双方阵容达到核心所需的完整程度。`partial` 模式至少要求我方阵容完整；对方可以传入：

- 已知的对方阵容和技能；
- 只含可见字段的对手摘要；
- 候选阵容或候选生成规则；
- 空阵容加上后续观测，由平台逐步建立候选。

阵容输入必须区分“用户已知但没有填入”和“用户明确不知道”。后者使用 `unknown`，不能使用空数组表示全部未知；空数组应只表示明确没有成员或没有技能。

### 8.3 传入选择和信息

```python
submit_selection(
    battle_id: str,
    side: Literal["own", "opponent"],
    selection: TurnSelection,
    *,
    request_id: str,
) -> SelectionResult
```

`TurnSelection` 至少包含：

```json
{
  "primary": {
    "kind": "skill",
    "skill_id": "skill:slash",
    "skill_slot": 0,
    "choice": null
  },
  "skill_list": [
    {"skill_id": "skill:slash", "name": "斩击", "slot": 0}
  ],
  "resonance_magic": {"name": null, "enabled": false},
  "choice_skills": [],
  "switch_to": null,
  "observed_opponent_action": null,
  "source": "user"
}
```

语义：

- `full` 模式必须在同一个回合收到双方选择，平台再调用核心结算。双方可以先后提交，但未收齐前不能推进状态。
- `partial` 模式通常只提交 `own`。对手动作未知时，平台根据候选策略、历史和观测生成分支；如果用户后来观测到对手动作，可以通过同一接口的 `observed_opponent_action` 补充事实并重新收敛。
- 若精灵力竭或入场效果要求换人，接口仍用于提交换人选择；此时 `phase` 为 `replacement`，必须提交 `switch_to`，不能提交普通技能。
- `skill_list` 是本回合用户看到或确认的技能信息，不等于强制覆盖平台历史。与历史冲突时返回冲突错误并要求显式校准。
- 共鸣魔法、选择类技能和技能槽选择必须原样记录到历史，以便回放和后续显示威力查询。

返回：

```json
{
  "battle_id": "nrc-20261006-000001",
  "accepted": true,
  "decision_index": 7,
  "phase": "turn_choice",
  "resolved": true,
  "result": {
    "events": [],
    "state_delta": {},
    "display": {},
    "branches": []
  },
  "next_required": ["own"],
  "warnings": []
}
```

`resolved=false` 表示仍在等待另一方输入或等待换人；此时不能把暂存选择当作已经生效的状态。

### 8.4 传入剩余血量校准

```python
calibrate_hp(
    battle_id: str,
    *,
    own_hp: int,
    opponent_hp_ratio: float,
    opponent_max_hp: float | None = None,
    observed_turn: int | None = None,
    request_id: str,
) -> CalibrationResult
```

该接口只用于 `partial` 模式：

- `own_hp` 是我方当前出场精灵的实际剩余血量，单位为整数；必须满足 `0 <= own_hp <= own_max_hp`。
- `opponent_hp_ratio` 是对方当前出场精灵的剩余百分比，使用 `[0, 1]`，例如 26% 传 `0.26`，不能传 `26`。
- 对方最大血量未知时，平台使用候选最大血量和历史伤害反推；不得把百分比直接当成固定整数。
- 校准应带有观测回合。若省略，默认当前尚未推进的回合，但实现应在响应中回显实际绑定的回合。
- 校准后重新过滤候选状态，保留被排除的原因；不能静默覆盖原始战报。

如果校准与已知我方状态冲突，应返回 `calibration_conflict`，并指出冲突字段；除非调用方明确选择 `replace_observation=true`，平台不得自动覆盖历史事实。

### 8.5 查询显示信息

```python
get_display_info(
    battle_id: str,
    side: Literal["own", "opponent"],
    *,
    include_damage_preview: bool = True,
) -> DisplayInfo
```

返回当前该方出场精灵的全部技能显示信息：

```json
{
  "battle_id": "nrc-20261006-000001",
  "side": "own",
  "turn": 12,
  "phase": "turn_choice",
  "active_index": 0,
  "skills": [
    {
      "skill_slot": 0,
      "skill_id": "skill:slash",
      "name": "斩击",
      "display_power": 60,
      "display_energy_cost": 2,
      "display_hits": 1,
      "type_effectiveness": 2.0,
      "effect_indicator": "super_effective",
      "certainty": "exact",
      "candidate_values": null
    }
  ],
  "assumptions": [],
  "warnings": []
}
```

`effect_indicator` 只表达技能对当前目标的规则效果，不表达技能附带的中毒、吸血或应对效果；这些放在 `effects` 中。有限信息模式下可返回：

```json
{
  "display_power": null,
  "candidate_values": [60, 72, 84],
  "range": {"min": 60, "max": 84},
  "certainty": "range",
  "uncertainty_sources": ["opponent.nature", "opponent.defense"]
}
```

## 9. 两种典型调用流程

### 9.1 双方对战（全知）

```python
battle = platform.create_battle(mode="full", seed=1002)
platform.set_roster(battle.battle_id, "own", own_roster)
platform.set_roster(battle.battle_id, "opponent", opponent_roster)

platform.submit_selection(battle.battle_id, "own", own_selection, request_id="t1-own")
result = platform.submit_selection(
    battle.battle_id,
    "opponent",
    opponent_selection,
    request_id="t1-opponent",
)

# result.result.state_delta 已写回平台；下一回合继续使用同一个 battle_id。
```

该模式下显示威力、伤害、血量和胜负应尽量是确定值；只有规则本身的随机分支会产生多个结果，且必须受 `seed` 控制并写入战报。

### 9.2 用户预测（有限信息）

```python
battle = platform.create_battle(mode="partial")
platform.set_roster(battle.battle_id, "own", own_roster)
platform.set_roster(battle.battle_id, "opponent", visible_opponent_info)

display = platform.get_display_info(battle.battle_id, "own")
prediction = platform.submit_selection(
    battle.battle_id,
    "own",
    my_selection,
    request_id="predict-t12",
)

platform.calibrate_hp(
    battle.battle_id,
    own_hp=315,
    opponent_hp_ratio=0.51,
    observed_turn=12,
    request_id="observe-t12",
)
```

有限信息结果应允许上层展示“可能为 A/B/C”“伤害范围为 X–Y”“在对方使用应对时为 Z”等条件结果。平台不得因为上层只想显示一个数字，就丢弃候选状态。

## 10. 状态更新、历史和幂等性

1. 所有改变状态的操作都必须带 `request_id`，并记录请求原文、规范化结果和平台版本。
2. 同一 `battle_id + request_id` 重复请求必须返回第一次结果，不能重复扣能量或重复推进回合。
3. 查询类接口不得改变状态；预测类接口即使内部调用多个候选核心模拟，也不得改变主状态。
4. 只有 `resolve_turn` 成功后才提交状态变更；核心抛错时平台保留结算前快照。
5. 每次状态变更记录 `before_hash`、`after_hash` 或等价的版本号，便于发现上层重复提交和并发覆盖。
6. `decision_index` 严格递增；回合号只由完整回合结算推进，替补决策不增加回合号。
7. 终局状态是只读的。终局后除查询战报、导出快照和读取结果外，任何选择或校准都应返回 `battle_terminated`。

## 11. 可见性和安全边界

平台对上层返回的 `opponent` 信息必须经过观察权限过滤：

- 全知对战的调试或回放接口可以显式请求完整状态，但普通用户观测仍应遵守权限。
- 有限信息模式不得返回对手未观测的技能、特性、IV、性格、完整属性、候选权重原始种子或内部评分细节。
- 返回候选时可以返回可解释的来源和范围，但不能通过候选排序间接泄漏不应公开的隐藏字段。
- `debug`、核心原始快照和完整历史应作为内部权限字段，不能默认出现在用户响应中。

## 12. 错误协议

所有可预期错误都应包含稳定 `code`、人类可读 `message` 和结构化 `details`：

| 错误码 | 含义 |
| --- | --- |
| `battle_not_found` | 对局 ID 不存在 |
| `invalid_phase` | 当前阶段不接受该操作 |
| `invalid_action` | 技能、槽位、选择项或换人对象不合法 |
| `missing_selection` | 尚未收齐需要的双方选择 |
| `unknown_required_field` | 全知模式仍存在核心必需未知字段 |
| `calibration_conflict` | 血量校准与已确认历史冲突 |
| `unsupported_mechanic` | 规则机制尚未由核心实现 |
| `version_mismatch` | 请求、快照和当前规则版本不兼容 |
| `battle_terminated` | 对局已经终局 |
| `stale_decision` | 调用方使用了旧的 `decision_index` |
| `duplicate_request` | 请求已处理；应返回原结果而不是再次执行 |

错误不得通过返回 `None`、空结果或默认伤害来掩盖。尤其是未知信息、未实现机制和非法动作必须可区分。

## 13. 快照和版本

平台需要支持导出和恢复对局，以便重启、回放和调试：

```python
export_battle(battle_id: str) -> Mapping[str, Any]
import_battle(snapshot: Mapping[str, Any]) -> CreateBattleResult
```

快照至少包含：

- 平台协议版本、核心规则版本、技能/精灵目录版本和环境名；
- 对局 ID、模式、随机种子、决策序号、回合号和阶段；
- 当前核心状态及平台历史；
- 未知字段、候选状态、权重、观测校准和已确认分支；
- 请求幂等记录和最近一次状态哈希。

版本不匹配时必须拒绝导入，除非提供显式迁移器。不能用“尽量读取旧字段”的方式恢复一个语义已经变化的战斗状态。

## 14. 与当前代码的关系

当前代码中的 `BattlePlatform` 仍暴露训练适配器风格的入口：

```python
platform.new_game(setup, seed)
platform.decision(state)
platform.observe(state, player)
platform.legal_actions(state, player)
platform.advance(state, actions, seed)
```

这些入口适合 `nrc_ai` 的多回合训练协议，保留其行为兼容性。本文新增的概念接口面向人工对战、有限信息推断和上层产品，后续实现应在平台内部复用同一份状态和历史，不应另起一套战斗状态。

建议的实现映射：

| 本文接口 | 核心/现有能力 |
| --- | --- |
| `query_display_power` | `nrc_core.core` 的显示威力计算与回合开始技能展示 |
| `predict_damage` | `DamageCalculator` 的无副作用预览适配器 |
| `query_type_effectiveness` | `nrc_core.models.get_type_effectiveness` 与平台属性目录 |
| `resolve_turn` | `nrc_core.simulate_turn` / `BattleSimulator.resolve_turn` |
| `get_display_info` | 读取当前出场精灵全部技能的显示字段 |
| `submit_selection` | 平台保存输入后，在收齐动作或生成候选后调用 `resolve_turn` |

平台实现不得直接依赖核心内部的临时字段名作为外部协议；例如 `_last_damage_details` 只能在适配器内转换成稳定的 `DamagePrediction` 字段。核心也不应为了查询技能而反向访问平台数据库；所有技能、精灵、属性和规则资料必须由平台先解析并随请求传入。

## 15. 实现验收标准

- 同一个全知初始状态和同一个 `seed` 重放，状态、事件顺序和显示威力一致。
- 平台完成所有数据库查询和资料规范化；核心不建立数据库连接、不进行名称搜索、不补全隐藏资料。
- 查询显示威力、属性克制和伤害预测均不改变主状态或历史。
- 有限信息模式不会把任意未知字段输出成确定值；血量校准可以过滤候选并解释排除原因。
- 技能、共鸣魔法、选择类技能和换人操作均能在历史中回放。
- 力竭后的换人是明确的下一阶段；不会自动换第一只存活精灵。
- 同一请求重试不会重复结算；过期 `decision_index` 不会覆盖新状态。
- 用户只拥有对手少量信息时，平台输出不泄露对手隐藏字段。
- 核心规则变更、技能目录变更或观测协议变更时，快照和 manifest 能阻止静默混用。
