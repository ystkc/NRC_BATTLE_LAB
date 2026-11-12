"""生成T08逐函数分支台账及T06对象的限定范围补证。"""
import ast
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT))
from nrc_core.engine.registry import _HANDLERS, _ABILITY_HANDLER_OVERRIDES

SOURCE='nrc_core/engine/handlers_skill.py'
TEXT=(ROOT/SOURCE).read_text(encoding='utf-8')
LINES=TEXT.splitlines()
FUNCTIONS=[n for n in ast.parse(TEXT).body if isinstance(n,ast.FunctionDef)]
NOTES={}
CONTRACT='用户AGENTS架构规则：未实现机制抛UnsupportedMechanicError、不静默降级'
STATE='data/状态分类.md:2-6'
FLOW='data/README.md:22-30'


def note(names,rule,review):
    """保存人工逐函数阅读的判断与边界。"""
    for name in names.split():NOTES[name]=(rule,review)


note('_h_damage','data/伤害数值计算.md:6-24；data/wiki/game_descriptions.csv:34,36',
     '逐分支读负威力、零能免伤、实际成本阈值、独立BEFORE_ATTACK上下文、威力相加倍率、毒/萌化连击、固定连击、临时龙噬倍率恢复及星陨消耗。基础伤害公式T03；逐段触发/最终扣血T04协同。星陨直接扣血又加入damage存在双扣接口，合T04既有根因；单击连击边界另probe。多DAMAGE下一攻击修正共用至整技能末清除需Q03。')
note('_h_self_buff _h_self_debuff _h_enemy_debuff',STATE,
     '静态逐条件检查runtime gate；特性self_buff用复合状态，普通用裸字段；敌方invert对debuff取abs反转。不推断所有专名阈值正确，清除/层数分类见T07 helpers。')
note('_h_heal_hp','data/wiki/game_descriptions.csv:29；data/wiki/skills.csv:23',
     '按最大HP比例且poison/burn层数缩放、int取整、封顶、anti分支、分享钩子均读；I07 anti_heal_multiplier仅真值未乘2；分享重复归T10-I13，不泛化其他治疗来源。')
note('_h_heal_energy',FLOW,
     'set_to直接赋值，普通gain_energy走10上限/无上限；系统发育调用分享nominal amount非实际增量，T10-I13主根因；set_to不分享及负值边界无正式规则。')
note('_h_self_ko',FLOW,'只写_self_ko，battle._execute_skill本次结算末消费，不能单凭标记判断自毁伤害及MP完整正确。')
note('_h_energy_all_in','data/wiki/skills.csv魔能爆原文',
     '正能量才将全部当前能量转换_power_bonus并清零；PRE_USE已在支付基础成本之后执行，零/负能不加；“所有能量”含原技能支付部分与否需逐原文确认。')
note('_h_reset_skill_cost',STATE,'恢复_base_energy_cost否则当前值；找到本技能槽清公开modifier成本项，其他项保留；传动/转换移动对象与共享基础值归T05/T07。')
note('_h_steal_energy','data/wiki/skills.csv:73,369','probe steal_available：敌1自己获3敌归0；不足量偷取的准确上限列Q01，不凭直觉规则通过。')
note('_h_enemy_lose_energy',FLOW,'self_mp分阵营直接减可为负；enemy/enemy_new/未知target均扣当前ctx.target封底0；未知target静默当enemy违约线索，具体配置目标需逐对象。')
note('_h_life_drain _h_grant_life_drain','data/wiki/game_descriptions.csv:29',
     'LIFE_DRAIN累加临时result、GRANT常驻life_drain_mod；I01普通路径在减伤/实际扣血前回血，应对路径无人消费；不能仅写入成功判吸血通过。')
