# T09 特性处理器问题

复现见probe.py/probe_output.json与source_correction_probe.py/source_correction_probe_output.json。用户授权特性原文用于子句核对，spirits.csv效果与DB description由T01证明一致；data根md/详解/通用规则冲突优先。不因缺独立md把明确差异存疑，没有修改业务代码。

## T09-I01 ABILITY_COMPUTE未知action静默忽略

- 严重度P1；主责T09；协同T07未知原语拒绝策略，根层不同，不重复计算同一调用。
- 规则：AGENTS.md“未实现机制抛UnsupportedMechanicError，不静默降级”。
- 代码：handlers_ability.py:31-282全部action分支末尾无else拒绝。
- 最小输入：合法Ctx，EffectTag(E.ABILITY_COMPUTE,{'action':'unknown-audit-action'})。
- 预期：明确拒绝。实际：正常返回，无状态变化、无异常；证据unknown_compute_action。
- 影响：所有配置action拼写错误或未实现子机制，默认/ability_mode均可进入。

## T09-I02 旧模型字段与不存在模块使属性倍率原语失效

- 严重度P1；主责T09；协同配置/伤害组。
- 规则：AGENTS.md显式拒绝不支持；data/伤害数值计算.md:8-16统一属性倍率模型。
- 代码：handlers_ability.py:662-738读Skill.type/Pokemon.type1/type2，from .types导入不存在的nrc_core.engine.types；:766-777用字符串“防御”比较SkillCategory枚举。
- 最小输入：标准模型Ctx含skill，分别调用DAMAGE_MOD_NON_STAB、NON_LIGHT、NON_WEAKNESS、DAMAGE_RESIST_SAME_TYPE；防御分类SkillCategory.DEFENSE调用SKILL_COST_REDUCTION_TYPE。
- 预期：正常模型可执行原语或明确拒绝，不得AttributeError/ModuleNotFoundError。实际前四项分别报错，缩壳返回空context且成本未变；证据non_stab/non_light/non_weakness/resist_same_type/defense_enum。
- 影响：涂鸦、目空/夺目、绒粉星光、偏振、缩壳。当前PASSIVE入口通常没有skill，会提前return，所以“不抛错”不表示倍率生效；执行伤害只触发BEFORE_ATTACK，相关PASSIVE没有安装持续标记。原文倍率已授权，具体未跑条件保留实现待证实，不再要求来源授权；偏振携带技能系别与代码自身type字段亦明确不符。

## T09-I03 灰色肖像与变形活画的运行标记不连通

- 严重度P1；主责T09；协同T06配置、T04伤害消费；按两专名合并现有配置问题。
- 规则：AGENTS.md禁止静默降级；data/状态分类.md:2-4要求效果状态和计算一致。用户授权原文spirits.csv:410-412，灰色肖像攻击使已有减益+3；变形活画每敌增益层威力+10%、速度+5；不存在来源授权缺口。
- 代码：handlers_ability.py:654-658只写debuff_stack_bonus，全核心无读；:1079-1083写bonus_pct_per_cost，battle.py:390-392读bonus_pct_per_layer默认0。
- 最小输入：灰色肖像ON_ENTER后正常加0.1atk_down，仍为0.1；变形活画PASSIVE后敌10层增益，同一80威力攻击伤害90仍90。证据gray_portrait/paint。
- 预期：已配置标记应在对应事件计算消费；若机制不支持明确拒绝。实际两个持久键都不能产生约定效果。
- 影响：两特性当前配置可达。灰色肖像只复现赋予标记后普通减益未变化，并静态搜索证实无消费者；未声称完整攻击回合已跑。变形活画展示速度层字符串不等于速度参与计算。

## T09-I04 多个已配置原语只写标记/临时context而无消费者

