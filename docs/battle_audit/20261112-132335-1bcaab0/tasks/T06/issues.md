# T06 配置与生成审计缺陷

以下只将结构或最小执行证据已确认的差异编号。严重度P1表示直接改变战斗结果或导致操作异常。每项中的对象表给出精确规则行（DB稳定ID及原文）、配置位置、参数差异；同根因合并，不将相似对象逐项制造重复问题。

重现环境：Python项目原有环境；`python .../tasks/T06/probe.py`和`minimal_repros.py`；数据库只读URI；业务源码与生成文件没有修改。输入输出分别保存在同目录JSON。

## T06-I01 生成回退重复包装SkillEffect，8技能在执行时崩溃

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

## T06-I02 手写技能覆盖保留过期数值，覆盖正确数据源

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

## T06-I03 生成产物数值和目标陈旧或错误

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

## T06-I04 固定技能威力误编码为百分比

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

## T06-I05 “回复”未被“恢复”正则识别，附加回复静默丢失

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

## T06-I06 应对容器有类别但丢失应对附加效果

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

## T06-I07 无伤害技能的本次多连击被猜测为全局永久连击增益

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

## T06-I08 动态条件丢失、状态凭空增加、条件主体改变

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

## T06-I09 手写复合效果与当前原文不符

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

## T06-I10 特性手写倍率/固定值与当前原文不符

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

## T06-I11 特性属性目标/触发阈值和子效果遗漏

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

## T06-I12 特性的时点、受益者和偷取行为错误

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。

具体例：大捞一笔/小偷小摸在ON_ENTER执行后双方能量仍3，预期从敌方偷3/2；结构中的实际阶段分别为ON_TURN_END/ON_ENEMY_SWITCH。证据`ability_probe.json`。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| ABILITY:0121 大捞一笔 | 入场时偷取敌方场上所有精灵3能量。 | nrc_core/effect_data.py:1716 | T06-I12；原文入场偷敌方场上所有精灵3能量；配置ON_TURN_END amount2。 |
| ABILITY:0123 小偷小摸 | 入场时偷取敌方场上所有精灵2能量。 | nrc_core/effect_data.py:996 | T06-I12；原文入场偷敌方场上所有精灵2能量；配置ON_ENEMY_SWITCH扣新入场精灵2能量，没有转给自身。 |
| ABILITY:0169 吉利丁片 | 离场后，更换入场的精灵获得双防+20%且免疫冻结。 | nrc_core/effect_data.py:1398 | T06-I12；原文离场给替换精灵双防20%冻结免疫；配置ON_ENTER给自己效果，目标及时点均反。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

## T06-I13 空技能效果未被拒绝，消耗能量后静默零效果

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

## T06-I14 先手属性解析后未输出、未注入，默认归零

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

代码位置：`scripts/generate_skill_effects.py:494`解析priority_mod；`:994`输出遗漏；`nrc_platform/catalog.py:151`Skill构造未注入该字段。最小输入：携带“先发制人”；预期priority_mod=1；实际完整回合输入快照priority=0。证据`minimal_repros.json`。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0023 伪造账单 | 若敌方本回合回复生命，改为失去2倍（含溢出的回复量）。先手+1。 | nrc_core/effect_data.py:717 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |
| SKILL:0036 先发制人 | 造成物理伤害，先手+1。 | nrc_core/skill_effects_generated.py:38 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |
| SKILL:0095 后发制人 | 造成物理伤害，先手-1。 | nrc_core/skill_effects_generated.py:104 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |
| SKILL:0130 天旋地转 | 造成物理伤害，先手+1，迸发：本次技能威力+30。 | nrc_core/skill_effects_generated.py:146 | T06-I14；原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。

## T06-I15 蓄力属性解析后未输出、未注入，默认立即攻击

严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。

代码位置：`scripts/generate_skill_effects.py:493`识别蓄力但`:994`不输出；平台Skill构造保留charge=False。最小输入：“升龙咆哮”，A先行动；预期本回合进入蓄力、无直接伤害；实际B生命500→320、charging_skill_idx仍-1。证据`minimal_repros.json`。

| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |
|---|---|---|---|
| SKILL:0078 升龙咆哮 | 蓄力，对敌方造成魔法伤害。 | nrc_core/skill_effects_generated.py:97 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |
| SKILL:0102 吹炎 | 蓄力，造成物伤，应对状态：本次技能威力翻倍。 | nrc_core/skill_effects_generated.py:109 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |
| SKILL:0170 怨力打击 | 蓄力，造成魔伤，若蓄力期间受到攻击，本技能威力变为敌方技能威力的3倍。 | nrc_core/skill_effects_generated.py:188 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |
| SKILL:0596 龙之利爪 | 蓄力，造成物伤并吸血50%。 | nrc_core/skill_effects_generated.py:646 | T06-I15；原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。 |

证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。
