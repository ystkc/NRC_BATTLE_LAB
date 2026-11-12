# 确认缺陷与已知未实现机制

业务代码未修复。下列按影响/严重度排序并合并跨任务同根反例。原编号保留以便追溯；完整参数、实际状态和事件见各任务输入/输出。P1为可改变结果、机制缺失或正常执行失败，P2为输入/协议/显示偏差，P3为局部界面问题。接口可达不等于当前阵容必现，原记录分别说明。

70种空特性属于未实现：direct builder正确抛UnsupportedMechanicError，但实际平台抹名后放行，主根因T11-I01；17血脉、传动、禁足和选择等静默缺口分别列于所属问题。完整对象清单见T06最终表，不能把未实现等同未上线。

| 汇总编号 | 严重度 | 主责任务 | 原编号/根因 |
|---|---|---|---|
| AUD-001 | P1 | T11 | [T11-I01 平台自动抹去未实现特性，绕过核心构建拒绝](#aud-001) |
| AUD-002 | P1 | T06 | [T06-I01 生成回退重复包装SkillEffect，8技能在执行时崩溃](#aud-002) |
| AUD-003 | P1 | T02 | [T02-I08 奉献减耗别名错字使随机初始化崩溃](#aud-003) |
| AUD-004 | P1 | T05 | [T05-I04 替补入场与连锁入场力竭不扣MP](#aud-004) |
| AUD-005 | P1 | T04 | [T04-I03 50回合强制裁决未实现](#aud-005) |
| AUD-006 | P1 | T03 | [T03-I01 Float16替代权威Float32导致六维错误](#aud-006) |
| AUD-007 | P1 | T10 | [T10-I11 化茧未免疫致命伤害、主动降为1生命且缺2次上限](#aud-007) |
| AUD-008 | P1 | T09 | [T09-I02 旧模型字段与不存在模块使属性倍率原语失效](#aud-008) |
| AUD-009 | P1 | T05 | [T05-I05 初始化、补位和下一回合准备在种子随机域之外](#aud-009) |
| AUD-010 | P1 | T01 | [T01-I01 采集目录迁移后入口导入及项目根路径失效](#aud-010) |
| AUD-011 | P1 | T02 | [T02-I01 构造输入中的力竭精灵被复活](#aud-011) |
| AUD-012 | P1 | T02 | [T02-I02 六项正资质被完整接受，缺少最多三项校验](#aud-012) |
| AUD-013 | P1 | T02 | [T02-I05 输入中多个同属性增益被后项覆盖](#aud-013) |
| AUD-014 | P1 | T03 | [T03-I02 双攻双防有效属性截断为40层提升/9层降低，违反99层规则](#aud-014) |
| AUD-015 | P1 | T03 | [T03-I03 原始增减益与计算入口未执行99层上限](#aud-015) |
| AUD-016 | P1 | T03 | [T03-I04 Skill.copy遗漏技能威力基准，复制后入场特性重复放大](#aud-016) |
| AUD-017 | P1 | T03 | [T03-I05 分精灵深拷贝破坏跨精灵状态引用，衡量增益写向游离副本](#aud-017) |
| AUD-018 | P1 | T03 | [T03-I07 BattleState.deep_copy复制天气id键却未映射新技能](#aud-018) |
| AUD-019 | P1 | T04 | [T04-I01 技能/特性减伤晚于逐击公式取整](#aud-019) |
| AUD-020 | P1 | T04 | [T04-I02 石头大餐用生命补能后重复扣完整能耗](#aud-020) |
| AUD-021 | P1 | T04 | [T04-I04 脱离未检查本回合入场免疫](#aud-021) |
| AUD-022 | P1 | T04 | [T04-I05 奉献已获得层数在每次使用时重复写为永久强化](#aud-022) |
| AUD-023 | P1 | T04 | [T04-I06 毒印/荆刺等直接扣血漏冻结实时力竭检查](#aud-023) |
| AUD-024 | P1 | T04 | [T04-I07 蓄电印记按入场回合而非首次行动生效](#aud-024) |
| AUD-025 | P1 | T04 | [T04-I08 回合末先特性回血后状态伤害，与总规则相反](#aud-025) |
| AUD-026 | P1 | T04 | [T04-I09 减速印记错误采用比例减速](#aud-026) |
| AUD-027 | P1 | T04 | [T04-I10 龙噬印记触发能耗和效果均不符原文](#aud-027) |
| AUD-028 | P1 | T04 | [T04-I11 普通脱离被随机换人且不等待用户选择](#aud-028) |
| AUD-029 | P1 | T04 | [T04-I13 湿润印记被擅自消费并永久写入全队技能能耗](#aud-029) |
| AUD-030 | P1 | T04 | [T04-I14 沙暴凭空对全队追加1/16生命伤害](#aud-030) |
| AUD-031 | P1 | T05 | [T05-I01 愿力动作按原首槽过滤且无法选择替换后不用](#aud-031) |
| AUD-032 | P1 | T05 | [T05-I02 愿力还原按原主人固定首槽，交换后临时技能遗留](#aud-032) |
| AUD-033 | P1 | T05 | [T05-I03 首领化更新六维和特性但未更新战斗属性](#aud-033) |
| AUD-034 | P1 | T05 | [T05-I06 技能槽锁定未进入合法动作过滤](#aud-034) |
| AUD-035 | P1 | T05 | [T05-I07 禁足机制未表示，流沙执行后仍可离场](#aud-035) |
| AUD-036 | P1 | T05 | [T05-I08 选择类仅保存选项字符串，两个分支效果未执行](#aud-036) |
| AUD-037 | P1 | T05 | [T05-I09 新对局未触发初始精灵入场特性](#aud-037) |
| AUD-038 | P1 | T06 | [T06-I02 手写技能覆盖保留过期数值，覆盖正确数据源](#aud-038) |
| AUD-039 | P1 | T06 | [T06-I03 生成产物数值和目标陈旧或错误](#aud-039) |
| AUD-040 | P1 | T06 | [T06-I04 固定技能威力误编码为百分比](#aud-040) |
| AUD-041 | P1 | T06 | [T06-I05 “回复”未被“恢复”正则识别，附加回复静默丢失](#aud-041) |
| AUD-042 | P1 | T06 | [T06-I06 应对容器有类别但丢失应对附加效果](#aud-042) |
| AUD-043 | P1 | T06 | [T06-I07 无伤害技能的本次多连击被猜测为全局永久连击增益](#aud-043) |
| AUD-044 | P1 | T06 | [T06-I08 动态条件丢失、状态凭空增加、条件主体改变](#aud-044) |
| AUD-045 | P1 | T06 | [T06-I09 手写复合效果与当前原文不符](#aud-045) |
| AUD-046 | P1 | T06 | [T06-I10 特性手写倍率/固定值与当前原文不符](#aud-046) |
| AUD-047 | P1 | T06 | [T06-I11 特性属性目标/触发阈值和子效果遗漏](#aud-047) |
| AUD-048 | P1 | T06 | [T06-I12 特性的时点、受益者和偷取行为错误](#aud-048) |
| AUD-049 | P1 | T06 | [T06-I13 空技能效果未被拒绝，消耗能量后静默零效果](#aud-049) |
| AUD-050 | P1 | T06 | [T06-I14 先手属性解析后未输出、未注入，默认归零](#aud-050) |
| AUD-051 | P1 | T06 | [T06-I15 蓄力属性解析后未输出、未注入，默认立即攻击](#aud-051) |
| AUD-052 | P1 | T07 | [T07-I01 未知效果被静默忽略](#aud-052) |
| AUD-053 | P1 | T07 | [T07-I02 迅捷攻击只计算伤害，未结算](#aud-053) |
| AUD-054 | P1 | T07 | [T07-I03 动态授予的迅捷标志不被迅捷入口识别](#aud-054) |
| AUD-055 | P1 | T07 | [T07-I05 传动入口执行旧含义，没有实现规则要求的技能移位](#aud-055) |
| AUD-056 | P1 | T07 | [T07-I07 POST_USE忽略过滤器，极限撕裂低血量仍受惩罚](#aud-056) |
| AUD-057 | P1 | T07 | [T07-I09 清除减益只清属性，漏全部明确异常与技能负修正](#aud-057) |
| AUD-058 | P1 | T07 | [T07-I10 王子的诺言把萌化误判增益，触发相反减耗](#aud-058) |
| AUD-059 | P1 | T08 | [T08-I01 吸血在实际伤害前结算，应对临时吸血无消费者](#aud-059) |
| AUD-060 | P1 | T08 | [T08-I02B 重复设置沙暴把已经折半的地系技能再次折半](#aud-060) |
| AUD-061 | P1 | T08（接口）+T04（调用） | [T08-I03 雷鸣回合末分支被外层天气白名单排除](#aud-061) |
| AUD-062 | P1 | T08 | [T08-I04 转换型施加绕过状态免疫；self 中毒先检查错误对象](#aud-062) |
| AUD-063 | P1 | T08 | [T08-I05 中毒印记专用写入绕过普通负面印记单槽](#aud-063) |
| AUD-064 | P1 | T08 | [T08-I06 心灵洞悉把星陨印记写为精灵星陨状态](#aud-064) |
| AUD-065 | P1 | T08 | [T08-I07 回血反转只把倍数当布尔值，丢失2倍](#aud-065) |
| AUD-066 | P1 | T08 | [T08-I08 应对两侧永久减耗参数被静默忽略](#aud-066) |
| AUD-067 | P1 | T08 | [T08-I09 听桥反击复制原始伤害，未按自身攻击和武系威力计算](#aud-067) |
| AUD-068 | P1 | T08 | [T08-I10 已配置动态威力条件无执行分支且不拒绝](#aud-068) |
| AUD-069 | P1 | T08 | [T08-I11 单击技能也受到连击增益](#aud-069) |
| AUD-070 | P1 | T09 | [T09-I01 ABILITY_COMPUTE未知action静默忽略](#aud-070) |
| AUD-071 | P1 | T09 | [T09-I03 灰色肖像与变形活画的运行标记不连通](#aud-071) |
| AUD-072 | P1 | T09 | [T09-I04 多个已配置原语只写标记/临时context而无消费者](#aud-072) |
| AUD-073 | P1 | T09 | [T09-I05 自动离场写入字段与消费字段不匹配](#aud-073) |
| AUD-074 | P1 | T09 | [T09-I06 最好的伙伴在没有造成伤害时触发](#aud-074) |
| AUD-075 | P1 | T09 | [T09-I07 固定被动授予随着每回合PASSIVE重复累加](#aud-075) |
| AUD-076 | P1 | T09 | [T09-I09 充分燃烧触发使用4%灼烧公式](#aud-076) |
| AUD-077 | P1 | T09 | [T09-I10 衡量漏复制明确增益并额外回能](#aud-077) |
| AUD-078 | P1 | T09 | [T09-I11 虫群入场时点和攻防速目标未落实（毒牙/毒腺合T06-I11）](#aud-078) |
| AUD-079 | P1 | T09 | [T09-I12 刺肤把50威力物理伤害当固定50HP](#aud-079) |
| AUD-080 | P1 | T10 | [T10-I01 随机奉献未剔除满层候选，指定奉献绕过上限](#aud-080) |
| AUD-081 | P1 | T10 | [T10-I02 折射按系别去重且排除本技能，丢失独立效果](#aud-081) |
| AUD-082 | P1 | T10 | [T10-I03 折射幻系写入星陨状态而非星陨印记](#aud-082) |
| AUD-083 | P1 | T10 | [T10-I04 折射漏火毒同系免疫，地系固定减速误作比例](#aud-083) |
| AUD-084 | P1 | T10 | [T10-I05 契约前三种球把速度百分比当固定点数，淘沙球也误用比例](#aud-084) |
| AUD-085 | P1 | T10 | [T10-I06 柔软球单效果错误复用常规球整包，9个分支效果超额或目标错误](#aud-085) |
| AUD-086 | P1 | T10 | [T10-I07 稀兽花宝只实现萌血脉，17分支缺失且入口固定萌](#aud-086) |
| AUD-087 | P1 | T10 | [T10-I08 解除或转移萌化只清层数，不恢复形态属性](#aud-087) |
| AUD-088 | P1 | T10 | [T10-I09 萌化覆盖基础速度导致永久速度增益下次退化丢失](#aud-088) |
| AUD-089 | P1 | T10 | [T10-I10 月光合奏把本次连击数永久写回技能，重复使用累加](#aud-089) |
| AUD-090 | P1 | T10 | [T10-I13 系统发育在回合消费者中向每只场下精灵复制全额收益](#aud-090) |
| AUD-091 | P1 | T11 | [T11-I02 全队状态变动的战报泄露未出场精灵身份](#aud-091) |
| AUD-092 | P2 | T00 | [T00-I01 核心必需的 NumPy 未列入基础或 dev 依赖](#aud-092) |
| AUD-093 | P2 | T01 | [T01-I02 分布表重写只做 upsert，不能移除旧项](#aud-093) |
| AUD-094 | P2 | T02 | [T02-I03 neutral/zero模式实际套用非中性坦率性格](#aud-094) |
| AUD-095 | P2 | T02 | [T02-I04 核心可解析的技能ID被建造校验拒绝，名称路径又重写ID](#aud-095) |
| AUD-096 | P2 | T02 | [T02-I06 属性值不识别时静默改为普通](#aud-096) |
| AUD-097 | P2 | T02 | [T02-I07 嵌套base类型未拒绝，预览请求落入AttributeError](#aud-097) |
| AUD-098 | P2 | T05 | [T05-I10 默认日志与环境变量行为不符README](#aud-098) |
| AUD-099 | P2 | T07 | [T07-I04 水环应对路径遗漏全技能公开修正归属](#aud-099) |
| AUD-100 | P2 | T07 | [T07-I06 旧格式迅捷释放多个技能（目前仅接口可达）](#aud-100) |
| AUD-101 | P2 | T11 | [T11-I03 双视角观测缺少对方奉献总层数](#aud-101) |
| AUD-102 | P2 | T11 | [T11-I04 predict_damage忽略组合状态，给出与显示接口不一致的精确预测](#aud-102) |
| AUD-103 | P2 | T12 | [T12-I01 直接 HP 输入与显式空资质导入被自动填入三个 8 资质](#aud-103) |
| AUD-104 | P2 | T12 | [T12-I02 不同共鸣魔法复合行动显示成完全相同按钮](#aud-104) |
| AUD-105 | P2 | T12 | [T12-I03 退出后在途房间摘要响应回填已清空的对局](#aud-105) |
| AUD-106 | P2 | T12 | [T12-I04 未配置性格时编辑器显示目录第一性格，实际未提交该显示性格](#aud-106) |
| AUD-107 | P2 | T12 | [T12-I06 战斗及补位界面缺少双方 MP 数值](#aud-107) |
| AUD-108 | P3 | T12 | [T12-I05 拼音匹配少量候选时重复追加已有候选](#aud-108) |

<a id="aud-001"></a>
## AUD-001 · P1 · 平台自动抹去未实现特性，绕过核心构建拒绝

主责：T11；原编号：T11-I01。[完整原记录](tasks/T11/issues.md)。

- 严重度：P1；主责T11，协同T02/T06/T12。
- 依据：AGENTS.md架构规则要求未实现机制抛 `UnsupportedMechanicError`，不静默降级；特性原文是精灵效果的核对依据。
- 位置：`nrc_platform/platform.py:_Catalog._normalize_creature` 第157-160行；接口另一端 `nrc_platform/builder.py:build` 的unsupported检查。
- 最小输入：双方阵容各一个“不咕钟”，技能槽均为火焰箭，未显式指定特性。先分别调用builder.build和真实平台set_roster。
- 预期：两入口均拒绝“整点报时”未实现，不开始少特性的对局。
- 实际：直接builder正确抛 `UnsupportedMechanicError`；平台规范化填入空特性字符串，实际精灵 `ability=''`、`ability_effects=[]`，对局成功初始化。
- 范围：目录内152个形态的特性无配置时会走此分支；显式传特性名的输入另行拒绝。不将直接builder正确拒绝宣传为Web拒绝。
- 证据：`probe_output.json.unsupported_ability_bypass`；T06的70个未实现特性记录保留局部拒绝和平台放行两个事实。

<a id="aud-002"></a>
## AUD-002 · P1 · 生成回退重复包装SkillEffect，8技能在执行时崩溃

主责：T06；原编号：T06-I01。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：对应8项技能说明要求治疗、回能、减速或换人；不允许以AttributeError代替可执行规则。代码根因：`scripts/generate_skill_effects.py:1130`、`:1147`回退；`:1212`把已提交`SE(...)`逐行取回后再次包入`SEEntry("ON_USE", base_tags)`；`nrc_core/engine/executor.py:188`读取内层tag.type崩溃。

最小输入/步骤：1000最大HP、当前500HP、20能量的A携带“休息回复”，B聚能；执行`execute_full_turn(state,(0,),(-1,))`。预期回复300HP；实际抛`AttributeError: SkillEffect object has no attribute type`。`skill_probe.json`对全部8项逐一复现同异常。内存重生成“休息回复”嵌套从2层增至3层，见`regeneration_diff.json`。影响：技能无法结算；重新生成会继续加深损坏。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0021 休息回复 | 自己回复30%生命。 | nrc_core/skill_effects_generated.py:34 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |
| SKILL:0138 富养化 | 为场下每个精灵回复3能量。 | nrc_core/skill_effects_generated.py:156 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |
| SKILL:0163 徒长 | 自己回复10能量。 | nrc_core/skill_effects_generated.py:181 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |
| SKILL:0249 杠杆置换 | 自己回复2能量，交换两侧技能位置。 | nrc_core/skill_effects_generated.py:274 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |
| SKILL:0253 架势 | 自己回复20%生命，下次技能无需蓄力。 | nrc_core/skill_effects_generated.py:284 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |
| SKILL:0255 根吸收 | 自己回复15%生命和4能量。 | nrc_core/skill_effects_generated.py:285 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |
| SKILL:0551 雪球 | 敌方获得速度-90。 | nrc_core/skill_effects_generated.py:606 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |
| SKILL:0568 风隐 | 敌方和自己均脱离，先手-1。 | nrc_core/skill_effects_generated.py:622 | T06-I01；AttributeError: 'SkillEffect' object has no attribute 'type'；effects内嵌SkillEffect而非EffectTag。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

协同证据：[T07-I08（T07）](tasks/T07/issues.md)；与上项同根不计新增问题。

<a id="aud-003"></a>
## AUD-003 · P1 · 奉献减耗别名错字使随机初始化崩溃

主责：T02；原编号：T02-I08。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02别名/初始化主责；T10奉献消费者协同
- 规则依据/原文行号：data/部分规则详解/奉献.md:1-2；nrc_core/engine/handlers_field.py DEVOTION_TYPES；builder初始化契约
- 代码位置：nrc_platform/builder.py:30-36,245-257,285-295
- 最小输入步骤：own.devotion指定power_bonus=5、random_draws=1，seed=2，完整双方正式build；seed0..7保留全部输出。
- 预期与实际：应获得五种中的一种合法奉献。实际随机到假寐后规范化仍是假寐，RANDOM_DEVOTION_CAPS[假寐]抛KeyError。别名和LEGACY_DEVOTION_KEYS使用假寥，正式handler使用假寐。seed1/3/4抽飞断则可成功但超过上限，该独立问题归T10-I01。
- 影响范围：随机奉献初始化抽到减耗时；已知canonical cost_reduce输入也被转换成假寥，可能不能被真实假寐消费者读取。前者已实际证实，后者消费者影响需要T10协同。
- 证据：`probe.py` 实际运行；`probe_output.json#I08_devotion_alias`。

<a id="aud-004"></a>
## AUD-004 · P1 · 替补入场与连锁入场力竭不扣MP

主责：T05；原编号：T05-I04。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P1；主责协同：T05补位主责，T04扣MP入口协同
- 规则依据/原文行号：data/README.md:30,35; nrc_core/models.py:604-606
- 代码位置：nrc_core/runtime.py:404-423,441-443,252-276
- 最小输入步骤：已死A已扣MP剩3，选择HP40替补，在荆刺1层下入场即死；另选抓到你了替补令B80HP获得冻结2层死亡。
- 预期与实际：本方再次力竭应MP3→2，实际仍3；敌方新力竭应MP4→3，实际仍4。虽然进入下一replacement阶段，整个补位流程没有调用扣MP/ON_FAINT结算；若继续替补，死亡者可永远不再被检查。
- 影响范围：入场印记伤害、入场攻击/冻结造成双方连锁死亡，可能逃过MP败北/复活触发。
- 证据：probe.py；probe_output.json:I04_entry_faint_mp `{"actual_phase": "replacement", "actual_players": [0], "actual_fainted": true, "actual_mp": 3, "expected_mp": 2, "next_legal": ["switch:index=2"]}`；probe_output.json:I04_enemy_entry_faint_mp `{"actual_fainted_b": true, "actual_mp_b": 4, "expected_mp_b": 3, "actual_phase": "replacement", "actual_players": [1]}`

<a id="aud-005"></a>
## AUD-005 · P1 · 50回合强制裁决未实现

主责：T04；原编号：T04-I03。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T03协同终局接口
- 规则依据/原文行号：data/README.md:37-42
- 代码位置：nrc_core/battle.py:1278-1415,2316-2330; nrc_core/core.py:151-217
- 最小输入步骤：turn=50，双方存活，MP为4:3，双方聚能。
- 预期与实际：应以MP高者A胜；实际进入turn51，winner=None。runtime也无50回合兜底。
- 影响范围：全部拖到50回合的PvP；四指标全平的额外规则另列问题，不影响此反例。
- 证据：repro.py中I03_turn50；repro_output.json对应结果：`{"next_turn": 51, "actual_winner": null, "expected_winner": "a"}`

T00独立补核：[cross_module_output.json](tasks/T00/cross_module_output.json)，包含多重减伤/最低伤害或四项50回合指标；不重复计数。

<a id="aud-006"></a>
## AUD-006 · P1 · Float16替代权威Float32导致六维错误

主责：T03；原编号：T03-I01。[完整原记录](tasks/T03/issues.md)。

- 严重度：P1；主责协同：T03主责，T01数据构建协同
- 规则依据/原文行号：data/属性数值计算.md:47-50
- 代码位置：nrc_core/catalog.py:20-23,39-57; nrc_core/constant.py:3-5
- 最小输入步骤：全量DB625形态、30性格、六维均IV0，以md总结公式构造严格Float32分步期望。
- 预期与实际：112500个标量比较中12325个不一致；例如丢丢沙地形态防御种族55、逞强（防御无修正）应121实120。Float16常数与性格小数均可偏移半数边界。
- 影响范围：全部六维计算；IV0已隔离6倍/5倍歧义，不能用该歧义解释差异。
- 证据：probe.py；probe_output.json:stats_IV0；实际摘要：`{"forms": 625, "natures": 30, "scalar_comparisons": 112500, "mismatch_count": 12325, "first_examples": [{"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "逞强", "field": "def", "base": 55, "actual": 120, "expected": 121}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "逞强", "field": "speed", "base": 75, "actual": 142, "expected": 143}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "理性", "field": "def", "base": 55, "actual": 120, "expected": 121}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "理性", "field": "speed", "base": 75, "actual": 142, "expected": 143}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "坦率", "field": "def", "base": 55, "actual": 134, "expected": 135}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "坦率", "field": "speed", "base": 75, "actual": 142, "expected": 143}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "焦虑", "field": "def", "base": 55, "actual": 120, "expected": 121}, {"form_id": 4, "form": "丢丢（沙地附近的样子）", "nature": "焦虑", "field": "speed", "base": 75, "actual": 142, "expected": 143}]}`

<a id="aud-007"></a>
## AUD-007 · P1 · 化茧未免疫致命伤害、主动降为1生命且缺2次上限

主责：T10；原编号：T10-I11。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：化茧原文“获得1层萌化，并免疫此次伤害（最多触发2次）”。

代码位置：nrc_core/engine/handlers_field.py:395（截至403的函数/分支），消费者位置见下文。

对象：化茧。

最小输入步骤：调用probe.py中的`cute_lethal_once、cute_lethal_three_calls、cute_lethal_consumer；executor.py:463,543及battle.py:2097`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：A500/1000HP面对600伤：原语把HP改1并写context.blocked_lethal；execute_ability返回独立result未带flag，battle读result未阻止扣600，实际HP0力竭。handler连续3次仍触发萌化3层，没有次数限制；即使修传递也会错误由500降1。

影响：化茧的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-008"></a>
## AUD-008 · P1 · 旧模型字段与不存在模块使属性倍率原语失效

主责：T09；原编号：T09-I02。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09；协同配置/伤害组。
- 规则：AGENTS.md显式拒绝不支持；data/伤害数值计算.md:8-16统一属性倍率模型。
- 代码：handlers_ability.py:662-738读Skill.type/Pokemon.type1/type2，from .types导入不存在的nrc_core.engine.types；:766-777用字符串“防御”比较SkillCategory枚举。
- 最小输入：标准模型Ctx含skill，分别调用DAMAGE_MOD_NON_STAB、NON_LIGHT、NON_WEAKNESS、DAMAGE_RESIST_SAME_TYPE；防御分类SkillCategory.DEFENSE调用SKILL_COST_REDUCTION_TYPE。
- 预期：正常模型可执行原语或明确拒绝，不得AttributeError/ModuleNotFoundError。实际前四项分别报错，缩壳返回空context且成本未变；证据non_stab/non_light/non_weakness/resist_same_type/defense_enum。
- 影响：涂鸦、目空/夺目、绒粉星光、偏振、缩壳。当前PASSIVE入口通常没有skill，会提前return，所以“不抛错”不表示倍率生效；执行伤害只触发BEFORE_ATTACK，相关PASSIVE没有安装持续标记。原文倍率已授权，具体未跑条件保留实现待证实，不再要求来源授权；偏振携带技能系别与代码自身type字段亦明确不符。

<a id="aud-009"></a>
## AUD-009 · P1 · 初始化、补位和下一回合准备在种子随机域之外

主责：T05；原编号：T05-I05。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P1；主责协同：T05主责，T04 rng工具通过不外推调用方
- 规则依据/原文行号：nrc_core/README.md:公开入口/规则模块；rng.py作用域契约；data/README.md:19
- 代码位置：nrc_core/runtime.py:68-72,225-226,441-443,480
- 最小输入步骤：固定new_game seed77，用正式盲拧ON_TURN_START改变进程random种子1/2/3；固定advance seed78，用柔软球替补入场；并从同一会话advance后准备下一回合。
- 预期与实际：同对战seed应相同；实际盲拧顺序、柔软球随机效果随进程random改变。_isolated_rng定义未在这些入口使用，simulate_turn只包技能回合的内部。
- 影响范围：初始/替补/回合准备的全部随机机制；共鸣首领入场也在同一未包裹区域，具体随机特性可达性逐配置另核。
- 证据：probe.py；probe_output.json:I05_seed_new_game `{"fixed_seed": 77, "ambient_seeds": [1, 2, 3], "actual_orders": [["四", "一", "三", "二"], ["二", "三", "四", "一"], ["四", "一", "三", "二"]], "expected_equal": true}`；probe_output.json:I05_seed_replacement `{"fixed_seed": 78, "ambient_seeds": [1, 2, 3], "actual_balls": ["spatk", "heal", "poison"], "expected_equal": true}`；probe_output.json:I05_seed_next_turn `{"fixed_seed": 78, "actual_orders": [["四", "三", "二", "一"], ["一", "二", "四", "三"]], "expected_equal": true}`

<a id="aud-010"></a>
## AUD-010 · P1 · 采集目录迁移后入口导入及项目根路径失效

主责：T01；原编号：T01-I01。[完整原记录](tasks/T01/issues.md)。

- 主责：T01；协同：T00（运行入口）。规则依据：AGENTS.md 指定 `python -m wiki_crawler`；本模块 README 的项目内 staging→确认→canonical/新库约定。
- 代码：`wiki_crawler/__main__.py:1` → `sync.py:33-45`；旧导入 `scripts.wiki_crawler.database`，`ROOT=parents[2]`。
- 最小输入与步骤：项目根执行 `python -m wiki_crawler --help`，无需网络或写权限；实际 exit 1、`ModuleNotFoundError`，预期能够展示参数。
- 第二端证据：只在审计内存模块替换失效 import 后，原 ROOT 算出 `D:/dotoro/project/python/rckdworld`，而项目为其下 `NRC_BATTLE_LAB`。默认 DB、CSV、staging 和资源路径均指向项目之外。没有实际执行下载或写入。
- 影响：全部采集模式当前入口不可运行；只修导入仍遗留错误数据目录。两处合并为同一目录迁移根因。
- 证据：[probe.py](tasks/T01/probe.py)、[probe_output.json](tasks/T01/probe_output.json) 的 `original_cli`、`configured_root`、[probe.log](tasks/T01/probe.log)。

<a id="aud-011"></a>
## AUD-011 · P1 · 构造输入中的力竭精灵被复活

主责：T02；原编号：T02-I01。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02构造主责；T03模型默认哨兵接口协同
- 规则依据/原文行号：data/README.md:30,35；nrc_core/schema.py CreatureState.hp/status 明确输入；GAME_RULE力竭
- 代码位置：nrc_platform/builder.py:459-487；nrc_core/models.py:354-364
- 最小输入步骤：完整六维HP1000，state.hp=0、status=fainted，正式BattleBuilder.build。另以真实一窝蜂/虫群鼓舞和其学习表前4技（乘风/信息素/借用/倾泻）复核，仍复活；附I01_real_species_control输入输出。
- 预期与实际：应保留HP0与力竭；实际HP1000、status=normal、is_fainted=False。builder将0传入Pokemon默认哨兵初始化后未还原，也完全忽略state.status。
- 影响范围：显式初始残血/力竭输入、需要保留已知状态的构造边界；不泛化到runtime pickle导入。
- 证据：`probe.py` 实际运行；`probe_output.json#I01_zero_hp`。

<a id="aud-012"></a>
## AUD-012 · P1 · 六项正资质被完整接受，缺少最多三项校验

主责：T02；原编号：T02-I02。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02输入校验主责，T03公式协同
- 规则依据/原文行号：data/属性数值计算.md:30（每个精灵最多拥有三项大于零的资质值）
- 代码位置：nrc_platform/builder.py:318-338,363-365,474-487,589-647
- 最小输入步骤：base.individual_values六项全部8，提供完整六维隔离公式，正式build。
- 预期与实际：应拒绝六项正资质；实际六项iv_*均8且无异常。这里只核最多三项约束，绝不裁决文档6倍与+8→+40冲突。
- 影响范围：所有显式资质输入，非法组合可进入公式；与T03 Float16/倍数问题不同。
- 证据：`probe.py` 实际运行；`probe_output.json#I02_six_positive_iv`。

<a id="aud-013"></a>
## AUD-013 · P1 · 输入中多个同属性增益被后项覆盖

主责：T02；原编号：T02-I05。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02状态注入主责，T03状态模型协同
- 规则依据/原文行号：data/伤害数值计算.md:15（同方加成和减弱同时存在、层数叠加）
- 代码位置：nrc_platform/builder.py:524-538
- 最小输入步骤：buffs=[物攻10%×2,物攻10%×3]，debuffs={atk:2}，基础物攻100。
- 预期与实际：应保留五层加成和两层减弱，atk_up=.5、atk_down=.2；实际atk_up=.3、atk_down=.2，有效物攻108.3333而非125。每条setattr覆盖前条而非合并。
- 影响范围：同一属性由多个条目给出的输入；增/减两桶本身并存通过。100层不封顶的输入端证据另关联T03-I03，避免重复主问题。
- 证据：`probe.py` 实际运行；`probe_output.json#I05_duplicate_buff`。

<a id="aud-014"></a>
## AUD-014 · P1 · 双攻双防有效属性截断为40层提升/9层降低，违反99层规则

主责：T03；原编号：T03-I02。[完整原记录](tasks/T03/issues.md)。

- 严重度：P1；主责协同：T03主责，T04执行顺序、T09/T10赋予协同
- 规则依据/原文行号：data/伤害数值计算.md:9,15,19
- 代码位置：nrc_core/models.py:387-420
- 最小输入步骤：基础攻击/防御100，分别设atk_up=9.9、def_down=9.9；附加速度同值用于观察但不由双攻双防段落推导速度上限。
- 预期与实际：99层物攻提升应1090实500，99层物防降低应约9.174实52.632；增减益并存样例125正确。速度也经过同一clamp，但其99层上限是否同属该规则保留待裁决。
- 影响范围：effective_atk/def/spatk/spdef直接调用方；计算器伤害直接读calculation_modifier，和有效属性接口不一致。
- 证据：probe.py；probe_output.json:I02_caps；实际摘要：`{"up99_actual": 500.0, "up99_expected": 1090, "down99_actual": 52.631578947368425, "down99_expected": 9.174311926605505, "both_actual": 125.0, "both_expected": 125.0, "atk99_actual": 500.0, "atk99_expected": 1090, "defdown99_actual": 52.631578947368425, "defdown99_expected": 9.174311926605505}`

<a id="aud-015"></a>
## AUD-015 · P1 · 原始增减益与计算入口未执行99层上限

主责：T03；原编号：T03-I03。[完整原记录](tasks/T03/issues.md)。

- 严重度：P1；主责协同：T03模型计算主责，T09/T10状态赋予协同
- 规则依据/原文行号：data/伤害数值计算.md:15
- 代码位置：nrc_core/models.py:422-424,440-454; nrc_core/engine/helpers.py:217-276
- 最小输入步骤：对普通精灵调用_apply_buff100次，每次atk=.1，读取calculation_modifier。
- 预期与实际：应封顶9.9；实际9.99999999999998，battle.DamageCalculator不经_clamp直接读取，100层可进入伤害公式。
- 影响范围：普通五维独立状态及复制状态输入；与I02低上限是两条不同路径错误。
- 证据：probe.py；probe_output.json:I03_max99；实际摘要：`{"actual_modifier": 9.99999999999998, "expected_max": 9.9}`

<a id="aud-016"></a>
## AUD-016 · P1 · Skill.copy遗漏技能威力基准，复制后入场特性重复放大

主责：T03；原编号：T03-I04。[完整原记录](tasks/T03/issues.md)。

- 严重度：P1；主责协同：T03复制主责，T06配置协同，T09/T10应用原语协同
- 规则依据/原文行号：data/状态分类.md:4; data/wiki/spirits.csv:613
- 代码位置：nrc_core/models.py:208-268; nrc_core/engine/helpers.py:475-477
- 最小输入步骤：100威力1能耗技能应用挺起胸脯对应power_pct=.5，再copy_state，对原对象和副本分别再次应用同一入场修正。
- 预期与实际：两者均应保持150；原对象150、副本225。Skill.copy未复制_ability_base_power；其他非显式动态字段也需逐来源核查。
- 影响范围：挺起胸脯、国王威严、勇敢、不移等使用技能基准修正的特性；simulate_turn默认克隆也经过该方法。
- 证据：probe.py；probe_output.json:I04_skill_copy；实际摘要：`{"original_power": 150, "cloned_power": 225, "expected_both": 150, "cloned_has_base_before_reapply": false}`

<a id="aud-017"></a>
## AUD-017 · P1 · 分精灵深拷贝破坏跨精灵状态引用，衡量增益写向游离副本

主责：T03；原编号：T03-I05。[完整原记录](tasks/T03/issues.md)。

- 严重度：P1；主责协同：T03复制主责，T04 simulate_turn、特性handler协同
- 规则依据/原文行号：data/wiki/spirits.csv:30-31; data/状态分类.md:2
- 代码位置：nrc_core/models.py:546-548,688-692
- 最小输入步骤：B.ability_state镜像引用A公平鸽；BattleState.deep_copy后给B+10%攻击。
- 预期与实际：副本B引用应指副本A，副本A应+0.1；实际指向另一个游离公平鸽，对其+0.1而场上A仍0。
- 影响范围：simulate_turn默认clone=True与单独deep_copy；runtime.clone采用整体copy.deepcopy，此入口保留共享引用，不能把本问题无差别套用runtime。
- 证据：probe.py；probe_output.json:I05_graph_copy；实际摘要：`{"ref_points_to_copied_active": false, "actual_active_buff": 0.0, "detached_buff": 0.1, "expected_active_buff": 0.1}`

<a id="aud-018"></a>
## AUD-018 · P1 · BattleState.deep_copy复制天气id键却未映射新技能

主责：T03；原编号：T03-I07。[完整原记录](tasks/T03/issues.md)。

- 严重度：P1；主责协同：T03模型复制主责，T04天气还原协同
- 规则依据/原文行号：GAME_RULE:0030；data/wiki/game_descriptions.csv:37
- 代码位置：nrc_core/models.py:688-704; nrc_core/battle.py:969-978
- 最小输入步骤：沙暴剩1回合，地系技能当前耗2，记录原耗5；simulate_turn默认clone=True双方聚能。
- 预期与实际：天气结束应恢复5；副本技能id不在旧id字典中，实际保持2。
- 影响范围：直接simulate_turn默认克隆接口；runtime.clone/new_game/export有天气键重建兜底，已明确入口差异。
- 证据：probe.py；probe_output.json:I07_weather_copy；实际摘要：`{"new_skill_key_present": false, "expected": true, "actual_cost_after_weather_ends": 2, "expected_cost_after_weather_ends": 5}`

<a id="aud-019"></a>
## AUD-019 · P1 · 技能/特性减伤晚于逐击公式取整

主责：T04；原编号：T04-I01。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T07协同伤害原语
- 规则依据/原文行号：data/伤害数值计算.md:7,9,21
- 代码位置：nrc_core/battle.py:1957-1973,2078-2101
- 最小输入步骤：威力10、攻防100、三连击、50%减伤；调用计算器后调用减伤接口。
- 预期与实际：公式把减伤乘入威力，逐击4合计12；实际先得27再乘0.5取整为13。
- 影响范围：所有存在减伤的攻击，特别多段与低伤害；特性减伤也在最终整数后相乘。
- 证据：repro.py中I01_reduction；repro_output.json对应结果：`{"base": 27, "actual": 13, "expected": 12}`

T00独立补核：[cross_module_output.json](tasks/T00/cross_module_output.json)，包含多重减伤/最低伤害或四项50回合指标；不重复计数。

<a id="aud-020"></a>
## AUD-020 · P1 · 石头大餐用生命补能后重复扣完整能耗

主责：T04；原编号：T04-I02。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T06协同特性
- 规则依据/原文行号：data/wiki/spirits.csv:460,558-559
- 代码位置：nrc_core/battle.py:1683-1720
- 最小输入步骤：最大生命1000、当前满血、能量1、技能耗4，设置hp_for_energy。
- 预期与实际：扣150生命替代缺少3能量后应能量0；实际能量置0后又减4，得到-4。
- 影响范围：石头大餐精灵，负能量可继续干扰免伤、聚能与能耗判定。
- 证据：repro.py中I02_hp_for_energy；repro_output.json对应结果：`{"actual_energy": -4, "expected_energy": 0, "hp": 850, "expected_hp": 850}`

<a id="aud-021"></a>
## AUD-021 · P1 · 脱离未检查本回合入场免疫

主责：T04；原编号：T04-I04。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T07协同脱离标签
- 规则依据/原文行号：GAME_RULE:0037,0036；data/wiki/game_descriptions.csv:4,26
- 代码位置：nrc_core/battle.py:607-666,2183-2202
- 最小输入步骤：turn7，当前精灵在burst_entry_turn中记录入场7，队伍有替补；调用脱离。
- 预期与实际：应免疫脱离且索引不变；实际立即随机换入索引1。
- 影响范围：普通脱离与紧急脱离共用入口；换入后同回合可能再次脱离。
- 证据：repro.py中I04_entry_immunity；repro_output.json对应结果：`{"actual_changed": true, "actual_index": 1, "expected_changed": false}`

<a id="aud-022"></a>
## AUD-022 · P1 · 奉献已获得层数在每次使用时重复写为永久强化

主责：T04；原编号：T04-I05。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T07协同奉献授予
- 规则依据/原文行号：data/部分规则详解/奉献.md:1-4; data/wiki/skills.csv:101
- 代码位置：nrc_core/battle.py:1762-1785
- 最小输入步骤：己方飞断奉献1层；受奉献影响攻击连续使用两次，不再获得新奉献。
- 预期与实际：该1层应始终提供威力+20；实际skill_power_bonus从20变40，且修正写在精灵上可影响非受益技能。
- 影响范围：全部奉献受益技能及同精灵其他攻击；能耗、吸血、连击也采用累加写法。
- 证据：repro.py中I05_devotion；repro_output.json对应结果：`{"actual_permanent_bonus": [20, 40], "expected_each": 20}`

<a id="aud-023"></a>
## AUD-023 · P1 · 毒印/荆刺等直接扣血漏冻结实时力竭检查

主责：T04；原编号：T04-I06。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T02协同冻结模型
- 规则依据/原文行号：GAME_RULE:0007,0002；data/wiki/game_descriptions.csv:5,15,20
- 代码位置：nrc_core/battle.py:1080-1106,1120-1145,2104-2110
- 最小输入步骤：最大HP1000，当前70，冻结1层，毒印1层；回合末结算。
- 预期与实际：扣30后40低于冻结50应力竭；实际40且is_fainted=False。荆刺同样直接扣血不检查阈值。
- 影响范围：冻结精灵遭印记伤害；力竭、MP扣除和终局均可延迟。
- 证据：repro.py中I06_freeze_mark；repro_output.json对应结果：`{"actual_hp": 40, "actual_fainted": false, "expected_fainted": true}`

协同证据：[T03-I06（T03）](tasks/T03/issues.md)；与上项同根不计新增问题。

<a id="aud-024"></a>
## AUD-024 · P1 · 蓄电印记按入场回合而非首次行动生效

主责：T04；原编号：T04-I07。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责
- 规则依据/原文行号：GAME_RULE:0042；data/wiki/game_descriptions.csv:11,24
- 代码位置：nrc_core/battle.py:1139-1145,1174-1180
- 最小输入步骤：入场回合1但尚未主动行动，当前turn2、_burst_pending=True，蓄电1层。
- 预期与实际：首次攻击应得威力+10；实际entry_turn与turn不等故加成0。反向：同回合已聚能仍可能受益。
- 影响范围：中途换入后下一回合首次行动、多次使用与首次行动消耗。
- 证据：repro.py中I07_charge_mark；repro_output.json对应结果：`{"actual_bonus": 0, "expected_bonus": 10}`

<a id="aud-025"></a>
## AUD-025 · P1 · 回合末先特性回血后状态伤害，与总规则相反

主责：T04；原编号：T04-I08。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T06协同特性阶段
- 规则依据/原文行号：data/README.md:19-31; data/wiki/game_descriptions.csv:2
- 代码位置：nrc_core/battle.py:761-816
- 最小输入步骤：HP20/1000、中毒1层、回合末回复5%特性，调用turn_end_effects。
- 预期与实际：状态30伤先结算应力竭；实际先回血50再扣30，剩40存活。双方末尾阶段也固定A→B，未按总规则拼速。
- 影响范围：全部回合结束特性、状态与先后相互影响；可改变生死与战果。
- 证据：repro.py中I08_end_order；repro_output.json对应结果：`{"actual_hp": 40, "actual_fainted": false, "expected_fainted": true}`

<a id="aud-026"></a>
## AUD-026 · P1 · 减速印记错误采用比例减速

主责：T04；原编号：T04-I09。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责
- 规则依据/原文行号：GAME_RULE:0009；data/wiki/game_descriptions.csv:32
- 代码位置：nrc_core/battle.py:533-542
- 最小输入步骤：A速度200、1层减速；B速度185，无先手差。
- 预期与实际：A应200-10=190仍先；实际A速度乘0.9=180导致B先。
- 影响范围：所有减速印记及不同基础速度对局。
- 证据：repro.py中I09_slow_mark；repro_output.json对应结果：`{"actual_first": 1, "expected_first": -1}`

<a id="aud-027"></a>
## AUD-027 · P1 · 龙噬印记触发能耗和效果均不符原文

主责：T04；原编号：T04-I10。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T07协同印记原语
- 规则依据/原文行号：GAME_RULE:0054；data/wiki/game_descriptions.csv:31
- 代码位置：nrc_core/battle.py:1162-1167,2205-2284
- 最小输入步骤：龙噬1层，使用3耗攻击后读取双攻；另查询5耗攻击修正。
- 预期与实际：3耗技能释放后应获得双攻40%；实际双攻仍0；反而5耗技能获得即时攻击倍率1.4。
- 影响范围：全部龙噬相关战斗，影响触发条件、永久/后续收益及初次伤害。
- 证据：repro.py中I10_dragon_mark；repro_output.json对应结果：`{"actual_attack_buff_after_3cost": 0.0, "actual_spattack_buff_after_3cost": 0.0, "actual_multiplier_for_5cost": 1.4, "expected_both_buff_after_3cost": 0.4, "expected_multiplier_for_5cost": 1}`

<a id="aud-028"></a>
## AUD-028 · P1 · 普通脱离被随机换人且不等待用户选择

主责：T04；原编号：T04-I11。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T03协同动作/暂停恢复，T07协同标签
- 规则依据/原文行号：GAME_RULE:0037,0036；data/README.md:27; data/wiki/game_descriptions.csv:4,26; data/wiki/skills.csv:372
- 代码位置：nrc_core/battle.py:607-666,2183-2202
- 最小输入步骤：移花接木仅配置其脱离原语，队伍有两个健康替补；分别seed0至4。
- 预期与实际：普通脱离应暂停供本人选择；实际新索引为2,1,1,1,1且pending为空。紧急脱离原文指定随机，随机本身在该场景合法；两者不能混同。
- 影响范围：所有普通脱离，无论自身或强制敌方；后手动作打到未经选择的目标。
- 证据：repro.py中I11_ordinary_disengage；repro_output.json对应结果：`{"actual_indices_by_seed": [2, 1, 1, 1, 1], "actual_pending": [], "expected": "暂停等待用户选择其他存活精灵"}`

<a id="aud-029"></a>
## AUD-029 · P1 · 湿润印记被擅自消费并永久写入全队技能能耗

主责：T04；原编号：T04-I13。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04主责，T00规则双向核对、印记handler协同
- 规则依据/原文行号：GAME_RULE:0032（湿润印记）；GAME_RULE:0010（印记）；data/wiki/game_descriptions.csv:23,41; data/状态分类.md:6
- 代码位置：nrc_core/battle.py:1059-1077
- 最小输入步骤：能耗5的场上与后排精灵，己方湿润印记1层；调用回合开始应用，再推进下一回合、驱散并换入后排。
- 预期与实际：首次印记变0、全队技能实值变4；第二回合仍4；驱散并换人后仍4。应保留阵营印记并仅在印记有效时享受-1；原文没有消耗或永久降低技能的子句。
- 影响范围：所有湿润印记：可见层数、驱散/替换正面印记、后排及跨回合；不应猜消费机制。
- 证据：repro.py中I13_moisture；repro_output.json对应结果：`{"after_first": {"mark": 0, "cost_a": 4, "cost_bench": 4}, "after_second": {"mark": 0, "cost_a": 4}, "after_dispel_and_switch": {"mark_exists": false, "cost_new_active": 4, "cost_old_active": 4}, "expected": "印记应持续存在并在生效期间全技能耗-1，驱散后失去该修正；原文没有消费或永久写入"}`

<a id="aud-030"></a>
## AUD-030 · P1 · 沙暴凭空对全队追加1/16生命伤害

主责：T04；原编号：T04-I14。[完整原记录](tasks/T04/issues.md)。

- 严重度：P1；主责协同：T04调用入口协同，天气handler所属任务主责，T00发现
- 规则依据/原文行号：GAME_RULE:0030；data/wiki/game_descriptions.csv:37
- 代码位置：nrc_core/battle.py:959-962; nrc_core/engine/handlers_skill.py:881-898
- 最小输入步骤：双方及A后排均普通/非地非机械，HP1000，沙暴剩2回合；调用回合末。
- 预期与实际：权威描述仅双方地系技能耗半，无附加扣血规则；应均1000，实际场上A、后排、B均938。且代码凭空设置地/机械免疫与保底1。
- 影响范围：所有沙暴回合的非地/机械全队精灵，包含后排；可能改变下一次上场生死。
- 证据：repro.py中I14_sandstorm；repro_output.json对应结果：`{"actual_hp_a": 938, "actual_hp_bench": 938, "actual_hp_b": 938, "expected_each": 1000}`

协同证据：[T08-I02（T08）](tasks/T08/issues.md)；与上项同根不计新增问题。

<a id="aud-031"></a>
## AUD-031 · P1 · 愿力动作按原首槽过滤且无法选择替换后不用

主责：T05；原编号：T05-I01。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P1；主责协同：T05主责
- 规则依据/原文行号：data/部分规则详解/共鸣魔法.md:7-22
- 代码位置：nrc_core/runtime.py:319-337,346-357
- 最小输入步骤：能量3，原首槽耗8，携愿力；另用双技能完整状态枚举动作。
- 预期与实际：应可将首槽变为能耗2愿力，实际仅charge；原首槽合法时也仅允许使用首槽，无法配合charge或其他技能，违反即使未使用仍消耗次数与到期还原的子句。
- 影响范围：全部愿力与原槽耗能/冷却/多次使用交叉；共鸣后应重新计算合法动作。
- 证据：probe.py；probe_output.json:I01_willpower_legal `{"energy": 3, "original_cost": 8, "actual_keys": ["charge"], "expected": "应能用能耗2愿力首槽，但原技能先按8耗过滤，愿力动作消失"}`；probe_output.json:I01_unused_willpower `{"actual_keys": ["skill:slot=0", "skill:slot=1", "charge", "skill:slot=0|resonance=willpower"], "expected": "应允许愿力本回合替换但不使用愿力，详解明确即便未使用下回合也替换回"}`

<a id="aud-032"></a>
## AUD-032 · P1 · 愿力还原按原主人固定首槽，交换后临时技能遗留

主责：T05；原编号：T05-I02。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P1；主责协同：T05还原主责，T07技能交换协同
- 规则依据/原文行号：data/部分规则详解/共鸣魔法.md:14,18; data/wiki/skills.csv:523
- 代码位置：nrc_core/rules_support.py:166-174,186-188
- 最小输入步骤：A慢于B，A用愿力，B真实隐藏条款先交换双方整套技能。
- 预期与实际：回合结束B仍永久持有愿力冲击，A被覆盖回A原技能；至少临时愿力必须在下一回合消失。按交换语义预期A保留隐藏条款、B得到A原技能，但跨交换精确归属仍需确认，不影响当前遗留临时技能事实。
- 影响范围：愿力和技能交换/替换交叉；传动当前未实现移动，本证据不假设传动已运行。
- 证据：probe.py；probe_output.json:I02_restore_swap `{"actual_skills_a": ["A原技能"], "actual_skills_b": ["愿力冲击"], "expected_a": ["隐藏条款"], "expected_b": ["A原技能"]}`

<a id="aud-033"></a>
## AUD-033 · P1 · 首领化更新六维和特性但未更新战斗属性

主责：T05；原编号：T05-I03。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P1；主责协同：T05主责，T03数值公式另有I01
- 规则依据/原文行号：data/部分规则详解/共鸣魔法.md:24-36
- 代码位置：nrc_core/rules_support.py:115-137
- 最小输入步骤：已解析首领血脉A普通系，唯一目标record为火/龙，使用进化之力。
- 预期与实际：首领名称/六维/特性已变、原技能保留，但pokemon_type/pokemon_types仍normal，应跟随首领火龙战斗属性。血脉远古变更没有充分字段规则，另列questions。
- 影响范围：所有首领形态与基础形态属性不同的记录；克制、本系、免疫等计算仍按旧属性。
- 证据：probe.py；probe_output.json:I03_boss_types `{"actual_name": "首领", "actual_types": ["normal"], "expected_types": ["fire", "dragon"], "skills": ["审计"], "expected_skill": "审计", "hp": 469, "attack": 280, "bossified": true}`

<a id="aud-034"></a>
## AUD-034 · P1 · 技能槽锁定未进入合法动作过滤

主责：T05；原编号：T05-I06。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P1；主责协同：T05主责，T06配置协同
- 规则依据/原文行号：正位宝剑/宝剑王牌原文与effect_data SKILL_SLOT_LOCK；nrc_core/README.md:advance只接受合法动作
- 代码位置：nrc_core/runtime.py:319-337; nrc_core/battle.py:1626-1631
- 最小输入步骤：当前skill_slot_lock=[0]且携两个能量足技能，枚举合法动作。
- 预期与实际：slot1仍被列为可选，且附带光合组合动作；实际执行则静默改聚能。应不列锁定槽动作，或按明确协议展示聚能。
- 影响范围：正位宝剑/宝剑王牌；合法动作和真正执行不一致，影响用户/搜索。
- 证据：probe.py；probe_output.json:I06_slot_lock `{"actual_keys": ["skill:slot=0", "skill:slot=1", "charge", "switch:index=1", "skill:slot=0|resonance=solar_heal", "skill:slot=1|resonance=solar_heal", "charge|resonance=solar_heal"], "expected_no_slot1": true}`

<a id="aud-035"></a>
## AUD-035 · P1 · 禁足机制未表示，流沙执行后仍可离场

主责：T05；原编号：T05-I07。[完整原记录](tasks/T05/issues.md)。

- 结论：未实现；严重度：P1；主责协同：T05合法动作协同，T06技能原文生成/状态handler主责
- 规则依据/原文行号：GAME_RULE禁足；data/wiki/game_descriptions.csv:52; data/wiki/skills.csv:287,354
- 代码位置：nrc_core/runtime.py:333-337; nrc_core/effect_models.py/全core检索禁足机制缺失
- 最小输入步骤：使用真实流沙原文/硬编码效果，目标有健康替补，执行后读取状态和合法动作。
- 预期与实际：未获得禁足且可switch；原文禁止离场3回合。未实现也没有UnsupportedMechanicError，不能静默忽略。
- 影响范围：流沙、石锁及一切禁足来源；再次施加免疫与持续回合均缺。
- 证据：probe.py；probe_output.json:I07_ban_switch `{"actual_b_keys": ["skill:slot=0", "charge", "switch:index=1", "skill:slot=0|resonance=solar_heal", "charge|resonance=solar_heal"], "actual_b_state": {"_burst_pending": false}, "expected": "流沙施加禁足3回合后应禁止switch，或未实现时显式抛UnsupportedMechanicError"}`

<a id="aud-036"></a>
## AUD-036 · P1 · 选择类仅保存选项字符串，两个分支效果未执行

主责：T05；原编号：T05-I08。[完整原记录](tasks/T05/issues.md)。

- 结论：未实现；严重度：P1；主责协同：T05选择接口主责，T07/T06效果配置协同
- 规则依据/原文行号：data/部分规则详解/选择类技能.md:3-5; data/wiki/skills.csv:441
- 代码位置：nrc_core/runtime.py:323-330; nrc_core/rules_support.py:203; 全core selected_choice引用
- 最小输入步骤：真实补觉，两分支分别从HP500/能量3开始执行。
- 预期与实际：第0分支应HP750/能量1、第1分支HP500/能量9；实际都HP500/能量1，只有selected_choice字符串不同。全core没有读取selected_choice的效果分发，不应假装已支持。
- 影响范围：所有选择技能、加尔额外触发及选择计数；具体技能效果若另缺也不掩盖分支协议缺口。
- 证据：probe.py；probe_output.json:I08_choice `{"actual": [{"choice": 0, "hp": 500, "energy": 1, "selected": "自己回复25%生命"}, {"choice": 1, "hp": 500, "energy": 1, "selected": "回复8能量"}], "expected": "第0分支恢复25%生命即750HP/能量1；第1分支恢复8能量即500HP/能量9，不能只记录字符串"}`

<a id="aud-037"></a>
## AUD-037 · P1 · 新对局未触发初始精灵入场特性

主责：T05；原编号：T05-I09。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P1；主责协同：T05初始化主责，T01构建入口协同
- 规则依据/原文行号：data/README.md:22; data/wiki/spirits.csv 抓到你了原文；nrc_core/README.md new_game初始化
- 代码位置：nrc_core/runtime.py:211-227,279-283
- 最小输入步骤：完整状态A带正式抓到你了ON_ENTER配置，B完整，调用new_game。
- 预期与实际：应使B冻结2层、全技能耗+1；实际冻结0、耗1不变、entry_count0。new_game仅battle_start和turn_start，未发ON_ENTER；平台builder也无该事件调用。
- 影响范围：开局仅定义ON_ENTER的特性，以及初始入场计数与入场印记；中途导入既有战局不能重复触发，需区分初始化责任。
- 证据：probe.py；probe_output.json:I09_initial_enter `{"actual_enemy_freeze": 0, "actual_enemy_cost": 1, "expected_enemy_freeze": 2, "expected_enemy_cost": 2, "actual_entry_count": 0}`

<a id="aud-038"></a>
## AUD-038 · P1 · 手写技能覆盖保留过期数值，覆盖正确数据源

主责：T06；原编号：T06-I02。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0009 丰饶 | 自己获得物攻和魔攻+140%。 | nrc_core/effect_data.py:284 | T06-I02；原文双攻+140%；手写双攻1.3，仅130%。 |
| SKILL:0056 冰蛋壳 | 减伤70%，应对攻击：敌方获得2层减速印记。 | nrc_core/effect_data.py:362 | T06-I02；原文减伤70%；手写pct=0.6。 |
| SKILL:0096 吓退 | 减伤60%，应对攻击：敌方脱离。 | nrc_core/effect_data.py:266 | T06-I02；原文减伤60%；手写pct=0.7。 |
| SKILL:0106 啮合传递 | 自己获得速度+30，本技能位于1号或3号位时额外获得物攻+80%，传动1。 | nrc_core/effect_data.py:159 | T06-I02；原文速度+30且1/3号物攻+80%；配置speed=0.8、atk=1.0，两个数值均错。 |
| SKILL:0108 嘲弄 | 自己获得魔攻+90%，若敌方本回合更换精灵，自己获得速度+70。 | nrc_core/effect_data.py:87 | T06-I02；原文魔攻+90%；手写spatk=0.7。 |
| SKILL:0174 恶意逃离 | 脱离，应对防御：额外使敌方攻击技能能耗+4。 | nrc_core/effect_data.py:93 | T06-I02；原文应对防御使攻击技能能耗+4；手写amount=6。 |
| SKILL:0220 放晴 | 光系技能威力永久+50%，应对防御：改为永久+100%。 | nrc_core/effect_data.py:485 | T06-I02；原文光系永久威力50%/100%；手写两次0.4，变成40%/80%。 |
| SKILL:0271 气势一击 | 造成物伤，若上回合应对成功，本次技能威力+180。 | nrc_core/effect_data.py:455 | T06-I02；原文上回合应对成功威力+180；手写bonus=240。 |
| SKILL:0277 水刃 | 造成物伤，应对状态：本技能能耗永久-3。 | nrc_core/effect_data.py:181 | T06-I02；原文应对状态永久能耗-3；手写delta=-4。 |
| SKILL:0285 水环 | 减伤60%，应对攻击：自己获得全技能能耗-2。 | nrc_core/effect_data.py:221 | T06-I02；原文减伤60%；手写pct=0.7。 |
| SKILL:0291 沙涌 | 将天气改为沙暴，持续8回合。 | nrc_core/effect_data.py:628 | T06-I02；原文沙暴8回合；手写turns=5。 |
| SKILL:0294 泡沫幻影 | 减伤80%，应对攻击：自己脱离。 | nrc_core/effect_data.py:71 | T06-I02；原文减伤80%；手写pct=0.7。 |
| SKILL:0299 流星火雨 | 造成物伤，每次击败敌方，本技能威力永久+85。 | nrc_core/effect_data.py:559 | T06-I02；原文每次击败永久威力+85；手写delta=75。 |
| SKILL:0321 火焰护盾 | 减伤70%，应对攻击：敌方获得6层灼烧。 | nrc_core/effect_data.py:199 | T06-I02；原文应对攻击6灼烧；手写stacks=4。 |
| SKILL:0383 示弱 | 自己获得萌化：速度永久+130。 | nrc_core/effect_data.py:754 | T06-I02；原文萌化速度永久+130；手写speed=150。 |
| SKILL:0435 落雷 | 造成魔伤，每次入场，本技能威力永久+40。 | nrc_core/effect_data.py:565 | T06-I02；原文每入场永久威力+40；手写delta=20。 |
| SKILL:0595 齿轮扭矩 | 造成物伤，每回合位置发生变化时，本技能威力永久+15。 | nrc_core/effect_data.py:254 | T06-I02；原文位置变化永久威力+15；手写delta=20。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-039"></a>
## AUD-039 · P1 · 生成产物数值和目标陈旧或错误

主责：T06；原编号：T06-I03。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0103 咆哮 | 敌方获得物攻-60%和速度-60。 | nrc_core/skill_effects_generated.py:113 | T06-I03；原文敌物攻-60%及速度-60；生成atk=1.3，未配置速度。 |
| SKILL:0135 孢子 | 敌方获得3层寄生。 | nrc_core/skill_effects_generated.py:151 | T06-I03；原文3层寄生；生成stacks=1。 |
| SKILL:0359 电离爆破 | 敌方获得魔攻-20%，速度-20，2连击。 | nrc_core/skill_effects_generated.py:385 | T06-I03；原文敌魔攻-20%、速度-20、2连击；生成只有自身hit_count+3，目标/数值/附效均不符。 |
| SKILL:0375 破防 | 敌方获得双防-70%，应对防御：额外使被应对技能冷却2回合。 | nrc_core/skill_effects_generated.py:405 | T06-I03；原文双防-70%；生成双防1.3，且应对冷却2回合为空。 |
| SKILL:0413 聒噪 | 敌方获得全攻击技能能耗+2，持续3回合。 | nrc_core/skill_effects_generated.py:452 | T06-I03；原文攻击技能能耗+2持续3回合；生成amount=3。 |
| SKILL:0428 芳香诱引 | 自己获得连击数+2，应对防御：额外造成打断，且敌方下回合获得眩晕。 | nrc_core/skill_effects_generated.py:467 | T06-I03；原文连击数+2；生成+3；应对眩晕遗漏。 |
| SKILL:0536 防反 | 减伤70%，应对攻击：自己获得物攻和魔攻+70%。 | nrc_core/skill_effects_generated.py:587 | T06-I03；原文减伤70%及应对双攻+70%；生成60%和双攻40%。 |
| SKILL:0598 龙吟 | 蓄力，自己获得双攻+150%和速度+80。 | nrc_core/skill_effects_generated.py:654 | T06-I03；原文双攻150%速度80；生成双攻100%速度60，且蓄力未保留。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-040"></a>
## AUD-040 · P1 · 固定技能威力误编码为百分比

主责：T06；原编号：T06-I04。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

具体例：化劲原文全技能威力+40；实际`skill_power_bonus=0`、`skill_power_pct_mod=0.4`。对基础威力100似乎相同，但基础威力50时应+40而实际仅+20。`minimal_repros.json`保存完整回合输出；根因`generate_skill_effects.py:789`、`:597`将全技能固定威力交给power_pct。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0071 力量吞噬 | 敌方获得全技能威力-20，自己获得全技能威力+20。 | nrc_core/skill_effects_generated.py:92 | T06-I04；原文全技能威力为固定点数；生成stat=power_pct并除100，改变为百分比。提气另漏换人额外+50；盛开另漏应对额外+30。 |
| SKILL:0077 化劲 | 自己获得全技能威力+40。 | nrc_core/skill_effects_generated.py:96 | T06-I04；原文全技能威力为固定点数；生成stat=power_pct并除100，改变为百分比。提气另漏换人额外+50；盛开另漏应对额外+30。 |
| SKILL:0212 提气 | 自己获得全技能威力+40，若敌方本回合更换精灵，额外获得威力+50。 | nrc_core/skill_effects_generated.py:234 | T06-I04；原文全技能威力为固定点数；生成stat=power_pct并除100，改变为百分比。提气另漏换人额外+50；盛开另漏应对额外+30。 |
| SKILL:0366 盛开 | 自己获得全技能威力+30，应对防御：改为威力+60。 | nrc_core/skill_effects_generated.py:389 | T06-I04；原文全技能威力为固定点数；生成stat=power_pct并除100，改变为百分比。提气另漏换人额外+50；盛开另漏应对额外+30。 |
| SKILL:0406 羽化加速 | 自己获得全技能威力+20，迅捷。 | nrc_core/skill_effects_generated.py:444 | T06-I04；原文全技能威力为固定点数；生成stat=power_pct并除100，改变为百分比。提气另漏换人额外+50；盛开另漏应对额外+30。 |
| SKILL:0538 防御反击 | 减伤80%，应对攻击：自己获得全技能威力+40。 | nrc_core/skill_effects_generated.py:591 | T06-I04；原文全技能威力为固定点数；生成stat=power_pct并除100，改变为百分比。提气另漏换人额外+50；盛开另漏应对额外+30。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-041"></a>
## AUD-041 · P1 · “回复”未被“恢复”正则识别，附加回复静默丢失

主责：T06；原编号：T06-I05。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0033 偷师 | 造成物伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:37 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0141 寸拳 | 造成物伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:161 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0191 抓挠 | 造成物伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:211 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0275 氧输送 | 自己回复4能量，并获得魔攻+70%。 | nrc_core/skill_effects_generated.py:295 | T06-I05；原文回复4能量并魔攻70%；当前仅魔攻70%，无回能。 |
| SKILL:0324 火苗 | 造成物伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:346 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0387 种子弹 | 造成物伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:415 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0389 移花接木 | 自己回复15%生命，随后脱离。 | nrc_core/skill_effects_generated.py:417 | T06-I05；原文回复15%生命后脱离；当前只有FORCE_SWITCH，漏治疗。 |
| SKILL:0441 藤绞 | 造成物伤，自己回复5能量。 | nrc_core/skill_effects_generated.py:476 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0448 虫网 | 造成魔伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:491 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0564 风吹雪 | 造成魔伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:620 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0580 鬼火 | 造成魔伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:629 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |
| SKILL:0583 魔爪 | 造成物伤，自己回复1能量。 | nrc_core/skill_effects_generated.py:632 | T06-I05；原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-042"></a>
## AUD-042 · P1 · 应对容器有类别但丢失应对附加效果

主责：T06；原编号：T06-I06。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0005 不动如山 | 减伤90%，应对攻击：自己获得物攻+50%。 | nrc_core/effect_data.py:418 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0015 二律背反 | 敌方获得3层星陨印记，应对防御：额外使敌方星陨印记层数翻倍。 | nrc_core/skill_effects_generated.py:28 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0045 冥想 | 减伤80%，应对攻击：敌方获得2层星陨印记。 | nrc_core/skill_effects_generated.py:42 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0049 冰墙 | 减伤80%，应对攻击：敌方获得2层冻结。 | nrc_core/skill_effects_generated.py:52 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0050 冰天雪地 | 减伤80%，应对攻击：被应对技能能耗+3。 | nrc_core/skill_effects_generated.py:56 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0053 冰点 | 敌方获得5层冻结，应对防御：额外获得5层。 | nrc_core/skill_effects_generated.py:62 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0070 剧毒 | 敌方获得3层中毒，应对防御：改为获得8层。 | nrc_core/skill_effects_generated.py:88 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0116 地陷 | 造成物伤，自己获得物防+70%，应对状态：本次技能威力翻倍，且物防额外+70%。 | nrc_core/skill_effects_generated.py:122 | T06-I06；应对状态配置威力翻倍，但原文额外物防+70%未配置。 |
| SKILL:0124 壁垒 | 减伤90%，应对攻击：防御技能冷却-1。 | nrc_core/skill_effects_generated.py:139 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0132 天火 | 敌方获得10层灼烧，应对防御：改为获得30层。 | nrc_core/skill_effects_generated.py:147 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0154 应激反应 | 自己回复25%生命，应对防御：改为回复50%生命。 | nrc_core/skill_effects_generated.py:168 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0158 强制重启 | 造成魔伤，应对状态：回合结束时使敌方精灵返场。 | nrc_core/skill_effects_generated.py:170 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0172 恶作剧 | 敌方失去3能量，应对防御：改为敌方失去6能量。 | nrc_core/skill_effects_generated.py:190 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0176 惊吓盒子 | 造成物伤，应对状态：使敌方失去6能量。 | nrc_core/skill_effects_generated.py:195 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0181 截拳 | 造成物伤，应对状态：造成打断，回复被打断技能能耗的能量。 | nrc_core/skill_effects_generated.py:199 | T06-I06；应对只配置INTERRUPT，遗漏按被打断技能能耗回复能量。 |
| SKILL:0195 报复 | 减伤70%，应对攻击：敌方失去3能量。 | nrc_core/skill_effects_generated.py:218 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0202 持续高温 | 造成魔伤，应对状态：下次攻击技能威力翻倍。 | nrc_core/skill_effects_generated.py:224 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0213 摇篮曲 | 敌方获得全技能能耗+3，应对防御：额外造成打断，且敌方下回合获得眩晕。 | nrc_core/skill_effects_generated.py:235 | T06-I06；应对只配置INTERRUPT，遗漏敌方下回合眩晕。 |
| SKILL:0221 散手 | 造成物伤，2连击，应对状态：本技能改为6连击。 | nrc_core/skill_effects_generated.py:248 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0246 有效预防 | 减伤50%，应对攻击：下一次行动获得先手+1。 | nrc_core/skill_effects_generated.py:270 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0250 极寒领域 | 造成魔伤，若敌方有冻结，本次技能威力+60，应对状态：使冻结翻倍。 | nrc_core/skill_effects_generated.py:275 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0297 泥浆铠甲 | 自己获得物攻和物防+60%，应对防御：额外使自己的增益翻倍。 | nrc_core/skill_effects_generated.py:314 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0306 淤泥表皮 | 减伤80%，应对攻击：敌方获得连击数-3。 | nrc_core/skill_effects_generated.py:324 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0307 淬火 | 减伤80%，应对攻击：下次攻击技能威力翻倍。 | nrc_core/skill_effects_generated.py:328 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0312 滚雪球 | 造成物伤，敌方获得2层冻结，应对状态：额外获得2层，本次技能威力翻倍。 | nrc_core/skill_effects_generated.py:334 | T06-I06；应对状态只配置威力翻倍，遗漏额外2层冻结。 |
| SKILL:0333 炙热波动 | 造成魔伤，敌方获得4层灼烧，应对状态：本次技能威力和赋予灼烧翻倍。 | nrc_core/skill_effects_generated.py:357 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0338 热身 | 下一次攻击时，技能威力翻倍，应对防御：改为威力变为4倍。 | nrc_core/skill_effects_generated.py:364 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0358 电磁偏转 | 减伤70%，应对攻击：下回合所选技能使用次数+1。 | nrc_core/skill_effects_generated.py:381 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0408 羽翼庇护 | 减伤70%，应对攻击：自己获得连击数+2。 | nrc_core/skill_effects_generated.py:446 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0447 虫结阵 | 减伤80%，应对攻击：己方队伍获得1次随机奉献。 | nrc_core/skill_effects_generated.py:487 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0457 蜡质膜 | 减伤80%，应对攻击：回复3能量。 | nrc_core/skill_effects_generated.py:497 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0460 血气 | 减伤60%，应对攻击：本回合受到致命伤害时，保留1生命值。 | nrc_core/skill_effects_generated.py:501 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0503 追打 | 造成魔伤，1连击，应对状态：本技能变为3连击。 | nrc_core/skill_effects_generated.py:550 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0512 酶浓度调整 | 减伤80%，应对攻击：自己回复20%生命。 | nrc_core/skill_effects_generated.py:556 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0527 错乱 | 造成魔伤，应对状态：敌方获得3层星陨印记。 | nrc_core/skill_effects_generated.py:571 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0528 镜像反射 | 减伤70%，应对攻击：本技能变为被应对的技能。 | nrc_core/skill_effects_generated.py:575 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0548 集中 | 减伤80%，应对攻击：自己回合结束返场。 | nrc_core/skill_effects_generated.py:598 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0550 雪替身 | 减伤70%，应对攻击：回复能量，回复值等于被应对技能能耗的2倍。 | nrc_core/skill_effects_generated.py:602 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0597 龙卷风 | 造成物伤，迅捷，应对状态：本次技能威力变为1.5倍。 | nrc_core/skill_effects_generated.py:650 | T06-I06；原文应对状态威力1.5倍；ON_COUNTER为空；生成器倍数正则仅接受整数。 |
| SKILL:0602 龙息环爆 | 造成魔伤，应对状态：下次技能无需蓄力。 | nrc_core/skill_effects_generated.py:656 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |
| SKILL:0605 龙血 | 减伤70%，本技能可以在蓄力状态下使用，应对攻击：下次技能无需蓄力。 | nrc_core/skill_effects_generated.py:662 | T06-I06；原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-043"></a>
## AUD-043 · P1 · 无伤害技能的本次多连击被猜测为全局永久连击增益

主责：T06；原编号：T06-I07。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

具体例：三连破原文“自己获得物攻+30%，3连击”，没有授予后续全部技能永久连击+3；实际一次增益且hit_count_mod永久+3。生成器`:1071`的注释明确以“更接近”作未经规则授权的猜测。本次重复次数细节不影响“凭空全局永久加连击”的反例。`minimal_repros.json`给出完整回合输出。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0002 三连破 | 自己获得物攻+30%，3连击。 | nrc_core/skill_effects_generated.py:12 | T06-I07；原文本技能多连击效果被生成器转换为永久自身hit_count_mod加成；无DAMAGE的状态技能也应按本技能段数重复本技能效果，而非增强后续全部技能。 |
| SKILL:0051 冰捆缚 | 2连击，每次连击敌方获得全技能能耗+1。 | nrc_core/skill_effects_generated.py:60 | T06-I07；原文本技能多连击效果被生成器转换为永久自身hit_count_mod加成；无DAMAGE的状态技能也应按本技能段数重复本技能效果，而非增强后续全部技能。 |
| SKILL:0233 星链 | 2连击，每次连击使敌方获得1层星陨印记。 | nrc_core/skill_effects_generated.py:261 | T06-I07；原文本技能多连击效果被生成器转换为永久自身hit_count_mod加成；无DAMAGE的状态技能也应按本技能段数重复本技能效果，而非增强后续全部技能。 |
| SKILL:0426 花炮 | 2连击，每次连击自己获得魔攻+60%。 | nrc_core/skill_effects_generated.py:462 | T06-I07；原文本技能多连击效果被生成器转换为永久自身hit_count_mod加成；无DAMAGE的状态技能也应按本技能段数重复本技能效果，而非增强后续全部技能。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-044"></a>
## AUD-044 · P1 · 动态条件丢失、状态凭空增加、条件主体改变

主责：T06；原编号：T06-I08。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0085 反击拳 | 造成物伤，2连击，若后手攻击，改为3连击。 | nrc_core/skill_effects_generated.py:102 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0112 回旋踢 | 造成物伤，若敌方本回合更换精灵，本次技能威力翻倍。 | nrc_core/skill_effects_generated.py:120 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0118 坍缩 | 造成魔伤，若击败敌方，自己获得魔攻+70%。 | nrc_core/skill_effects_generated.py:128 | T06-I08；原文增益有击败/敌方换人条件；生成PRE_USE无条件SELF_BUFF，提前且条件丢失。 |
| SKILL:0119 坟场搏击 | 造成物伤，敌方每有1能量，本次技能威力-10%。 | nrc_core/skill_effects_generated.py:132 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0121 埋伏 | 造成魔伤，3连击，若敌方本回合更换精灵，本次技能连击数+3。 | nrc_core/skill_effects_generated.py:134 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0126 多维击打 | 造成魔伤，1连击，敌方每有1层星陨印记，本次技能连击数+1。 | nrc_core/skill_effects_generated.py:143 | T06-I08；原文以已有印记/冻结/中毒为缩放条件；生成错误新增1层对应状态，且未配置所述动态连击/威力/减益缩放。 |
| SKILL:0159 当头棒喝 | 造成物伤，若敌方本回合更换精灵，本次技能威力+100。 | nrc_core/skill_effects_generated.py:174 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0168 怒火 | 自己获得双攻+120%和双防-40%。 | nrc_core/skill_effects_generated.py:187 | T06-I08；原文自身负面属性效果未配置；只保留正面属性/伤害/应对正面效果。 |
| SKILL:0325 灵光 | 造成魔伤，3连击，若敌方本回合更换精灵，本次技能连击数翻倍。 | nrc_core/skill_effects_generated.py:347 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0330 炎打 | 造成高额魔法伤害，自己获得物防-40%。 | nrc_core/skill_effects_generated.py:355 | T06-I08；原文自身负面属性效果未配置；只保留正面属性/伤害/应对正面效果。 |
| SKILL:0344 燃尽 | 造成魔伤，敌方每失去5%生命，本次技能威力-5。 | nrc_core/skill_effects_generated.py:369 | T06-I08；原文按敌方失去生命缩放；生成condition=self_missing_hp_step，主体变为自己。 |
| SKILL:0361 疾风刺 | 造成物伤，1连击，若先于敌方攻击，改为3连击。 | nrc_core/skill_effects_generated.py:386 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0369 石肤术 | 自己获得物防+160%和魔防-60%。 | nrc_core/skill_effects_generated.py:394 | T06-I08；原文自身负面属性效果未配置；只保留正面属性/伤害/应对正面效果。 |
| SKILL:0371 砂石冲撞 | 造成物伤，若敌方本回合更换精灵，自己获得物防+100%。 | nrc_core/skill_effects_generated.py:396 | T06-I08；原文增益有击败/敌方换人条件；生成PRE_USE无条件SELF_BUFF，提前且条件丢失。 |
| SKILL:0374 破罐破摔 | 造成魔伤，自己有减益时，本次技能威力+60。 | nrc_core/skill_effects_generated.py:404 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0378 碎冰冰 | 造成魔伤，敌方每有1层冻结，本次技能威力+20。 | nrc_core/skill_effects_generated.py:410 | T06-I08；原文以已有印记/冻结/中毒为缩放条件；生成错误新增1层对应状态，且未配置所述动态连击/威力/减益缩放。 |
| SKILL:0394 筛管奔流 | 造成物伤，自己生命大于80%时，本次技能威力+75。 | nrc_core/skill_effects_generated.py:428 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0417 背袭 | 造成魔伤，若敌方能量等于0，造成20倍伤害。 | nrc_core/skill_effects_generated.py:454 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0422 腐化 | 敌方每有1层中毒效果，敌方获得双攻-30%。 | nrc_core/skill_effects_generated.py:457 | T06-I08；原文以已有印记/冻结/中毒为缩放条件；生成错误新增1层对应状态，且未配置所述动态连击/威力/减益缩放。 |
| SKILL:0430 草虫冲击 | 造成物伤，若敌方本回合更换精灵，本次威力+90且无视敌方系别抵抗。 | nrc_core/skill_effects_generated.py:472 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0445 虫击 | 造成物伤，应对状态：本次技能威力变为2倍，无视敌方系别抵抗。 | nrc_core/skill_effects_generated.py:482 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0466 触底强击 | 造成魔伤，使用后若能量耗尽，本次技能威力+120。 | nrc_core/skill_effects_generated.py:514 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0474 贮藏 | 自己获得双攻+50%，每携带1个0能耗技能，额外+50%。 | nrc_core/skill_effects_generated.py:520 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0481 超新星馈赠 | 敌方获得2层星陨印记，每使用1次，赋予的星陨印记层数永久+1。 | nrc_core/skill_effects_generated.py:530 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0484 跌落 | 造成大量物伤，自己获得物攻-50%，应对状态：改为获得物攻+50%。 | nrc_core/skill_effects_generated.py:532 | T06-I08；原文自身负面属性效果未配置；只保留正面属性/伤害/应对正面效果。 |
| SKILL:0523 钧势 | 自己获得物防+140%和速度-30。 | nrc_core/skill_effects_generated.py:570 | T06-I08；原文自身负面属性效果未配置；只保留正面属性/伤害/应对正面效果。 |
| SKILL:0556 霜天 | 敌方获得1层冻结，且每有1层冻结获得全技能能耗+1。 | nrc_core/skill_effects_generated.py:610 | T06-I08；原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。 |
| SKILL:0588 鸩毒 | 造成魔伤，敌方每有1层中毒效果，本次技能威力+10，应对状态：改为本次威力+40。 | nrc_core/skill_effects_generated.py:635 | T06-I08；原文以已有印记/冻结/中毒为缩放条件；生成错误新增1层对应状态，且未配置所述动态连击/威力/减益缩放。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-045"></a>
## AUD-045 · P1 · 手写复合效果与当前原文不符

主责：T06；原编号：T06-I09。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0146 山火 | 造成物伤，每使用1次其他火系技能，本技能威力永久翻倍。 | nrc_core/effect_data.py:553 | T06-I09；原文每其他火技能使威力永久翻倍；手写delta=15的固定加法，增长规律错误。 |
| SKILL:0225 无畏之心 | 减伤100%，应对攻击：减免的伤害变为回复自己生命，且本技能能耗永久+2。 | nrc_core/effect_data.py:448 | T06-I09；原文应对把减免伤害转治疗并能耗+2；配置固定治疗30%最大生命，且POST_USE能耗+2无应对条件。 |
| SKILL:0352 甜心续航 | 自己和敌方获得萌化：回复40%生命。 | nrc_core/effect_data.py:793 | T06-I09；原文双方萌化各回复40%生命；配置只对自己HEAL_HP并额外回复4能量。 |
| SKILL:0354 生日蛋糕 | 驱散自己的减益，自己的增益翻倍。 | nrc_core/effect_data.py:759 | T06-I09；原文驱散己方减益并增益翻倍；配置却萌化降全技能能耗4，无清除或翻倍。 |
| SKILL:0400 绵里藏针 | 造成魔伤，若自己上回合未使用攻击技能，本技能威力永久+20。 | nrc_core/effect_data.py:594 | T06-I09；原文自己上回合未用攻击技，永久威力+20；配置delta30且trigger=per_enemy_no_damage_last_turn，条件主体错误。 |
| SKILL:0415 聚盐 | 2连击，每次连击自己回复8%生命，使用后本技能连击数永久+1。 | nrc_core/effect_data.py:617 | T06-I09；原文2连击各回复8%生命；手写只有一次5%治疗及额外1能量；后续hit_count+1未指定触发但本技能重复行为缺失。 |
| SKILL:0476 赤子之心 | 自己获得萌化：全技能能耗永久-2。 | nrc_core/effect_data.py:776 | T06-I09；原文自己萌化且全技能能耗永久-2；配置场下全体萌化+自己40%治疗+4能量，无所述永久降耗。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-046"></a>
## AUD-046 · P1 · 特性手写倍率/固定值与当前原文不符

主责：T06；原编号：T06-I10。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

具体例：图书守卫者在己方MP=1入场，组合状态每层atk_up/spatk_up均0.5；预期各1.0。蓄电池/超级电池分别0.2/0.3，原文分别0.3/0.4。`ability_probe.json`记录完整输入输出及组合状态，未误读未展开的原始*_up字段。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| ABILITY:0009 图书守卫者 | 入场时，若自己魔力值为1，自己获得双攻+100%。 | nrc_core/effect_data.py:1565 | T06-I10；原文MP=1增益100%；配置buff=0.5，少一半。MP条件处理器直接使用此参数，无补偿。 |
| ABILITY:0010 观星 | 敌方每有1层星陨印记，自己的地系技能威力+20%。 | nrc_core/effect_data.py:1302 | T06-I10；原文每星陨印记威力20%；配置bonus_pct_per_mark=0.15。观星另缺仅地系技能过滤。 |
| ABILITY:0041 构装契约者 | 入场时，若敌方魔力值为1，自己获得双防+100%。 | nrc_core/effect_data.py:1591 | T06-I10；原文MP=1增益100%；配置buff=0.5，少一半。MP条件处理器直接使用此参数，无补偿。 |
| ABILITY:0047 斗技 | 应对成功后，获得全技能威力永久+30。 | nrc_core/effect_data.py:1172 | T06-I10；原文应对后全技能威力永久+30；配置delta=20。 |
| ABILITY:0088 蓄电池 | 每入场1次，永久获得双攻+30%。 | nrc_core/effect_data.py:1507 | T06-I10；原文每入场永久双攻30%；配置20%，且永久保存机制需T09协同。 |
| ABILITY:0130 洄游 | 每次进入蓄力状态，获得全技能能耗永久-2。 | nrc_core/effect_data.py:1774 | T06-I10；原文每次蓄力永久能耗-2；配置reduce=1。 |
| ABILITY:0174 超级电池 | 每入场1次，获得双攻永久+40%。 | nrc_core/effect_data.py:1512 | T06-I10；原文每入场永久双攻40%；配置30%，且永久保存机制需T09协同。 |
| ABILITY:0205 坠星 | 敌方每有1层星陨印记，自己的技能威力+20%。 | nrc_core/effect_data.py:1296 | T06-I10；原文每星陨印记威力20%；配置bonus_pct_per_mark=0.15。观星另缺仅地系技能过滤。 |
| ABILITY:0210 指挥家 | 应对成功后，永久获得双攻+30%。 | nrc_core/effect_data.py:1166 | T06-I10；原文应对成功永久双攻30%；配置只有atk=0.2，漏魔攻且物攻值错。 |
| ABILITY:0211 自由飘 | 自己每有1层萌化，获得连击数+3。 | nrc_core/effect_data.py:1801 | T06-I10；原文每萌化连击+3；配置per=2。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-047"></a>
## AUD-047 · P1 · 特性属性目标/触发阈值和子效果遗漏

主责：T06；原编号：T06-I11。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

具体例：毒腺使用能耗3技能，敌方中毒1→5；预期该能耗不触发。毒牙在敌有1层中毒时使用普通攻击技能，敌魔攻/魔防各减40%而物攻/速度未减；原文应成功施毒时施加物攻和速度减益。鼓气/三鼓作气组合状态只含atk_up/def_up各0.2。证据`ability_probe.json`；消费这些参数的handler在`handlers_ability.py:781`、`:792`。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| ABILITY:0042 毒牙 | 使敌方获得中毒时，也会使其获得物攻-40%和速度-40。 | nrc_core/effect_data.py:1385 | T06-I11；原文成功施毒时敌物攻-40%速度-40；配置ON_USE_SKILL且spatk/spdef-40%，触发与目标属性均错。 |
| ABILITY:0064 毒腺 | 使用能耗小于等于1的技能时，敌方获得4层中毒。 | nrc_core/effect_data.py:1391 | T06-I11；原文使用能耗≤1的技能；配置阈值5且handler使用actual_cost<5，能耗2/3/4也施毒。 |
| ABILITY:0087 三鼓作气 | 使用能耗为3的技能后，获得双攻和双防永久+20%。 | nrc_core/effect_data.py:1537 | T06-I11；原文双攻双防20%；buff仅atk和def各0.2，未配置spatk/spdef。 |
| ABILITY:0162 鼓气 | 使用能耗为3的技能时，获得双攻和双防+20%。 | nrc_core/effect_data.py:1517 | T06-I11；原文双攻双防20%；buff仅atk和def各0.2，未配置spatk/spdef。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

T09毒牙/毒腺协同：[source_correction_probe_output.json](tasks/T09/source_correction_probe_output.json)。虫群处理器另列T09-I11。

<a id="aud-048"></a>
## AUD-048 · P1 · 特性的时点、受益者和偷取行为错误

主责：T06；原编号：T06-I12。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

具体例：大捞一笔/小偷小摸在ON_ENTER执行后双方能量仍3，预期从敌方偷3/2；结构中的实际阶段分别为ON_TURN_END/ON_ENEMY_SWITCH。证据`ability_probe.json`。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| ABILITY:0121 大捞一笔 | 入场时偷取敌方场上所有精灵3能量。 | nrc_core/effect_data.py:1716 | T06-I12；原文入场偷敌方场上所有精灵3能量；配置ON_TURN_END amount2。 |
| ABILITY:0123 小偷小摸 | 入场时偷取敌方场上所有精灵2能量。 | nrc_core/effect_data.py:996 | T06-I12；原文入场偷敌方场上所有精灵2能量；配置ON_ENEMY_SWITCH扣新入场精灵2能量，没有转给自身。 |
| ABILITY:0169 吉利丁片 | 离场后，更换入场的精灵获得双防+20%且免疫冻结。 | nrc_core/effect_data.py:1398 | T06-I12；原文离场给替换精灵双防20%冻结免疫；配置ON_ENTER给自己效果，目标及时点均反。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-049"></a>
## AUD-049 · P1 · 空技能效果未被拒绝，消耗能量后静默零效果

主责：T06；原编号：T06-I13。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：表中每个对象的完整原文。调用链：`nrc_platform/builder.py:630`只检查技能存在、选项和random_source，不检查效果完整性；`nrc_core/battle.py:1788`全部进入效果引擎；空列表通过legacy分支返回damage0。

最小输入/步骤：A 500/1000HP、20能量，携带“可爱”（能耗3、魔法攻击），B聚能。执行完整回合；预期造成DB威力对应魔法伤害；实际A能量20→17、B生命500→500，未报UnsupportedMechanicError。证据`minimal_repros.json`。影响：整个技能规则静默失效；选择技能即使有合法选项仍没有分支效果。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0004 下注 | 造成物伤，选择：本次技能威力+40，使用后自己生命-10%或自己生命低于50%时本次技能威力+100。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0008 丰收 | 造成物伤，自己回复20%生命。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0020 仰望夜空 | 自己获得魔攻和魔防+70%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0025 信息素 | 己方队伍获得1次随机奉献，若上回合双方有精灵使用地系技能，额外获得3次随机奉献。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0026 俯冲 | 造成物伤，先手+1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0030 假冒 | 自己的生命比例变为与敌方生命比例相同，巧变：恶系攻击技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0032 做好事 | 造成魔伤，自己每使用过1次选择技能，自己获得3层随机永久属性增益，使用后重置。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0042 入梦 | 敌方下回合回复的能量-5，冷却2回合。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0043 六自由度 | 造成魔伤，威力额外增加两侧技能威力差的四分之一，传动1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0044 养分回流 | 造成魔伤，为场下所有精灵回复1能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0057 冰裂 | 造成物伤，选择：敌方获得物防-30%或敌方获得速度-20。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0063 冷凝 | 造成物伤，敌方每有1层冻结，自己回复1能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0065 减压阀 | 主动：本技能被动永久额外+20威力，被动：两侧技能威力+10，传动1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0067 分光 | 自己获得魔攻+20%，己方队伍中精灵每有1个不同的系别，额外获得魔攻+10%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0075 加油 | 自己获得1层萌芽印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0081 友谊满溢 | 造成魔伤，选择：每次使用后威力永久+20或应对状态时本次技能威力+100%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0088 叠加态 | 自己获得随机16层属性增益，巧变：幻系攻击技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0090 叠浪 | 造成物伤，3连击，本技能能耗每-1，威力+10。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0091 可爱 | 对敌方精灵造成魔法伤害。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0093 吃独食 | 造成魔伤，自己每使用过1次选择技能，敌方获得3层随机永久属性减益，使用后重置。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0094 同频 | 造成魔法伤害，巧变：魔攻技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0100 吹散 | 造成魔伤，选择：驱散敌方所有增益或驱散双方1层印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0111 回收 | 造成魔伤，若敌方本回合更换精灵，敌方失去4能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0114 困兽 | 造成物伤，若自己生命低于50%，本次攻击吸血50%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0128 天体吸积 | 造成物伤，敌方每有1层印记，本次攻击威力+20。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0133 奇点 | 造成魔伤，若上回合双方有精灵使用水系技能，敌方获得4层星陨印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0134 委屈 | 减伤70%，应对攻击：自己获得1层萌芽印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0137 守护咒 | 减伤90%，应对攻击。巧变：龙系状态技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0139 寒潮 | 造成魔伤，敌方获得1层冻结，应对状态：额外获得4层冻结，巧变：冻结相关技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0144 小型打劫 | 敌方队伍中所有精灵失去1能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0153 广播 | 对敌方精灵造成魔法伤害。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0155 引力偏转 | 减伤80%，应对攻击：以魔法伤害触发敌方的星陨效果。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0164 微型斥候 | 造成魔伤，每受到1次抵抗的技能攻击（不含连击），本技能威力永久+20。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0169 急中生智 | 造成魔伤，自己有减益时，本次技能威力+40。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0177 惊雷 | 将天气改为雷鸣，持续8回合。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0178 惊鸿一瞥 | 自己获得连击数+1，迅捷。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0183 打喷嚏 | 3连击，每次连击敌方获得1层冻结。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0188 扬尘 | 造成魔伤，天气为沙暴时，先手+1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0198 拆礼物 | 造成物伤，若敌方有萌化，本次技能威力+100。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0200 拖拉机 | 造成物伤，位于1号位时，先手+1。传动1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0201 拟寄生 | 造成魔伤，偷取敌方1层印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0204 振翅 | 选择：己方队伍获得1次奉献：连击+1或威力+20。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0207 掉包 | 敌方的属性增益变为对应的属性减益。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0208 排气 | 敌方获得威力-20，自己每受到1次抵抗伤害（不含连击），敌方额外获得威力-20，使用后重置。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0210 掠影 | 造成物伤，若上回合双方有精灵使用火系技能，偷取敌方3能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0215 撒花 | 造成魔伤，选择：自己生命大于80%时威力+50或应对状态时自己回复35%生命。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0218 撞鬼 | 对敌方精灵造成物理伤害。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0226 无风 | 减伤50%，应对攻击：敌方和自己均脱离。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0230 星火 | 敌方获得8层灼烧，若上回合双方有精灵使用光系技能，敌方额外获得12层灼烧。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0231 星痕 | 造成魔伤，若敌方有印记，本次技能威力+40。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0235 暖气 | 减伤70%，应对攻击：下一次攻击时，技能威力+50。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0236 暖阳 | 造成物伤，每使用1次其他火系技能，威力永久+40，使用本技能后重置。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0239 暴打 | 对敌方精灵造成魔法伤害。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0244 月影交错 | 造成物伤，2连击，若上回合双方有精灵使用幻系技能，本技能获得迅捷。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0245 月蚀 | 造成物伤，若敌方生命低于50%，本次技能能耗-3。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0248 杂耍 | 造成魔伤，巧变：吸血相关技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0267 毒肽 | 减伤70%，巧变：毒系状态技能，应对攻击。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0268 毒誓 | 对敌方精灵造成物理伤害。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0288 汇流 | 雨天的回合数延长4回合，应对防御：改为延长8回合。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0290 沉溺 | 造成物伤，天气为雨天时，本技能能耗-2。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0292 沙石阵 | 自己获得速度-20，选择：且额外获得物防+90%或魔防+90%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0308 清洗 | 驱散自己的减益，自己每有1层减益，本技能能耗-1，巧变：水系攻击技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0311 溶解 | 减伤90%，应对攻击：驱散敌方1种增益。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0334 点亮 | 减伤90%，应对攻击：自己获得光系技能威力永久+50%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0340 焚尽 | 驱散自己所有印记，每驱散1层，获得物攻+50%。巧变：火系攻击技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0343 焚身 | 造成高额物理伤害，自己下回合获得眩晕。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0353 甜蜜陷阱 | 造成魔伤，自己每有1能量，本次技能威力+10。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0367 相位移动 | 减伤50%，本技能位于1号位或3号位时，额外减伤40%，应对攻击，传动1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0386 离魂术 | 偷取敌方2能量，脱离。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0398 纺纱 | 敌方获得1层暗涌印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0399 绞轮 | 造成物伤，每受到1次抵抗的技能攻击（不含连击），本技能能耗永久-1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0401 缓一缓 | 自己回复1能量和10%生命，并获得魔攻魔防+10%，速度+10。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0412 耍赖 | 自己获得双攻永久+10%，2连击。自己有减益时，本次技能连击数+1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0424 色散 | 造成魔伤，对混血精灵造成伤害+50%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0425 花火 | 造成物伤，敌方获得4层灼烧。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0436 蒸汽进行曲 | 选择：自己获得速度+60或物攻+90%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0440 薄纱环 | 选择：敌方随机获得1种负面印记或自己随机获得1种正面印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0459 血契 | 造成物伤，自己每失去10%生命，本技能威力+15。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0461 补觉 | 选择：自己回复25%生命或回复8能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0464 观测者效应 | 自己脱离，更换入场的精灵以月陨星状态登场。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0469 许愿池 | 造成魔伤，双方已有的印记层数+1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0471 试飞 | 造成物伤，2连击。选择：每次使用后本技能威力永久+10或连击数永久+1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0478 超声波 | 自己获得全技能威力+20，选择：本次能耗-1或应对防御时改为全技能威力永久+20。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0487 踏雷 | 自己回合结束时返场，携带的攻击技能下回合获得1个已触发过的迸发效果，应对防御：改为获得所有触发过的迸发效果。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0488 蹦跶 | 造成魔伤，自己有减益时本技能能耗-1，选择：自己获得萌化或解除萌化。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0489 转圈圈 | 造成魔伤，若敌方本回合更换精灵，本次攻击使敌方获得萌化。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0490 轮班 | 造成物伤，传动1，选择：本技能位于1号位时威力+65或本回合额外传动1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0492 迁飞扩散 | 造成物伤，若敌方本回合更换精灵，己方队伍获得3次随机奉献。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0493 过山车 | 使己方队伍中的所有精灵携带的技能跨精灵向下移动1个位置，巧变：机械系技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0494 过敏原 | 造成魔伤，1连击，若敌方有中毒效果，本次技能连击数+2。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0498 远行 | 造成魔伤，自己每先于敌方行动1次，本技能威力永久+25。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0508 透镜实验 | 造成物伤，选择：敌方携带光系技能时威力+50或应对状态时被应对的技能变为透射。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0509 通电 | 造成物伤，敌方获得1层引电。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0514 重组 | 下一次攻击时，额外造成100%幻系伤害，应对防御：改为额外造成300%幻系伤害。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0515 重金属粉尘 | 携带的攻击技能获得附加中毒3，应对防御：改为获得附加中毒6。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0516 野火 | 选择：敌方获得7层灼烧或物防-90%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0517 量子涨落 | 造成物伤，若敌方没有星陨印记，则敌方获得3层星陨印记。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0524 铁蒺藜 | 造成魔伤，应对状态：本次伤害翻倍。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0525 锁芯 | 造成魔伤，此技能位置不会改变。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0531 闪光弹 | 造成物伤，自己脱离。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0542 限时特惠 | 造成魔伤，敌方每有1只力竭精灵，本次技能能耗-1。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0549 雪原狩猎 | 造成物伤，天气为暴风雪时，本次技能威力+50 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0572 飞箭 | 造成魔伤，3连击。巧变：翼系防御技能。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0576 马步 | 本技能先手-1，选择：若自己生命低于20%，回复60%生命或若自己生命高于80%，获得物攻+150%。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0577 驱赶 | 造成魔伤，选择：本次技能威力+20或应对状态时本次技能威力+140。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0585 魔镜 | 敌方获得魔防-50%，且失去3能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0590 麦芒 | 造成物伤，若上回合双方有精灵使用萌系技能，自己回复7能量。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |
| SKILL:0601 龙守望 | 下次技能无需蓄力，本技能可在蓄力状态下使用。选择：本次能耗-1或应对防御时打断，敌方下回合获得眩晕。 | nrc_core/skill_effects_generated.py:缺项 | T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-050"></a>
## AUD-050 · P1 · 先手属性解析后未输出、未注入，默认归零

主责：T06；原编号：T06-I14。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

代码位置：`scripts/generate_skill_effects.py:494`解析priority_mod；`:994`输出遗漏；`nrc_platform/catalog.py:151`Skill构造未注入该字段。最小输入：携带“先发制人”；预期priority_mod=1；实际完整回合输入快照priority=0。证据`minimal_repros.json`。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0023 伪造账单 | 若敌方本回合回复生命，改为失去2倍（含溢出的回复量）。先手+1。 | nrc_core/effect_data.py:717 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |
| SKILL:0036 先发制人 | 造成物理伤害，先手+1。 | nrc_core/skill_effects_generated.py:38 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |
| SKILL:0095 后发制人 | 造成物理伤害，先手-1。 | nrc_core/skill_effects_generated.py:104 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |
| SKILL:0130 天旋地转 | 造成物理伤害，先手+1，迸发：本次技能威力+30。 | nrc_core/skill_effects_generated.py:146 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-051"></a>
## AUD-051 · P1 · 蓄力属性解析后未输出、未注入，默认立即攻击

主责：T06；原编号：T06-I15。[完整原记录](tasks/T06/issues.md)。

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

代码位置：`scripts/generate_skill_effects.py:493`识别蓄力但`:994`不输出；平台Skill构造保留charge=False。最小输入：“升龙咆哮”，A先行动；预期本回合进入蓄力、无直接伤害；实际B生命500→320、charging_skill_idx仍-1。证据`minimal_repros.json`。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0078 升龙咆哮 | 蓄力，对敌方造成魔法伤害。 | nrc_core/skill_effects_generated.py:97 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |
| SKILL:0102 吹炎 | 蓄力，造成物伤，应对状态：本次技能威力翻倍。 | nrc_core/skill_effects_generated.py:109 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |
| SKILL:0170 怨力打击 | 蓄力，造成魔伤，若蓄力期间受到攻击，本技能威力变为敌方技能威力的3倍。 | nrc_core/skill_effects_generated.py:188 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |
| SKILL:0596 龙之利爪 | 蓄力，造成物伤并吸血50%。 | nrc_core/skill_effects_generated.py:646 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

<a id="aud-052"></a>
## AUD-052 · P1 · 未知效果被静默忽略

主责：T07；原编号：T07-I01。[完整原记录](tasks/T07/issues.md)。

- 严重度 P1；主责 T07；协同核心输入支持性校验组。
- 规则依据：用户本次提供的 AGENTS.md“未实现机制抛 UnsupportedMechanicError，不静默降级”。
- 代码：`nrc_core/engine/dispatch.py:85-142`，尤其 `if handler` 后没有拒绝分支；`registry.py:240-425`。
- 最小步骤：构造合法 Ctx，调用 `_apply_tag(EffectTag('unregistered-audit-effect'), ctx)`。
- 预期：明确拒绝未知机制。实际：无异常，`handled=False` 只进调试日志。证据 `probe_output.json:unknown_effect`。
- 影响：公开效果执行入口，无论技能或特性模式均可静默失效。当前 E 共200种，199种注册，唯一未注册 INTERRUPT 在两种应对入口有明确特判，不能据此误报“正常应对打断未实现”；但放在普通效果位置同样静默忽略。

<a id="aud-053"></a>
## AUD-053 · P1 · 迅捷攻击只计算伤害，未结算

主责：T07；原编号：T07-I02。[完整原记录](tasks/T07/issues.md)。

- 严重度 P1；主责 T07；协同回合/切换组。
- 规则依据：`data/README.md:22-28`，主动更换精灵触发迅捷技能；`data/wiki/game_descriptions.csv:6` 使用第一个能量满足的迅捷技能；`data/伤害数值计算.md:6-10` 伤害公式。
- 代码：`executor.py:551-570` 丢弃 execute_skill 返回值；伤害在 `handlers_skill.py:118` 写入 result，不扣目标普通伤害；`battle.py:1555` 直接调用迅捷入口，没有消费该结果。
- 最小步骤：500HP目标，普通80威力攻击附 E.AGILITY/E.DAMAGE，调用 execute_agility_entry。
- 预期：至少扣除已计算出的90普通攻击伤害。实际：能量10→8，目标500→500，单独execute_skill返回damage=90。证据 `agility_damage`。
- 影响：所有有 effects 的迅捷攻击，例如生成配置的翼击（`skill_effects_generated.py:450`）。同一入口也丢弃应对容器、脱离、自毁等需上层消费的结果；这些附加影响未逐项复现，不扩大确证范围。

<a id="aud-054"></a>
## AUD-054 · P1 · 动态授予的迅捷标志不被迅捷入口识别

主责：T07；原编号：T07-I03。[完整原记录](tasks/T07/issues.md)。

- 严重度 P1；主责 T07；协同特性配置组。
- 规则依据：`game_descriptions.csv:6` 具备迅捷应能主动换入释放；`effect_models.py` 没有另一种“只展示不执行”的迅捷语义。快锤/暴食具体授予条件见配置，详见 Q02 的来源限制。
- 代码：`helpers.py:473-474` 只设置 s.agility=True；`executor.py:559-565` 对有effects的技能只扫描 E.AGILITY，不读skill.agility。
- 最小步骤：有DAMAGE效果的2能耗技能，调用 `_apply_matching_skill_mods(..., {'grant_agility':True,'energy_cost_lt':3})`，再调用迅捷入口。
- 预期：已经被本实现授予迅捷的技能进入释放流程。实际：agility=True，能量仍10，未执行。证据 `granted_agility`。
- 影响：所有经modify_matching_skills授予迅捷的带effects技能；当前快锤、暴食走此路。区别于I02：本项连扣能和效果分发都未开始。

<a id="aud-055"></a>
## AUD-055 · P1 · 传动入口执行旧含义，没有实现规则要求的技能移位

主责：T07；原编号：T07-I05。[完整原记录](tasks/T07/issues.md)。

- 严重度 P1；结论 未实现；主责 T07；协同回合开始组、技能传动配置组。
- 规则依据：`data/部分规则详解/传动机制.md:3-9`，回合开始循环移位，所有传动次数完成后结束；`game_descriptions.csv:33`同义。
- 代码：`executor.py:578-618` 计算后N位技能并触发其被动，既不移动列表，也不计传动次数；`battle.py:2220-2223` 从使用技能后调用。全nrc_core搜索DRIVE/drive/传动未找到另一套规则移位入口。
- 最小步骤：技能列表[审计攻击,后位]，execute_drive(...,1)。实际顺序仍[审计攻击,后位]，预期传动后[后位,审计攻击]。证据 `drive_position`。
- 影响：所有携带DRIVE的技能及相关位置特性。没有把此处“使用后触发被动”解释为文档允许的另一种机制。

协同证据：[T10-I12（T10）](tasks/T10/issues.md)；与上项同根不计新增问题。

<a id="aud-056"></a>
## AUD-056 · P1 · POST_USE忽略过滤器，极限撕裂低血量仍受惩罚

主责：T07；原编号：T07-I07。[完整原记录](tasks/T07/issues.md)。

- 严重度 P1；可达性 当前生成配置可达；主责 T07；协同技能生成组。
- 依据：`effect_models.py:424-441` SkillEffect 定义包含阶段与过滤器，未声明ON_USE/POST_USE过滤无效；具体游戏规则需要Q01裁决。
- 代码：`executor.py:194-203,220-224` 不检查filter；`filters.py:39-40` 遇category直接返回True，跳过其余合取条件；counter_se只检查category。
- 最小步骤：满血，HEAL_ENERGY(amount=1)配filter self_hp_lt=0.5，分别放ON_USE/POST_USE，实际都回1；category+不满足HP过滤实际True。
- 预期：filter不满足不触发。实际如上，见 `filter_ON_USE`、`filter_POST_USE`、`category_filter`。
- 现有配置复现：`skill_effects_generated.py:282` 极限撕裂POST_USE明确self_hp_gt=0.5。100/500HP使用后，atk_up/spatk_up仍变为-0.5，见 `live_post_filter`。这会把有条件惩罚改为无条件惩罚。data/wiki/skills.csv:243原文已获用户授权，“若自己生命高于50%”明确不是无条件惩罚；使用前/后精确取值时点另见Q01，不再保留来源缺失。
- 完整配置枚举证据config_filters.json：POST_USE有且仅有该一项；ON_USE没有非空SE.filter，category组合亦未发现，因此另外两种构造仅属潜在扩展缺陷，不当成现有实战问题。
- 影响范围：现有极限撕裂低血量也被施加双攻惩罚；ON_USE/category合取只证明扩展协议风险，不扩成现有全部技能必现。

<a id="aud-057"></a>
## AUD-057 · P1 · 清除减益只清属性，漏全部明确异常与技能负修正

主责：T07；原编号：T07-I09。[完整原记录](tasks/T07/issues.md)。

- 严重度 P1；结论确认缺陷；主责 T07 helpers；协同 T08 CLEANSE/DISPEL_DEBUFFS入口、T06真实技能对象、T00 GAME_RULE8双向规则。
- 规则依据：data/wiki/game_descriptions.csv:14（主清单GAME_RULE8）明确减益包含降低属性/技能威力/连击、增加能耗以及中毒、灼烧、寄生、冻结、萌化、引电；排除印记/特性/其他。data/wiki/skills.csv:285洗礼、:521除厄明确驱散自己的减益；data/状态分类.md:2-6区分精灵/技能/阵营绑定，不把绑定位置解释为不能清除。
- 代码位置：helpers.py:300-312 `_clear_debuffs`只归零五个_down和负priority，注释主动排除poison/burn等；handlers_skill.py:766-784 CLEANSE/DISPEL_DEBUFFS委派该函数；generated.py:318、595真实配置可达。
- 最小输入/步骤：cleanse_probe.py从当前合并配置读取洗礼、除厄的完整effects，不手写替代清除标签。甲800/1000HP，毒1/烧2/冻1/寄生1/萌化1/引电1，atk_down=.3、全技能成本mod=2、威力bonus=-20、临时加耗2；阵营poison_mark=2，最好的伙伴特性及1层复合状态。执行execute_skill。
- 预期：明确减益异常清零、属性减益清零；印记和特性保留。全技能负威力、加耗亦属于明确减益，不能全数遗留；洗礼自身降耗的先后来源另说明。
- 实际：两个真实技能全部六种异常原样保留，atk_down确实归0；除厄的成本mod=2、威力-20、临时加耗2全部保留。洗礼先自身-1使成本mod=1后仍未清。印记、特性身份和复合状态控制均保留，控制没有把正确排除项误算缺陷。
- 影响范围：洗礼/除厄及所有清除减益委派入口；单技能永久负状态和特性组合分类需逐源核对，不把这次异常反例扩成所有状态都应删除。
- 证据：cleanse_probe.py、cleanse_probe_output.json#洗礼/#除厄；coverage对应CODE helpers.py:300已从限定通过改确认缺陷；T08 object_resolution回填两技能。

<a id="aud-058"></a>
## AUD-058 · P1 · 王子的诺言把萌化误判增益，触发相反减耗

主责：T07；原编号：T07-I10。[完整原记录](tasks/T07/issues.md)。

- 严重度 P1；结论确认缺陷；主责 T07分类快照；协同 T10萌化施加、T06原文配置。萌化施加本身不是本问题根因。
- 规则依据：game_descriptions.csv:14明确萌化为减益；spirits.csv:58已授权王子原文：每回合各1次，获得增益-1成本、获得减益+1成本。
- 代码：helpers.py:24-35把cute_stacks列buffs而非debuffs；:39-55按buff分支减耗；dispatch.py:84、124附近对双方前后快照并调用。
- 最小输入/步骤：读取真实“退化”完整effects；敌方王子的诺言，未触发当回合增减益监听，有1个合法退化形态，携带成本2技能；执行退化。
- 预期：获得1层萌化属于减益，成本2→3，记录debuff回合限次。
- 实际：cute_stacks=1，但成本2→1，记录prince_promise_buff_turn=1，触发相反方向。
- 影响：王子所有萌化来源；其他未观察技能负修正/复合状态不以此样本判断。
- 证据：cleanse_probe_output.json#王子萌化分类；未调用伤害计算器生成期望，2+1=3取自原文常量。

<a id="aud-059"></a>
## AUD-059 · P1 · 吸血在实际伤害前结算，应对临时吸血无消费者

主责：T08；原编号：T08-I01。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08 原语协议，协同 T07 executor、T04 最终伤害/扣血。T04 已确认此前无同问题主记录。
- 规则依据：data/wiki/game_descriptions.csv:29，吸血按造成伤害值回复；技能原文 data/wiki/skills.csv:211 撕裂“应对状态：本次攻击吸血100%”。
- 实现位置：handlers_skill.py:260；executor.py:120-131、216-225（普通吸血在返回伤害前执行）；execute_counter_se:248-362 与旧 execute_counter 都不消费 `_life_drain_pct`；battle.py:1891 之后才应对、减伤和实际扣血。
- 最小步骤：甲500/1000HP，80威力普通攻击带100%吸血；乙使用50%减伤防御，完整回合。另使用真实撕裂配置对无效果状态技能；以及直接 ON_COUNTER LIFE_DRAIN 的协议输入。
- 预期：普通场景吸血依据减伤后的实际造成伤害；撕裂成功应对状态时，本次攻击具备100%吸血。
- 实际：`drain_before_reduction` 乙500→455，甲500→590（吸90但扣45）；`counter_drain` 只返回 `_life_drain_pct=1.0`，甲仍500。真实撕裂完整回合见 `actual_counter_drain_撕裂`，甲未回血。
- 影响：LIFE_DRAIN、GRANT_LIFE_DRAIN 常驻吸血，以及应对阶段授予本次吸血；溢出伤害/其他最终修正尚未逐场景推断。
- 证据：probe_output.json 上述3项；parameter_review.csv 所有关联 LIFE_DRAIN/GRANT_LIFE_DRAIN 行。不能把全体受关联对象的其他子句升级通过。

<a id="aud-060"></a>
## AUD-060 · P1 · 重复设置沙暴把已经折半的地系技能再次折半

主责：T08；原编号：T08-I02B。[完整原记录](tasks/T08/issues.md)。

主责T08，协同T04。规则依据：data/wiki/game_descriptions.csv沙暴只使双方地系技能能耗减半；持续天气不授权重复累乘。代码：handlers_skill.py:851-869。最小输入：一地系技能原耗4，连续执行两次沙暴设置。预期同一天气仍耗2，实际4→2→1。影响重复天气来源的成本、合法动作和支付。证据：tasks/T08/probe_output.json 的 sand_reapply；源问题T08-I02同时含额外天气伤害，后者已合T04-I14。

<a id="aud-061"></a>
## AUD-061 · P1 · 雷鸣回合末分支被外层天气白名单排除

主责：T08；原编号：T08-I03。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08 原语与调用接口，协同 T04 回合末。
- 规则依据：data/wiki/game_descriptions.csv:50，雷鸣时双方每回合结束获得1层引电，电系免疫；data/wiki/skills.csv:171 惊雷设置8回合雷鸣。
- 实现位置：handlers_skill.py:906-912 有 thunder/雷鸣处理；battle.py:939 仅允许 sandstorm/hail/snow 调用该函数。
- 最小步骤：双方普通系无引电，state.weather='thunder'、weather_turns=8，运行 turn_end_effects。
- 预期：双方各1层引电。
- 实际：`thunder_guard` 双方均0；不是 handler 不存在，而是正常回合入口到不了其分支。
- 影响：惊雷及显式雷鸣天气状态；不据不可达把实现缺口标未上线。
- 证据：probe_output.json#thunder_guard；parameter_review.csv 惊雷行。

<a id="aud-062"></a>
## AUD-062 · P1 · 转换型施加绕过状态免疫；self 中毒先检查错误对象

主责：T08；原编号：T08-I04。[完整原记录](tasks/T08/issues.md)。

- 严重度：High（转换免疫）；self 参数为 Medium、当前专名可达性待证实；主责 T08，特性其他直接施加归 T09。
- 规则依据：data/wiki/game_descriptions.csv:2-3 毒系免疫中毒、火系免疫灼烧。
- 实现位置：handlers_skill.py:270-290 先检查 ctx.target 免疫再选择 self；487-507 将印记直接转 burn_stacks；580-588 增益直接转 poison_stacks；959-965 counter_override 直接替换中毒层数同类接口风险。
- 最小步骤：火系乙已有2层攻击印记，转换每层3灼烧。另普通甲对毒系乙执行 target=self 的2层中毒。
- 预期：火系不获得灼烧；self 中毒应查甲自身是否免疫，不能由乙系别阻止。
- 实际：`convert_fire_immune` 火系获得6灼烧；`self_poison_wrong_immunity` 普通甲未获得中毒。
- 影响：炎爆术、焚烧烙印等原语配置；增益转毒与counter_override静态见同样直接写入，但本次没有独立参数复现，不宣称每个技能已实证。self 参数当前配置是否实际使用单列 reachability。
- 证据：probe_output.json 对应2项；parameter_review.csv 转换原语行。

<a id="aud-063"></a>
## AUD-063 · P1 · 中毒印记专用写入绕过普通负面印记单槽

主责：T08；原编号：T08-I05。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08，协同 T10 吟游来源槽。
- 规则依据：data/wiki/game_descriptions.csv:41，最多1种正面、1种负面印记；data/状态分类.md:6 绑定阵营。
- 实现位置：handlers_skill.py:332-334 与592-605 直接写 poison_mark；361-389 通用 handler 才执行普通负槽替换及吟游来源隔离。
- 最小步骤：敌阵营已有 spirit_mark=2，执行 POISON_MARK stacks=1。
- 预期：普通中毒印记替换其他普通负面印记，不能让普通负面并存；吟游例外仅由其来源规则授权。
- 实际：`poison_mark_slot_bypass` 同时留下 spirit_mark=2 与 poison_mark=1。
- 影响：中毒印记施加、毒层转印记入口；吟游专属来源在这两个函数亦未分槽，属于静态协同线索而未冒充该特性完整复现。
- 证据：probe_output.json#poison_mark_slot_bypass；mark_slots 表明通用函数本身确实替换，差异是旁路写入。

<a id="aud-064"></a>
## AUD-064 · P1 · 心灵洞悉把星陨印记写为精灵星陨状态

主责：T08；原编号：T08-I06。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08，协同 T06 配置语义。
- 规则依据：data/wiki/skills.csv:159 原文“敌方获得星陨印记，获得层数等于敌方印记层数”；data/状态分类.md:4-6 区分精灵状态与阵营印记；data/wiki/game_descriptions.csv:34 星陨印记由非幻技能攻击触发。
- 实现位置：effect_data.py:392-393 → MARKS_TO_METEOR；handlers_skill.py:527-534 增加 ctx.target.meteor_stacks 并设3回合倒计时。
- 最小步骤：敌方阵营 attack_mark=2，执行该原语。
- 预期：敌阵营新增2层星陨印记，并依印记槽规则处理旧负面印记。
- 实际：`marks_to_meteor_kind` 阵营仍只有 attack_mark=2；精灵 meteor_stacks=2、meteor_countdown=3。
- 影响：心灵洞悉的触发、下场继承、驱散和伤害时点全部不同。
- 证据：probe_output.json#marks_to_meteor_kind；object_resolution.csv 心灵洞悉。

<a id="aud-065"></a>
## AUD-065 · P1 · 回血反转只把倍数当布尔值，丢失2倍

主责：T08；原编号：T08-I07。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08 通用回血，协同 T09 元素回血、T07 executor 吸血（相同模式），T06 伪造账单配置。
- 规则依据：data/wiki/skills.csv:23 伪造账单“改为失去2倍（含溢出的回复量）”。
- 实现位置：handlers_skill.py:189-191、518-521。anti_heal_multiplier 为2时仅 max(0,current_hp-heal)，没有乘 anti。
- 最小步骤：甲500/1000HP，anti_heal_multiplier=2，HEAL_HP pct=0.1。
- 预期：失去200HP，至300。
- 实际：`anti_heal_multiplier` 甲至400，只失去100。
- 影响：普通技能回血、消耗印记回血；其他来源应逐消费者合并根因，不能因某个来源已查就全路径通过。
- 证据：probe_output.json#anti_heal_multiplier；T09 static_review 中对应回血说明。

<a id="aud-066"></a>
## AUD-066 · P1 · 应对两侧永久减耗参数被静默忽略

主责：T08；原编号：T08-I08。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08，协同 T06 原文参数与 T07 应对专用分发。
- 规则依据：data/wiki/skills.csv:400 能量守恒“应对攻击：两侧技能能耗永久-1”。
- 实现位置：effect_data.py:473 后配置 PASSIVE_ENERGY_REDUCE range='adjacent'；executor.py:321 专门调用 handlers_skill.py:969-975，而后者只处理 range=='all'。
- 最小步骤：己方三个槽成本[4,2,3]，中槽技能应对攻击；调用 execute_counter 的真实新格式，原语 reduce=1、range=adjacent。
- 预期：两侧槽成本变[3,2,2]。
- 实际：`adjacent_counter_reduce` 仍[4,2,3]，无异常。
- 影响：能量守恒应对增益；all范围公开修正缺失已归 T07-I04，不重报该根因。
- 证据：probe_output.json#adjacent_counter_reduce；object_resolution.csv 能量守恒。

<a id="aud-067"></a>
## AUD-067 · P1 · 听桥反击复制原始伤害，未按自身攻击和武系威力计算

主责：T08；原编号：T08-I09。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08，协同 T04 应对传入伤害。
- 规则依据：data/wiki/skills.csv:96 原文要求武系物理伤害、威力等于被应对技能；data/伤害数值计算.md:6-24 区分威力、攻防、属性克制与减伤。
- 实现位置：handlers_skill.py:943-955 注释和实现均原样反射 ctx.damage，不读取敌技能威力、自己物攻/对方物防/武系克制。
- 最小步骤：自身物攻200、敌物防100，双方普通系，被应对技能威力80、传入原始伤害90。依原文武克普通系数2、自身非武系所以本系1，独立用Fraction计算 floor(half_up(80×2×1×200×37/41)/100)。
- 预期：独立推导288（此数用于证明两种语义不同，不证明听桥所有条件）；推导源为原文与显式输入，不调用DamageCalculator。
- 实际：`mirror_raw_damage` 仅反90，敌500→410。
- 影响：听桥反击伤害，尤其双方攻防不同、对手属性克制不同时。
- 证据：probe_output.json#mirror_raw_damage 实际90；independent_oracle.py与independent_oracle_output.json 独立期望288。旧probe曾调用DamageCalculator给期望，只能作为差异线索，已用独立有理数推导替代，probe.py未来复跑也已改用独立算法。不与 T04 最终减伤规则混为同一机制。

<a id="aud-068"></a>
## AUD-068 · P1 · 已配置动态威力条件无执行分支且不拒绝

主责：T08；原编号：T08-I10。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08，协同 T06 参数生成；未知机制静默降级与 T07-I01 共同违反拒绝原则，但此处是已注册原语的参数遗漏。
- 规则依据：用户 AGENTS 未实现机制抛 UnsupportedMechanicError；data/wiki/skills.csv:56 冰锋横扫等于敌技能总成本10倍，:500 钢钻等于两侧技能威力和三分之一。
- 实现位置：handlers_skill.py:660-714 缺 enemy_total_cost/adjacent_power_sum 分支；effect_data 的两个原语配置已带上述参数，原技能威力为占位1。
- 最小步骤：真实配置，敌唯一技能成本4；钢钻左右威力120、60。调用 execute_skill；同时直接未知条件测试拒绝协议。
- 预期：动态基础威力分别40、60，再走伤害公式；不支持时明确拒绝。
- 实际：`actual_dynamic_冰锋横扫`、`actual_dynamic_钢钻` 都按基础1结算，伤害1、显示最终威力1.25；未知条件也无异常、result空。
- 影响：这两个具名技能已证实；其他 conditional_buff/stat/filter 未识别静默跳过只是同类静态线索，不能推断其所有配置当前都缺失。
- 证据：probe_output.json 三项 power_condition 与两项 actual_dynamic；parameter_review.csv 保留实际参数。

<a id="aud-069"></a>
## AUD-069 · P1 · 单击技能也受到连击增益

主责：T08；原编号：T08-I11。[完整原记录](tasks/T08/issues.md)。

- 严重度：High；主责 T08 连击展开，协同 T03 DamageCalculator 通用输入。
- 规则依据：data/wiki/game_descriptions.csv:36 改变连击次数仅对有连击技能生效。
- 实现位置：handlers_skill.py:79-104 对所有攻击统一加 hit_count_mod/毒层/萌化层，未先判断原技能是否连击；battle.py:332 直接使用传入 hit_count_override。
- 最小步骤：原技能 hit_count=1，80威力；无连击修正运行一次，再将 hit_count_mod=2 运行相同技能。
- 预期：原始单击技能不获得连击变化，仍90伤害。
- 实际：`single_hit_buff` 90→270，变为3击。
- 影响：单击技能受全局连击、毒层连击/萌化连击等修正；特性明确“固定连击数”的规则例外须逐原文确认，不能把所有例外一并推断。
- 证据：probe_output.json#single_hit_buff；未检查逐击被动触发/击杀停止，本问题只证实单击边界。

<a id="aud-070"></a>
## AUD-070 · P1 · ABILITY_COMPUTE未知action静默忽略

主责：T09；原编号：T09-I01。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09；协同T07未知原语拒绝策略，根层不同，不重复计算同一调用。
- 规则：AGENTS.md“未实现机制抛UnsupportedMechanicError，不静默降级”。
- 代码：handlers_ability.py:31-282全部action分支末尾无else拒绝。
- 最小输入：合法Ctx，EffectTag(E.ABILITY_COMPUTE,{'action':'unknown-audit-action'})。
- 预期：明确拒绝。实际：正常返回，无状态变化、无异常；证据unknown_compute_action。
- 影响：所有配置action拼写错误或未实现子机制，默认/ability_mode均可进入。

<a id="aud-071"></a>
## AUD-071 · P1 · 灰色肖像与变形活画的运行标记不连通

主责：T09；原编号：T09-I03。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09；协同T06配置、T04伤害消费；按两专名合并现有配置问题。
- 规则：AGENTS.md禁止静默降级；data/状态分类.md:2-4要求效果状态和计算一致。用户授权原文spirits.csv:410-412，灰色肖像攻击使已有减益+3；变形活画每敌增益层威力+10%、速度+5；不存在来源授权缺口。
- 代码：handlers_ability.py:654-658只写debuff_stack_bonus，全核心无读；:1079-1083写bonus_pct_per_cost，battle.py:390-392读bonus_pct_per_layer默认0。
- 最小输入：灰色肖像ON_ENTER后正常加0.1atk_down，仍为0.1；变形活画PASSIVE后敌10层增益，同一80威力攻击伤害90仍90。证据gray_portrait/paint。
- 预期：已配置标记应在对应事件计算消费；若机制不支持明确拒绝。实际两个持久键都不能产生约定效果。
- 影响：两特性当前配置可达。灰色肖像只复现赋予标记后普通减益未变化，并静态搜索证实无消费者；未声称完整攻击回合已跑。变形活画展示速度层字符串不等于速度参与计算。

<a id="aud-072"></a>
## AUD-072 · P1 · 多个已配置原语只写标记/临时context而无消费者

主责：T09；原编号：T09-I04。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09；协同回合/技能成本组。
- 规则：AGENTS.md显式拒绝不支持；data/README.md:22-35要求触发效果参与回合；data/wiki/game_descriptions.csv:6迅捷。
- 代码与影响：:434 double_damage_next（圣火骑士），:500 first_skill_agility（起飞加速），:568 aff_bonus（振奋虫心），:576/:602 context.stat_multiplier（囤积/全神贯注），:640 freeze_becomes_meteor（月牙雪糕），:1051 interrupt_cooldown_turns（威慑）；:884 carry_skill_power_bonus、:955 entry_buff_duration、:1058 low_cost_skill_power_bonus目前无特性配置，仍为实现待证实，不能归“未上线”。
- 临时倍率路径：:476破空/顺风以及:625坠星/观星写context.power_multiplier。回合末PASSIVE上下文不会用于下一次攻击，BEFORE_ATTACK只读该时点配置，不能覆盖这些PASSIVE。
- 最小输入：圣火骑士ON_COUNTER_SUCCESS后直接正常DamageCalculator，flag=True伤害仍90；破空PASSIVE传is_first=True虽然context倍率1.75，标准伤害仍90且没有first_strike_power_bonus持久flag。证据double_next/first_strike_context。其他项通过全核心写读搜索确认，未逐项完整回合动态复现。
- 预期：效果有明确消费或明确拒绝。实际：无消费且不报未支持。
- 影响边界：只证明当前原语链路不完整，不用spirits.csv独有数值认定游戏倍率绝对值。_h_ability_compute中的同名替代action有些安装了有效flag，不能误报所有first_strike功能全无实现。

<a id="aud-073"></a>
## AUD-073 · P1 · 自动离场写入字段与消费字段不匹配

主责：T09；原编号：T09-I05。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09；协同T04离场结算。
- 规则：data/wiki/game_descriptions.csv:4脱离效果；AGENTS.md未实现不能静默。用户授权原文spirits.csv:42“每次行动后脱离”，配置回合结束也是明确时点差异，合T06，不再待来源裁决。
- 代码：handlers_ability.py:506-510写Pokemon.force_switch（非模型声明字段）；:513-516写auto_switch_eot；battle.py:592-599只消费auto_switch_zero_energy/auto_switch_every_turn。
- 最小步骤：防过载保护带一只存活队友，ON_TURN_END触发后ability_auto_switch(reason=every_turn)。
- 预期：已授予自动离场标记能驱动切换。实际auto_switch_eot=True，switched=False，current_a仍0；证据auto_switch。警惕/星地善良的零能路径为同类静态键不匹配，没有单独运行。
- 影响：防过载保护、奔波命、警惕、星地善良。行动后还是回合后是另一个配置问题，不和消费缺失混为同一证据。

<a id="aud-074"></a>
## AUD-074 · P1 · 最好的伙伴在没有造成伤害时触发

主责：T09；原编号：T09-I06。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09；协同伤害成功事件组。
- 权威规则：data/部分规则详解/最好的伙伴.md:3-7“造成克制伤害后”，不是单纯使用克制系别技能。
- 代码：handlers_ability.py:1329-1343只检查ctx.skill存在与属性克制>1；effect_data.py:1606-1607挂ON_USE_SKILL。
- 最小输入：火系STATUS技能，对方草系，自己能量0；ON_USE_SKILL执行当前最好的伙伴配置。
- 预期：无攻击伤害，不加层不回能。实际完整状态+1层并回2能；证据best_partner_status。
- 影响：所有用可克制系别的状态/防御技能；免疫等实际0伤害攻击也可能错误触发，后者尚未逐组合运行。完整层状存储本身正确，不将其错误拆分为裸buff。

<a id="aud-075"></a>
## AUD-075 · P1 · 固定被动授予随着每回合PASSIVE重复累加

主责：T09；原编号：T09-I07。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09；协同回合末/迸发组。
- 规则：data/wiki/game_descriptions.csv:11迸发入场首次行动、AGENTS.md不凭空扩展规则；具体+1/+40以用户授权spirits.csv原文为子句依据，固定授予不意味着每回合无新事件自动增长。
- 代码：handlers_ability.py:1379-1390 turn_end_repeat/skip使用+=；:1438-1448 burst_power_bonus/burst_enemy_cost_up、:1461-1464 burst_extend使用+=；battle.py:793每次回合结束重复触发PASSIVE，不清这些键。
- 最小输入：双向光速，500HP、中毒1层，连跑两次真实turn_end_effects。实际repeat=1→2，HP500→470→425（首回合2次15，次回合3次15）。预期固定触发次数加成保持相同，不因没有新事件而增长。证据repeat_accumulates。
- 另对当前配置连续两次PASSIVE：电流刺激40→80，连续负荷1→2；证据同名键。前者真正回合中是否影响第二次入场或延长迸发需迸发组完整复演，已证明存储重复增加。
- 影响：上述五类原语；passive标记可以用固定值覆盖的其他handler未受本项推断。

<a id="aud-076"></a>
## AUD-076 · P1 · 充分燃烧触发使用4%灼烧公式

主责：T09；原编号：T09-I09。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09（ABILITY_COMPUTE技能复用）；协同技能组。
- 规则：data/wiki/game_descriptions.csv:3每层2%生命火系伤害；没有单独“触发伤害翻倍”依据。
- 代码：handlers_ability.py:241-252 action=double_enemy_burn_and_tick先层数*=2，再hp*0.04*层数。
- 最小输入：敌最大HP1000、当前HP500、灼烧1层，调用该action。
- 预期：层数翻为2后，按已翻倍层数触发一次2%伤害40。实际扣80，HP420；证据burn_tick。
- 影响：effect_data.py:643充分燃烧。该分支还没火系免疫过滤、没有使用统一dot伤害入口，其他附加影响只作协同线索。

<a id="aud-077"></a>
## AUD-077 · P1 · 衡量漏复制明确增益并额外回能

主责：T09；原编号：T09-I10。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；结论确认缺陷；主责T09；协同状态分类组。
- 规则：data/wiki/game_descriptions.csv:13增益含威力、连击、降耗、吸血而未含当前能量；用户授权spirits.csv:30“复制敌方的增益”。
- 代码：handlers_ability.py:417-431只max复制五维up，额外能量取max、对手hook同步仅helpers._apply_buff路径；不复制全技能威力/吸血等，也不会同步_apply_ability_buff复合状态。
- 最小输入：自己能量0、敌能10/全技能威力+20，ON_ENTER。
- 预期：应复制已明确的全技能威力增益，不凭空回能；实际能量变10、威力bonus仍0，证据balance。已有同类自身增益取max或叠加才留Q03，不影响当前漏项与额外能量缺陷成立。
- 影响：公平鸽；不把双公平鸽监听、复合状态分类或其他未跑子句判通过。

<a id="aud-078"></a>
## AUD-078 · P1 · 虫群入场时点和攻防速目标未落实（毒牙/毒腺合T06-I11）

主责：T09；原编号：T09-I11。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责虫群handler目标T09、配置阶段/毒牙毒腺合T06-I11，避免重复计数。
- 规则原文：spirits.csv:158 虫群突袭入场攻防速+15%、:2 虫群鼓舞入场攻防速+10%；:85 毒牙成功施毒时物攻-40%速度-40；:115 毒腺成本<=1才加4毒。
- 实现：handlers_ability.py:520-550 只双攻且现配置PASSIVE；:781-788 检查已有毒后减魔攻魔防；:792-804 对基础cost<5施毒，effect_data.py:1246、1252、1385、1391对应。
- 最小输入与步骤：source_correction_probe.py中一只其他存活虫队友，先ON_ENTER再PASSIVE；敌预有1毒但本次普通攻击无施毒事件；毒腺使用成本3。
- 预期：虫群入场含双攻双防速度；毒牙只有本次成功施毒才加正确属性；成本3不触发毒腺。
- 实际：虫群入场无状态、PASSIVE仅atk_up/spatk_up；毒牙atk_down/speed_down仍0、spatk_down/spdef_down各0.4；3耗毒腺加4毒。
- 影响：上述4特性；存活/力竭虫计数、成本基础/实际等其他细节没有据此判通过。
- 证据：source_correction_probe_output.json；T06 ability_probe.json既有毒牙毒腺证据；clause_review逐子句保留来源行。明确差异不需要用户再次授权原文。

<a id="aud-079"></a>
## AUD-079 · P1 · 刺肤把50威力物理伤害当固定50HP

主责：T09；原编号：T09-I12。[完整原记录](tasks/T09/issues.md)。

- 严重度P1；主责T09，协同T03通用伤害公式。
- 规则：用户授权spirits.csv:423“对攻击自己的精灵造成50威力物理伤害”；data/伤害数值计算.md:6-10 威力必须结合攻击防御计算。
- 实现：handlers_ability.py:942-951 `dmg=max(1,int(power))`，不读category、不用自身攻击或目标防御。
- 最小步骤：当前刺肤ON_TAKE_HIT配置，分别令反击者物攻100和200，其他条件固定、目标物防100、HP500。
- 预期：在没有取整饱和的本输入，50威力伤害随物攻改变；未知伤害系别不影响该比例关系。
- 实际：两组均固定500→450。未调用DamageCalculator生成期望，只按原文公式的独立比例关系验证。
- 影响：刺肤所有反击；伤害系别/本系归属的未明细节留Q04，但不影响“威力当HP”缺陷成立。
- 证据：source_correction_probe.py及source_correction_probe_output.json 刺肤_100/200。

<a id="aud-080"></a>
## AUD-080 · P1 · 随机奉献未剔除满层候选，指定奉献绕过上限

主责：T10；原编号：T10-I01。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/奉献.md:1-3。

代码位置：nrc_core/engine/handlers_field.py:22（截至55的函数/分支），消费者位置见下文。

对象：devotion_grant_random/on_hit及指定技能。

最小输入步骤：调用probe.py中的`_h_devotion_grant_random_capped、_h_devotion_on_hit_capped、devotion_all_full、devotion_explicit_cap_*`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：随机飞断5层时仍候选五种并选中飞断，实际总层数不变；应保证从未满四种中增加1。指定飞断5→6、其他10→11，超过规则上限。全满仍进行无效随机选择。

影响：devotion_grant_random/on_hit及指定技能的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-081"></a>
## AUD-081 · P1 · 折射按系别去重且排除本技能，丢失独立效果

主责：T10；原编号：T10-I02。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/折射效果.md:1。

代码位置：nrc_core/engine/handlers_field.py:58（截至67的函数/分支），消费者位置见下文。

对象：技能折射。

最小输入步骤：调用probe.py中的`refraction_duplicate_fire、refraction_LIGHT以及其余17类型case`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：携带折射（光）、火1、火2，预期魔攻+30%、灼烧8；实际魔攻0、灼烧4。set把两个同系技能折为一种，skill is not ctx.skill排除自身；仅另携光技能时才+30%。

影响：技能折射的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-082"></a>
## AUD-082 · P1 · 折射幻系写入星陨状态而非星陨印记

主责：T10；原编号：T10-I03。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/折射效果.md:19。

代码位置：nrc_core/engine/handlers_field.py:99（截至101的函数/分支），消费者位置见下文。

对象：技能折射携幻技能。

最小输入步骤：调用probe.py中的`refraction_PSYCHIC`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：预期敌方场地meteor_mark+1；实际target.meteor_stacks=1、marks_b={}。两者为完全不同机制（状态倒计时与印记受攻击触发）。

影响：技能折射携幻技能的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-083"></a>
## AUD-083 · P1 · 折射漏火毒同系免疫，地系固定减速误作比例

主责：T10；原编号：T10-I04。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/折射效果.md:1,7,4,12；data/wiki/game_descriptions.csv:2-3。

代码位置：nrc_core/engine/handlers_field.py:89（截至119的函数/分支），消费者位置见下文。

对象：折射火/毒/地。

最小输入步骤：调用probe.py中的`refraction_type_immunity_FIRE、POISON、ICE；refraction_GROUND`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：火系目标仍得4灼烧，毒系目标仍得2中毒；原文同系免疫。冰通过add_freeze_stacks检查，独立对照确实保持0。地对速度200的目标写speed_down=.4，后续变成除1.4的比例，而应固定-40。

影响：折射火/毒/地的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-084"></a>
## AUD-084 · P1 · 契约前三种球把速度百分比当固定点数，淘沙球也误用比例

主责：T10；原编号：T10-I05。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/契约的形状.md:2-4,12。

代码位置：nrc_core/engine/handlers_field.py:174（截至187的函数/分支），消费者位置见下文。

对象：契约的形状：普通/高级/国王/淘沙球。

最小输入步骤：调用probe.py中的`contract_普通咕噜球、contract_高级咕噜球、contract_国王球、contract_淘沙球`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：基础速度200，普通球应+5%=10而实际+5（speed_up=.025）；高级应+20实+10，国王应+30实+15。淘沙原文-40却写speed_down=.4。

影响：契约的形状：普通/高级/国王/淘沙球的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-085"></a>
## AUD-085 · P1 · 柔软球单效果错误复用常规球整包，9个分支效果超额或目标错误

主责：T10；原编号：T10-I06。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/契约的形状.md:14-32。

代码位置：nrc_core/engine/handlers_field.py:164（截至239的函数/分支），消费者位置见下文。

对象：柔软咕噜球18候选。

最小输入步骤：调用probe.py中的`soft_*全部18case`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：逐一固定候选18种：skill_power额外敌双攻-30%；heal额外己魔攻40%；slow_combo额外敌物防-40%且速度单位错；speed额外敌中毒；def应敌物防-40%却自己双防30%并敌星陨印记；atk额外敌魔防-40%；combo额外全技能耗-1；freeze额外4灼烧；energy额外30%吸血。其余9候选的单效果与原文匹配。

影响：柔软咕噜球18候选的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-086"></a>
## AUD-086 · P1 · 稀兽花宝只实现萌血脉，17分支缺失且入口固定萌

主责：T10；原编号：T10-I07。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/稀兽花宝.md:1-18。

代码位置：nrc_core/engine/handlers_field.py:244（截至250的函数/分支），消费者位置见下文。

对象：稀兽花宝全部血脉。

最小输入步骤：调用probe.py中的`bloodline_*全部18case；跨模块搜索resolved_bloodline_type`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：18类型逐一传element，只有萌使敌双攻减60%，其余17均零效果；effect_data.py固定element=萌，既不读取resolved_bloodline_type也不按实际血脉分支。普通应技能威力+40等全部未实现。

影响：稀兽花宝全部血脉的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-087"></a>
## AUD-087 · P1 · 解除或转移萌化只清层数，不恢复形态属性

主责：T10；原编号：T10-I08。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/wiki/game_descriptions.csv:7；反弹技能原文。

代码位置：nrc_core/engine/handlers_field.py:322（截至336的函数/分支），消费者位置见下文。

对象：反弹/逆向演化及CUTE_CLEAR_SELF接口。

最小输入步骤：调用probe.py中的`_h_cute_transfer、_h_cute_clear_self`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：A由1000HP/200速退化为幼1（900HP/180速），转移后cute_stacks=0但仍幼1、900/180；B正确进入自身幼1。预期解除该退化效果后恢复基础形态数值；恢复生命比例等细节另Q02。

影响：反弹/逆向演化及CUTE_CLEAR_SELF接口的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-088"></a>
## AUD-088 · P1 · 萌化覆盖基础速度导致永久速度增益下次退化丢失

主责：T10；原编号：T10-I09。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：示弱原文“速度永久+130”；data/wiki/game_descriptions.csv:7。

代码位置：nrc_core/engine/handlers_field.py:264（截至277的函数/分支），消费者位置见下文。

对象：示弱后再次萌化。

最小输入步骤：调用probe.py中的`cute_permanent_speed_next_gain`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：先退化、以参数130获得永久速度后user.speed=290，下一次退化直接覆盖为140，永久+130完全丢失；应新形态基础140再保留130=270。参数默认150陈旧另归T06-I02。

影响：示弱后再次萌化的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-089"></a>
## AUD-089 · P1 · 月光合奏把本次连击数永久写回技能，重复使用累加

主责：T10；原编号：T10-I10。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：月光合奏原文“本次技能连击数+1”。

代码位置：nrc_core/engine/handlers_field.py:384（截至391的函数/分支），消费者位置见下文。

对象：月光合奏。

最小输入步骤：调用probe.py中的`cute_team_power_twice`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：敌1层萌化，总层数始终1，本技能基础1连击；调用两次应每次2连击、基础保持1。实际ctx.skill.hit_count依次2、3，脱离本次修正生命周期。

影响：月光合奏的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-090"></a>
## AUD-090 · P1 · 系统发育在回合消费者中向每只场下精灵复制全额收益

主责：T10；原编号：T10-I13。[完整原记录](tasks/T10/issues.md)。

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：系统发育原文“等量…随机分配给场下的精灵”。

代码位置：nrc_core/engine/handlers_field.py:155（截至157的函数/分支），消费者位置见下文。

对象：系统发育。

最小输入步骤：调用probe.py中的`share_gains_consumer；battle.py:1213-1234、1362/1383；handlers_skill.py:195/207`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：A本次获100生命，两个场下初始各500；_apply_share_gains让每只都600，总增200。原文等量总收益只应100并随机分配。HEAL_HP/ENERGY原语另有随机分配调用，完整回合再调用该函数可重复。

影响：系统发育的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

<a id="aud-091"></a>
## AUD-091 · P1 · 全队状态变动的战报泄露未出场精灵身份

主责：T11；原编号：T11-I02。[完整原记录](tasks/T11/issues.md)。

- 严重度：P1；主责T11，协同T05/T10/T12。
- 依据：`data/对战过程中的信息遮蔽规则.md:5` 未上场精灵对方无法看见任何信息。
- 位置：`nrc_platform/rooms.py:_visible_events` 第40-70行只按事件类型/私有标志遮蔽，没有依据revealed登记过滤pokemon身份；接口 `nrc_core/runtime.py:_report_state` 枚举所有精灵状态。
- 最小步骤：1007阵容以A寒音蛇首发、B大耳帽兜首发；A赤子之心，B聚能；B读取events和state。
- 预期：A未出场替补仍未知，其变更不向B暴露名称。
- 实际：B的state.opponent_team[1]仍是未知精灵，但events包含 `pokemon='厉毒小萝'`、萌化0→1。该精灵从未上场；全队作用后的退化名泄露。
- 范围：所有会改变从未出场替补状态/技能/资源并生成公开state_change的机制；与面板本身正确遮蔽分开。
- 证据：`probe_output.json.unrevealed_bench_events` 的before/after/events/submit_result完整保存。

<a id="aud-092"></a>
## AUD-092 · P2 · 核心必需的 NumPy 未列入基础或 dev 依赖

主责：T00；原编号：T00-I01。[完整原记录](tasks/T00/issues.md)。

- 主责：T00（依赖清单）；协同：T03（核心数值）、T02（目录入口）。依据：AGENTS.md 的 `pip install -e ".[dev]"` 运行命令及核心必须可导入的接口约定。
- 代码：`pyproject.toml:12-16,33-35` 只有screen/training附加项声明NumPy；`nrc_core/catalog.py:12`、`constant.py` 直接导入NumPy，平台目录导入核心时也必需。
- 最小输入与步骤：`dependency_probe.py` 子进程仅模拟NumPy缺失，其余当前环境不变，`import nrc_platform.catalog`。
- 预期：安装声明的基础/dev依赖足以导入并运行核心。实际：阻断NumPy后 `ModuleNotFoundError`，而基础/dev声明均不含NumPy。
- 影响：干净环境依照文档只安装dev时可能启动/测试失败；当前机器已有NumPy所以19测试通过，不能据此证明依赖完整。未实际卸载软件，也不声称当前环境损坏。
- 证据：[dependency_probe.py](tasks/T00/dependency_probe.py)、[dependency_output.json](tasks/T00/dependency_output.json)。不涉及修复规则。

<a id="aud-093"></a>
## AUD-093 · P2 · 分布表重写只做 upsert，不能移除旧项

主责：T01；原编号：T01-I02。[完整原记录](tasks/T01/issues.md)。

- 主责：T01；协同：T02（目录消费 `distribution_records`）。依据：`sync.py:802-811,1056-1080` 的 `--remove-missing` 与 CSV/数据库同步约定；不是用旧实现推导战斗规则。
- 代码：`database.py:401-407` → `write_database:469-471`，缺少与其他类别相同的保留键清理；消费端 `nrc_platform/catalog.py:95`。
- 最小输入与步骤：在 `sqlite :memory:` 创建当前 schema，先写甲的“旧技能100%”，第二次仅写“新技能100%”。两次均调用实际 `_write_distributions`。
- 预期：按第二份完整、已合并快照只保留新技能；实际同时存在新、旧技能。空列表也不会清除旧项。四类分布均共用此函数。
- 影响：执行移除策略时 canonical CSV 已移除的分布仍可留在 SQLite，平台可能继续显示旧分布；当前快照字段核对一致，不声称历史已有此污染。
- 证据：[probe.py](tasks/T01/probe.py)、[probe_output.json](tasks/T01/probe_output.json) 的 `distribution_replace_probe`。源库只读，复现未创建持久数据库。

<a id="aud-094"></a>
## AUD-094 · P2 · neutral/zero模式实际套用非中性坦率性格

主责：T02；原编号：T02-I03。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02默认解析主责；P2内部协议/说明偏差
- 规则依据/原文行号：data/属性数值计算.md:6-22（坦率位于生命-/物防+，分别-10%/+20%）；builder的attribute_assumption协议
- 代码位置：nrc_platform/builder.py:354-362,398-411
- 最小输入步骤：只提供HP1000，metadata.attribute_assumption=neutral；物防种族27、资质0。
- 预期与实际：neutral/zero标记应代表无性格修正；实际记录assumption:neutral但nature=坦率、物防98。独立无性格公式round_half_up(round_half_up(27×1.1+10)×1)+50=90；坦率则40×1.2+50=98。游戏没有中性性格，若产品只想任选性格，至少不能将此输出标为neutral。
- 影响范围：单HP快捷输入被强制切neutral；zero/all_zero和无分布fallback同样使用坦率。默认应如何选择性格仍另列Q02，不从本问题强推产品默认。
- 证据：`probe.py` 实际运行；`probe_output.json#I03_neutral_nature`。

<a id="aud-095"></a>
## AUD-095 · P2 · 核心可解析的技能ID被建造校验拒绝，名称路径又重写ID

主责：T02；原编号：T02-I04。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02平台结构化协议主责
- 规则依据/原文行号：nrc_core/schema.py:SkillSlotInput.skill_id/name；nrc_core/catalog.py:CoreCatalog.get_skill支持ID；nrc_platform/builder.py接口
- 代码位置：nrc_platform/builder.py:442-453,586-587,630-633
- 最小输入步骤：拍击目录ID skill_000303；对照catalog.get_skill(ID)，再以skills=[{skill_id:ID}]正式build。
- 预期与实际：目录能解析该ID为拍击；build先用names-only集合拒绝unknown skill。仅传name时又将目录稳定ID重写为拍击。应保持名称/ID两种协议一致并保留稳定标识。
- 影响范围：所有ID-only输入、需要目录ID的下游关联；目前常用slot动作仍可执行，不夸大为全技能不可用。
- 证据：`probe.py` 实际运行；`probe_output.json#I04_id_only`。

<a id="aud-096"></a>
## AUD-096 · P2 · 属性值不识别时静默改为普通

主责：T02；原编号：T02-I06。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02类型适配主责
- 规则依据/原文行号：nrc_core/models.py Type枚举；nrc_platform/catalog.py _TYPE_ALIASES；AGENTS未知机制不静默降级
- 代码位置：nrc_platform/builder.py:422-429
- 最小输入步骤：完整构造输入base.attributes=[fire,water]（核心Type.value与目录解析均使用/接受的名称）。
- 预期与实际：应识别火/水，或按明确中文输入契约拒绝；实际接受后变成normal/normal，既不保留输入也不报错。中文18系正式目录装载转换已独立通过，不能据此掩盖该显式输入路径。
- 影响范围：英文核心枚举回填、拼写错误和未知类型；影响克制、本系与免疫。P2输入适配缺陷，具体公开输入枚举约束另请明确。
- 证据：`probe.py` 实际运行；`probe_output.json#I06_english_combat_types`。

<a id="aud-097"></a>
## AUD-097 · P2 · 嵌套base类型未拒绝，预览请求落入AttributeError

主责：T02；原编号：T02-I07。[完整原记录](tasks/T02/issues.md)。

- 主责协同：T02输入主责；T12 HTTP协同
- 规则依据/原文行号：nrc_platform/input.py merge_creature_spec映射协议；HTTP预览结构化参数错误约定（T12端到端）
- 代码位置：nrc_platform/input.py:35-49；rooms.py:282-291；codec.py:66-88
- 最小输入步骤：RoomService.pokemon_preview({name:迪莫,base:invalid})；并测base=[1]、3。
- 预期与实际：应以结构化参数错误拒绝。merge将非Mapping的base原样交给下游，三个输入分别触发str/list/int没有get的AttributeError；T12实际HTTP返回500。修正应在输入边界或统一schema拒绝，不把坏参数变成服务器内部错误。
- 影响范围：预览及共用merge/codec的嵌套字段；非游戏规则问题、不泛化安全攻击。单HP后缀与坏base组合还会得到不同ValueError，属于同一缺少统一形状校验根因。
- 证据：`probe.py` 实际运行；`probe_output.json#I07_preview_invalid_base`。

<a id="aud-098"></a>
## AUD-098 · P2 · 默认日志与环境变量行为不符README

主责：T05；原编号：T05-I10。[完整原记录](tasks/T05/issues.md)。

- 结论：确认缺陷；严重度：P2；主责协同：T05诊断文档主责
- 规则依据/原文行号：nrc_core/README.md:验证与诊断末段；nrc_core/debug.py函数说明
- 代码位置：nrc_core/debug.py:10,37-38
- 最小输入步骤：NRC_CORE_LOG环境变量设为空，configure_core_logging(None)后记录damage事件。
- 预期与实际：README称默认不输出并由环境变量控制；实际读取硬编码NRC_CORE_LOG="damage"，仍输出一条日志。此为公开诊断接口偏差，不作为游戏规则缺陷。
- 影响范围：所有默认import与日志配置，无需假设敏感信息攻击风险。
- 证据：probe.py；probe_output.json:I10_logging_docs `{"env_disabled": "", "actual_categories": ["damage"], "actual_output": "[nrc_core:damage] {\"event\": \"audit\"}\n", "expected": "README默认无日志，环境变量为空应关闭；实现固定damage"}`

<a id="aud-099"></a>
## AUD-099 · P2 · 水环应对路径遗漏全技能公开修正归属

主责：T07；原编号：T07-I04。[完整原记录](tasks/T07/issues.md)。

- 严重度 P2；主责 T07；协同状态可见性组。
- 规则依据：`data/对战过程中的信息遮蔽规则.md:3-7`，全局增减益公开，特定技能效果仅己方可见。
- 代码：`executor.py:308-309,402-404` 直调 `_h_passive_energy_reduce_water_ring`；`dispatch.py:30-39` 已定义该handler的全局来源记录，但直调绕过它。
- 最小步骤：2能耗技能，执行 ON_COUNTER(category=attack) 内 PASSIVE_ENERGY_REDUCE(reduce=2,range=all)。对照以 ability_mode=True 从_apply_tag执行相同原语。
- 预期：两条路径均记录全技能能耗-2并保留逐槽实际变化。实际：应对路径cost=0，public/private均null；对照组public.energy_cost=-2。证据 `counter_public` 与 `ability_public_control`。
- 影响：新旧应对格式水环效果；底层能耗确实降低，问题是公开归属缺失，而非能耗没有变化。平台最终展示由协同组验证。

<a id="aud-100"></a>
## AUD-100 · P2 · 旧格式迅捷释放多个技能（目前仅接口可达）

主责：T07；原编号：T07-I06。[完整原记录](tasks/T07/issues.md)。

- 严重度 P2；可达性：兼容接口可达，当前平台配置未证实；主责 T07。没有文档明确尚未上线，规则结论不能用可达性替代。
- 规则依据：`game_descriptions.csv:6` 第一个能量满足要求的迅捷技能。
- 代码：`executor.py:559-562` 旧格式释放后continue，和新格式的break不一致。
- 最小步骤：携带两个均agility=True、无effects、各2能耗的技能，调用迅捷入口。
- 预期：仅首个，剩8能量。实际：剩6，两个均释放。证据 `legacy_agility_first`。
- 影响：旧模型兼容入口；当前平台支持技能是否存在无effects的可用迅捷项未得到充分证明，因此不当成线上必现。

<a id="aud-101"></a>
## AUD-101 · P2 · 双视角观测缺少对方奉献总层数

主责：T11；原编号：T11-I03。[完整原记录](tasks/T11/issues.md)。

- 严重度：P2；主责T11，协同T10/T12。
- 依据：`data/部分规则详解/奉献.md:5` 对方可以看到总层数，不能看到具体分配。
- 位置：`nrc_platform/state.py:normalize_observation` 末尾计算opponent_devotion却未输出。
- 最小输入：已初始化双方奉献分别 `{'飞断':2,'假寐':1}` 和 `{'虫茧':4}`，分别读取双方public_state。
- 预期：A有own.total3/distribution及opponent.total4；B有own.total4/distribution及opponent.total3。
- 实际：两视角只有own键，缺少对方总数。
- 范围：全部有奉献的对局，分布保密仍正确。
- 证据：`probe_output.json.devotion_visibility`。

<a id="aud-102"></a>
## AUD-102 · P2 · predict_damage忽略组合状态，给出与显示接口不一致的精确预测

主责：T11；原编号：T11-I04。[完整原记录](tasks/T11/issues.md)。

- 严重度：P2；主责T11，协同T03/T04/T05。
- 依据：`data/部分规则详解/战报.md:5` 技能耗能和显示威力由核心计算；`data/部分规则详解/最好的伙伴.md` 组合状态计算时应用派生加成；拨浪鼓原文每个状态技能使毒萌技能威力+10。
- 位置：`nrc_platform/platform.py:predict_damage` 第590行直接调用DamageCalculator，缺少技能组合状态power展开；对照 `core._turn_start_skill_display` 的power_override。
- 最小输入：寒音蛇携带撒娇、己方状态技能累计2，触发拨浪鼓ON_ENTER后同时调用get_display_info、query_display_power、predict_damage(reduction=0)。
- 预期：三入口均纳入固定+20；显式技能30、加成20、萌本系1.25后威力62.5（显示62），对手魔防196、魔攻156，规则每击floor(round(62.5×156×37/41)/196)=44，三击132。
- 实际：display/query显示62、每击44、3击；predict显示37、每击26、总78，却标记certainty=exact。
- 范围：带技能维度组合状态的直接平台预测API；Web是否调用由T12单列。另有减伤取整问题与T04-I01共用根因，不重复计数。
- 证据：`probe_output.json.prediction_contract`。

<a id="aud-103"></a>
## AUD-103 · P2 · 直接 HP 输入与显式空资质导入被自动填入三个 8 资质

主责：T12；原编号：T12-I01。[完整原记录](tasks/T12/issues.md)。

- 严重度：P2。主责 T12；协同 T02/T03 核对面板输入与公式。
- 规则依据：`nrc_server/README.md:48-58` 的 Direct stat input 明确只给 HP 时其余五维用零资质、中性性格公式；`data/属性数值计算.md:30` 明确资质可为零。README 是本功能输入契约，不作为战斗公式权威。
- 代码位置：`nrc_server/static/app.js:72-83` 的 `ensureDefaultCustomization`；`addCreature:181-190`；`importRoster:256-257`。无条件对空 `individual_values` 填目录前三项，未区分显式空值与缺省，也未排除 `base.stats` 的直接输入。
- 最小输入/步骤：全新标签页，己方搜索输入 `迪莫 420`，确认，导出阵容。第二条独立输入是在合法阵容 JSON 中显式设 `base.individual_values={}`，导入后导出。
- 预期：第一条保留 `stats.hp=420`，其他五维不增添资质；第二条保留用户显式空资质。
- 实际：两条都变为 `individual_values={speed:8,spatk:8,atk:8}`，血脉还按目录首项补为首领。此处只将不该补的资质判缺陷，不擅自判断血脉默认政策。
- 影响：单 HP 直接输入的其余面板改变；零资质阵容导入导出不能保持配置。六维全部覆盖时资质可能不影响显式六维，不能把本问题泛化成六维覆盖被忽略。
- 证据：`browser_output.json` 的 `directStatExport`、失败检查 `direct HP does not add aptitudes`；`supplement_output.json` 的 `emptyAptitudeRoundtrip`；`06_editor.png`。
- 复现命令：`node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/browser_probe.js` 和 `supplement_probe.js`。两脚本自动使用已空闲的 8774，均关闭自己创建的浏览器和服务。

<a id="T12-I02"></a>

<a id="aud-104"></a>
## AUD-104 · P2 · 不同共鸣魔法复合行动显示成完全相同按钮

主责：T12；原编号：T12-I02。[完整原记录](tasks/T12/issues.md)。

- 严重度：P2。主责 T12；协同 T05 提供合法复合行动。
- 规则依据：`data/部分规则详解/共鸣魔法.md:3-18,34-38` 区分愿力强化与光合治愈，两者效果、次数和本场所携带种类不同；页面选择必须能区分实际提交的合法动作。
- 代码位置：`nrc_server/static/app.js:528-532` 的 `actionLabel` 只读 `primary.kind/skill_name`；`:566-568` 的 `renderBagDrawer` 把完整含 resonance 的 key 放在按钮，文字却不显示 resonance。
- 最小输入/步骤：1007 A/B 各前两只即可，把 A 首只迪莫技能换为 `[假寐,火焰箭,棘突,超导]`，光血脉，正常准备确认后打开“背包”。
- 预期：至少用“假寐 + 愿力强化”和“假寐 + 光合治愈”等不同文字说明将提交哪种共鸣。
- 实际：两个按钮文字都只有“假寐”，一个提交 `skill:slot=0|resonance=willpower`，另一个提交 `skill:slot=0|resonance=solar_heal`；没有 title、图标或辅助文字区分。其它共鸣条目也只显示原技能或聚能名。
- 影响：玩家无法从 UI 判断正在选择的共鸣种类，可能提交另一种共鸣并消耗对应次数。本问题不判断下层共鸣实现是否符合原文。
- 证据：`supplement_output.json` 的 `bagButtons/indistinguishable`；已人工查看 `07_resonance_choices.png`。
- 复现：运行 `supplement_probe.js`，检查 `bag distinguishes resonance choices=false`。

<a id="T12-I03"></a>

<a id="aud-105"></a>
## AUD-105 · P2 · 退出后在途房间摘要响应回填已清空的对局

主责：T12；原编号：T12-I03。[完整原记录](tasks/T12/issues.md)。

- 严重度：P2。主责 T12；不需要下层业务配合才能复现。
- 规则依据：`nrc_server/static/session.js:11-29` 定义退出清除当前会话；`nrc_server/README.md:17-25` 说明页面状态由令牌绑定当前房间。清除后不应重新持有无令牌的旧房间。
- 代码位置：`nrc_server/static/battle.js:32-47` 的 `refreshBattle` 捕获 ID 后 await 摘要，随后直接写回 `state.battle`，没有请求代次、房间或认证检查。`app.js:644-655` 清理退出；相对地 `app.js:400` 的 operation 轮询已有房间/decision 复核，不能据此推定刷新也安全。
- 最小步骤：双方正常进入回合；提交双方聚能，使用 Playwright `route` 仅延迟 A 的 `GET /api/battles/{id}` 摘要请求，保持真实服务器响应；A 点击“退出”；释放摘要响应，等待 300ms。
- 预期：准备屏可见，`state.battle=null`、`playerToken=''`，旧响应不再改写本地状态。
- 实际：退出当刻二者均已清空；响应释放后 `state.battle` 恢复为旧房间 turn=3/initialized=true，`playerToken=''`，准备屏仍可见。后续状态请求因令牌清空而失败，页面处于房间与认证不一致的状态。
- 影响：快速退出与网络延迟组合可令旧战斗状态重现；随后创建/提交可能对旧房间发起无认证请求。未宣称导致服务端跨身份访问。
- 证据：`supplement_output.json` 的 `raceImmediately/raceAfter` 与失败检查；`10_exit_race.png`。`supplement_first_attempt.json` 延迟的是后续 state 请求、该时间点没有回填 battle，作为负对照保留。
- 复现：运行 `supplement_probe.js`。只控制网络时序，不注入或修改业务状态。

<a id="T12-I04"></a>

<a id="aud-106"></a>
## AUD-106 · P2 · 未配置性格时编辑器显示目录第一性格，实际未提交该显示性格

主责：T12；原编号：T12-I04。[完整原记录](tasks/T12/issues.md)。

- 严重度：P2。主责 T12；协同 T02/T03 为实际预览提供性格与数值。
- 规则依据：`data/属性数值计算.md:4-22`，性格直接改变属性；`nrc_server/README.md:56-58` 明确直接数值输入不臆造性格。展示当前配置时应与提交/预览一致。
- 代码位置：`nrc_server/static/roster.js:103`：`base.nature || customization.natures?.[0]?.name || ''`；该回退仅用于输入框和加成说明，不写入 base；`:244-249` 的 `previewPayload` 仍提交原 base。
- 最小输入/步骤：新标签页搜索 `迪莫 420`，确认，打开编辑器，不选择任何性格；导出并请求同一 base 的预览。
- 预期：输入框显示未设置/中性，或显式选定某性格并让预览/提交一致。
- 实际：输入框为“莽撞”，加成说明“魔防 -0.1 / 速度 +0.2”；base 没有 nature 字段，同一 HTTP 预览 `nature=null`。这里只证明实际未提交该显示性格，不推导最终面板是否中性；T02 已证明另一 neutral 构造路径实际套用非中性坦率。小数加成是否改成百分号另属文案，不额外记问题。
- 影响：未选择性格的用户会误认为已采用目录高频性格，但请求与预览没有该配置；最终计算走哪条性格回退路径尚未由本场景独立测定。导入性格缺省的阵容也可遇到。
- 证据：`supplement_output.json` 的 `editor.displayedNature/base` 与 `naturePreview.nature`；已人工查看 `11_nature_mismatch.png`。
- 复现：运行 `supplement_probe.js`，检查 `displayed nature matches submitted nature=false`。

<a id="T12-I05"></a>

<a id="aud-107"></a>
## AUD-107 · P2 · 战斗及补位界面缺少双方 MP 数值

主责：T12；原编号：T12-I06。[完整原记录](tasks/T12/issues.md)。

- 严重度：P2。主责 T12；投影已提供字段，无需 T11 配合补数据。
- 规则依据：`data/对战过程中的信息遮蔽规则.md:3` 明确双方 MP 值属于双方可见信息。MP 是阵营资源，精灵当前能量和阵容圆点不能代替 MP 数值。
- 代码位置：`nrc_server/static/battle.js:49-64` 取得 state 后交给 `mergeObservation/renderSide`；`app.js:420-430` 保存完整 shared，但 `:455-481` 只渲染精灵名字、HP、能量、状态及阵容圆点；`index.html:24-27` 没有 MP 容器。其它精灵/背包抽屉与公共状态渲染也未读取 `shared.mp`。
- 最小步骤：按照已有真实 `supplement_probe.js` 的双人场景进入战斗并打开共鸣背包；再对照已有 `browser_probe.js` 制造力竭后的 replacement。无需重新启动服务器复核静态证据。
- 预期：两视角均显示自己的及对方的当前 MP 数值。
- 实际：`supplement_output.json.devotion.a.mp` 与 `.b.mp` 均为 `{own:4,opponent:4}`，字段已由真实 HTTP 观测保存，但全屏 `07_resonance_choices.png` 与 `05_replacement.png` 只有HP/能量、状态和圆点，均无双方 MP。标准同步/渲染链没有MP读取或隐藏入口。
- 影响：用户无法从当前界面知道双方阵营资源，特别是精灵力竭后的剩余 MP；不是把后端缺字段再次计为UI问题。
- 证据：`missing_mp_evidence.json` 保存两个真实视角 MP、源码渲染片段、精准词匹配结果及两截图哈希；两截图已人工复看。只复用已完成 Chrome 真实截图与捕获状态，不重新打开浏览器，也不声称本轮另有DOM快照。
- 复核命令：`python docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/final_supplement.py`；原始真实场景可运行 `supplement_probe.js/browser_probe.js`，本轮未重跑。

<a id="aud-108"></a>
## AUD-108 · P3 · 拼音匹配少量候选时重复追加已有候选

主责：T12；原编号：T12-I05。[完整原记录](tasks/T12/issues.md)。

- 严重度：P3。主责 T12。
- 规则依据：目录检索/编辑器候选展示契约；没有战斗规则推断。
- 代码位置：`nrc_server/static/roster.js:34-38`：首次匹配已经包括 pinyin；少于5项时再次追加同一 pinyin 匹配集合，没有排重。
- 最小输入：真实浏览器目录提供的21项性格候选，query=`mangzhuang`。直接调用同一导出的 `createRosterEditor({}).choiceMatches`；该方法不依赖 DOM。
- 预期：`[莽撞]`。
- 实际：`[莽撞,莽撞]`。本次 `dimo` 匹配较多，因此原始页面探针没有暴露此分支；不能把那条通过推广到小候选集。
- 影响：性格、血脉、资质或技能检索出现重复按钮，挤占最多5项的显示位置。
- 证据：`pure_js_output.json`，输入候选来自 `supplement_output.json.editor.nature`，不是虚构 metadata。
- 复现：`node docs/battle_audit/20261112-132335-1bcaab0/tasks/T12/pure_js_probe.mjs`。Node 模块类型检测警告已保留；业务 package.json 未改。

<a id="T12-I06"></a>

## 未实现拒绝方式

| 机制 | 拒绝/放行事实 | 证据 |
|---|---|---|
| 70种空特性、152形态 | direct builder正确抛出；平台抹特性名后错误放行 | T11-I01；tasks/T10/unsupported_ability_forms.json |
| 空技能效果 | 构建接受，正式执行扣能量后零效果 | T06-I13 |
| 未知E/ABILITY_COMPUTE action | 静默返回，没有UnsupportedMechanicError | T07-I01；T09-I01 |
| 17血脉/传动/禁足/选择 | 无效果或未执行完整规则，未明确拒绝 | T10-I07；T07-I05；T05-I07/I08 |
| 闪焰爆发/节流术 | 权威文档明确未上线，非上述实现缺口 | questions.md；T05报告 |

根因拆并明细见 [issue_aliases.csv](issue_aliases.csv)。存疑或证据不足项不在此表冒充确认缺陷，见 [questions.md](questions.md)。