- 严重度P1；主责T09；协同回合/技能成本组。
- 规则：AGENTS.md显式拒绝不支持；data/README.md:22-35要求触发效果参与回合；data/wiki/game_descriptions.csv:6迅捷。
- 代码与影响：:434 double_damage_next（圣火骑士），:500 first_skill_agility（起飞加速），:568 aff_bonus（振奋虫心），:576/:602 context.stat_multiplier（囤积/全神贯注），:640 freeze_becomes_meteor（月牙雪糕），:1051 interrupt_cooldown_turns（威慑）；:884 carry_skill_power_bonus、:955 entry_buff_duration、:1058 low_cost_skill_power_bonus目前无特性配置，仍为实现待证实，不能归“未上线”。
- 临时倍率路径：:476破空/顺风以及:625坠星/观星写context.power_multiplier。回合末PASSIVE上下文不会用于下一次攻击，BEFORE_ATTACK只读该时点配置，不能覆盖这些PASSIVE。
- 最小输入：圣火骑士ON_COUNTER_SUCCESS后直接正常DamageCalculator，flag=True伤害仍90；破空PASSIVE传is_first=True虽然context倍率1.75，标准伤害仍90且没有first_strike_power_bonus持久flag。证据double_next/first_strike_context。其他项通过全核心写读搜索确认，未逐项完整回合动态复现。
- 预期：效果有明确消费或明确拒绝。实际：无消费且不报未支持。
- 影响边界：只证明当前原语链路不完整，不用spirits.csv独有数值认定游戏倍率绝对值。_h_ability_compute中的同名替代action有些安装了有效flag，不能误报所有first_strike功能全无实现。

## T09-I05 自动离场写入字段与消费字段不匹配

- 严重度P1；主责T09；协同T04离场结算。
- 规则：data/wiki/game_descriptions.csv:4脱离效果；AGENTS.md未实现不能静默。用户授权原文spirits.csv:42“每次行动后脱离”，配置回合结束也是明确时点差异，合T06，不再待来源裁决。
- 代码：handlers_ability.py:506-510写Pokemon.force_switch（非模型声明字段）；:513-516写auto_switch_eot；battle.py:592-599只消费auto_switch_zero_energy/auto_switch_every_turn。
- 最小步骤：防过载保护带一只存活队友，ON_TURN_END触发后ability_auto_switch(reason=every_turn)。
- 预期：已授予自动离场标记能驱动切换。实际auto_switch_eot=True，switched=False，current_a仍0；证据auto_switch。警惕/星地善良的零能路径为同类静态键不匹配，没有单独运行。
- 影响：防过载保护、奔波命、警惕、星地善良。行动后还是回合后是另一个配置问题，不和消费缺失混为同一证据。

## T09-I06 最好的伙伴在没有造成伤害时触发

- 严重度P1；主责T09；协同伤害成功事件组。
- 权威规则：data/部分规则详解/最好的伙伴.md:3-7“造成克制伤害后”，不是单纯使用克制系别技能。
- 代码：handlers_ability.py:1329-1343只检查ctx.skill存在与属性克制>1；effect_data.py:1606-1607挂ON_USE_SKILL。
- 最小输入：火系STATUS技能，对方草系，自己能量0；ON_USE_SKILL执行当前最好的伙伴配置。
- 预期：无攻击伤害，不加层不回能。实际完整状态+1层并回2能；证据best_partner_status。
- 影响：所有用可克制系别的状态/防御技能；免疫等实际0伤害攻击也可能错误触发，后者尚未逐组合运行。完整层状存储本身正确，不将其错误拆分为裸buff。

## T09-I07 固定被动授予随着每回合PASSIVE重复累加

- 严重度P1；主责T09；协同回合末/迸发组。
- 规则：data/wiki/game_descriptions.csv:11迸发入场首次行动、AGENTS.md不凭空扩展规则；具体+1/+40以用户授权spirits.csv原文为子句依据，固定授予不意味着每回合无新事件自动增长。
- 代码：handlers_ability.py:1379-1390 turn_end_repeat/skip使用+=；:1438-1448 burst_power_bonus/burst_enemy_cost_up、:1461-1464 burst_extend使用+=；battle.py:793每次回合结束重复触发PASSIVE，不清这些键。
- 最小输入：双向光速，500HP、中毒1层，连跑两次真实turn_end_effects。实际repeat=1→2，HP500→470→425（首回合2次15，次回合3次15）。预期固定触发次数加成保持相同，不因没有新事件而增长。证据repeat_accumulates。
- 另对当前配置连续两次PASSIVE：电流刺激40→80，连续负荷1→2；证据同名键。前者真正回合中是否影响第二次入场或延长迸发需迸发组完整复演，已证明存储重复增加。
- 影响：上述五类原语；passive标记可以用固定值覆盖的其他handler未受本项推断。

