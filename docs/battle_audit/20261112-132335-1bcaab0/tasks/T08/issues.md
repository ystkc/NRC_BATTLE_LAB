# T08 技能原语问题

本任务只承担 `nrc_core/engine/handlers_skill.py`。运行命令：设置 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1` 后运行 `python docs/battle_audit/20261112-132335-1bcaab0/tasks/T08/probe.py`。输入完整保存在 probe.py，输出为 probe_output.json。以下没有把其他函数分支、未采样参数或完整技能均判成缺陷；覆盖范围见 coverage.csv 与 parameter_review.csv。

## T08-I01 吸血在实际伤害前结算，应对临时吸血无消费者

- 严重度：High；主责 T08 原语协议，协同 T07 executor、T04 最终伤害/扣血。T04 已确认此前无同问题主记录。
- 规则依据：data/wiki/game_descriptions.csv:29，吸血按造成伤害值回复；技能原文 data/wiki/skills.csv:211 撕裂“应对状态：本次攻击吸血100%”。
- 实现位置：handlers_skill.py:260；executor.py:120-131、216-225（普通吸血在返回伤害前执行）；execute_counter_se:248-362 与旧 execute_counter 都不消费 `_life_drain_pct`；battle.py:1891 之后才应对、减伤和实际扣血。
- 最小步骤：甲500/1000HP，80威力普通攻击带100%吸血；乙使用50%减伤防御，完整回合。另使用真实撕裂配置对无效果状态技能；以及直接 ON_COUNTER LIFE_DRAIN 的协议输入。
- 预期：普通场景吸血依据减伤后的实际造成伤害；撕裂成功应对状态时，本次攻击具备100%吸血。
- 实际：`drain_before_reduction` 乙500→455，甲500→590（吸90但扣45）；`counter_drain` 只返回 `_life_drain_pct=1.0`，甲仍500。真实撕裂完整回合见 `actual_counter_drain_撕裂`，甲未回血。
- 影响：LIFE_DRAIN、GRANT_LIFE_DRAIN 常驻吸血，以及应对阶段授予本次吸血；溢出伤害/其他最终修正尚未逐场景推断。
- 证据：probe_output.json 上述3项；parameter_review.csv 所有关联 LIFE_DRAIN/GRANT_LIFE_DRAIN 行。不能把全体受关联对象的其他子句升级通过。

## T08-I02 沙暴添加规则外伤害，并在重设时重复折半

- 严重度：High；主责 T08 weather handler；沙暴额外伤害与 T04-I14 合并同一根因，T04 保留真实回合调用入口协同。
- 汇总拆分：本编号是两项独立子根因的交付组；`T08-I02#额外伤害` 与 T04-I14 合并，`T08-I02#重复折半` 独立保留，不能因为前者去重而丢掉后者。0成本被抬到1为折半表达式的静态附带边界，未作为已运行样本。
- 规则依据：data/wiki/game_descriptions.csv:37 只规定双方地系技能能耗减半；用户架构规则禁止推测未载明机制。
- 实现位置：handlers_skill.py:851-869、881-900；battle.py:938-955 调用与天气结束恢复。
- 最小步骤：沙暴下，普通系甲当前500HP、场下普通精灵100HP，均最大1000HP，调用回合末天气处理。另地技能初始成本4，连续设置两次沙暴。
- 预期：不产生无依据的额外天气扣血；重设相同天气不会把当前半价再折半。
- 实际：`sand_invented_damage` 场上500→438、场下100→38；`sand_reapply` 成本4→2→1。代码还强制至少1成本，初始0成本地技能可被提高到1，未为这条另跑输入。
- 影响：沙涌、任何设置沙暴的入口；沙暴存续期间双方所有非地/机械存活精灵（含场下）被额外扣血，重复设天气持续压低地技能成本。天气恢复覆盖其他并行成本修正需 T04 进一步核对。
- 证据：probe_output.json#sand_invented_damage、sand_reapply；静态语句 max(1, sk.energy_cost // 2)。

## T08-I03 雷鸣回合末分支被外层天气白名单排除

- 严重度：High；主责 T08 原语与调用接口，协同 T04 回合末。
- 规则依据：data/wiki/game_descriptions.csv:50，雷鸣时双方每回合结束获得1层引电，电系免疫；data/wiki/skills.csv:171 惊雷设置8回合雷鸣。
- 实现位置：handlers_skill.py:906-912 有 thunder/雷鸣处理；battle.py:939 仅允许 sandstorm/hail/snow 调用该函数。
- 最小步骤：双方普通系无引电，state.weather='thunder'、weather_turns=8，运行 turn_end_effects。
- 预期：双方各1层引电。
- 实际：`thunder_guard` 双方均0；不是 handler 不存在，而是正常回合入口到不了其分支。
- 影响：惊雷及显式雷鸣天气状态；不据不可达把实现缺口标未上线。
- 证据：probe_output.json#thunder_guard；parameter_review.csv 惊雷行。

