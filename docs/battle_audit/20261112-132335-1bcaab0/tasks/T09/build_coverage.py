"""T09 逐对象、分支与特性原文子句的保守审阅台账。"""
import ast
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
from nrc_core.effect_data import ABILITY_EFFECTS, SKILL_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
from nrc_core.engine.registry import _HANDLERS, _ABILITY_HANDLER_OVERRIDES

SOURCE = 'nrc_core/engine/handlers_ability.py'
TEXT = (ROOT / SOURCE).read_text(encoding='utf-8')
TREE = ast.parse(TEXT)
FUNCTIONS = [n for n in TREE.body if isinstance(n, ast.FunctionDef)]
NOTES = {}


def annotate(names, conclusion, rule, note):
    """登记人工审查的相似原语结论范围。"""
    for name in names.split():
        NOTES['_h_' + name] = (conclusion, rule, note)


STATE = 'data/状态分类.md:2-6'
PROCESS = 'data/README.md:22-35'
CONTRACT = 'AGENTS.md用户本轮架构规则：未实现机制抛UnsupportedMechanicError'
annotate('ability_compute', '确认缺陷', CONTRACT, 'I01未知action静默忽略；I09充分燃烧4%tick；子action逐项列于static_review，借用/取念/复写需原文来源；不把所有action判定相同正确性')
annotate('ability_increment_counter', '规则存疑', PROCESS, '给团队counter_count再加1；counter入口本已加1，身经百练触发是否故意额外计数需Q01，不因handler存在通过')
annotate('transfer_mods', '规则存疑', STATE, '优先_snapshot_mods否则裸字段；仅十个属性，不含复合状态/技能修正，洁癖传递范围需正式原文；与调用处离场先清理有关')
annotate('burn_no_decay', '通过', 'data/wiki/game_descriptions.csv:3', '仅验证协议：result.burn_no_decay在battle.py:788-797收集，停止衰减/增长由外层执行；不判煤渣草特殊增长规则数值')
annotate('power_multiplier_buff', '规则存疑', 'data/伤害数值计算.md:16', '独立乘法层写Pokemon.power_multiplier且DamageCalculator读取、下场清1；当前无特性配置，调用次数与持续期需原文')
annotate('threat_speed_buff', '规则存疑', PROCESS, '调用_has_ko_threat读取敌技能，叠speed_up并标记；清理固定减0.5，若speed参数非0.5不对称；条件威胁是否含应对及动态能耗需回合组')
annotate('counter_accumulate_transform', '规则存疑', PROCESS, '防御/状态/攻击分类过滤；同回合guard_counter_turn只计一次；可_defer_transform；三特性共用guard queen目标是否都成立需正式原文，缺skill时跳过分类')
annotate('delayed_revive', '规则存疑', PROCESS, '写undying_revive_in，battle.py:270递减并满HP能复活；重复力竭处理重置计时与力竭当回合算第1回合需Q02')
annotate('copy_switch_state', '规则存疑', STATE, '仅snapshot与switched_in都存在才调用_transfer_pokemon_state；当前snapshot真值与字段完整性需换人组；引用传递不改离场对象')
annotate('cost_invert cost_change_double', '通过', STATE, '只设置布尔标记，helpers._adjust_cost_delta按反转/翻倍消费；结论限协议，不判断当前标记首次安装时点')
annotate('mirror_enemy_buffs', '规则存疑', 'data/wiki/game_descriptions.csv:13', 'I10线索：max复制五维up，额外把能量取max，不复制life_drain/全威力/连击/技能降耗；清me镜像引用会取消双公平鸽一侧监听；原文需Q03')
annotate('counter_success_double_damage', '确认缺陷', CONTRACT, 'I04：只写double_damage_next，全核心无读取，下一攻击不翻倍且标记不消费')
annotate('counter_success_buff_permanent', '规则存疑', STATE, '转_apply_ability_buff复合状态；on_switch_out清除compound_statuses，与“永久”是否限站场需原文')
annotate('counter_success_power_bonus', '规则存疑', STATE, 'skill_power_bonus+=delta有消费；下场清零，永久跨离场范围待Q01')
annotate('counter_success_cost_reduce', '规则存疑', STATE, '技能逐项永久减delta封底0；绕过_adjust_cost_delta的反转/翻倍；特性共存/复制情况下规则待确认')
annotate('counter_success_speed_priority', '规则存疑', 'data/wiki/game_descriptions.csv:21', '写priority_stage，有行动顺序消费；原文“速度+1”和技能先手层级是否同义需Q01')
annotate('first_strike_power_bonus mark_power_per_meteor', '确认缺陷', CONTRACT, 'I04：只把power_multiplier写ctx.result；PASSIVE在回合末ctx无skill/is_first，攻击入口只BEFORE_ATTACK，正常伤害不会读该临时key')
annotate('first_strike_hit_count', '规则存疑', PROCESS, 'PASSIVE无skill/is_first默认不触发；若人工调用则永久改skill.hit_count且不恢复；配置与阶段错位，同I04消费者问题')
annotate('first_strike_agility', '确认缺陷', 'data/wiki/game_descriptions.csv:6', 'I04：写first_skill_agility无消费者；另一compute action有实际插AGILITY，但本E未委派')
annotate('auto_switch_on_zero_energy auto_switch_after_action', '确认缺陷', 'data/wiki/game_descriptions.csv:4', 'I05：前者写Pokemon.force_switch，后者auto_switch_eot；消费者读auto_switch_zero_energy/every_turn，键不匹配')
annotate('team_synergy_bug_swarm_attack team_synergy_bug_swarm_inspire team_synergy_brave_if_bugs', '规则存疑', STATE, '只统计其他存活虫系，buff仅双攻。原文线索要求攻防速且入场，配置PASSIVE每回合末触发会累加复合状态；需Q01正式原文，不因当前可达错配称未上线')
annotate('team_synergy_bug_kill_aff', '确认缺陷', CONTRACT, 'I04：写aff_bonus没有核心消费；亲密度模型与规则字段未实现，不能因未引用就标未上线')
annotate('stat_scale_defense_per_energy stat_scale_attack_decay', '确认缺陷', CONTRACT, 'I04：写ctx.stat_multiplier无消费；全神贯注action_count没有递增路径；动态属性不会进calculation_modifier')
annotate('stat_scale_hits_per_hp_lost', '规则存疑', 'data/wiki/game_descriptions.csv:36', '按当前缺血四分位计算后+=hit_count_mod；每回合重复PASSIVE会重复累加而非当前快照替换；Q01需确认累计失去还是当前缺失')
annotate('stat_scale_meteor_marks_per_turn', '通过', STATE, '仅协议验证：写meteor_mark_add固定值而非+=；battle.py:928读并每回合给敌阵营，不对“吸积盘”数值/归属原文作通过')
annotate('mark_freeze_to_meteor', '确认缺陷', CONTRACT, 'I04：freeze_becomes_meteor标记无消费者；add_freeze_stacks无转换分支')
annotate('mark_stack_no_replace', '通过', STATE, '仅来源隔离协议：mark_stack_additive由handlers_skill._h_mark_generic读取，独立bard_mark来源槽；效果是否符合所有印记特例不在本结论')
annotate('mark_stack_debuffs', '确认缺陷', CONTRACT, 'I03：debuff_stack_bonus只写不读；不能触发灰色肖像攻击后已有减益+3')
annotate('damage_mod_non_stab damage_mod_non_light damage_mod_non_weakness damage_resist_same_type', '确认缺陷', CONTRACT, 'I02：Skill.type/Pokemon.type1/type2与模型不符，.types模块不存在；PASSIVE无skill早退且未安装可消费标记，传skill运行报错')
annotate('damage_mod_pollutant_blood damage_mod_leader_blood', '通过', 'data/伤害数值计算.md:8-16', '仅攻击修正协议：BEFORE_ATTACK读目标blood_type或lab_metadata血脉，写_power_mult；_h_damage独立attack_context消费，未改持久skill.power。额外倍率具体数值需正式特性来源')
annotate('heal_per_turn', '通过', PROCESS, '仅协议：固定覆盖heal_per_turn_pct，回合末读取且封顶；不是重复叠加，回血死亡门槛在外层')
annotate('heal_on_grass_skill on_skill_element_heal', '规则存疑', PROCESS, '回血封顶、anti_heal分支扣血；未将anti_heal_multiplier数值乘入，也未触发frostbite判死，系统发育分享钩子未在此调用；专名数值需原文')
annotate('skill_cost_reduction_type', '确认缺陷', CONTRACT, 'I02：Enum SkillCategory.DEFENSE与字符串防御比较永远不等；即便手工字符串也只写context.cost_reduction，正常能耗路径不读取')
annotate('poison_stat_debuff', '规则存疑', STATE, '检测敌已有毒才叠spatk_down/spdef_down，与原文线索物攻-40%速度-40且成功施毒时不同；中毒免疫/本次未施毒也会触发，归Q01')
annotate('poison_on_skill_apply', '规则存疑', 'data/wiki/game_descriptions.csv:2', '用_base_energy_cost及严格<阈值而非实际成本；直接+=poison无毒系免疫；专名线索≤1与配置cost_threshold5另归配置组')
annotate('freeze_immunity_and_buff', '通过', 'data/wiki/game_descriptions.csv:5', '仅冻结免疫协议：add_freeze_stacks先检查freeze_immune；双防写复合状态并计算时消费。具体授予百分比与换人保留需正式来源')
annotate('extra_freeze_on_freeze', '通过', 'data/wiki/game_descriptions.csv:5', 'pass是固定规则标记并非空缺：models.add_freeze_stacks按source PASSIVE定义读取extra，每次成功施加只加一次')
annotate('extra_consumption_on_freeze', '通过', 'data/wiki/game_descriptions.csv:5', '仅ON_INFLICT_FREEZE且added>0才调敌技能成本；add_freeze_stacks免疫/力竭/非正数先返回；probe冻结2层敌成本2→3，控制标志隔离')
annotate('faint_no_mp_loss', '规则存疑', PROCESS, '写faint_no_mp_loss，外层MP处理需回合组；不只凭标记存在判规则通过')
annotate('on_skill_element_buff on_skill_element_poison on_skill_element_enemy_energy', '规则存疑', PROCESS, '元素过滤依靠AbilityEffect.filter；handler单独不检element。毒+=未免疫；能量扣除封底0；buff转复合状态，具体特性原文见clause_review')
annotate('on_skill_element_cost_reduce enemy_switch_self_cost_reduce carry_skill_cost_reduce carry_element_count_buff', '规则存疑', STATE, '逐技能过滤和_adjust_cost_delta已静态核对；持续/重复授予应否重置需原文；global范围dispatch单独来源记录，特定系保持私有')
annotate('carry_skill_power_bonus low_cost_skill_power_bonus', '确认缺陷', CONTRACT, 'I04：分别写carry_skill_power_bonus/low_cost_skill_power_bonus但全核心无消费；现配置可能已迁移compute，仍属实现缺口，reachability另列')
annotate('on_kill_buff', '规则存疑', PROCESS, 'ON_KILL入口保证击败后，buff按stacks转复合状态；受反伤/自毁力竭是否还触发与永久范围需原文')
annotate('recoil_damage', '规则存疑', 'data/伤害数值计算.md:6-10', '把power直接当HP扣除而非按物攻魔攻/防御伤害公式；category未读取。刺肤正式规则需Q04，代码注释固定伤害与power语义冲突')
annotate('entry_buff', '确认缺陷', CONTRACT, 'I04：entry_buff_duration/keys只写不消费；若配置要求持续1回合不会失效，当前无配置，reachability单列')
annotate('on_enter_grant_drain', '规则存疑', 'data/wiki/game_descriptions.csv:29', '+=life_drain_mod，普通执行器消费回血；下场清0，重复入场与特性层分类需原文')
annotate('enemy_all_cost_up', '规则存疑', STATE, '入场直接永久改敌技能，没有在自己离场时回滚；注释在场与实现持续不一致，需Q01')
annotate('entry_freeze_extra', '规则存疑', 'data/wiki/game_descriptions.csv:5', '调用统一冻结入口正确，额外能耗不依赖施加成功；即使免疫冻结也加成本，是否应如此需抓到你了原文')
annotate('leave_heal_ally leave_buff_ally', '规则存疑', PROCESS, '仅放result由主动换人接收；脱离/死亡替换是否一致须切换组；回血封顶在外层，不单凭handler存在通过')
annotate('leave_energy_refill energy_regen_per_turn', '通过', PROCESS, '仅能量增益协议：调用gain_energy支持energy_no_cap和正常10上限；当前缺配置不是未上线证明，数值专名待原文')
annotate('steal_all_enemy_energy', '规则存疑', STATE, '逐存活敌方扣min能量并gain_energy，amount非负由配置保证；未上场者能量变化私有战报由平台负责；回能叠加封顶后是否继续扣敌需原文')
annotate('enemy_switch_debuff', '规则存疑', PROCESS, 'energy_loss与poison都可执行；直接poison_stacks+=不检毒免疫；调用目标需确认switched_in，当前无E配置不能判未上线')
annotate('on_interrupt_cooldown', '确认缺陷', CONTRACT, 'I04：仅写interrupt_cooldown_turns无消费者，且配置在COUNTER_SUCCESS而非确认打断成功，未把敌被打断槽设冷却')
annotate('energy_cost_condition_buff', '规则存疑', STATE, '使用_base_energy_cost等于配置cost判断，忽略实际cost和permanent参数；buff复合状态；正确依据基础或实际需Q01')
annotate('enemy_tech_total_power', '确认缺陷', CONTRACT, 'I03：写bonus_pct_per_cost，DamageCalculator读bonus_pct_per_layer；现变形活画敌10层增益伤害90不变，速度仅展示字符串无计算')
annotate('half_meteor_full_damage', '规则存疑', 'data/wiki/game_descriptions.csv:34', '标记读取于meteor_stacks引爆而非meteor_mark触发；实际用一半层数算威力而非满伤，取ceil/floor和对象需Q01')
annotate('energy_drain_by_cost_diff', '规则存疑', PROCESS, 'last_skill_cost差>0才扣能；缺动作本回合时保留上回合cost，是否重置需回合组')
annotate('entry_buff_per_skill_count', '规则存疑', STATE, 'count_keys优先、<=0早退；status_key直接存复合状态；成本累计、power从共享_ability_base_power绝对重算；grant_agility只布尔与T07-I03同缺口；计数重入重复与全局增益归属需正式原文')
annotate('hit_count_per_poison fixed_hit_count_all', '通过', 'data/wiki/game_descriptions.csv:36', '仅连击标记协议：_h_damage读毒层和任一方fixed_hit_count_all；命中数算法与状态/1连击边界不在此结论')
annotate('first_action_hit_bonus', '通过', PROCESS, '入场无skill设flag，使用后清；battle._skill_use_repetitions及runtime合法动作均读flag，额外次数与能耗同步；不是只改伤害连击')
annotate('extra_poison_tick', '通过', 'data/wiki/game_descriptions.csv:2', '标记由turn_end_effects在敌方中毒结算额外1次读取；固定True不会每回合累加；全流程状态致死由回合组')
annotate('conditional_entry_buff_total_cost conditional_entry_buff_mp', '规则存疑', STATE, '基础cost总和严格<、MP严格==，check_enemy侧别正确；不满足不会清先前复合状态；条件是否每入场重新判断待原文')
annotate('immune_zero_energy_attacker immune_low_cost_attack', '通过', PROCESS, '仅免伤协议：_h_damage先查零能与_last_actual_cost<=阈值且仅攻击；没有增加临时技能修正。零能使用后判断时点/阈值原文归配置组')
annotate('entry_self_damage', '规则存疑', PROCESS, '首次标志不会下场清；当前HP//2且至少1。奇数减半向下与冻结阈值即时致死缺规则需回合组')
annotate('specific_skill_power_bonus', '规则存疑', STATE, '只第一个同名技能，_ability_base_power共用后重算可能覆盖其他永久变化；相同技能多槽规则及跨入场永久范围待原文')
annotate('energy_no_cap hp_for_energy', '通过', PROCESS, '仅协议：gain_energy读energy_no_cap；battle/runtime成本合法性读hp_for_energy；不是空处理器。具体替代HP公式归能耗组')
annotate('shuffle_skills_reduce_last', '规则存疑', STATE, '随机明确来自盲拧原文线索，打乱skills原列表；第四槽减-_adjust_cost_delta(positive)和调整negative等价；cooldowns槽映射是否随技能移动待Q05')
annotate('weather_conditional_buff', '规则存疑', STATE, '仅天气相等则复合buff新增层，不相等不撤旧层；配置ON_TURN_START重复累加，天气条件状态应快照还是累计需Q01')
annotate('fainted_allies_buff', '规则存疑', STATE, 'scope=all累加双方力竭数，其他值当allies；存一份复合状态并加stacks，重复入场/计数改变会保留旧层定义；需Q01')
annotate('on_super_effective_buff', '确认缺陷', 'data/部分规则详解/最好的伙伴.md:3-7', 'I06：只检查skill系别克制，不检查伤害/攻击类型，状态技能也加完整层并回2能；正确完整存层但触发条件错误')
annotate('enemy_element_diversity_power', '规则存疑', STATE, '按敌携带技能种类计数+=全技能威力，ON_ENTER重入可重复叠；原文是否攻击时重算而非入场快照需Q01')
annotate('kill_mp_penalty', '通过', PROCESS, '仅时点协议：execute_ability写_ability_timing，ON_KILL扣对手/ON_FAINT扣己方，双侧封底0；额外基础MP的统一结算归回合组')
annotate('turn_end_repeat turn_end_skip burst_power_bonus burst_enemy_cost_up burst_extend', '确认缺陷', CONTRACT, 'I07：PASSIVE重复执行使用+=累积固定授予；回合末每次调用不会清零，重复次数或迸发幅度无限增长。probe两次真实回合末repeat1→2')
annotate('noise_debuff', '规则存疑', STATE, '追加temporary_skill_cost_mods(filter attack,turns)供skill_energy_cost消费并回合末递减；amount未调对流/倾轧，持续3回合是否含当前回合待Q01')
annotate('skill_slot_lock', '通过', PROCESS, '仅合法动作协议：allowed_slots存列表，runtime读取允许槽；多次PASSIVE赋值不累计，不解析技能描述')
annotate('buff_extra_layers', '规则存疑', STATE, '固定赋值extra供_apply_buff/_apply_ability_buff读；复合层buff按乘数放大未必实际加层、全技能/生命吸取不统一，需营养液泡正式分类')
annotate('barrel_state', '通过', PROCESS, '仅下一替换标记协议：按team写pending，主动切换接收barrel_active；DamageCalculator任一方木桶使eff=1，主动行动清除由回合组')
annotate('burst_element_cost_reduce', '规则存疑', 'data/wiki/game_descriptions.csv:11', '固定覆盖元素/减耗字典，battle迸发后退款；合法性预览和_last_actual_cost同步问题属能耗组，不单凭写flag通过')

