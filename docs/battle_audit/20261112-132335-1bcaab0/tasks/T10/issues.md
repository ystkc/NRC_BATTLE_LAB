# T10 场地原语审计问题

所有输入见probe.py，完整前后状态见probe_output.json；均为内存调用，不修改业务或数据库。123个探针覆盖常规12球、柔软18候选、18血脉、18折射类型及重复/免疫/萌化/消费者。数值夹具：HP1000当前500，四攻防与速度200，能量5，技能威力50耗4。

## T10-I01 随机奉献未剔除满层候选，指定奉献绕过上限

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/奉献.md:1-3。

代码位置：nrc_core/engine/handlers_field.py:22（截至55的函数/分支），消费者位置见下文。

对象：devotion_grant_random/on_hit及指定技能。

最小输入步骤：调用probe.py中的`_h_devotion_grant_random_capped、_h_devotion_on_hit_capped、devotion_all_full、devotion_explicit_cap_*`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：随机飞断5层时仍候选五种并选中飞断，实际总层数不变；应保证从未满四种中增加1。指定飞断5→6、其他10→11，超过规则上限。全满仍进行无效随机选择。

影响：devotion_grant_random/on_hit及指定技能的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I02 折射按系别去重且排除本技能，丢失独立效果

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/折射效果.md:1。

代码位置：nrc_core/engine/handlers_field.py:58（截至67的函数/分支），消费者位置见下文。

对象：技能折射。

最小输入步骤：调用probe.py中的`refraction_duplicate_fire、refraction_LIGHT以及其余17类型case`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：携带折射（光）、火1、火2，预期魔攻+30%、灼烧8；实际魔攻0、灼烧4。set把两个同系技能折为一种，skill is not ctx.skill排除自身；仅另携光技能时才+30%。

影响：技能折射的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I03 折射幻系写入星陨状态而非星陨印记

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/折射效果.md:19。

代码位置：nrc_core/engine/handlers_field.py:99（截至101的函数/分支），消费者位置见下文。

对象：技能折射携幻技能。

最小输入步骤：调用probe.py中的`refraction_PSYCHIC`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：预期敌方场地meteor_mark+1；实际target.meteor_stacks=1、marks_b={}。两者为完全不同机制（状态倒计时与印记受攻击触发）。

影响：技能折射携幻技能的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I04 折射漏火毒同系免疫，地系固定减速误作比例

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/折射效果.md:1,7,4,12；data/wiki/game_descriptions.csv:2-3。

代码位置：nrc_core/engine/handlers_field.py:89（截至119的函数/分支），消费者位置见下文。

对象：折射火/毒/地。

最小输入步骤：调用probe.py中的`refraction_type_immunity_FIRE、POISON、ICE；refraction_GROUND`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：火系目标仍得4灼烧，毒系目标仍得2中毒；原文同系免疫。冰通过add_freeze_stacks检查，独立对照确实保持0。地对速度200的目标写speed_down=.4，后续变成除1.4的比例，而应固定-40。

影响：折射火/毒/地的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I05 契约前三种球把速度百分比当固定点数，淘沙球也误用比例

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/契约的形状.md:2-4,12。

代码位置：nrc_core/engine/handlers_field.py:174（截至187的函数/分支），消费者位置见下文。

对象：契约的形状：普通/高级/国王/淘沙球。

最小输入步骤：调用probe.py中的`contract_普通咕噜球、contract_高级咕噜球、contract_国王球、contract_淘沙球`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：基础速度200，普通球应+5%=10而实际+5（speed_up=.025）；高级应+20实+10，国王应+30实+15。淘沙原文-40却写speed_down=.4。

影响：契约的形状：普通/高级/国王/淘沙球的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I06 柔软球单效果错误复用常规球整包，9个分支效果超额或目标错误

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/契约的形状.md:14-32。

代码位置：nrc_core/engine/handlers_field.py:164（截至239的函数/分支），消费者位置见下文。

对象：柔软咕噜球18候选。

最小输入步骤：调用probe.py中的`soft_*全部18case`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：逐一固定候选18种：skill_power额外敌双攻-30%；heal额外己魔攻40%；slow_combo额外敌物防-40%且速度单位错；speed额外敌中毒；def应敌物防-40%却自己双防30%并敌星陨印记；atk额外敌魔防-40%；combo额外全技能耗-1；freeze额外4灼烧；energy额外30%吸血。其余9候选的单效果与原文匹配。

影响：柔软咕噜球18候选的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I07 稀兽花宝只实现萌血脉，17分支缺失且入口固定萌

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/稀兽花宝.md:1-18。

代码位置：nrc_core/engine/handlers_field.py:244（截至250的函数/分支），消费者位置见下文。

