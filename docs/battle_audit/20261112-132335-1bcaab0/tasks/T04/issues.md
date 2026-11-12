# T04 问题记录

所有复现只操作内存状态；业务代码、数据库均未修改。完整输入见repro.py，实际输出见repro_output.json。I01至I11及I13至I14为P1确定规则偏差；I12单列已复现事实与尚待裁决预期。GAME_RULE为稳定数据库规则ID，CSV冒号数字是当前文件物理行，两者不是同一编号。

## T04-I01 技能/特性减伤晚于逐击公式取整

- 严重度：P1；主责协同：T04主责，T07协同伤害原语
- 规则依据/原文行号：data/伤害数值计算.md:7,9,21
- 代码位置：nrc_core/battle.py:1957-1973,2078-2101
- 最小输入步骤：威力10、攻防100、三连击、50%减伤；调用计算器后调用减伤接口。
- 预期与实际：公式把减伤乘入威力，逐击4合计12；实际先得27再乘0.5取整为13。
- 影响范围：所有存在减伤的攻击，特别多段与低伤害；特性减伤也在最终整数后相乘。
- 证据：repro.py中I01_reduction；repro_output.json对应结果：`{"base": 27, "actual": 13, "expected": 12}`

## T04-I02 石头大餐用生命补能后重复扣完整能耗

- 严重度：P1；主责协同：T04主责，T06协同特性
- 规则依据/原文行号：data/wiki/spirits.csv:460,558-559
- 代码位置：nrc_core/battle.py:1683-1720
- 最小输入步骤：最大生命1000、当前满血、能量1、技能耗4，设置hp_for_energy。
- 预期与实际：扣150生命替代缺少3能量后应能量0；实际能量置0后又减4，得到-4。
- 影响范围：石头大餐精灵，负能量可继续干扰免伤、聚能与能耗判定。
- 证据：repro.py中I02_hp_for_energy；repro_output.json对应结果：`{"actual_energy": -4, "expected_energy": 0, "hp": 850, "expected_hp": 850}`

## T04-I03 50回合强制裁决未实现

- 严重度：P1；主责协同：T04主责，T03协同终局接口
- 规则依据/原文行号：data/README.md:37-42
- 代码位置：nrc_core/battle.py:1278-1415,2316-2330; nrc_core/core.py:151-217
- 最小输入步骤：turn=50，双方存活，MP为4:3，双方聚能。
- 预期与实际：应以MP高者A胜；实际进入turn51，winner=None。runtime也无50回合兜底。
- 影响范围：全部拖到50回合的PvP；四指标全平的额外规则另列问题，不影响此反例。
- 证据：repro.py中I03_turn50；repro_output.json对应结果：`{"next_turn": 51, "actual_winner": null, "expected_winner": "a"}`

## T04-I04 脱离未检查本回合入场免疫

- 严重度：P1；主责协同：T04主责，T07协同脱离标签
- 规则依据/原文行号：GAME_RULE:0037,0036；data/wiki/game_descriptions.csv:4,26
- 代码位置：nrc_core/battle.py:607-666,2183-2202
- 最小输入步骤：turn7，当前精灵在burst_entry_turn中记录入场7，队伍有替补；调用脱离。
- 预期与实际：应免疫脱离且索引不变；实际立即随机换入索引1。
- 影响范围：普通脱离与紧急脱离共用入口；换入后同回合可能再次脱离。
- 证据：repro.py中I04_entry_immunity；repro_output.json对应结果：`{"actual_changed": true, "actual_index": 1, "expected_changed": false}`

## T04-I05 奉献已获得层数在每次使用时重复写为永久强化

- 严重度：P1；主责协同：T04主责，T07协同奉献授予
- 规则依据/原文行号：data/部分规则详解/奉献.md:1-4; data/wiki/skills.csv:101
- 代码位置：nrc_core/battle.py:1762-1785
- 最小输入步骤：己方飞断奉献1层；受奉献影响攻击连续使用两次，不再获得新奉献。
- 预期与实际：该1层应始终提供威力+20；实际skill_power_bonus从20变40，且修正写在精灵上可影响非受益技能。
- 影响范围：全部奉献受益技能及同精灵其他攻击；能耗、吸血、连击也采用累加写法。
- 证据：repro.py中I05_devotion；repro_output.json对应结果：`{"actual_permanent_bonus": [20, 40], "expected_each": 20}`

## T04-I06 毒印/荆刺等直接扣血漏冻结实时力竭检查