## T08-I04 转换型施加绕过状态免疫；self 中毒先检查错误对象

- 严重度：High（转换免疫）；self 参数为 Medium、当前专名可达性待证实；主责 T08，特性其他直接施加归 T09。
- 规则依据：data/wiki/game_descriptions.csv:2-3 毒系免疫中毒、火系免疫灼烧。
- 实现位置：handlers_skill.py:270-290 先检查 ctx.target 免疫再选择 self；487-507 将印记直接转 burn_stacks；580-588 增益直接转 poison_stacks；959-965 counter_override 直接替换中毒层数同类接口风险。
- 最小步骤：火系乙已有2层攻击印记，转换每层3灼烧。另普通甲对毒系乙执行 target=self 的2层中毒。
- 预期：火系不获得灼烧；self 中毒应查甲自身是否免疫，不能由乙系别阻止。
- 实际：`convert_fire_immune` 火系获得6灼烧；`self_poison_wrong_immunity` 普通甲未获得中毒。
- 影响：炎爆术、焚烧烙印等原语配置；增益转毒与counter_override静态见同样直接写入，但本次没有独立参数复现，不宣称每个技能已实证。self 参数当前配置是否实际使用单列 reachability。
- 证据：probe_output.json 对应2项；parameter_review.csv 转换原语行。

## T08-I05 中毒印记专用写入绕过普通负面印记单槽

- 严重度：High；主责 T08，协同 T10 吟游来源槽。
- 规则依据：data/wiki/game_descriptions.csv:41，最多1种正面、1种负面印记；data/状态分类.md:6 绑定阵营。
- 实现位置：handlers_skill.py:332-334 与592-605 直接写 poison_mark；361-389 通用 handler 才执行普通负槽替换及吟游来源隔离。
- 最小步骤：敌阵营已有 spirit_mark=2，执行 POISON_MARK stacks=1。
- 预期：普通中毒印记替换其他普通负面印记，不能让普通负面并存；吟游例外仅由其来源规则授权。
- 实际：`poison_mark_slot_bypass` 同时留下 spirit_mark=2 与 poison_mark=1。
- 影响：中毒印记施加、毒层转印记入口；吟游专属来源在这两个函数亦未分槽，属于静态协同线索而未冒充该特性完整复现。
- 证据：probe_output.json#poison_mark_slot_bypass；mark_slots 表明通用函数本身确实替换，差异是旁路写入。

## T08-I06 心灵洞悉把星陨印记写为精灵星陨状态

- 严重度：High；主责 T08，协同 T06 配置语义。
- 规则依据：data/wiki/skills.csv:159 原文“敌方获得星陨印记，获得层数等于敌方印记层数”；data/状态分类.md:4-6 区分精灵状态与阵营印记；data/wiki/game_descriptions.csv:34 星陨印记由非幻技能攻击触发。
- 实现位置：effect_data.py:392-393 → MARKS_TO_METEOR；handlers_skill.py:527-534 增加 ctx.target.meteor_stacks 并设3回合倒计时。
- 最小步骤：敌方阵营 attack_mark=2，执行该原语。
- 预期：敌阵营新增2层星陨印记，并依印记槽规则处理旧负面印记。
- 实际：`marks_to_meteor_kind` 阵营仍只有 attack_mark=2；精灵 meteor_stacks=2、meteor_countdown=3。
- 影响：心灵洞悉的触发、下场继承、驱散和伤害时点全部不同。
- 证据：probe_output.json#marks_to_meteor_kind；object_resolution.csv 心灵洞悉。

## T08-I07 回血反转只把倍数当布尔值，丢失2倍

- 严重度：High；主责 T08 通用回血，协同 T09 元素回血、T07 executor 吸血（相同模式），T06 伪造账单配置。
- 规则依据：data/wiki/skills.csv:23 伪造账单“改为失去2倍（含溢出的回复量）”。
- 实现位置：handlers_skill.py:189-191、518-521。anti_heal_multiplier 为2时仅 max(0,current_hp-heal)，没有乘 anti。
- 最小步骤：甲500/1000HP，anti_heal_multiplier=2，HEAL_HP pct=0.1。
- 预期：失去200HP，至300。
- 实际：`anti_heal_multiplier` 甲至400，只失去100。
- 影响：普通技能回血、消耗印记回血；其他来源应逐消费者合并根因，不能因某个来源已查就全路径通过。
- 证据：probe_output.json#anti_heal_multiplier；T09 static_review 中对应回血说明。

## T08-I08 应对两侧永久减耗参数被静默忽略

