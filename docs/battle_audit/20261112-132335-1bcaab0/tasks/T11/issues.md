# T11 平台、房间和观测缺陷

所有反例使用独立内存平台，不连接现有浏览器或服务器。命令：`python docs/battle_audit/20261112-132335-1bcaab0/tasks/T11/probe.py`（`PYTHONIOENCODING=utf-8; PYTHONUTF8=1`）。实际退出0，完整输入与状态/事件见 [probe_output.json](probe_output.json)。

## T11-I01：平台自动抹去未实现特性，绕过核心构建拒绝

- 严重度：P1；主责T11，协同T02/T06/T12。
- 依据：AGENTS.md架构规则要求未实现机制抛 `UnsupportedMechanicError`，不静默降级；特性原文是精灵效果的核对依据。
- 位置：`nrc_platform/platform.py:_Catalog._normalize_creature` 第157-160行；接口另一端 `nrc_platform/builder.py:build` 的unsupported检查。
- 最小输入：双方阵容各一个“不咕钟”，技能槽均为火焰箭，未显式指定特性。先分别调用builder.build和真实平台set_roster。
- 预期：两入口均拒绝“整点报时”未实现，不开始少特性的对局。
- 实际：直接builder正确抛 `UnsupportedMechanicError`；平台规范化填入空特性字符串，实际精灵 `ability=''`、`ability_effects=[]`，对局成功初始化。
- 范围：目录内152个形态的特性无配置时会走此分支；显式传特性名的输入另行拒绝。不将直接builder正确拒绝宣传为Web拒绝。
- 证据：`probe_output.json.unsupported_ability_bypass`；T06的70个未实现特性记录保留局部拒绝和平台放行两个事实。

## T11-I02：全队状态变动的战报泄露未出场精灵身份

- 严重度：P1；主责T11，协同T05/T10/T12。
- 依据：`data/对战过程中的信息遮蔽规则.md:5` 未上场精灵对方无法看见任何信息。
- 位置：`nrc_platform/rooms.py:_visible_events` 第40-70行只按事件类型/私有标志遮蔽，没有依据revealed登记过滤pokemon身份；接口 `nrc_core/runtime.py:_report_state` 枚举所有精灵状态。
- 最小步骤：1007阵容以A寒音蛇首发、B大耳帽兜首发；A赤子之心，B聚能；B读取events和state。
- 预期：A未出场替补仍未知，其变更不向B暴露名称。
- 实际：B的state.opponent_team[1]仍是未知精灵，但events包含 `pokemon='厉毒小萝'`、萌化0→1。该精灵从未上场；全队作用后的退化名泄露。
- 范围：所有会改变从未出场替补状态/技能/资源并生成公开state_change的机制；与面板本身正确遮蔽分开。
- 证据：`probe_output.json.unrevealed_bench_events` 的before/after/events/submit_result完整保存。

## T11-I03：双视角观测缺少对方奉献总层数

- 严重度：P2；主责T11，协同T10/T12。
- 依据：`data/部分规则详解/奉献.md:5` 对方可以看到总层数，不能看到具体分配。
- 位置：`nrc_platform/state.py:normalize_observation` 末尾计算opponent_devotion却未输出。
- 最小输入：已初始化双方奉献分别 `{'飞断':2,'假寐':1}` 和 `{'虫茧':4}`，分别读取双方public_state。
- 预期：A有own.total3/distribution及opponent.total4；B有own.total4/distribution及opponent.total3。
- 实际：两视角只有own键，缺少对方总数。
- 范围：全部有奉献的对局，分布保密仍正确。
- 证据：`probe_output.json.devotion_visibility`。

## T11-I04：predict_damage忽略组合状态，给出与显示接口不一致的精确预测

- 严重度：P2；主责T11，协同T03/T04/T05。
- 依据：`data/部分规则详解/战报.md:5` 技能耗能和显示威力由核心计算；`data/部分规则详解/最好的伙伴.md` 组合状态计算时应用派生加成；拨浪鼓原文每个状态技能使毒萌技能威力+10。
- 位置：`nrc_platform/platform.py:predict_damage` 第590行直接调用DamageCalculator，缺少技能组合状态power展开；对照 `core._turn_start_skill_display` 的power_override。
- 最小输入：寒音蛇携带撒娇、己方状态技能累计2，触发拨浪鼓ON_ENTER后同时调用get_display_info、query_display_power、predict_damage(reduction=0)。
- 预期：三入口均纳入固定+20；显式技能30、加成20、萌本系1.25后威力62.5（显示62），对手魔防196、魔攻156，规则每击floor(round(62.5×156×37/41)/196)=44，三击132。
- 实际：display/query显示62、每击44、3击；predict显示37、每击26、总78，却标记certainty=exact。
- 范围：带技能维度组合状态的直接平台预测API；Web是否调用由T12单列。另有减伤取整问题与T04-I01共用根因，不重复计数。
- 证据：`probe_output.json.prediction_contract`。
