# T03 问题记录

所有条目已由probe.py实际运行。仅审计，不修改业务代码；证据读库使用mode=ro。P1为可改变规则数值/战果的确定缺陷。

## T03-I01 Float16替代权威Float32导致六维错误

- 严重度：P1；主责协同：T03主责，T01数据构建协同
- 规则依据/原文行号：data/属性数值计算.md:47-50
- 代码位置：nrc_core/catalog.py:20-23,39-57; nrc_core/constant.py:3-5
- 最小输入步骤：全量DB625形态、30性格、六维均IV0，以md总结公式构造严格Float32分步期望。
- 预期与实际：112500个标量比较中12325个不一致；例如丢丢沙地形态防御种族55、逞强（防御无修正）应121实120。Float16常数与性格小数均可偏移半数边界。
- 影响范围：全部六维计算；IV0已隔离6倍/5倍歧义，不能用该歧义解释差异。
- 证据：probe.py；probe_output.json:stats_IV0；实际摘要：`{"forms": 625, "natures": 30, "scalar_comparisons": 112500, "mismatch_count": 12325, "first_examples": [{"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "逞强", "field": "def", "base": 55, "actual": 120, "expected": 121}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "逞强", "field": "speed", "base": 75, "actual": 142, "expected": 143}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "理性", "field": "def", "base": 55, "actual": 120, "expected": 121}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "理性", "field": "speed", "base": 75, "actual": 142, "expected": 143}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "坦率", "field": "def", "base": 55, "actual": 134, "expected": 135}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "坦率", "field": "speed", "base": 75, "actual": 142, "expected": 143}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "焦虑", "field": "def", "base": 55, "actual": 120, "expected": 121}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "焦虑", "field": "speed", "base": 75, "actual": 142, "expected": 143}]}`

## T03-I02 双攻双防有效属性截断为40层提升/9层降低，违反99层规则

- 严重度：P1；主责协同：T03主责，T04执行顺序、T09/T10赋予协同
- 规则依据/原文行号：data/伤害数值计算.md:9,15,19
- 代码位置：nrc_core/models.py:387-420
- 最小输入步骤：基础攻击/防御100，分别设atk_up=9.9、def_down=9.9；附加速度同值用于观察但不由双攻双防段落推导速度上限。
- 预期与实际：99层物攻提升应1090实500，99层物防降低应约9.174实52.632；增减益并存样例125正确。速度也经过同一clamp，但其99层上限是否同属该规则保留待裁决。
- 影响范围：effective_atk/def/spatk/spdef直接调用方；计算器伤害直接读calculation_modifier，和有效属性接口不一致。
- 证据：probe.py；probe_output.json:I02_caps；实际摘要：`{"up99_actual": 500.0, "up99_expected": 1090, "down99_actual": 52.631578947368425, "down99_expected": 9.174311926605505, "both_actual": 125.0, "both_expected": 125.0, "atk99_actual": 500.0, "atk99_expected": 1090, "defdown99_actual": 52.631578947368425, "defdown99_expected": 9.174311926605505}`

## T03-I03 原始增减益与计算入口未执行99层上限

- 严重度：P1；主责协同：T03模型计算主责，T09/T10状态赋予协同
- 规则依据/原文行号：data/伤害数值计算.md:15
- 代码位置：nrc_core/models.py:422-424,440-454; nrc_core/engine/helpers.py:217-276
- 最小输入步骤：对普通精灵调用_apply_buff100次，每次atk=.1，读取calculation_modifier。
- 预期与实际：应封顶9.9；实际9.99999999999998，battle.DamageCalculator不经_clamp直接读取，100层可进入伤害公式。
- 影响范围：普通五维独立状态及复制状态输入；与I02低上限是两条不同路径错误。
- 证据：probe.py；probe_output.json:I03_max99；实际摘要：`{"actual_modifier": 9.99999999999998, "expected_max": 9.9}`

