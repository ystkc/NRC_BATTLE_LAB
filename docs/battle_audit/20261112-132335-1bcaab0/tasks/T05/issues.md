# T05 问题记录

10项中I07/I08为已知规则机制未实现且静默跳过，其他为确定偏差；I10仅诊断文档P2，游戏规则问题均P1。T04普通脱离暂停不在本任务重复编号。

## T05-I01 愿力动作按原首槽过滤且无法选择替换后不用

- 结论：确认缺陷；严重度：P1；主责协同：T05主责
- 规则依据/原文行号：data/部分规则详解/共鸣魔法.md:7-22
- 代码位置：nrc_core/runtime.py:319-337,346-357
- 最小输入步骤：能量3，原首槽耗8，携愿力；另用双技能完整状态枚举动作。
- 预期与实际：应可将首槽变为能耗2愿力，实际仅charge；原首槽合法时也仅允许使用首槽，无法配合charge或其他技能，违反即使未使用仍消耗次数与到期还原的子句。
- 影响范围：全部愿力与原槽耗能/冷却/多次使用交叉；共鸣后应重新计算合法动作。
- 证据：probe.py；probe_output.json:I01_willpower_legal `{"energy": 3, "original_cost": 8, "actual_keys": ["charge"], "expected": "应能用能耗2愿力首槽，但原技能先按8耗过滤，愿力动作消失"}`；probe_output.json:I01_unused_willpower `{"actual_keys": ["skill:slot=0", "skill:slot=1", "charge", "skill:slot=0|resonance=willpower"], "expected": "应允许愿力本回合替换但不使用愿力，详解明确即便未使用下回合也替换回"}`

## T05-I02 愿力还原按原主人固定首槽，交换后临时技能遗留

- 结论：确认缺陷；严重度：P1；主责协同：T05还原主责，T07技能交换协同
- 规则依据/原文行号：data/部分规则详解/共鸣魔法.md:14,18; data/wiki/skills.csv:523
- 代码位置：nrc_core/rules_support.py:166-174,186-188
- 最小输入步骤：A慢于B，A用愿力，B真实隐藏条款先交换双方整套技能。
- 预期与实际：回合结束B仍永久持有愿力冲击，A被覆盖回A原技能；至少临时愿力必须在下一回合消失。按交换语义预期A保留隐藏条款、B得到A原技能，但跨交换精确归属仍需确认，不影响当前遗留临时技能事实。
- 影响范围：愿力和技能交换/替换交叉；传动当前未实现移动，本证据不假设传动已运行。
- 证据：probe.py；probe_output.json:I02_restore_swap `{"actual_skills_a": ["A原技能"], "actual_skills_b": ["愿力冲击"], "expected_a": ["隐藏条款"], "expected_b": ["A原技能"]}`

## T05-I03 首领化更新六维和特性但未更新战斗属性

- 结论：确认缺陷；严重度：P1；主责协同：T05主责，T03数值公式另有I01
- 规则依据/原文行号：data/部分规则详解/共鸣魔法.md:24-36
- 代码位置：nrc_core/rules_support.py:115-137
- 最小输入步骤：已解析首领血脉A普通系，唯一目标record为火/龙，使用进化之力。
- 预期与实际：首领名称/六维/特性已变、原技能保留，但pokemon_type/pokemon_types仍normal，应跟随首领火龙战斗属性。血脉远古变更没有充分字段规则，另列questions。
- 影响范围：所有首领形态与基础形态属性不同的记录；克制、本系、免疫等计算仍按旧属性。
- 证据：probe.py；probe_output.json:I03_boss_types `{"actual_name": "首领", "actual_types": ["normal"], "expected_types": ["fire", "dragon"], "skills": ["审计"], "expected_skill": "审计", "hp": 469, "attack": 280, "bossified": true}`

## T05-I04 替补入场与连锁入场力竭不扣MP