# 用户已授权技能/特性原文用于子句核对；T01证明spirits原文与DB描述一致。
# 这里纠正此前把“无专名md”等同“无规则来源”的误解，不批量升级执行正确性。
annotate('team_synergy_bug_swarm_attack team_synergy_bug_swarm_inspire','确认缺陷',
         'data/wiki/spirits.csv:158,2（用户授权特性原文）；'+STATE,
         'I11/T06-I11协同：原文入场攻防速+15%/+10%，实现PASSIVE且仅双攻，不含双防和速度；队伍存活过滤另需具体边界，不因handler存在通过。')
annotate('poison_stat_debuff','确认缺陷','data/wiki/spirits.csv:85（用户授权特性原文）',
         'I11/T06-I11：原文成功施毒时敌物攻-40%速度-40，配置ON_USE且handler要求已有毒，然后降低魔攻魔防；明确触发与属性差异，无需用户重复授权。')
annotate('poison_on_skill_apply','确认缺陷','data/wiki/spirits.csv:115（用户授权特性原文）；data/wiki/game_descriptions.csv:2',
         'I11/T06-I11：原文能耗<=1，配置阈值5且handler按基础cost<5，成本2/3/4错误施4毒；直接+=亦未检毒系免疫。基础/实际成本边界仍可具体提问。')
