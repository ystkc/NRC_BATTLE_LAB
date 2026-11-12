# T07 问题清单

所有复现使用 `python docs/battle_audit/20261112-132335-1bcaab0/tasks/T07/probe.py`；输入在 probe.py，实际输出在 probe_output.json。数字为构造场景，未冒充完整平台对局。没有修改业务代码。

## T07-I01 未知效果被静默忽略

- 严重度 P1；主责 T07；协同核心输入支持性校验组。
- 规则依据：用户本次提供的 AGENTS.md“未实现机制抛 UnsupportedMechanicError，不静默降级”。
- 代码：`nrc_core/engine/dispatch.py:85-142`，尤其 `if handler` 后没有拒绝分支；`registry.py:240-425`。
- 最小步骤：构造合法 Ctx，调用 `_apply_tag(EffectTag('unregistered-audit-effect'), ctx)`。
- 预期：明确拒绝未知机制。实际：无异常，`handled=False` 只进调试日志。证据 `probe_output.json:unknown_effect`。
- 影响：公开效果执行入口，无论技能或特性模式均可静默失效。当前 E 共200种，199种注册，唯一未注册 INTERRUPT 在两种应对入口有明确特判，不能据此误报“正常应对打断未实现”；但放在普通效果位置同样静默忽略。

## T07-I02 迅捷攻击只计算伤害，未结算

- 严重度 P1；主责 T07；协同回合/切换组。
- 规则依据：`data/README.md:22-28`，主动更换精灵触发迅捷技能；`data/wiki/game_descriptions.csv:6` 使用第一个能量满足的迅捷技能；`data/伤害数值计算.md:6-10` 伤害公式。
- 代码：`executor.py:551-570` 丢弃 execute_skill 返回值；伤害在 `handlers_skill.py:118` 写入 result，不扣目标普通伤害；`battle.py:1555` 直接调用迅捷入口，没有消费该结果。
- 最小步骤：500HP目标，普通80威力攻击附 E.AGILITY/E.DAMAGE，调用 execute_agility_entry。
- 预期：至少扣除已计算出的90普通攻击伤害。实际：能量10→8，目标500→500，单独execute_skill返回damage=90。证据 `agility_damage`。
- 影响：所有有 effects 的迅捷攻击，例如生成配置的翼击（`skill_effects_generated.py:450`）。同一入口也丢弃应对容器、脱离、自毁等需上层消费的结果；这些附加影响未逐项复现，不扩大确证范围。

## T07-I03 动态授予的迅捷标志不被迅捷入口识别

- 严重度 P1；主责 T07；协同特性配置组。
- 规则依据：`game_descriptions.csv:6` 具备迅捷应能主动换入释放；`effect_models.py` 没有另一种“只展示不执行”的迅捷语义。快锤/暴食具体授予条件见配置，详见 Q02 的来源限制。
- 代码：`helpers.py:473-474` 只设置 s.agility=True；`executor.py:559-565` 对有effects的技能只扫描 E.AGILITY，不读skill.agility。
- 最小步骤：有DAMAGE效果的2能耗技能，调用 `_apply_matching_skill_mods(..., {'grant_agility':True,'energy_cost_lt':3})`，再调用迅捷入口。
- 预期：已经被本实现授予迅捷的技能进入释放流程。实际：agility=True，能量仍10，未执行。证据 `granted_agility`。
- 影响：所有经modify_matching_skills授予迅捷的带effects技能；当前快锤、暴食走此路。区别于I02：本项连扣能和效果分发都未开始。

## T07-I04 水环应对路径遗漏全技能公开修正归属

- 严重度 P2；主责 T07；协同状态可见性组。
- 规则依据：`data/对战过程中的信息遮蔽规则.md:3-7`，全局增减益公开，特定技能效果仅己方可见。
- 代码：`executor.py:308-309,402-404` 直调 `_h_passive_energy_reduce_water_ring`；`dispatch.py:30-39` 已定义该handler的全局来源记录，但直调绕过它。
- 最小步骤：2能耗技能，执行 ON_COUNTER(category=attack) 内 PASSIVE_ENERGY_REDUCE(reduce=2,range=all)。对照以 ability_mode=True 从_apply_tag执行相同原语。
- 预期：两条路径均记录全技能能耗-2并保留逐槽实际变化。实际：应对路径cost=0，public/private均null；对照组public.energy_cost=-2。证据 `counter_public` 与 `ability_public_control`。
- 影响：新旧应对格式水环效果；底层能耗确实降低，问题是公开归属缺失，而非能耗没有变化。平台最终展示由协同组验证。