note('_h_poison','data/wiki/game_descriptions.csv:2','免疫先查ctx.target再选self/enemy；I04 self目标错误免疫对象。stacks_per_poison_skill及印记读取实际层数，数量零/负输入未校验但当前配置非负。')
note('_h_burn _h_leech','data/wiki/game_descriptions.csv:3,9','直接敌目标免疫后+=；一般免疫路径静态成立，转换型直接加状态绕过另列I04；无逐对象持续伤害本文件结论。')
note('_h_freeze','data/wiki/game_descriptions.csv:5','免疫先返回再add_freeze_stacks(source=user,state/team)；成功施冻事件与力竭由models统一，T03/T09验证。')
note('_h_electric_lure','data/wiki/game_descriptions.csv:50-51','委派统一add_electric_stacks；电系免疫、每2层触发与冻结致死跨机制归T03，委派不作全规则通过。')
note('_h_meteor',STATE,'精灵绑定meteor_stacks+倒计时<=0才设3；与meteor_mark分离；持续3回合的起算、叠层重置需原文。')
note('_h_poison_mark','data/wiki/game_descriptions.csv:41','I05直接写普通poison_mark，没有通用负面槽替换及吟游专属来源隔离。')
note('_h_moisture_mark','data/wiki/game_descriptions.csv:24；'+STATE,
     '加湿润后立刻对全队所有技能减stacks再清0；单独处理cost_invert不处理cost_change_double，绕通用_adjust_cost_delta；是否覆盖其他正印记、立即消耗及阵亡技能范围需专门规则。')
note('_h_mark_generic','data/wiki/game_descriptions.csv:41',
     '普通正/负各1槽替换同类不同名、同名加层；mark_stack_additive使用bard_mark:key:user.name不占普通槽。双方目标与清同类分支逐项读；同名精灵来源是否唯一另Q02。')
note('_mark_stacks',STATE,'委派models.get_mark_stacks同时合普通与吟游来源；没有自行解释层数。')
note('_h_dragon_mark _h_wind_mark _h_charge_mark _h_solar_mark _h_attack_mark _h_slow_mark _h_sluggish_mark _h_spirit_mark _h_meteor_mark _h_thorn_mark _h_momentum_mark','data/wiki/game_descriptions.csv:41',
     '一行包装传固定key给通用印记函数；逐个key与函数名对应已核对，仅这个映射协议通过，不把印记具体收益、来源和时点判通过。')
note('_h_dispel_enemy_marks','data/wiki/game_descriptions.csv:41','<=0全清；正数按最大层逐层扣，非数值/<=0最大项停止。多个同层印记选谁与bard来源是否优先缺规则Q02。')
note('_h_convert_marks_to_burn _h_dispel_marks_to_burn','data/wiki/game_descriptions.csv:3',
     '只求数值层总和后直接burn+=；I04火系/免烧绕过；一个清敌方、一个清双方，ratio/burn_per参数逐对象配置关联表可追。')