- 严重度：P1；主责协同：T04主责，T02协同冻结模型
- 规则依据/原文行号：GAME_RULE:0007,0002；data/wiki/game_descriptions.csv:5,15,20
- 代码位置：nrc_core/battle.py:1080-1106,1120-1145,2104-2110
- 最小输入步骤：最大HP1000，当前70，冻结1层，毒印1层；回合末结算。
- 预期与实际：扣30后40低于冻结50应力竭；实际40且is_fainted=False。荆刺同样直接扣血不检查阈值。
- 影响范围：冻结精灵遭印记伤害；力竭、MP扣除和终局均可延迟。
- 证据：repro.py中I06_freeze_mark；repro_output.json对应结果：`{"actual_hp": 40, "actual_fainted": false, "expected_fainted": true}`

## T04-I07 蓄电印记按入场回合而非首次行动生效

- 严重度：P1；主责协同：T04主责
- 规则依据/原文行号：GAME_RULE:0042；data/wiki/game_descriptions.csv:11,24
- 代码位置：nrc_core/battle.py:1139-1145,1174-1180
- 最小输入步骤：入场回合1但尚未主动行动，当前turn2、_burst_pending=True，蓄电1层。
- 预期与实际：首次攻击应得威力+10；实际entry_turn与turn不等故加成0。反向：同回合已聚能仍可能受益。
- 影响范围：中途换入后下一回合首次行动、多次使用与首次行动消耗。
- 证据：repro.py中I07_charge_mark；repro_output.json对应结果：`{"actual_bonus": 0, "expected_bonus": 10}`

## T04-I08 回合末先特性回血后状态伤害，与总规则相反

- 严重度：P1；主责协同：T04主责，T06协同特性阶段
- 规则依据/原文行号：data/README.md:19-31; data/wiki/game_descriptions.csv:2
- 代码位置：nrc_core/battle.py:761-816
- 最小输入步骤：HP20/1000、中毒1层、回合末回复5%特性，调用turn_end_effects。
- 预期与实际：状态30伤先结算应力竭；实际先回血50再扣30，剩40存活。双方末尾阶段也固定A→B，未按总规则拼速。
- 影响范围：全部回合结束特性、状态与先后相互影响；可改变生死与战果。
- 证据：repro.py中I08_end_order；repro_output.json对应结果：`{"actual_hp": 40, "actual_fainted": false, "expected_fainted": true}`

## T04-I09 减速印记错误采用比例减速

- 严重度：P1；主责协同：T04主责
- 规则依据/原文行号：GAME_RULE:0009；data/wiki/game_descriptions.csv:32
- 代码位置：nrc_core/battle.py:533-542
- 最小输入步骤：A速度200、1层减速；B速度185，无先手差。
- 预期与实际：A应200-10=190仍先；实际A速度乘0.9=180导致B先。
- 影响范围：所有减速印记及不同基础速度对局。
- 证据：repro.py中I09_slow_mark；repro_output.json对应结果：`{"actual_first": 1, "expected_first": -1}`

## T04-I10 龙噬印记触发能耗和效果均不符原文

- 严重度：P1；主责协同：T04主责，T07协同印记原语
- 规则依据/原文行号：GAME_RULE:0054；data/wiki/game_descriptions.csv:31
- 代码位置：nrc_core/battle.py:1162-1167,2205-2284
- 最小输入步骤：龙噬1层，使用3耗攻击后读取双攻；另查询5耗攻击修正。
- 预期与实际：3耗技能释放后应获得双攻40%；实际双攻仍0；反而5耗技能获得即时攻击倍率1.4。
- 影响范围：全部龙噬相关战斗，影响触发条件、永久/后续收益及初次伤害。
- 证据：repro.py中I10_dragon_mark；repro_output.json对应结果：`{"actual_attack_buff_after_3cost": 0.0, "actual_spattack_buff_after_3cost": 0.0, "actual_multiplier_for_5cost": 1.4, "expected_both_buff_after_3cost": 0.4, "expected_multiplier_for_5cost": 1}`

## T04-I11 普通脱离被随机换人且不等待用户选择