## T07-I05 传动入口执行旧含义，没有实现规则要求的技能移位

- 严重度 P1；结论 未实现；主责 T07；协同回合开始组、技能传动配置组。
- 规则依据：`data/部分规则详解/传动机制.md:3-9`，回合开始循环移位，所有传动次数完成后结束；`game_descriptions.csv:33`同义。
- 代码：`executor.py:578-618` 计算后N位技能并触发其被动，既不移动列表，也不计传动次数；`battle.py:2220-2223` 从使用技能后调用。全nrc_core搜索DRIVE/drive/传动未找到另一套规则移位入口。
- 最小步骤：技能列表[审计攻击,后位]，execute_drive(...,1)。实际顺序仍[审计攻击,后位]，预期传动后[后位,审计攻击]。证据 `drive_position`。
- 影响：所有携带DRIVE的技能及相关位置特性。没有把此处“使用后触发被动”解释为文档允许的另一种机制。

## T07-I06 旧格式迅捷释放多个技能（目前仅接口可达）

- 严重度 P2；可达性：兼容接口可达，当前平台配置未证实；主责 T07。没有文档明确尚未上线，规则结论不能用可达性替代。
- 规则依据：`game_descriptions.csv:6` 第一个能量满足要求的迅捷技能。
- 代码：`executor.py:559-562` 旧格式释放后continue，和新格式的break不一致。
- 最小步骤：携带两个均agility=True、无effects、各2能耗的技能，调用迅捷入口。
- 预期：仅首个，剩8能量。实际：剩6，两个均释放。证据 `legacy_agility_first`。
- 影响：旧模型兼容入口；当前平台支持技能是否存在无effects的可用迅捷项未得到充分证明，因此不当成线上必现。

## T07-I07 POST_USE忽略过滤器，极限撕裂低血量仍受惩罚

- 严重度 P1；可达性 当前生成配置可达；主责 T07；协同技能生成组。
- 依据：`effect_models.py:424-441` SkillEffect 定义包含阶段与过滤器，未声明ON_USE/POST_USE过滤无效；具体游戏规则需要Q01裁决。
- 代码：`executor.py:194-203,220-224` 不检查filter；`filters.py:39-40` 遇category直接返回True，跳过其余合取条件；counter_se只检查category。
- 最小步骤：满血，HEAL_ENERGY(amount=1)配filter self_hp_lt=0.5，分别放ON_USE/POST_USE，实际都回1；category+不满足HP过滤实际True。
- 预期：filter不满足不触发。实际如上，见 `filter_ON_USE`、`filter_POST_USE`、`category_filter`。
- 现有配置复现：`skill_effects_generated.py:282` 极限撕裂POST_USE明确self_hp_gt=0.5。100/500HP使用后，atk_up/spatk_up仍变为-0.5，见 `live_post_filter`。这会把有条件惩罚改为无条件惩罚。data/wiki/skills.csv:243原文已获用户授权，“若自己生命高于50%”明确不是无条件惩罚；使用前/后精确取值时点另见Q01，不再保留来源缺失。
- 完整配置枚举证据config_filters.json：POST_USE有且仅有该一项；ON_USE没有非空SE.filter，category组合亦未发现，因此另外两种构造仅属潜在扩展缺陷，不当成现有实战问题。
- 影响范围：现有极限撕裂低血量也被施加双攻惩罚；ON_USE/category合取只证明扩展协议风险，不扩成现有全部技能必现。

## T07-I08 嵌套SkillEffect导致正常技能执行崩溃