annotate('mirror_enemy_buffs','确认缺陷','data/wiki/spirits.csv:30（用户授权特性原文）；data/wiki/game_descriptions.csv:13',
         'I10：复制敌增益却额外能量取max；增益范围明确含吸血/连击/技能威力和降耗而未复制。已有自身增益max还是叠加仍需Q03；双公平鸽监听与复合特性分类待复演。')
annotate('recoil_damage','确认缺陷','data/wiki/spirits.csv:423（用户授权特性原文）；data/伤害数值计算.md:6-10',
         'I12：刺肤原文50威力物理伤害，handler把power直接当HP扣且category不读；按攻防计算这一点无歧义。未说明的伤害系别/本系归属仅保留具体Q04，不再把威力与固定HP之别当待授权。')

for function,(conclusion,rule,note) in list(NOTES.items()):
    for old,new in {
        '需正式特性来源':'需补该数值条件的独立执行验证',
        '需正式原文':'需按已授权原文补执行边界验证',
        '需Q01正式原文':'需按Q01具体边界补证',
        '专名数值需原文':'专名数值需逐对象执行补证',
        '原文需Q01':'具体边界待Q01',
        '借用/取念/复写需原文来源':'借用/取念/复写具体子句需逐对象补证',
        '正式层计数':'具体层计数',
    }.items():note=note.replace(old,new)
    NOTES[function]=(conclusion,rule,note)