note('_h_consume_marks_heal','data/wiki/skills.csv食腐；data/wiki/skills.csv:23','清敌印记总层数按最大HP回血封顶；I07 anti_multiplier只真值；未走系统发育分享，协同T10。')
note('_h_marks_to_meteor','data/状态分类.md:4-6；data/wiki/skills.csv:159','I06原文星陨印记，实际精灵meteor_stacks与三回合倒计时，阵营不新增meteor_mark。')
note('_h_steal_marks','data/wiki/game_descriptions.csv:41','字典全转移累加，未限制stacks、不清被盗方印记同类冲突，不为新主人重建吟游来源；实际翅刃参数与全偷/1层原文逐对象需补证。')
note('_h_energy_cost_per_enemy_mark _h_energy_cost_dynamic','data/状态分类.md:4','写_energy_refund外层却永久修改energy_cost而不退本次能量，动态成本预览另battle.skill_energy_cost；具体本次减耗/永久原文未逐场景证明，列Q04与T04协同。')
note('_h_damage_reduction','data/伤害数值计算.md:20','_damage_reduction覆盖且特性额外写ability_damage_reduction；普通外层另扫描所有减伤tag连乘，不能根据result覆盖直接判不叠；本函数协议与外层T04核对。')
note('_h_force_switch _h_force_enemy_switch','data/wiki/game_descriptions.csv:4','分别写己/敌强制换人标志；当回合入场免疫与候选选择由外层，不单凭标记判通过。')
note('_h_agility','data/wiki/game_descriptions.csv:6','pass是外层迅捷入口标记；T07-I02/I03已报伤害丢失与只布尔配置不可执行，T08不重报。')
note('_h_convert_buff_to_poison','data/wiki/game_descriptions.csv:2,13','仅五个裸up各乘10并归零，忽略复合状态、技能增益、吸血、hit等；直接毒+=绕免疫，I04。更广增益分类范围需Q02。')
note('_h_convert_poison_to_mark','data/wiki/game_descriptions.csv:2,41','kill&&fainted全毒转普通poison_mark；否则ratio>0整除、扣余数正确保留未转换；普通槽绕过合I05。')
note('_h_dispel_marks','data/wiki/game_descriptions.csv:41','not_blocked只写延迟标志由回合消费，其他值直接清双方；未知condition不拒绝合I10；不以无配置为未上线。')
note('_h_conditional_buff','用户AGENTS不得静默降级；'+STATE,
     '支持敌换人延迟、用后半血、实时四种HPgt/lt、开始HPabove/below、毒层缩放；严格大/小不含等号。未知条件静默跳过I10；after_use_hp_gt_half是否在回血之前判断见Q03。')
note('_h_power_dynamic','data/伤害数值计算.md:10,24；'+CONTRACT,
     '逐first_strike/敌换人/前回合状态及应对/零能/敌能<=/缺血阶/超基准成本/毒层/counter条件读。I10 enemy_total_cost及adjacent_power_sum现有参数无分支直接忽略；counter直接base*倍率另T07Q06；5%浮点整数阶边界需Q03。')
note('_h_permanent_mod',STATE,'只委派helpers._apply_permanent_mod；range相邻/power_double等参数消费范围见T07及object_resolution，不把参数存在当实现。')
note('_h_skill_mod',STATE,'条件gate、enemy_switch、起始HP条件、power/pct/cost/hit/本次hit/priority全部分支读；cost走_adjust；未知stat不拒绝合I10。全局字段下场清除与单技能范围另T07。')
note('_h_next_attack_mod',STATE,'累加next两个字段；普通execute_skill结束清除，多个DAMAGE共享到末尾，问题Q03。')
note('_h_cleanse _h_dispel_buffs _h_dispel_debuffs','data/wiki/game_descriptions.csv:13-14；'+STATE,
     '清除目标self/enemy及mode分别委派helpers；T07-I09已用真实洗礼/除厄完整effects确认六种异常、全局负威力/加耗未清，印记/特性控制保留。T08入口协同不独立重报；复合状态/单技能buff其他来源仍待逐类核对。')