- 结论：确认缺陷；严重度：P1；主责协同：T05补位主责，T04扣MP入口协同
- 规则依据/原文行号：data/README.md:30,35; nrc_core/models.py:604-606
- 代码位置：nrc_core/runtime.py:404-423,441-443,252-276
- 最小输入步骤：已死A已扣MP剩3，选择HP40替补，在荆刺1层下入场即死；另选抓到你了替补令B80HP获得冻结2层死亡。
- 预期与实际：本方再次力竭应MP3→2，实际仍3；敌方新力竭应MP4→3，实际仍4。虽然进入下一replacement阶段，整个补位流程没有调用扣MP/ON_FAINT结算；若继续替补，死亡者可永远不再被检查。
- 影响范围：入场印记伤害、入场攻击/冻结造成双方连锁死亡，可能逃过MP败北/复活触发。
- 证据：probe.py；probe_output.json:I04_entry_faint_mp `{"actual_phase": "replacement", "actual_players": [0], "actual_fainted": true, "actual_mp": 3, "expected_mp": 2, "next_legal": ["switch:index=2"]}`；probe_output.json:I04_enemy_entry_faint_mp `{"actual_fainted_b": true, "actual_mp_b": 4, "expected_mp_b": 3, "actual_phase": "replacement", "actual_players": [1]}`

## T05-I05 初始化、补位和下一回合准备在种子随机域之外

- 结论：确认缺陷；严重度：P1；主责协同：T05主责，T04 rng工具通过不外推调用方
- 规则依据/原文行号：nrc_core/README.md:公开入口/规则模块；rng.py作用域契约；data/README.md:19
- 代码位置：nrc_core/runtime.py:68-72,225-226,441-443,480
- 最小输入步骤：固定new_game seed77，用正式盲拧ON_TURN_START改变进程random种子1/2/3；固定advance seed78，用柔软球替补入场；并从同一会话advance后准备下一回合。
- 预期与实际：同对战seed应相同；实际盲拧顺序、柔软球随机效果随进程random改变。_isolated_rng定义未在这些入口使用，simulate_turn只包技能回合的内部。
- 影响范围：初始/替补/回合准备的全部随机机制；共鸣首领入场也在同一未包裹区域，具体随机特性可达性逐配置另核。
- 证据：probe.py；probe_output.json:I05_seed_new_game `{"fixed_seed": 77, "ambient_seeds": [1, 2, 3], "actual_orders": [["四", "一", "三", "二"], ["二", "三", "四", "一"], ["四", "一", "三", "二"]], "expected_equal": true}`；probe_output.json:I05_seed_replacement `{"fixed_seed": 78, "ambient_seeds": [1, 2, 3], "actual_balls": ["spatk", "heal", "poison"], "expected_equal": true}`；probe_output.json:I05_seed_next_turn `{"fixed_seed": 78, "actual_orders": [["四", "三", "二", "一"], ["一", "二", "四", "三"]], "expected_equal": true}`

## T05-I06 技能槽锁定未进入合法动作过滤

- 结论：确认缺陷；严重度：P1；主责协同：T05主责，T06配置协同
- 规则依据/原文行号：正位宝剑/宝剑王牌原文与effect_data SKILL_SLOT_LOCK；nrc_core/README.md:advance只接受合法动作
- 代码位置：nrc_core/runtime.py:319-337; nrc_core/battle.py:1626-1631
- 最小输入步骤：当前skill_slot_lock=[0]且携两个能量足技能，枚举合法动作。
- 预期与实际：slot1仍被列为可选，且附带光合组合动作；实际执行则静默改聚能。应不列锁定槽动作，或按明确协议展示聚能。
- 影响范围：正位宝剑/宝剑王牌；合法动作和真正执行不一致，影响用户/搜索。
- 证据：probe.py；probe_output.json:I06_slot_lock `{"actual_keys": ["skill:slot=0", "skill:slot=1", "charge", "switch:index=1", "skill:slot=0|resonance=solar_heal", "skill:slot=1|resonance=solar_heal", "charge|resonance=solar_heal"], "expected_no_slot1": true}`

## T05-I07 禁足机制未表示，流沙执行后仍可离场