def review_clause(ability, clause, assessment):
    """按明确子句差异给结论，其余保留执行待证实而非来源不足。"""
    confirmed={
        '虫群突袭':('入场时获得攻防速',), '虫群鼓舞':('入场时获得攻防速',),
        '毒牙':('使敌方获得中毒时','物攻-40%','速度-40'),
        '毒腺':('使用能耗小于等于1',),
        '游弋':('蓄力','双防'), '腐植循环':('回复','生命'),
        '耐活王':('受到中毒','等量'), '仁心':('受到灼烧','等量'),
        '慢热型':('入场前','回复5'), '地脉':('入场前','回复3'), '散热':('入场前','回复3'),
        '贪心算法':('1号位','传动','使用后'), '夺目':('3个','三个','随机'),
        '灰色肖像':('攻击','减益'), '变形活画':('增益','威力','速度'),
        '刺肤':('50威力物理',), '衡量':('复制敌方的增益','敌方获得增益自己也会获得'),
    }
    patterns=confirmed.get(ability,())
    if any(pattern in clause for pattern in patterns):
        return '确认缺陷',assessment+'；该子句原文与完整消费者已确认不符，合并既有T06/T09问题；其余参数不因此通过','原文来源充分；缺陷证据是具体目标/阈值/阶段/消费者差异，不是缺少专名md'
    return '规则存疑',assessment,'原文来源充分；该子句的完整触发条件、数值或跨阶段消费者尚未独立验证，保留实现待证实，非要求用户再次授权原文'