note('_h_position_buff',STATE,'用当前技能对象在列表index判positions；重复相同对象/index找首个、传动槽位时点由T05/T07，未凭配置判断所有位置条件正确。')
note('_h_drive','data/wiki/game_descriptions.csv:33','特性无skill且positions时去重注入POST_USE DRIVE，普通写_drive_value；后者旧流程由execute_drive消费不按回合开始移动，T07-I05；嵌套SE/EffectTag两形态已静态读。')
note('_h_passive_energy_reduce','data/wiki/skills.csv水环；'+STATE,'pass是execute_drive独立扫描的标记，不等于未实现；应对专门handler与普通传动路径范围不同。')
note('_h_replay_agility _h_agility_cost_share','data/wiki/skills.csv疾风连袭；data/wiki/game_descriptions.csv:6','只写_replay_agility/_agility_cost_share；battle重放入口/除数取整refund方向另T07，未完整验证实扣。')
note('_h_energy_cost_accumulate',STATE,'本技能加delta经_adjust_cost_delta封底0；是否每技能使用/每回合递增由阶段配置，沙涌当前手写原文漂移T06。')
note('_h_weather','data/wiki/game_descriptions.csv:37','I02沙暴重设重复对现成本折半且max1让0变1；备份只记第一次值，覆盖其他成本变化恢复问题协同T04。所有存活含场下技能遍历；默认天气sunny/turn5需要配置明确。')
note('_apply_weather_damage','data/wiki/game_descriptions.csv:37-38,50','I02沙暴凭空扣所有场上场下1/16HP并保留最低1；与T04-I14同根因。I03雷鸣自身有分支但battle回合末guard排除；雪天用对手作source可能额外触发冻结特性需Q05。')
note('_h_enemy_energy_cost_up',STATE,'duration存临时mod+used/other技能名；永久只attack/all。临时amount未调cost_invert/double、未知filter落空，持续本回合是否计入需Q04。')
note('_h_mirror_damage','data/伤害数值计算.md:6-24；data/wiki/skills.csv:96','I09听桥反射对方原始伤害而非以自身物攻/武系/对方防御按等技能威力重新算，ctx.damage0即无反击；直接扣HP判死。')
note('_h_counter_override','data/wiki/game_descriptions.csv:2','直接毒层-=from+=to，不检查敌免疫/实际先前已加层；反应原文若只替换本技能施加必须保留原有层，I04协同待具体免疫场景。')
note('_h_passive_energy_reduce_water_ring','data/wiki/skills.csv:400','I08 only rangeall，现能量守恒rangeadjacent直接无动作；全范围路径公开modifier不记录T07-I04。')
note('_h_permanent_mod_ability',STATE,'per_counter按当前count以_ability_base_power绝对重算；positions/elements过滤、全局公开delta；无skill按positions或全技能委派，不把counter总量归属/绝对覆盖其他永久状态判正确，T07 Q04同类。')
note('_h_counter_attack _h_counter_status _h_counter_defense','data/wiki/game_descriptions.csv:16-18','仅把容器加入counter_effects等待外层按类别应对；类别优先/失败不触发/count/冷却T04/T07；包装协议已读，不完整通过。')

# 问题仅给实际涉及的代码范围结论，整个函数的其他分支保持规则存疑。
DEFECTS=[(28,146,'T08-I11'),(178,196,'T08-I07'),(260,261,'T08-I01'),(270,272,'T08-I04'),(332,334,'T08-I05'),
         (487,507,'T08-I04'),(511,523,'T08-I07'),(527,534,'T08-I06'),(580,588,'T08-I04'),
         (592,605,'T08-I05'),(660,714,'T08-I10'),(851,869,'T08-I02'),(881,900,'T08-I02'),(943,955,'T08-I09'),(969,975,'T08-I08')]
WRAPPERS={n.name for n in FUNCTIONS if n.name.startswith('_h_') and n.end_lineno-n.lineno==1 and '_mark' in n.name}


def write_csv(name,rows,fields):
    """输出UTF-8 CSV。"""
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def nested_tags(value):
    """遍历配置树保留每个原语及参数。"""
    if isinstance(value,list):
        for item in value:yield from nested_tags(item)
    elif isinstance(value,dict):
        if 'type' in value:yield value
        for key,item in value.items():
            if key!='type' and isinstance(item,(dict,list)):yield from nested_tags(item)


