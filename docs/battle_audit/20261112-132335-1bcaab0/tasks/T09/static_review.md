# T09 逐函数静态检查范围

结论仅对应所述协议/规则；原文子句全部拆分见clause_review.csv。所有函数全文已读；分支仅静态审阅，动态运行范围见probe。

## _h_ability_compute（31-284）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I01未知action静默忽略；I09充分燃烧4%tick；子action逐项列于static_review，借用/取念/复写具体子句需逐对象补证；不把所有action判定相同正确性。

当前配置：“国王”的威严:ON_BATTLE_START、“国王”的威严:ON_ENTER、不移:ON_BATTLE_START、不移:ON_ENTER、冰钻:ON_BATTLE_START、冰钻:ON_ENTER、冻土:ON_BATTLE_START、冻土:ON_ENTER、勇敢:ON_BATTLE_START、勇敢:ON_ENTER、快锤:ON_BATTLE_START、快锤:ON_ENTER、挺起胸脯:ON_BATTLE_START、挺起胸脯:ON_ENTER、暴食:ON_BATTLE_START、暴食:ON_ENTER、水翼飞升:ON_ENTER、溶解扩散:ON_BATTLE_START、王子的诺言:PASSIVE、盲从:ON_TURN_START、飓风:ON_BATTLE_START