def main():
    """逐清单登记，未知规则与未调用分别保留。"""
    missing = [node.name for node in FUNCTIONS if node.name not in NOTES]
    assert not missing, missing
    references = defaultdict(list)
    for name, effects in ABILITY_EFFECTS.items():
        for ae in effects:
            for tag in ae.effects:
                handler = _ABILITY_HANDLER_OVERRIDES.get(tag.type) or _HANDLERS.get(tag.type)
                if handler and handler.__module__.endswith('handlers_ability'):
                    references[handler.__name__].append({'ability': name, 'timing': ae.timing.name, 'filter': ae.filter, 'params': tag.params})
    descriptions = defaultdict(list)
    spirit_path = ROOT / 'data/wiki/spirits.csv'
    with spirit_path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    # 字段名来自当前CSV表头，原文同时保留行号以便复核。
    for i, row in enumerate(rows, 2):
        if row.get('特性'):
            descriptions[row['特性']].append((i, row['特性效果']))
    assigned = list(csv.DictReader((OUT / 'assigned_inventory.csv').open(encoding='utf-8-sig')))
    coverage = []
    fields = ['item_id','conclusion','rule_basis','implementation','objects','method','evidence','notes','reachability']
    for row in assigned:
        line = int(row['line'])
        fn = next((n for n in FUNCTIONS if n.lineno <= line <= n.end_lineno), None)
        if fn:
            conclusion, rule, note = NOTES[fn.name]
            refs = references[fn.name]
            original_sources=[]
            for ref in refs:
                if descriptions.get(ref['ability']):
                    original_sources.append('data/wiki/spirits.csv:'+str(descriptions[ref['ability']][0][0])+':'+ref['ability'])
            if original_sources:
                rule+='；用户授权特性原文：'+'、'.join(sorted(set(original_sources)))
                note+='；无专名md不构成来源缺口；未证实子句仅保留实现待证实，具体明确差异见clause_review'
            reach = '当前特性配置：' + '、'.join(sorted({r['ability'] for r in refs})) if refs else '无当前特性配置；注册接口仍可调用，不能据此称未上线'
            if row['kind'] == 'code_branch':
                note += '；本行分支条件：' + row['description'] + '；仅逐条件静态定位，不声称真假均动态运行'
                if conclusion == '确认缺陷':
                    conclusion = '规则存疑'
                    note += '；关联函数问题见issues；本分支单独结论尚无充分规则证明'
        else:
            conclusion, rule, note, reach = '规则存疑', CONTRACT, '模块包含多类已复现缺口；TYPE_CHECKING仅类型导入，无游戏结论', '运行模块可达；TYPE_CHECKING真分支仅静态类型检查'
        coverage.append(dict(zip(fields, [row['item_id'], conclusion, rule, SOURCE+':'+str(line), fn.name if fn else row['name'],
            '逐函数全文、逐条件源码审阅；相关原文全部子句拆分；选定疑点实际运行', 'static_review.md；clause_review.csv；probe_output.json；issues.md；questions.md', note, reach])))
    unique = {}
    for row in coverage:
        if row['item_id'] in unique:
            unique[row['item_id']]['notes'] += '；同ID附加条件：' + row['notes']
        else:
            unique[row['item_id']] = row
    coverage = list(unique.values())
    clauses = []
    for fn in FUNCTIONS:
        for ref in references[fn.name]:
            sources = descriptions.get(ref['ability'], [])
            source = sources[0] if sources else (0, '尚未定位特性原文；配置不作为自证')
            for clause in re.split('[，。；]', source[1]):
                if clause:
                    clause_conclusion,assessment,gap=review_clause(ref['ability'],clause,NOTES[fn.name][2])
                    clauses.append({'ability':ref['ability'], 'handler':fn.name, 'timing':ref['timing'], 'clause':clause,
                        'basis': 'data/wiki/spirits.csv:'+str(source[0])+'（用户授权特性原文；冲突时data根md/详解/通用规则优先）',
                        'conclusion':clause_conclusion,
                        'implementation':SOURCE+':'+str(fn.lineno), 'assessment': assessment,
                        'rule_gap':gap})
    named = {
        '游弋':'PASSIVE无条件双防，缺蓄力自由行动；明确差异合T06，跨handlers_skill/field',
        '腐植循环':'ON_TURN_END固定5%而非能量增益事件；明确阶段错误合T06；实际/名义能量仅细节Q01',
        '耐活王':'按自身HP比例及敌毒层，不消费敌实际毒伤事件；明确差异合T06',
        '仁心':'按自身HP比例及敌烧层，不消费敌实际烧伤事件；明确差异合T06',
        '慢热型':'入场set_to0，自身应对回5，不是入场前己方事件；明确差异合T06',
        '地脉':'入场set_to0，自身地系使用回3，不是入场前己方事件；明确差异合T06',
        '散热':'入场set_to0，自身火系使用回3，不是入场前己方事件；明确差异合T06',
        '贪心算法':'无位置过滤且缺传动授予；明确差异合T06及T07-I05',
        '夺目':'仅NON_LIGHT且无skill早退/有skill导入报错，缺随机3技能；明确差异I02/T06；随机池细节仍可问',
        '盲从':'compute multiple_borrow及三随机转换分支多槽/非幻-2已实现；普通非幻技能减耗未找到，Q01',
        '灰色肖像':'只写debuff_stack_bonus，无消费者；I03，已有减益种类定义待Q01',
        '变形活画':'倍率参数key不匹配，速度只展示；I03/Q01',
    }
    for ability, note in named.items():
        source = descriptions[ability][0]
        for clause in re.split('[，。；]', source[1]):
            if clause:
                clause_conclusion,assessment,gap=review_clause(ability,clause,note)
                clauses.append({'ability':ability,'handler':'专名跨入口核对','timing':','.join(ae.timing.name for ae in ABILITY_EFFECTS[ability]),
                    'clause':clause,'basis':'data/wiki/spirits.csv:'+str(source[0])+'（用户授权特性原文）','conclusion':clause_conclusion,
                    'implementation':'nrc_core/effect_data.py；'+SOURCE,'assessment':assessment,
                    'rule_gap':gap})
    with (OUT/'coverage.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(coverage)
    with (OUT/'clause_review.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(clauses[0]));writer.writeheader();writer.writerows(clauses)
    static=['# T09 逐函数静态检查范围','','结论仅对应所述协议/规则；原文子句全部拆分见clause_review.csv。所有函数全文已读；分支仅静态审阅，动态运行范围见probe。','']
    for fn in FUNCTIONS:
        conclusion, rule, note=NOTES[fn.name]
        static += [f'## {fn.name}（{fn.lineno}-{fn.end_lineno}）','',f'{conclusion}；{rule}。{note}。', '',
                   '当前配置：'+('、'.join(sorted({r['ability']+':'+r['timing'] for r in references[fn.name]})) or '无特性配置，保留实现缺口审查'), '']
        if fn.name == '_h_ability_compute':
            for node in ast.walk(fn):
                if isinstance(node,ast.If):
                    static.append('- 条件 `'+ast.unparse(node.test)+'`：逐分支读赋值、复制与随机来源；未知action缺少拒绝，swap/borrow与嵌套状态规则需Q01/Q05，不因条件可达性缺失判通过。')
    (OUT/'static_review.md').write_text('\n'.join(static),encoding='utf-8')
    (OUT/'handler_configuration.json').write_text(json.dumps(references,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'assigned_rows':len(assigned),'unique_ids':len(coverage),'functions':len(FUNCTIONS),'clauses':len(clauses),'conclusions':dict(Counter(r['conclusion'] for r in coverage))},ensure_ascii=False))


if __name__=='__main__':
    main()