def run():
    """保存所有分配行、函数与原文对象的检查范围。"""
    assert set(NOTES)=={f.name for f in FUNCTIONS},set(f.name for f in FUNCTIONS)-set(NOTES)
    base=list(csv.DictReader((OUT/'assigned_inventory.csv').open(encoding='utf-8-sig')))
    objects=json.loads((OUT.parent/'T06/objects.json').read_text(encoding='utf-8'))
    old={r['item_id']:r for r in csv.DictReader((OUT.parent/'T06/object_review.csv').open(encoding='utf-8-sig'))}
    probes={r['item_id']:r for r in json.loads((OUT/'object_probe.json').read_text(encoding='utf-8'))}
    references=defaultdict(list);resolutions=[];parameters=[]
    issue_names={'心灵洞悉':'T08-I06','听桥':'T08-I09','能量守恒':'T08-I08','惊雷':'T08-I03','沙涌':'T08-I02','冰锋横扫':'T08-I10','钢钻':'T08-I10','洗礼':'T07-I09（T08入口协同；T07/cleanse_probe_output.json）','除厄':'T07-I09（T08入口协同；T07/cleanse_probe_output.json）'}
    for obj in objects:
        configs=[];handlers=[]
        for tag in nested_tags(obj.get('config')):
            selected=None
            for enum,handler in _HANDLERS.items():
                if enum.name==tag['type']:selected=handler;break
            if obj['kind']=='ability':
                for enum,handler in _ABILITY_HANDLER_OVERRIDES.items():
                    if enum.name==tag['type']:selected=handler;break
            if selected and selected.__module__.endswith('handlers_skill'):
                handlers.append(selected.__name__);configs.append(tag)
                references[selected.__name__].append(obj['item_id']+':'+obj['name'])
                parameters.append({'item_id':obj['item_id'],'name':obj['name'],'handler':selected.__name__,
                                   'tag':tag['type'],'params':json.dumps(tag.get('params',{}),ensure_ascii=False),
                                   'original_clause':obj['description'],'review':NOTES[selected.__name__][1],
                                   'evidence':'static_review.csv；只有probe具名对象有独立参数运行'})
        if not handlers and obj['kind']!='skill':continue
        previous=old[obj['item_id']]['conclusion'];new=previous
        evidence='static_review.csv；T06/object_review.csv及skill_probe.json（复用输入与中性输出，不证明边界）'
        detail='逐配置原语关联本文件；复杂条件、阶段、附加子句未完整证实，保留原结论。' if handlers else '已读原文与完整配置树，本文件无执行原语；保留T06配置结论，不能据此通过或称未上线。'
        issue=issue_names.get(obj['name'],'')
        if issue:
            new='确认缺陷';evidence=('T07/cleanse_probe.py；T07/cleanse_probe_output.json；' if issue.startswith('T07-I09') else 'probe_output.json；')+issue
            detail='本轮原语边界已确认至少一处完整原文不满足；不是全技能其他子句通过。'
        if obj['item_id'] in probes:
            probe=probes[obj['item_id']]
            evidence='object_probe.json#'+obj['item_id']
            detail=probe['limits']+'；字段'+probe['field']+'预期'+str(probe['expected'])+'实际'+str(probe['actual'])
            if not probe['matches']:new='确认缺陷';detail+='；配置/原文漂移归T06-I02/I03协同'
            else:detail+='；仅此原语子句通过，不升级完整技能结论'
        resolutions.append({'item_id':obj['item_id'],'name':obj['name'],'prior_conclusion':previous,'new_conclusion':new,
                            'handlers':'|'.join(sorted(set(handlers))),'rule_basis':obj['source']+'原文:'+obj['description'],
                            'implementation':json.dumps(configs,ensure_ascii=False),'method':'全配置子树关联+逐函数静态；标明对象才独立运行',
                            'evidence':evidence,'notes':detail,'reachability':'已有'+obj['config_source']+'配置；不等同所有参数实战可达'})
    write_csv('object_resolution.csv',resolutions,list(resolutions[0]))
    write_csv('parameter_review.csv',parameters,list(parameters[0]))
    static=[]
    for function in FUNCTIONS:
        rule,review=NOTES[function.name]
        static.append({'function':function.name,'line':function.lineno,'end_line':function.end_lineno,'rule_basis':rule,'review':review,
                       'objects':'|'.join(sorted(set(references[function.name]))),'runtime_evidence':'probe_output.json仅具名输入；其他分支静态已读不冒充动态覆盖'})
    write_csv('static_review.csv',static,list(static[0]))
    coverage=[]
    duplicates=Counter(row['item_id'] for row in base)
    for index,row in enumerate(base):
        line=int(row['line']);function=next((f for f in FUNCTIONS if f.lineno<=line<=f.end_lineno),None)
        conclusion='规则存疑';rule=CONTRACT;review='文件所有73函数及分支已静态阅读；具体缺口和有限范围见static_review.csv。'
        implementation=SOURCE+':'+str(line);objects_text='全技能配置中本文件可执行原语'
        if function:
            rule,review=NOTES[function.name];objects_text='|'.join(sorted(set(references[function.name]))) or '当前配置未引用；不以不可达掩盖实现待证实'
            if function.name in WRAPPERS:conclusion='通过'
            for start,end,issue in DEFECTS:
                if start<=line<=end:
                    review=issue+'；'+review
                    if row['kind']=='code_object':conclusion='确认缺陷'
        if row['kind']=='code_branch':
            review+='；本行表达式静态核对方向='+row['name']+'；'+row['description']+'；共享证据不表示该子条件已动态走到'
        if duplicates[row['item_id']]>1:review+='；基线同源行多个表达式ID碰撞：保留全部行ordinal='+str(index)+'，主协调T00拆后缀，不宣称逐子条件运行'
        coverage.append({'item_id':row['item_id'],'conclusion':conclusion,'rule_basis':rule,'implementation':implementation,
                         'objects':objects_text,'method':'逐函数/每分配表达式双向静态；具名probe边界运行',
                         'evidence':'static_review.csv#'+(function.name if function else 'file')+'；issues.md；probe_output.json',
                         'notes':review,'reachability':'已有配置见objects；无引用则实现待证实，与正确性结论分列'})
    fields=['item_id','conclusion','rule_basis','implementation','objects','method','evidence','notes','reachability']
    write_csv('coverage.csv',coverage,fields)
    extra=[]
    for name in ('POSITIVE_MARKS','NEGATIVE_MARKS','_WEATHER_DAMAGE_TYPES','_WEATHER_IMMUNE_TYPES'):
        line=next(i for i,text in enumerate(LINES,1) if text.startswith(name+' ='))
        extra.append({'item_id':'SEM:'+SOURCE+':'+name,'kind':'semantic_constant','name':name,'owner':'T08','source':SOURCE,'line':line,
                      'parent_id':'FILE:'+SOURCE,'description':LINES[line-1],'reachability':'印记分类使用；天气两个常量当前无消费者，不能称未上线'})
    write_csv('inventory_extra.csv',extra,list(base[0]))
    for row in extra:
        coverage.append({'item_id':row['item_id'],'conclusion':'规则存疑','rule_basis':'data/wiki/game_descriptions.csv:37-38,41,50',
                         'implementation':SOURCE+':'+str(row['line']),'objects':row['name'],'method':'常量集合与实际消费者静态对照',
                         'evidence':'static_review.csv；probe_output.json#poison_mark_slot_bypass','notes':'分类定义已读；普通毒印记绕过负面槽；两个天气常量不控制真实调用guard',
                         'reachability':row['reachability']})
    write_csv('coverage.csv',coverage,fields)
    summary={'assigned_rows':len(base),'assigned_unique_ids':len(set(r['item_id'] for r in base)),'functions':len(FUNCTIONS),
             'extra':len(extra),'coverage_rows':len(coverage),'conclusions':dict(Counter(r['conclusion'] for r in coverage)),
             'object_resolution_rows':len(resolutions),'prior_pending_objects':sum(r['prior_conclusion']=='检查受阻' for r in resolutions),
             'parameter_rows':len(parameters),
             'upgraded_pending_to_pass':sum(r['prior_conclusion']=='检查受阻' and r['new_conclusion']=='通过' for r in resolutions)}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':run()