- 严重度：P1；主责协同：T04主责，T03协同动作/暂停恢复，T07协同标签
- 规则依据/原文行号：GAME_RULE:0037,0036；data/README.md:27; data/wiki/game_descriptions.csv:4,26; data/wiki/skills.csv:372
- 代码位置：nrc_core/battle.py:607-666,2183-2202
- 最小输入步骤：移花接木仅配置其脱离原语，队伍有两个健康替补；分别seed0至4。
- 预期与实际：普通脱离应暂停供本人选择；实际新索引为2,1,1,1,1且pending为空。紧急脱离原文指定随机，随机本身在该场景合法；两者不能混同。
- 影响范围：所有普通脱离，无论自身或强制敌方；后手动作打到未经选择的目标。
- 证据：repro.py中I11_ordinary_disengage；repro_output.json对应结果：`{"actual_indices_by_seed": [2, 1, 1, 1, 1], "actual_pending": [], "expected": "暂停等待用户选择其他存活精灵"}`

## T04-I12 先手自力竭后后手动作跳过（规则存疑）

- 严重度：待裁决；主责协同：T04主责，T03协同runtime；须人工裁决
- 规则依据/原文行号：GAME_RULE:0035；data/README.md:27-31; data/wiki/game_descriptions.csv:40; data/wiki/skills.csv:154
- 代码位置：nrc_core/core.py:187-188; nrc_core/battle.py:669-725,1360-1408,1438-1445
- 最小输入步骤：A先手彗星消耗全部生命，A2健康，B选耗2攻击；通过simulate_turn执行。
- 预期与实际：实际turn2、A仍死者索引0、待补位、B能量10且技能报告只有A。若自力竭需要立即补位，则B行动被丢失；但README将力竭补位列在回合末，且术语离场排除力竭，目前不能把该预期判为确定规则。
- 影响范围：先手自毁/反伤导致己方空场且未终局；待明确后手攻击是否空过，以及B状态/聚能是否应继续。
- 证据：repro.py中I12_midturn_replacement；repro_output.json对应结果：`{"next_turn": 2, "pending": [{"team": "a", "reason": "fainted", "alive": [1]}], "active_a": 0, "b_energy": 10, "skill_teams": ["a"], "expected": "待裁决：若自力竭要求立即补位，则须先选A2再恢复B；术语离场排除力竭，不能仅套用普通脱离规则"}`

## T04-I13 湿润印记被擅自消费并永久写入全队技能能耗

- 严重度：P1；主责协同：T04主责，T00规则双向核对、印记handler协同
- 规则依据/原文行号：GAME_RULE:0032（湿润印记）；GAME_RULE:0010（印记）；data/wiki/game_descriptions.csv:23,41; data/状态分类.md:6
- 代码位置：nrc_core/battle.py:1059-1077
- 最小输入步骤：能耗5的场上与后排精灵，己方湿润印记1层；调用回合开始应用，再推进下一回合、驱散并换入后排。
- 预期与实际：首次印记变0、全队技能实值变4；第二回合仍4；驱散并换人后仍4。应保留阵营印记并仅在印记有效时享受-1；原文没有消耗或永久降低技能的子句。
- 影响范围：所有湿润印记：可见层数、驱散/替换正面印记、后排及跨回合；不应猜消费机制。
- 证据：repro.py中I13_moisture；repro_output.json对应结果：`{"after_first": {"mark": 0, "cost_a": 4, "cost_bench": 4}, "after_second": {"mark": 0, "cost_a": 4}, "after_dispel_and_switch": {"mark_exists": false, "cost_new_active": 4, "cost_old_active": 4}, "expected": "印记应持续存在并在生效期间全技能耗-1，驱散后失去该修正；原文没有消费或永久写入"}`

## T04-I14 沙暴凭空对全队追加1/16生命伤害

- 严重度：P1；主责协同：T04调用入口协同，天气handler所属任务主责，T00发现
- 规则依据/原文行号：GAME_RULE:0030；data/wiki/game_descriptions.csv:37
- 代码位置：nrc_core/battle.py:959-962; nrc_core/engine/handlers_skill.py:881-898
- 最小输入步骤：双方及A后排均普通/非地非机械，HP1000，沙暴剩2回合；调用回合末。
- 预期与实际：权威描述仅双方地系技能耗半，无附加扣血规则；应均1000，实际场上A、后排、B均938。且代码凭空设置地/机械免疫与保底1。
- 影响范围：所有沙暴回合的非地/机械全队精灵，包含后排；可能改变下一次上场生死。
- 证据：repro.py中I14_sandstorm；repro_output.json对应结果：`{"actual_hp_a": 938, "actual_hp_bench": 938, "actual_hp_b": 938, "expected_each": 1000}`