- 严重度 P1；主责 T06生成fallback（主协调已确认与其8技能异常合并）；T07协同执行器/分发边界，保留本项接口证据，不重复计算问题。
- 规则依据：AGENTS.md未实现机制应显式UnsupportedMechanicError；SkillEffect.effects契约为EffectTag列表；`data/README.md:8`状态技能应执行回复等效果，不应因内部配置类型崩溃。
- 代码：`skill_effects_generated.py:284-285` 架势、根吸收的外SE内再次包SE；`executor.py:197-198` 未校验子节点类型，`dispatch.py:99` 访问tag.type抛AttributeError。
- 最小步骤：从当前SKILL_EFFECTS_GENERATED读取架势效果，交给execute_skill。实际：`AttributeError: 'SkillEffect' object has no attribute 'type'`。预期：可正常执行已支持的回复原语；若配置不支持，应在边界明确拒绝。证据`nested_skill_effect`。
- 当前生成表叠加手写覆盖后，顶层SE内部直接嵌SE共8项：休息回复、富养化、徒长、杠杆置换、架势、根吸收、雪球、风隐。见`nested_skill_effect_configs`，这是结构枚举，不声称其余7项均运行到故障；不同阶段/条件可能延迟暴露。
- 影响范围：8项生成嵌套配置的正常效果结算可能崩溃，重新生成又会加深嵌套；T06逐对象执行作为主证据，本任务仅分发接口协同。

## T07-I09 清除减益只清属性，漏全部明确异常与技能负修正

- 严重度 P1；结论确认缺陷；主责 T07 helpers；协同 T08 CLEANSE/DISPEL_DEBUFFS入口、T06真实技能对象、T00 GAME_RULE8双向规则。
- 规则依据：data/wiki/game_descriptions.csv:14（主清单GAME_RULE8）明确减益包含降低属性/技能威力/连击、增加能耗以及中毒、灼烧、寄生、冻结、萌化、引电；排除印记/特性/其他。data/wiki/skills.csv:285洗礼、:521除厄明确驱散自己的减益；data/状态分类.md:2-6区分精灵/技能/阵营绑定，不把绑定位置解释为不能清除。
- 代码位置：helpers.py:300-312 `_clear_debuffs`只归零五个_down和负priority，注释主动排除poison/burn等；handlers_skill.py:766-784 CLEANSE/DISPEL_DEBUFFS委派该函数；generated.py:318、595真实配置可达。
- 最小输入/步骤：cleanse_probe.py从当前合并配置读取洗礼、除厄的完整effects，不手写替代清除标签。甲800/1000HP，毒1/烧2/冻1/寄生1/萌化1/引电1，atk_down=.3、全技能成本mod=2、威力bonus=-20、临时加耗2；阵营poison_mark=2，最好的伙伴特性及1层复合状态。执行execute_skill。
- 预期：明确减益异常清零、属性减益清零；印记和特性保留。全技能负威力、加耗亦属于明确减益，不能全数遗留；洗礼自身降耗的先后来源另说明。
- 实际：两个真实技能全部六种异常原样保留，atk_down确实归0；除厄的成本mod=2、威力-20、临时加耗2全部保留。洗礼先自身-1使成本mod=1后仍未清。印记、特性身份和复合状态控制均保留，控制没有把正确排除项误算缺陷。
- 影响范围：洗礼/除厄及所有清除减益委派入口；单技能永久负状态和特性组合分类需逐源核对，不把这次异常反例扩成所有状态都应删除。
- 证据：cleanse_probe.py、cleanse_probe_output.json#洗礼/#除厄；coverage对应CODE helpers.py:300已从限定通过改确认缺陷；T08 object_resolution回填两技能。

## T07-I10 王子的诺言把萌化误判增益，触发相反减耗

- 严重度 P1；结论确认缺陷；主责 T07分类快照；协同 T10萌化施加、T06原文配置。萌化施加本身不是本问题根因。
- 规则依据：game_descriptions.csv:14明确萌化为减益；spirits.csv:58已授权王子原文：每回合各1次，获得增益-1成本、获得减益+1成本。
- 代码：helpers.py:24-35把cute_stacks列buffs而非debuffs；:39-55按buff分支减耗；dispatch.py:84、124附近对双方前后快照并调用。
- 最小输入/步骤：读取真实“退化”完整effects；敌方王子的诺言，未触发当回合增减益监听，有1个合法退化形态，携带成本2技能；执行退化。
- 预期：获得1层萌化属于减益，成本2→3，记录debuff回合限次。
- 实际：cute_stacks=1，但成本2→1，记录prince_promise_buff_turn=1，触发相反方向。
- 影响：王子所有萌化来源；其他未观察技能负修正/复合状态不以此样本判断。
- 证据：cleanse_probe_output.json#王子萌化分类；未调用伤害计算器生成期望，2+1=3取自原文常量。