- 严重度：High；主责 T08，协同 T06 原文参数与 T07 应对专用分发。
- 规则依据：data/wiki/skills.csv:400 能量守恒“应对攻击：两侧技能能耗永久-1”。
- 实现位置：effect_data.py:473 后配置 PASSIVE_ENERGY_REDUCE range='adjacent'；executor.py:321 专门调用 handlers_skill.py:969-975，而后者只处理 range=='all'。
- 最小步骤：己方三个槽成本[4,2,3]，中槽技能应对攻击；调用 execute_counter 的真实新格式，原语 reduce=1、range=adjacent。
- 预期：两侧槽成本变[3,2,2]。
- 实际：`adjacent_counter_reduce` 仍[4,2,3]，无异常。
- 影响：能量守恒应对增益；all范围公开修正缺失已归 T07-I04，不重报该根因。
- 证据：probe_output.json#adjacent_counter_reduce；object_resolution.csv 能量守恒。

## T08-I09 听桥反击复制原始伤害，未按自身攻击和武系威力计算

- 严重度：High；主责 T08，协同 T04 应对传入伤害。
- 规则依据：data/wiki/skills.csv:96 原文要求武系物理伤害、威力等于被应对技能；data/伤害数值计算.md:6-24 区分威力、攻防、属性克制与减伤。
- 实现位置：handlers_skill.py:943-955 注释和实现均原样反射 ctx.damage，不读取敌技能威力、自己物攻/对方物防/武系克制。
- 最小步骤：自身物攻200、敌物防100，双方普通系，被应对技能威力80、传入原始伤害90。依原文武克普通系数2、自身非武系所以本系1，独立用Fraction计算 floor(half_up(80×2×1×200×37/41)/100)。
- 预期：独立推导288（此数用于证明两种语义不同，不证明听桥所有条件）；推导源为原文与显式输入，不调用DamageCalculator。
- 实际：`mirror_raw_damage` 仅反90，敌500→410。
- 影响：听桥反击伤害，尤其双方攻防不同、对手属性克制不同时。
- 证据：probe_output.json#mirror_raw_damage 实际90；independent_oracle.py与independent_oracle_output.json 独立期望288。旧probe曾调用DamageCalculator给期望，只能作为差异线索，已用独立有理数推导替代，probe.py未来复跑也已改用独立算法。不与 T04 最终减伤规则混为同一机制。

## T08-I10 已配置动态威力条件无执行分支且不拒绝

- 严重度：High；主责 T08，协同 T06 参数生成；未知机制静默降级与 T07-I01 共同违反拒绝原则，但此处是已注册原语的参数遗漏。
- 规则依据：用户 AGENTS 未实现机制抛 UnsupportedMechanicError；data/wiki/skills.csv:56 冰锋横扫等于敌技能总成本10倍，:500 钢钻等于两侧技能威力和三分之一。
- 实现位置：handlers_skill.py:660-714 缺 enemy_total_cost/adjacent_power_sum 分支；effect_data 的两个原语配置已带上述参数，原技能威力为占位1。
- 最小步骤：真实配置，敌唯一技能成本4；钢钻左右威力120、60。调用 execute_skill；同时直接未知条件测试拒绝协议。
- 预期：动态基础威力分别40、60，再走伤害公式；不支持时明确拒绝。
- 实际：`actual_dynamic_冰锋横扫`、`actual_dynamic_钢钻` 都按基础1结算，伤害1、显示最终威力1.25；未知条件也无异常、result空。
- 影响：这两个具名技能已证实；其他 conditional_buff/stat/filter 未识别静默跳过只是同类静态线索，不能推断其所有配置当前都缺失。
- 证据：probe_output.json 三项 power_condition 与两项 actual_dynamic；parameter_review.csv 保留实际参数。

## T08-I11 单击技能也受到连击增益

- 严重度：High；主责 T08 连击展开，协同 T03 DamageCalculator 通用输入。
- 规则依据：data/wiki/game_descriptions.csv:36 改变连击次数仅对有连击技能生效。
- 实现位置：handlers_skill.py:79-104 对所有攻击统一加 hit_count_mod/毒层/萌化层，未先判断原技能是否连击；battle.py:332 直接使用传入 hit_count_override。
- 最小步骤：原技能 hit_count=1，80威力；无连击修正运行一次，再将 hit_count_mod=2 运行相同技能。
- 预期：原始单击技能不获得连击变化，仍90伤害。
- 实际：`single_hit_buff` 90→270，变为3击。
- 影响：单击技能受全局连击、毒层连击/萌化连击等修正；特性明确“固定连击数”的规则例外须逐原文确认，不能把所有例外一并推断。
- 证据：probe_output.json#single_hit_buff；未检查逐击被动触发/击杀停止，本问题只证实单击边界。