## T03-I04 Skill.copy遗漏技能威力基准，复制后入场特性重复放大

- 严重度：P1；主责协同：T03复制主责，T06配置协同，T09/T10应用原语协同
- 规则依据/原文行号：data/状态分类.md:4; data/wiki/spirits.csv:613
- 代码位置：nrc_core/models.py:208-268; nrc_core/engine/helpers.py:475-477
- 最小输入步骤：100威力1能耗技能应用挺起胸脯对应power_pct=.5，再copy_state，对原对象和副本分别再次应用同一入场修正。
- 预期与实际：两者均应保持150；原对象150、副本225。Skill.copy未复制_ability_base_power；其他非显式动态字段也需逐来源核查。
- 影响范围：挺起胸脯、国王威严、勇敢、不移等使用技能基准修正的特性；simulate_turn默认克隆也经过该方法。
- 证据：probe.py；probe_output.json:I04_skill_copy；实际摘要：`{"original_power": 150, "cloned_power": 225, "expected_both": 150, "cloned_has_base_before_reapply": false}`

## T03-I05 分精灵深拷贝破坏跨精灵状态引用，衡量增益写向游离副本

- 严重度：P1；主责协同：T03复制主责，T04 simulate_turn、特性handler协同
- 规则依据/原文行号：data/wiki/spirits.csv:30-31; data/状态分类.md:2
- 代码位置：nrc_core/models.py:546-548,688-692
- 最小输入步骤：B.ability_state镜像引用A公平鸽；BattleState.deep_copy后给B+10%攻击。
- 预期与实际：副本B引用应指副本A，副本A应+0.1；实际指向另一个游离公平鸽，对其+0.1而场上A仍0。
- 影响范围：simulate_turn默认clone=True与单独deep_copy；runtime.clone采用整体copy.deepcopy，此入口保留共享引用，不能把本问题无差别套用runtime。
- 证据：probe.py；probe_output.json:I05_graph_copy；实际摘要：`{"ref_points_to_copied_active": false, "actual_active_buff": 0.0, "detached_buff": 0.1, "expected_active_buff": 0.1}`

## T03-I06 引电扣血未执行冻结实时力竭

- 严重度：P1；主责协同：T03主责，T04统一伤害后检查协同
- 规则依据/原文行号：GAME_RULE:0007,0021；data/wiki/game_descriptions.csv:5,51
- 代码位置：nrc_core/models.py:579-590
- 最小输入步骤：HP1000、当前270、冻结1层；施加2层引电。
- 预期与实际：25%生命扣250后剩20低于冻结阈值50，应力竭；实际20存活。不是阈值相等争议。
- 影响范围：引电与冻结相互作用、即时MP和终局；与T04毒印漏检查为不同扣血入口。
- 证据：probe.py；probe_output.json:I06_electric_freeze；实际摘要：`{"actual_hp": 20, "actual_fainted": false, "expected_fainted": true}`

## T03-I07 BattleState.deep_copy复制天气id键却未映射新技能

- 严重度：P1；主责协同：T03模型复制主责，T04天气还原协同
- 规则依据/原文行号：GAME_RULE:0030；data/wiki/game_descriptions.csv:37
- 代码位置：nrc_core/models.py:688-704; nrc_core/battle.py:969-978
- 最小输入步骤：沙暴剩1回合，地系技能当前耗2，记录原耗5；simulate_turn默认clone=True双方聚能。
- 预期与实际：天气结束应恢复5；副本技能id不在旧id字典中，实际保持2。
- 影响范围：直接simulate_turn默认克隆接口；runtime.clone/new_game/export有天气键重建兜底，已明确入口差异。
- 证据：probe.py；probe_output.json:I07_weather_copy；实际摘要：`{"new_skill_key_present": false, "expected": true, "actual_cost_after_weather_ends": 2, "expected_cost_after_weather_ends": 5}`