对象：稀兽花宝全部血脉。

最小输入步骤：调用probe.py中的`bloodline_*全部18case；跨模块搜索resolved_bloodline_type`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：18类型逐一传element，只有萌使敌双攻减60%，其余17均零效果；effect_data.py固定element=萌，既不读取resolved_bloodline_type也不按实际血脉分支。普通应技能威力+40等全部未实现。

影响：稀兽花宝全部血脉的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I08 解除或转移萌化只清层数，不恢复形态属性

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/wiki/game_descriptions.csv:7；反弹技能原文。

代码位置：nrc_core/engine/handlers_field.py:322（截至336的函数/分支），消费者位置见下文。

对象：反弹/逆向演化及CUTE_CLEAR_SELF接口。

最小输入步骤：调用probe.py中的`_h_cute_transfer、_h_cute_clear_self`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：A由1000HP/200速退化为幼1（900HP/180速），转移后cute_stacks=0但仍幼1、900/180；B正确进入自身幼1。预期解除该退化效果后恢复基础形态数值；恢复生命比例等细节另Q02。

影响：反弹/逆向演化及CUTE_CLEAR_SELF接口的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I09 萌化覆盖基础速度导致永久速度增益下次退化丢失

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：示弱原文“速度永久+130”；data/wiki/game_descriptions.csv:7。

代码位置：nrc_core/engine/handlers_field.py:264（截至277的函数/分支），消费者位置见下文。

对象：示弱后再次萌化。

最小输入步骤：调用probe.py中的`cute_permanent_speed_next_gain`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：先退化、以参数130获得永久速度后user.speed=290，下一次退化直接覆盖为140，永久+130完全丢失；应新形态基础140再保留130=270。参数默认150陈旧另归T06-I02。

影响：示弱后再次萌化的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I10 月光合奏把本次连击数永久写回技能，重复使用累加

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：月光合奏原文“本次技能连击数+1”。

代码位置：nrc_core/engine/handlers_field.py:384（截至391的函数/分支），消费者位置见下文。

对象：月光合奏。

最小输入步骤：调用probe.py中的`cute_team_power_twice`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：敌1层萌化，总层数始终1，本技能基础1连击；调用两次应每次2连击、基础保持1。实际ctx.skill.hit_count依次2、3，脱离本次修正生命周期。

影响：月光合奏的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I11 化茧未免疫致命伤害、主动降为1生命且缺2次上限

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：化茧原文“获得1层萌化，并免疫此次伤害（最多触发2次）”。

代码位置：nrc_core/engine/handlers_field.py:395（截至403的函数/分支），消费者位置见下文。

对象：化茧。

最小输入步骤：调用probe.py中的`cute_lethal_once、cute_lethal_three_calls、cute_lethal_consumer；executor.py:463,543及battle.py:2097`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：A500/1000HP面对600伤：原语把HP改1并写context.blocked_lethal；execute_ability返回独立result未带flag，battle读result未阻止扣600，实际HP0力竭。handler连续3次仍触发萌化3层，没有次数限制；即使修传递也会错误由500降1。

影响：化茧的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I12 传动扩展标志写入后无消费者

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：data/部分规则详解/传动机制.md:3-9；翼轴/机械变式原文。

代码位置：nrc_core/engine/handlers_field.py:122（截至139的函数/分支），消费者位置见下文。

对象：翼轴、机械变式。

最小输入步骤：调用probe.py中的`drive_flags、drive_slot_outside；rg全core两个字段只有本文件写入`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：extra_drives与drive_on_position_change_reduce只在此写入，无核心读取；翼轴同时只设skill.agility=True，现迅捷入口不识别。回合开始移位缺失根因由T07-I05主责，动态迅捷由T07-I03主责，此处只补消费者证据，不重复计算。

影响：翼轴、机械变式的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。

## T10-I13 系统发育在回合消费者中向每只场下精灵复制全额收益

严重度：P1；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。

规则依据/原文行号：系统发育原文“等量…随机分配给场下的精灵”。

代码位置：nrc_core/engine/handlers_field.py:155（截至157的函数/分支），消费者位置见下文。

对象：系统发育。

最小输入步骤：调用probe.py中的`share_gains_consumer；battle.py:1213-1234、1362/1383；handlers_skill.py:195/207`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。

预期与实际：A本次获100生命，两个场下初始各500；_apply_share_gains让每只都600，总增200。原文等量总收益只应100并随机分配。HEAL_HP/ENERGY原语另有随机分配调用，完整回合再调用该函数可重复。

影响：系统发育的规则结果，不能据接口无异常或技能能执行而认为已支持。

证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。