- 结论：未实现；严重度：P1；主责协同：T05合法动作协同，T06技能原文生成/状态handler主责
- 规则依据/原文行号：GAME_RULE禁足；data/wiki/game_descriptions.csv:52; data/wiki/skills.csv:287,354
- 代码位置：nrc_core/runtime.py:333-337; nrc_core/effect_models.py/全core检索禁足机制缺失
- 最小输入步骤：使用真实流沙原文/硬编码效果，目标有健康替补，执行后读取状态和合法动作。
- 预期与实际：未获得禁足且可switch；原文禁止离场3回合。未实现也没有UnsupportedMechanicError，不能静默忽略。
- 影响范围：流沙、石锁及一切禁足来源；再次施加免疫与持续回合均缺。
- 证据：probe.py；probe_output.json:I07_ban_switch `{"actual_b_keys": ["skill:slot=0", "charge", "switch:index=1", "skill:slot=0|resonance=solar_heal", "charge|resonance=solar_heal"], "actual_b_state": {"_burst_pending": false}, "expected": "流沙施加禁足3回合后应禁止switch，或未实现时显式抛UnsupportedMechanicError"}`

## T05-I08 选择类仅保存选项字符串，两个分支效果未执行

- 结论：未实现；严重度：P1；主责协同：T05选择接口主责，T07/T06效果配置协同
- 规则依据/原文行号：data/部分规则详解/选择类技能.md:3-5; data/wiki/skills.csv:441
- 代码位置：nrc_core/runtime.py:323-330; nrc_core/rules_support.py:203; 全core selected_choice引用
- 最小输入步骤：真实补觉，两分支分别从HP500/能量3开始执行。
- 预期与实际：第0分支应HP750/能量1、第1分支HP500/能量9；实际都HP500/能量1，只有selected_choice字符串不同。全core没有读取selected_choice的效果分发，不应假装已支持。
- 影响范围：所有选择技能、加尔额外触发及选择计数；具体技能效果若另缺也不掩盖分支协议缺口。
- 证据：probe.py；probe_output.json:I08_choice `{"actual": [{"choice": 0, "hp": 500, "energy": 1, "selected": "自己回复25%生命"}, {"choice": 1, "hp": 500, "energy": 1, "selected": "回复8能量"}], "expected": "第0分支恢复25%生命即750HP/能量1；第1分支恢复8能量即500HP/能量9，不能只记录字符串"}`

## T05-I09 新对局未触发初始精灵入场特性

- 结论：确认缺陷；严重度：P1；主责协同：T05初始化主责，T01构建入口协同
- 规则依据/原文行号：data/README.md:22; data/wiki/spirits.csv 抓到你了原文；nrc_core/README.md new_game初始化
- 代码位置：nrc_core/runtime.py:211-227,279-283
- 最小输入步骤：完整状态A带正式抓到你了ON_ENTER配置，B完整，调用new_game。
- 预期与实际：应使B冻结2层、全技能耗+1；实际冻结0、耗1不变、entry_count0。new_game仅battle_start和turn_start，未发ON_ENTER；平台builder也无该事件调用。
- 影响范围：开局仅定义ON_ENTER的特性，以及初始入场计数与入场印记；中途导入既有战局不能重复触发，需区分初始化责任。
- 证据：probe.py；probe_output.json:I09_initial_enter `{"actual_enemy_freeze": 0, "actual_enemy_cost": 1, "expected_enemy_freeze": 2, "expected_enemy_cost": 2, "actual_entry_count": 0}`

## T05-I10 默认日志与环境变量行为不符README

- 结论：确认缺陷；严重度：P2；主责协同：T05诊断文档主责
- 规则依据/原文行号：nrc_core/README.md:验证与诊断末段；nrc_core/debug.py函数说明
- 代码位置：nrc_core/debug.py:10,37-38
- 最小输入步骤：NRC_CORE_LOG环境变量设为空，configure_core_logging(None)后记录damage事件。
- 预期与实际：README称默认不输出并由环境变量控制；实际读取硬编码NRC_CORE_LOG="damage"，仍输出一条日志。此为公开诊断接口偏差，不作为游戏规则缺陷。
- 影响范围：所有默认import与日志配置，无需假设敏感信息攻击风险。
- 证据：probe.py；probe_output.json:I10_logging_docs `{"env_disabled": "", "actual_categories": ["damage"], "actual_output": "[nrc_core:damage] {\"event\": \"audit\"}\n", "expected": "README默认无日志，环境变量为空应关闭；实现固定damage"}`