## T09-I09 充分燃烧触发使用4%灼烧公式

- 严重度P1；主责T09（ABILITY_COMPUTE技能复用）；协同技能组。
- 规则：data/wiki/game_descriptions.csv:3每层2%生命火系伤害；没有单独“触发伤害翻倍”依据。
- 代码：handlers_ability.py:241-252 action=double_enemy_burn_and_tick先层数*=2，再hp*0.04*层数。
- 最小输入：敌最大HP1000、当前HP500、灼烧1层，调用该action。
- 预期：层数翻为2后，按已翻倍层数触发一次2%伤害40。实际扣80，HP420；证据burn_tick。
- 影响：effect_data.py:643充分燃烧。该分支还没火系免疫过滤、没有使用统一dot伤害入口，其他附加影响只作协同线索。

## T09-I10 衡量漏复制明确增益并额外回能

- 严重度P1；结论确认缺陷；主责T09；协同状态分类组。
- 规则：data/wiki/game_descriptions.csv:13增益含威力、连击、降耗、吸血而未含当前能量；用户授权spirits.csv:30“复制敌方的增益”。
- 代码：handlers_ability.py:417-431只max复制五维up，额外能量取max、对手hook同步仅helpers._apply_buff路径；不复制全技能威力/吸血等，也不会同步_apply_ability_buff复合状态。
- 最小输入：自己能量0、敌能10/全技能威力+20，ON_ENTER。
- 预期：应复制已明确的全技能威力增益，不凭空回能；实际能量变10、威力bonus仍0，证据balance。已有同类自身增益取max或叠加才留Q03，不影响当前漏项与额外能量缺陷成立。
- 影响：公平鸽；不把双公平鸽监听、复合状态分类或其他未跑子句判通过。

## T09-I11 虫群属性时点、毒牙属性事件、毒腺阈值与原文不符

- 严重度P1；主责虫群handler目标T09、配置阶段/毒牙毒腺合T06-I11，避免重复计数。
- 规则原文：spirits.csv:158 虫群突袭入场攻防速+15%、:2 虫群鼓舞入场攻防速+10%；:85 毒牙成功施毒时物攻-40%速度-40；:115 毒腺成本<=1才加4毒。
- 实现：handlers_ability.py:520-550 只双攻且现配置PASSIVE；:781-788 检查已有毒后减魔攻魔防；:792-804 对基础cost<5施毒，effect_data.py:1246、1252、1385、1391对应。
- 最小输入与步骤：source_correction_probe.py中一只其他存活虫队友，先ON_ENTER再PASSIVE；敌预有1毒但本次普通攻击无施毒事件；毒腺使用成本3。
- 预期：虫群入场含双攻双防速度；毒牙只有本次成功施毒才加正确属性；成本3不触发毒腺。
- 实际：虫群入场无状态、PASSIVE仅atk_up/spatk_up；毒牙atk_down/speed_down仍0、spatk_down/spdef_down各0.4；3耗毒腺加4毒。
- 影响：上述4特性；存活/力竭虫计数、成本基础/实际等其他细节没有据此判通过。
- 证据：source_correction_probe_output.json；T06 ability_probe.json既有毒牙毒腺证据；clause_review逐子句保留来源行。明确差异不需要用户再次授权原文。

## T09-I12 刺肤把50威力物理伤害当固定50HP

- 严重度P1；主责T09，协同T03通用伤害公式。
- 规则：用户授权spirits.csv:423“对攻击自己的精灵造成50威力物理伤害”；data/伤害数值计算.md:6-10 威力必须结合攻击防御计算。
- 实现：handlers_ability.py:942-951 `dmg=max(1,int(power))`，不读category、不用自身攻击或目标防御。
- 最小步骤：当前刺肤ON_TAKE_HIT配置，分别令反击者物攻100和200，其他条件固定、目标物防100、HP500。
- 预期：在没有取整饱和的本输入，50威力伤害随物攻改变；未知伤害系别不影响该比例关系。
- 实际：两组均固定500→450。未调用DamageCalculator生成期望，只按原文公式的独立比例关系验证。
- 影响：刺肤所有反击；伤害系别/本系归属的未明细节留Q04，但不影响“威力当HP”缺陷成立。
- 证据：source_correction_probe.py及source_correction_probe_output.json 刺肤_100/200。