- 条件 `action == 'multiple_borrow'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action in {'magic_hat', 'sleep_context', 'context_time_buff', 'autumn_harvest'}`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'prince_promise'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `previous is not None`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'count_poison_skills'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not hasattr(pokemon, 'ability_state')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'modify_matching_skills'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'shared_wing_skills'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'grant_first_skill_agility'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `p.name == pokemon.name`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `has_type(p, Type.FLYING)`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `s.name in shared`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `pokemon.skills`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'first_strike_power_bonus'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `getattr(s, 'effects', None)`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `getattr(first_skill, 'effects', None) and isinstance(first_skill.effects, list)`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not hasattr(pokemon, 'ability_state')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'first_strike_hit_bonus'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `s.name in my_skills`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not any((e.type == E.AGILITY for e in _iter_flat_tags_static(s.effects)))`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not has_agility`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not hasattr(pokemon, 'ability_state')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'auto_switch_on_zero_energy'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `isinstance(s.effects[0], SkillEffect)`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `isinstance(first_skill.effects[0], SkillEffect)`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not hasattr(pokemon, 'ability_state')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'auto_switch_every_turn'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not hasattr(pokemon, 'ability_state')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'swap_ally_on_zero_energy'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `se.timing == SkillTiming.ON_USE`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `se.timing == SkillTiming.ON_USE`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not hasattr(pokemon, 'ability_state')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'swap_hp_ratio'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `pokemon.hp > 0 and target.hp > 0`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'swap_buffs'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'swap_skills'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'borrow_ally_skill'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `ally_skills`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'copy_enemy_skill'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `i != current_idx and (not p.is_fainted)`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not pokemon.ability_state.get('multiple_borrow')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `enemy_skills`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'copy_random_skill'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `pokemon.ability_state.get('multiple_borrow')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not p.is_fainted`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not pokemon.ability_state.get('multiple_borrow')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `candidates`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'double_enemy_burn_and_tick'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `chosen.skill_type != Type.PSYCHIC`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `pokemon.ability_state.get('multiple_borrow')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `not pokemon.ability_state.get('multiple_borrow')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `target.burn_stacks > 0`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'double_enemy_debuffs'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `chosen.skill_type != Type.PSYCHIC`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `chosen is None`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `pokemon.ability_state.get('multiple_borrow')`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `target.current_hp <= 0`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'grant_random_devotion'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `replacement.skill_type != Type.PSYCHIC`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'cast_all_normal_skills_double_cost'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
- 条件 `action == 'anti_heal'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。
## _h_ability_increment_counter（288-293）

规则存疑；data/README.md:22-35。给团队counter_count再加1；counter入口本已加1，身经百练触发是否故意额外计数需Q01，不因handler存在通过。

当前配置：身经百练:ON_ALLY_COUNTER

## _h_transfer_mods（297-312）

规则存疑；data/状态分类.md:2-6。优先_snapshot_mods否则裸字段；仅十个属性，不含复合状态/技能修正，洁癖传递范围需按已授权原文补执行边界验证；与调用处离场先清理有关。

当前配置：洁癖:ON_LEAVE

## _h_burn_no_decay（316-318）

通过；data/wiki/game_descriptions.csv:3。仅验证协议：result.burn_no_decay在battle.py:788-797收集，停止衰减/增长由外层执行；不判煤渣草特殊增长规则数值。

当前配置：煤渣草:PASSIVE

## _h_power_multiplier_buff（322-324）

规则存疑；data/伤害数值计算.md:16。独立乘法层写Pokemon.power_multiplier且DamageCalculator读取、下场清1；当前无特性配置，调用次数与持续期需原文。

当前配置：无特性配置，保留实现缺口审查

## _h_threat_speed_buff（328-341）

规则存疑；data/README.md:22-35。调用_has_ko_threat读取敌技能，叠speed_up并标记；清理固定减0.5，若speed参数非0.5不对称；条件威胁是否含应对及动态能耗需回合组。

当前配置：哨兵:ON_TURN_START、预警:ON_TURN_START

## _h_counter_accumulate_transform（345-375）

规则存疑；data/README.md:22-35。防御/状态/攻击分类过滤；同回合guard_counter_turn只计一次；可_defer_transform；三特性共用guard queen目标是否都成立需按已授权原文补执行边界验证，缺skill时跳过分类。

当前配置：保卫:ON_COUNTER_SUCCESS、好象坏象:ON_COUNTER_SUCCESS、腾挪:ON_COUNTER_SUCCESS

## _h_delayed_revive（379-382）

规则存疑；data/README.md:22-35。写undying_revive_in，battle.py:270递减并满HP能复活；重复力竭处理重置计时与力竭当回合算第1回合需Q02。

当前配置：不朽:ON_FAINT

## _h_copy_switch_state（386-394）

规则存疑；data/状态分类.md:2-6。仅snapshot与switched_in都存在才调用_transfer_pokemon_state；当前snapshot真值与字段完整性需换人组；引用传递不改离场对象。

当前配置：贪婪:ON_ENEMY_SWITCH

## _h_cost_invert（398-400）

通过；data/状态分类.md:2-6。只设置布尔标记，helpers._adjust_cost_delta按反转/翻倍消费；结论限协议，不判断当前标记首次安装时点。

当前配置：对流:PASSIVE

## _h_mirror_enemy_buffs（404-430）

确认缺陷；data/wiki/spirits.csv:30（用户授权特性原文）；data/wiki/game_descriptions.csv:13。I10：复制敌增益却额外能量取max；增益范围明确含吸血/连击/技能威力和降耗而未复制。已有自身增益max还是叠加仍需Q03；双公平鸽监听与复合特性分类待复演。。

当前配置：衡量:ON_ENTER

## _h_counter_success_double_damage（434-437）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：只写double_damage_next，全核心无读取，下一攻击不翻倍且标记不消费。

当前配置：圣火骑士:ON_COUNTER_SUCCESS

## _h_counter_success_buff_permanent（441-445）

规则存疑；data/状态分类.md:2-6。转_apply_ability_buff复合状态；on_switch_out清除compound_statuses，与“永久”是否限站场需原文。

当前配置：指挥家:ON_COUNTER_SUCCESS

## _h_counter_success_power_bonus（449-454）

规则存疑；data/状态分类.md:2-6。skill_power_bonus+=delta有消费；下场清零，永久跨离场范围待Q01。

当前配置：斗技:ON_COUNTER_SUCCESS

## _h_counter_success_cost_reduce（458-464）

规则存疑；data/状态分类.md:2-6。技能逐项永久减delta封底0；绕过_adjust_cost_delta的反转/翻倍；特性共存/复制情况下规则待确认。

当前配置：思维之盾:ON_COUNTER_SUCCESS

## _h_counter_success_speed_priority（468-472）

规则存疑；data/wiki/game_descriptions.csv:21。写priority_stage，有行动顺序消费；原文“速度+1”和技能先手层级是否同义需Q01。

当前配置：野性感官:ON_COUNTER_SUCCESS

## _h_first_strike_power_bonus（476-484）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：只把power_multiplier写ctx.result；PASSIVE在回合末ctx无skill/is_first，攻击入口只BEFORE_ATTACK，正常伤害不会读该临时key。

当前配置：破空:PASSIVE、顺风:PASSIVE

## _h_first_strike_hit_count（488-496）

规则存疑；data/README.md:22-35。PASSIVE无skill/is_first默认不触发；若人工调用则永久改skill.hit_count且不恢复；配置与阶段错位，同I04消费者问题。

当前配置：咔咔冲刺:PASSIVE

## _h_first_strike_agility（500-502）

确认缺陷；data/wiki/game_descriptions.csv:6。I04：写first_skill_agility无消费者；另一compute action有实际插AGILITY，但本E未委派。

当前配置：起飞加速:ON_ENTER

## _h_auto_switch_on_zero_energy（506-509）

确认缺陷；data/wiki/game_descriptions.csv:4。I05：前者写Pokemon.force_switch，后者auto_switch_eot；消费者读auto_switch_zero_energy/every_turn，键不匹配。

当前配置：星地善良:ON_TURN_END、警惕:ON_TURN_END

## _h_auto_switch_after_action（513-516）

确认缺陷；data/wiki/game_descriptions.csv:4。I05：前者写Pokemon.force_switch，后者auto_switch_eot；消费者读auto_switch_zero_energy/every_turn，键不匹配。

当前配置：奔波命:ON_TURN_END、防过载保护:ON_TURN_END

## _h_team_synergy_bug_swarm_attack（520-533）

确认缺陷；data/wiki/spirits.csv:158,2（用户授权特性原文）；data/状态分类.md:2-6。I11/T06-I11协同：原文入场攻防速+15%/+10%，实现PASSIVE且仅双攻，不含双防和速度；队伍存活过滤另需具体边界，不因handler存在通过。。

当前配置：虫群突袭:PASSIVE

## _h_team_synergy_bug_swarm_inspire（537-550）

确认缺陷；data/wiki/spirits.csv:158,2（用户授权特性原文）；data/状态分类.md:2-6。I11/T06-I11协同：原文入场攻防速+15%/+10%，实现PASSIVE且仅双攻，不含双防和速度；队伍存活过滤另需具体边界，不因handler存在通过。。

当前配置：虫群鼓舞:PASSIVE

## _h_team_synergy_brave_if_bugs（554-564）

规则存疑；data/状态分类.md:2-6。只统计其他存活虫系，buff仅双攻。原文线索要求攻防速且入场，配置PASSIVE每回合末触发会累加复合状态；需按Q01具体边界补证，不因当前可达错配称未上线。

当前配置：壮胆:PASSIVE

## _h_team_synergy_bug_kill_aff（568-572）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：写aff_bonus没有核心消费；亲密度模型与规则字段未实现，不能因未引用就标未上线。

当前配置：振奋虫心:ON_KILL

## _h_stat_scale_defense_per_energy（576-584）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：写ctx.stat_multiplier无消费；全神贯注action_count没有递增路径；动态属性不会进calculation_modifier。

当前配置：囤积:PASSIVE

## _h_stat_scale_hits_per_hp_lost（588-598）

规则存疑；data/wiki/game_descriptions.csv:36。按当前缺血四分位计算后+=hit_count_mod；每回合重复PASSIVE会重复累加而非当前快照替换；Q01需确认累计失去还是当前缺失。

当前配置：嫁祸:PASSIVE

## _h_stat_scale_attack_decay（602-613）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：写ctx.stat_multiplier无消费；全神贯注action_count没有递增路径；动态属性不会进calculation_modifier。

当前配置：全神贯注:PASSIVE

## _h_stat_scale_meteor_marks_per_turn（617-621）

通过；data/状态分类.md:2-6。仅协议验证：写meteor_mark_add固定值而非+=；battle.py:928读并每回合给敌阵营，不对“吸积盘”数值/归属原文作通过。

当前配置：吸积盘:ON_TURN_END

## _h_mark_power_per_meteor（625-636）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：只把power_multiplier写ctx.result；PASSIVE在回合末ctx无skill/is_first，攻击入口只BEFORE_ATTACK，正常伤害不会读该临时key。

当前配置：坠星:PASSIVE、观星:PASSIVE

## _h_mark_freeze_to_meteor（640-643）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：freeze_becomes_meteor标记无消费者；add_freeze_stacks无转换分支。

当前配置：月牙雪糕:ON_USE_SKILL

## _h_mark_stack_no_replace（647-650）

通过；data/状态分类.md:2-6。仅来源隔离协议：mark_stack_additive由handlers_skill._h_mark_generic读取，独立bard_mark来源槽；效果是否符合所有印记特例不在本结论。

当前配置：吟游之弦:PASSIVE

## _h_mark_stack_debuffs（654-658）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I03：debuff_stack_bonus只写不读；不能触发灰色肖像攻击后已有减益+3。

当前配置：灰色肖像:ON_ENTER

## _h_damage_mod_non_stab（662-671）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I02：Skill.type/Pokemon.type1/type2与模型不符，.types模块不存在；PASSIVE无skill早退且未安装可消费标记，传skill运行报错。

当前配置：涂鸦:PASSIVE

## _h_damage_mod_non_light（675-685）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I02：Skill.type/Pokemon.type1/type2与模型不符，.types模块不存在；PASSIVE无skill早退且未安装可消费标记，传skill运行报错。

当前配置：夺目:PASSIVE、目空:PASSIVE

## _h_damage_mod_non_weakness（689-700）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I02：Skill.type/Pokemon.type1/type2与模型不符，.types模块不存在；PASSIVE无skill早退且未安装可消费标记，传skill运行报错。

当前配置：绒粉星光:PASSIVE

## _h_damage_mod_pollutant_blood（704-711）

通过；data/伤害数值计算.md:8-16。仅攻击修正协议：BEFORE_ATTACK读目标blood_type或lab_metadata血脉，写_power_mult；_h_damage独立attack_context消费，未改持久skill.power。额外倍率具体数值需补该数值条件的独立执行验证。

当前配置：天通地明:BEFORE_ATTACK

## _h_damage_mod_leader_blood（715-722）

通过；data/伤害数值计算.md:8-16。仅攻击修正协议：BEFORE_ATTACK读目标blood_type或lab_metadata血脉，写_power_mult；_h_damage独立attack_context消费，未改持久skill.power。额外倍率具体数值需补该数值条件的独立执行验证。

当前配置：月光审判:BEFORE_ATTACK

## _h_damage_resist_same_type（726-735）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I02：Skill.type/Pokemon.type1/type2与模型不符，.types模块不存在；PASSIVE无skill早退且未安装可消费标记，传skill运行报错。

当前配置：偏振:PASSIVE

## _h_heal_per_turn（739-744）

通过；data/README.md:22-35。仅协议：固定覆盖heal_per_turn_pct，回合末读取且封顶；不是重复叠加，回血死亡门槛在外层。

当前配置：生长:ON_TURN_END

## _h_heal_on_grass_skill（748-762）

规则存疑；data/README.md:22-35。回血封顶、anti_heal分支扣血；未将anti_heal_multiplier数值乘入，也未触发frostbite判死，系统发育分享钩子未在此调用；专名数值需逐对象执行补证。

当前配置：深层氧循环:ON_USE_SKILL

## _h_skill_cost_reduction_type（766-777）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I02：Enum SkillCategory.DEFENSE与字符串防御比较永远不等；即便手工字符串也只写context.cost_reduction，正常能耗路径不读取。

当前配置：缩壳:PASSIVE

## _h_poison_stat_debuff（781-788）

确认缺陷；data/wiki/spirits.csv:85（用户授权特性原文）。I11/T06-I11：原文成功施毒时敌物攻-40%速度-40，配置ON_USE且handler要求已有毒，然后降低魔攻魔防；明确触发与属性差异，无需用户重复授权。。

当前配置：毒牙:ON_USE_SKILL

## _h_poison_on_skill_apply（792-803）

确认缺陷；data/wiki/spirits.csv:115（用户授权特性原文）；data/wiki/game_descriptions.csv:2。I11/T06-I11：原文能耗<=1，配置阈值5且handler按基础cost<5，成本2/3/4错误施4毒；直接+=亦未检毒系免疫。基础/实际成本边界仍可具体提问。。

当前配置：毒腺:ON_USE_SKILL

## _h_freeze_immunity_and_buff（807-813）

通过；data/wiki/game_descriptions.csv:5。仅冻结免疫协议：add_freeze_stacks先检查freeze_immune；双防写复合状态并计算时消费。具体授予百分比与换人保留需正式来源。

当前配置：吉利丁片:ON_ENTER

## _h_extra_freeze_on_freeze（817-820）

通过；data/wiki/game_descriptions.csv:5。pass是固定规则标记并非空缺：models.add_freeze_stacks按source PASSIVE定义读取extra，每次成功施加只加一次。

当前配置：加个雪球:PASSIVE

## _h_extra_consumption_on_freeze（824-832）

通过；data/wiki/game_descriptions.csv:5。仅ON_INFLICT_FREEZE且added>0才调敌技能成本；add_freeze_stacks免疫/力竭/非正数先返回；probe冻结2层敌成本2→3，控制标志隔离。

当前配置：捉迷藏:ON_INFLICT_FREEZE

## _h_faint_no_mp_loss（836-838）

规则存疑；data/README.md:22-35。写faint_no_mp_loss，外层MP处理需回合组；不只凭标记存在判规则通过。

当前配置：诈死:PASSIVE

## _h_on_skill_element_buff（842-846）

规则存疑；data/README.md:22-35。元素过滤依靠AbilityEffect.filter；handler单独不检element。毒+=未免疫；能量扣除封底0；buff转复合状态，具体特性原文见clause_review。

当前配置：助燃:ON_USE_SKILL、爆燃:ON_USE_SKILL

## _h_on_skill_element_poison（850-853）

规则存疑；data/README.md:22-35。元素过滤依靠AbilityEffect.filter；handler单独不检element。毒+=未免疫；能量扣除封底0；buff转复合状态，具体特性原文见clause_review。

当前配置：生物碱:ON_USE_SKILL

## _h_on_skill_element_cost_reduce（857-861）

规则存疑；data/状态分类.md:2-6。逐技能过滤和_adjust_cost_delta已静态核对；持续/重复授予应否重置需原文；global范围dispatch单独来源记录，特定系保持私有。

当前配置：浪潮:ON_USE_SKILL、浸润:ON_USE_SKILL

## _h_on_skill_element_heal（865-873）

规则存疑；data/README.md:22-35。回血封顶、anti_heal分支扣血；未将anti_heal_multiplier数值乘入，也未触发frostbite判死，系统发育分享钩子未在此调用；专名数值需逐对象执行补证。

当前配置：氧循环:ON_USE_SKILL

## _h_on_skill_element_enemy_energy（877-880）

规则存疑；data/README.md:22-35。元素过滤依靠AbilityEffect.filter；handler单独不检element。毒+=未免疫；能量扣除封底0；buff转复合状态，具体特性原文见clause_review。

当前配置：碰瓷:ON_USE_SKILL

## _h_carry_skill_power_bonus（884-892）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：分别写carry_skill_power_bonus/low_cost_skill_power_bonus但全核心无消费；现配置可能已迁移compute，仍属实现缺口，reachability另列。

当前配置：无特性配置，保留实现缺口审查

## _h_carry_skill_cost_reduce（896-912）

规则存疑；data/状态分类.md:2-6。逐技能过滤和_adjust_cost_delta已静态核对；持续/重复授予应否重置需原文；global范围dispatch单独来源记录，特定系保持私有。

当前配置：无特性配置，保留实现缺口审查

## _h_carry_element_count_buff（916-930）

规则存疑；data/状态分类.md:2-6。逐技能过滤和_adjust_cost_delta已静态核对；持续/重复授予应否重置需原文；global范围dispatch单独来源记录，特定系保持私有。

当前配置：消波块:ON_ENTER

## _h_on_kill_buff（934-938）

规则存疑；data/README.md:22-35。ON_KILL入口保证击败后，buff按stacks转复合状态；受反伤/自毁力竭是否还触发与永久范围需原文。

当前配置：恶魔的晚宴:ON_KILL

## _h_recoil_damage（942-951）

确认缺陷；data/wiki/spirits.csv:423（用户授权特性原文）；data/伤害数值计算.md:6-10。I12：刺肤原文50威力物理伤害，handler把power直接当HP扣且category不读；按攻防计算这一点无歧义。未说明的伤害系别/本系归属仅保留具体Q04，不再把威力与固定HP之别当待授权。。

当前配置：刺肤:ON_TAKE_HIT

## _h_entry_buff（955-963）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：entry_buff_duration/keys只写不消费；若配置要求持续1回合不会失效，当前无配置，reachability单列。

当前配置：无特性配置，保留实现缺口审查

## _h_on_enter_grant_drain（967-970）

规则存疑；data/wiki/game_descriptions.csv:29。+=life_drain_mod，普通执行器消费回血；下场清0，重复入场与特性层分类需原文。

当前配置：渴求:ON_ENTER

## _h_enemy_all_cost_up（974-978）

规则存疑；data/状态分类.md:2-6。入场直接永久改敌技能，没有在自己离场时回滚；注释在场与实现持续不一致，需Q01。

当前配置：冰封:ON_ENTER

## _h_entry_freeze_extra（982-990）

规则存疑；data/wiki/game_descriptions.csv:5。调用统一冻结入口正确，额外能耗不依赖施加成功；即使免疫冻结也加成本，是否应如此需抓到你了原文。

当前配置：抓到你了:ON_ENTER

## _h_leave_heal_ally（994-997）

规则存疑；data/README.md:22-35。仅放result由主动换人接收；脱离/死亡替换是否一致须切换组；回血封顶在外层，不单凭handler存在通过。

当前配置：茶多酚:ON_LEAVE

## _h_leave_buff_ally（1001-1004）

规则存疑；data/README.md:22-35。仅放result由主动换人接收；脱离/死亡替换是否一致须切换组；回血封顶在外层，不单凭handler存在通过。

当前配置：美拉德反应:ON_LEAVE

## _h_leave_energy_refill（1008-1011）

通过；data/README.md:22-35。仅能量增益协议：调用gain_energy支持energy_no_cap和正常10上限；当前缺配置不是未上线证明，数值专名待原文。

当前配置：无特性配置，保留实现缺口审查

## _h_energy_regen_per_turn（1015-1018）

通过；data/README.md:22-35。仅能量增益协议：调用gain_energy支持energy_no_cap和正常10上限；当前缺配置不是未上线证明，数值专名待原文。

当前配置：无特性配置，保留实现缺口审查

## _h_steal_all_enemy_energy（1022-1030）

规则存疑；data/状态分类.md:2-6。逐存活敌方扣min能量并gain_energy，amount非负由配置保证；未上场者能量变化私有战报由平台负责；回能叠加封顶后是否继续扣敌需原文。

当前配置：大捞一笔:ON_TURN_END、毒蘑菇:ON_TURN_END

## _h_enemy_switch_debuff（1034-1039）

规则存疑；data/README.md:22-35。energy_loss与poison都可执行；直接poison_stacks+=不检毒免疫；调用目标需确认switched_in，当前无E配置不能判未上线。

当前配置：无特性配置，保留实现缺口审查

## _h_enemy_switch_self_cost_reduce（1043-1047）

规则存疑；data/状态分类.md:2-6。逐技能过滤和_adjust_cost_delta已静态核对；持续/重复授予应否重置需原文；global范围dispatch单独来源记录，特定系保持私有。

当前配置：珊瑚骨:ON_ENEMY_SWITCH

## _h_on_interrupt_cooldown（1051-1054）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：仅写interrupt_cooldown_turns无消费者，且配置在COUNTER_SUCCESS而非确认打断成功，未把敌被打断槽设冷却。

当前配置：威慑:ON_COUNTER_SUCCESS

## _h_low_cost_skill_power_bonus（1058-1063）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I04：分别写carry_skill_power_bonus/low_cost_skill_power_bonus但全核心无消费；现配置可能已迁移compute，仍属实现缺口，reachability另列。

当前配置：无特性配置，保留实现缺口审查

## _h_energy_cost_condition_buff（1067-1075）

规则存疑；data/状态分类.md:2-6。使用_base_energy_cost等于配置cost判断，忽略实际cost和permanent参数；buff复合状态；正确依据基础或实际需Q01。

当前配置：三鼓作气:ON_USE_SKILL、鼓气:ON_USE_SKILL

## _h_enemy_tech_total_power（1079-1083）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I03：写bonus_pct_per_cost，DamageCalculator读bonus_pct_per_layer；现变形活画敌10层增益伤害90不变，速度仅展示字符串无计算。

当前配置：变形活画:PASSIVE

## _h_half_meteor_full_damage（1087-1089）

规则存疑；data/wiki/game_descriptions.csv:34。标记读取于meteor_stacks引爆而非meteor_mark触发；实际用一半层数算威力而非满伤，取ceil/floor和对象需Q01。

当前配置：守望星:PASSIVE

## _h_energy_drain_by_cost_diff（1093-1102）

规则存疑；data/README.md:22-35。last_skill_cost差>0才扣能；缺动作本回合时保留上回合cost，是否重置需回合组。

当前配置：石天平:ON_TURN_END

## _h_entry_buff_per_skill_count（1106-1182）

规则存疑；data/状态分类.md:2-6。count_keys优先、<=0早退；status_key直接存复合状态；成本累计、power从共享_ability_base_power绝对重算；grant_agility只布尔与T07-I03同缺口；计数重入重复与全局增益归属需按已授权原文补执行边界验证。

当前配置：定向精炼:ON_ENTER、拨浪鼓:ON_ENTER、水翼推进:ON_ENTER、水翼飞升:ON_ENTER、渗透:ON_ENTER、蒸汽膨胀:ON_ENTER

## _h_hit_count_per_poison（1186-1190）

通过；data/wiki/game_descriptions.csv:36。仅连击标记协议：_h_damage读毒层和任一方fixed_hit_count_all；命中数算法与状态/1连击边界不在此结论。

当前配置：侵蚀:PASSIVE

## _h_first_action_hit_bonus（1194-1205）

通过；data/README.md:22-35。入场无skill设flag，使用后清；battle._skill_use_repetitions及runtime合法动作均读flag，额外次数与能耗同步；不是只改伤害连击。

当前配置：噼啪！:ON_ENTER、噼啪！:ON_USE_SKILL

## _h_fixed_hit_count_all（1209-1211）

通过；data/wiki/game_descriptions.csv:36。仅连击标记协议：_h_damage读毒层和任一方fixed_hit_count_all；命中数算法与状态/1连击边界不在此结论。

当前配置：无差别过滤:PASSIVE

## _h_extra_poison_tick（1215-1217）

通过；data/wiki/game_descriptions.csv:2。标记由turn_end_effects在敌方中毒结算额外1次读取；固定True不会每回合累加；全流程状态致死由回合组。

当前配置：复方汤剂:ON_TURN_END

## _h_conditional_entry_buff_total_cost（1221-1227）

规则存疑；data/状态分类.md:2-6。基础cost总和严格<、MP严格==，check_enemy侧别正确；不满足不会清先前复合状态；条件是否每入场重新判断待原文。

当前配置：保守派:ON_ENTER

## _h_conditional_entry_buff_mp（1231-1242）

规则存疑；data/状态分类.md:2-6。基础cost总和严格<、MP严格==，check_enemy侧别正确；不满足不会清先前复合状态；条件是否每入场重新判断待原文。

当前配置：图书守卫者:ON_ENTER、构装契约者:ON_ENTER

## _h_immune_zero_energy_attacker（1246-1248）

通过；data/README.md:22-35。仅免伤协议：_h_damage先查零能与_last_actual_cost<=阈值且仅攻击；没有增加临时技能修正。零能使用后判断时点/阈值原文归配置组。

当前配置：惊吓:PASSIVE

## _h_immune_low_cost_attack（1252-1254）

通过；data/README.md:22-35。仅免伤协议：_h_damage先查零能与_last_actual_cost<=阈值且仅攻击；没有增加临时技能修正。零能使用后判断时点/阈值原文归配置组。

当前配置：逐魂鸟:PASSIVE

## _h_entry_self_damage（1258-1263）

规则存疑；data/README.md:22-35。首次标志不会下场清；当前HP//2且至少1。奇数减半向下与冻结阈值即时致死缺规则需回合组。

当前配置：铃兰晚钟:ON_ENTER

## _h_specific_skill_power_bonus（1267-1276）

规则存疑；data/状态分类.md:2-6。只第一个同名技能，_ability_base_power共用后重算可能覆盖其他永久变化；相同技能多槽规则及跨入场永久范围待原文。

当前配置：共鸣:ON_ENTER

## _h_energy_no_cap（1280-1282）

通过；data/README.md:22-35。仅协议：gain_energy读energy_no_cap；battle/runtime成本合法性读hp_for_energy；不是空处理器。具体替代HP公式归能耗组。

当前配置：多人宿舍:ON_ENTER

## _h_hp_for_energy（1286-1288）

通过；data/README.md:22-35。仅协议：gain_energy读energy_no_cap；battle/runtime成本合法性读hp_for_energy；不是空处理器。具体替代HP公式归能耗组。

当前配置：石头大餐:ON_ENTER

## _h_shuffle_skills_reduce_last（1292-1301）

规则存疑；data/状态分类.md:2-6。随机明确来自盲拧原文线索，打乱skills原列表；第四槽减-_adjust_cost_delta(positive)和调整negative等价；cooldowns槽映射是否随技能移动待Q05。

当前配置：盲拧:ON_TURN_START

## _h_weather_conditional_buff（1305-1310）

规则存疑；data/状态分类.md:2-6。仅天气相等则复合buff新增层，不相等不撤旧层；配置ON_TURN_START重复累加，天气条件状态应快照还是累计需Q01。

当前配置：得寸进尺:ON_TURN_START

## _h_fainted_allies_buff（1314-1325）

规则存疑；data/状态分类.md:2-6。scope=all累加双方力竭数，其他值当allies；存一份复合状态并加stacks，重复入场/计数改变会保留旧层定义；需Q01。

当前配置：悲悯:ON_ENTER、悼亡:ON_ENTER

## _h_on_super_effective_buff（1329-1342）

确认缺陷；data/部分规则详解/最好的伙伴.md:3-7。I06：只检查skill系别克制，不检查伤害/攻击类型，状态技能也加完整层并回2能；正确完整存层但触发条件错误。

当前配置：最好的伙伴:ON_USE_SKILL

## _h_enemy_element_diversity_power（1346-1354）

规则存疑；data/状态分类.md:2-6。按敌携带技能种类计数+=全技能威力，ON_ENTER重入可重复叠；原文是否攻击时重算而非入场快照需Q01。

当前配置：血型吸引:ON_ENTER

## _h_kill_mp_penalty（1358-1375）

通过；data/README.md:22-35。仅时点协议：execute_ability写_ability_timing，ON_KILL扣对手/ON_FAINT扣己方，双侧封底0；额外基础MP的统一结算归回合组。

当前配置：付给恶魔的赎价:ON_FAINT、付给恶魔的赎价:ON_KILL

## _h_turn_end_repeat（1379-1382）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I07：PASSIVE重复执行使用+=累积固定授予；回合末每次调用不会清零，重复次数或迸发幅度无限增长。probe两次真实回合末repeat1→2。

当前配置：双向光速:PASSIVE

## _h_turn_end_skip（1386-1389）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I07：PASSIVE重复执行使用+=累积固定授予；回合末每次调用不会清零，重复次数或迸发幅度无限增长。probe两次真实回合末repeat1→2。

当前配置：陨落:PASSIVE

## _h_cost_change_double（1393-1395）

通过；data/状态分类.md:2-6。只设置布尔标记，helpers._adjust_cost_delta按反转/翻倍消费；结论限协议，不判断当前标记首次安装时点。

当前配置：倾轧:PASSIVE

## _h_noise_debuff（1399-1406）

规则存疑；data/状态分类.md:2-6。追加temporary_skill_cost_mods(filter attack,turns)供skill_energy_cost消费并回合末递减；amount未调对流/倾轧，持续3回合是否含当前回合待Q01。

当前配置：泛音列:ON_USE_SKILL

## _h_skill_slot_lock（1410-1413）

通过；data/README.md:22-35。仅合法动作协议：allowed_slots存列表，runtime读取允许槽；多次PASSIVE赋值不累计，不解析技能描述。

当前配置：宝剑王牌:PASSIVE、正位宝剑:PASSIVE

## _h_buff_extra_layers（1417-1420）

规则存疑；data/状态分类.md:2-6。固定赋值extra供_apply_buff/_apply_ability_buff读；复合层buff按乘数放大未必实际加层、全技能/生命吸取不统一，需营养液泡正式分类。

当前配置：营养液泡:PASSIVE

## _h_barrel_state（1424-1434）

通过；data/README.md:22-35。仅下一替换标记协议：按team写pending，主动切换接收barrel_active；DamageCalculator任一方木桶使eff=1，主动行动清除由回合组。

当前配置：木桶戏法:ON_LEAVE

## _h_burst_power_bonus（1438-1441）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I07：PASSIVE重复执行使用+=累积固定授予；回合末每次调用不会清零，重复次数或迸发幅度无限增长。probe两次真实回合末repeat1→2。

当前配置：电流刺激:PASSIVE

## _h_burst_enemy_cost_up（1445-1448）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I07：PASSIVE重复执行使用+=累积固定授予；回合末每次调用不会清零，重复次数或迸发幅度无限增长。probe两次真实回合末repeat1→2。

当前配置：超负荷:PASSIVE

## _h_burst_element_cost_reduce（1452-1457）

规则存疑；data/wiki/game_descriptions.csv:11。固定覆盖元素/减耗字典，battle迸发后退款；合法性预览和_last_actual_cost同步问题属能耗组，不单凭写flag通过。

当前配置：生物电:PASSIVE

## _h_burst_extend（1461-1464）

确认缺陷；AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError。I07：PASSIVE重复执行使用+=累积固定授予；回合末每次调用不会清零，重复次数或迸发幅度无限增长。probe两次真实回合末repeat1→2。

当前配置：连续负荷:PASSIVE
