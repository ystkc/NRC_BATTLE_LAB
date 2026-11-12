"""从稳定清单输出逐项审计结论；保守保留未获规则证明的细分条件。"""
import ast
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent

ISSUES = [
    ('I01', 'P1', '技能/特性减伤晚于逐击公式取整', 'data/伤害数值计算.md:5,7,21', 'nrc_core/battle.py:1957-1973,2078-2101', 'I01_reduction', '威力10、攻防100、三连击、50%减伤；调用计算器后调用减伤接口。', '公式把减伤乘入威力，逐击4合计12；实际先得27再乘0.5取整为13。', '所有存在减伤的攻击，特别多段与低伤害；特性减伤也在最终整数后相乘。', 'T04主责，T07协同伤害原语'),
    ('I02', 'P1', '石头大餐用生命补能后重复扣完整能耗', 'data/wiki/spirits.csv:460,558-559', 'nrc_core/battle.py:1683-1720', 'I02_hp_for_energy', '最大生命1000、当前满血、能量1、技能耗4，设置hp_for_energy。', '扣150生命替代缺少3能量后应能量0；实际能量置0后又减4，得到-4。', '石头大餐精灵，负能量可继续干扰免伤、聚能与能耗判定。', 'T04主责，T06协同特性'),
    ('I03', 'P1', '50回合强制裁决未实现', 'data/README.md:37-42', 'nrc_core/battle.py:1278-1415,2316-2330; nrc_core/core.py:151-217', 'I03_turn50', 'turn=50，双方存活，MP为4:3，双方聚能。', '应以MP高者A胜；实际进入turn51，winner=None。runtime也无50回合兜底。', '全部拖到50回合的PvP；四指标全平的额外规则另列问题，不影响此反例。', 'T04主责，T03协同终局接口'),
    ('I04', 'P1', '脱离未检查本回合入场免疫', 'data/wiki/game_descriptions.csv:4,26', 'nrc_core/battle.py:607-666,2183-2202', 'I04_entry_immunity', 'turn7，当前精灵在burst_entry_turn中记录入场7，队伍有替补；调用脱离。', '应免疫脱离且索引不变；实际立即随机换入索引1。', '普通脱离与紧急脱离共用入口；换入后同回合可能再次脱离。', 'T04主责，T07协同脱离标签'),
    ('I05', 'P1', '奉献已获得层数在每次使用时重复写为永久强化', 'data/部分规则详解/奉献.md:1-4; data/wiki/skills.csv:101', 'nrc_core/battle.py:1762-1785', 'I05_devotion', '己方飞断奉献1层；受奉献影响攻击连续使用两次，不再获得新奉献。', '该1层应始终提供威力+20；实际skill_power_bonus从20变40，且修正写在精灵上可影响非受益技能。', '全部奉献受益技能及同精灵其他攻击；能耗、吸血、连击也采用累加写法。', 'T04主责，T07协同奉献授予'),
    ('I06', 'P1', '毒印/荆刺等直接扣血漏冻结实时力竭检查', 'data/wiki/game_descriptions.csv:5,15,20', 'nrc_core/battle.py:1080-1106,1120-1145,2104-2110', 'I06_freeze_mark', '最大HP1000，当前70，冻结1层，毒印1层；回合末结算。', '扣30后40低于冻结50应力竭；实际40且is_fainted=False。荆刺同样直接扣血不检查阈值。', '冻结精灵遭印记伤害；力竭、MP扣除和终局均可延迟。', 'T04主责，T02协同冻结模型'),
    ('I07', 'P1', '蓄电印记按入场回合而非首次行动生效', 'data/wiki/game_descriptions.csv:11,24', 'nrc_core/battle.py:1139-1145,1174-1180', 'I07_charge_mark', '入场回合1但尚未主动行动，当前turn2、_burst_pending=True，蓄电1层。', '首次攻击应得威力+10；实际entry_turn与turn不等故加成0。反向：同回合已聚能仍可能受益。', '中途换入后下一回合首次行动、多次使用与首次行动消耗。', 'T04主责'),
    ('I08', 'P1', '回合末先特性回血后状态伤害，与总规则相反', 'data/README.md:19-31; data/wiki/game_descriptions.csv:2', 'nrc_core/battle.py:761-816', 'I08_end_order', 'HP20/1000、中毒1层、回合末回复5%特性，调用turn_end_effects。', '状态30伤先结算应力竭；实际先回血50再扣30，剩40存活。双方末尾阶段也固定A→B，未按总规则拼速。', '全部回合结束特性、状态与先后相互影响；可改变生死与战果。', 'T04主责，T06协同特性阶段'),
    ('I09', 'P1', '减速印记错误采用比例减速', 'data/wiki/game_descriptions.csv:32', 'nrc_core/battle.py:533-542', 'I09_slow_mark', 'A速度200、1层减速；B速度185，无先手差。', 'A应200-10=190仍先；实际A速度乘0.9=180导致B先。', '所有减速印记及不同基础速度对局。', 'T04主责'),
    ('I10', 'P1', '龙噬印记触发能耗和效果均不符原文', 'data/wiki/game_descriptions.csv:31', 'nrc_core/battle.py:1162-1167,2205-2284', 'I10_dragon_mark', '龙噬1层，使用3耗攻击后读取双攻；另查询5耗攻击修正。', '3耗技能释放后应获得双攻40%；实际双攻仍0；反而5耗技能获得即时攻击倍率1.4。', '全部龙噬相关战斗，影响触发条件、永久/后续收益及初次伤害。', 'T04主责，T07协同印记原语'),
    ('I11', 'P1', '普通脱离被随机换人且不等待用户选择', 'data/README.md:28; data/wiki/game_descriptions.csv:4,26; data/wiki/skills.csv:372', 'nrc_core/battle.py:607-666,2183-2202', 'I11_ordinary_disengage', '移花接木仅配置其脱离原语，队伍有两个健康替补；分别seed0至4。', '普通脱离应暂停供本人选择；实际新索引为2,1,1,1,1且pending为空。紧急脱离原文指定随机，随机本身在该场景合法；两者不能混同。', '所有普通脱离，无论自身或强制敌方；后手动作打到未经选择的目标。', 'T04主责，T03协同动作/暂停恢复，T07协同标签'),
    ('I12', 'P0', '先手自力竭后未在回合内补位，后手动作被整段丢弃', 'data/README.md:28-32; data/wiki/skills.csv:154', 'nrc_core/core.py:187-188; nrc_core/battle.py:669-725,1360-1408,1438-1445', 'I12_midturn_replacement', 'A先手彗星消耗全部生命，A2健康，B选耗2攻击；通过simulate_turn执行。', '应暂停选择A2，入场后恢复本回合B技能；实际turn2、A仍死者索引0、待补位、B能量10且技能报告只有A。回调恒None使补位留到下一决策，后手看到敌方已死直接break。', '先手自毁/反伤等导致己方空场且未终局的回合；真实补位与剩余动作无法正确衔接。', 'T04主责，T03协同runtime恢复协议'),
]


# 最后逐行复核时发现“离场”原文明确排除力竭，保留事实但收回未获证明的预期。
ISSUES[0] = ISSUES[0][:3] + ('data/伤害数值计算.md:7,9,21',) + ISSUES[0][4:]
ISSUES[10] = ISSUES[10][:3] + ('data/README.md:27; data/wiki/game_descriptions.csv:4,26; data/wiki/skills.csv:372',) + ISSUES[10][4:]
ISSUES[11] = (
    'I12', '待裁决', '先手自力竭后后手动作跳过（规则存疑）',
    'data/README.md:27-31; data/wiki/game_descriptions.csv:40; data/wiki/skills.csv:154',
    'nrc_core/core.py:187-188; nrc_core/battle.py:669-725,1360-1408,1438-1445',
    'I12_midturn_replacement',
    'A先手彗星消耗全部生命，A2健康，B选耗2攻击；通过simulate_turn执行。',
    '实际turn2、A仍死者索引0、待补位、B能量10且技能报告只有A。若自力竭需要立即补位，则B行动被丢失；但README将力竭补位列在回合末，且术语离场排除力竭，目前不能把该预期判为确定规则。',
    '先手自毁/反伤导致己方空场且未终局；待明确后手攻击是否空过，以及B状态/聚能是否应继续。',
    'T04主责，T03协同runtime；须人工裁决',
)
ISSUES.extend([
    ('I13','P1','湿润印记被擅自消费并永久写入全队技能能耗','GAME_RULE:0032（湿润印记）；GAME_RULE:0010（印记）；data/wiki/game_descriptions.csv:23,41; data/状态分类.md:6','nrc_core/battle.py:1059-1077','I13_moisture','能耗5的场上与后排精灵，己方湿润印记1层；调用回合开始应用，再推进下一回合、驱散并换入后排。','首次印记变0、全队技能实值变4；第二回合仍4；驱散并换人后仍4。应保留阵营印记并仅在印记有效时享受-1；原文没有消耗或永久降低技能的子句。','所有湿润印记：可见层数、驱散/替换正面印记、后排及跨回合；不应猜消费机制。','T04主责，T00规则双向核对、印记handler协同'),
    ('I14','P1','沙暴凭空对全队追加1/16生命伤害','GAME_RULE:0030；data/wiki/game_descriptions.csv:37','nrc_core/battle.py:959-962; nrc_core/engine/handlers_skill.py:881-898','I14_sandstorm','双方及A后排均普通/非地非机械，HP1000，沙暴剩2回合；调用回合末。','权威描述仅双方地系技能耗半，无附加扣血规则；应均1000，实际场上A、后排、B均938。且代码凭空设置地/机械免疫与保底1。','所有沙暴回合的非地/机械全队精灵，包含后排；可能改变下一次上场生死。','T04调用入口协同，天气handler所属任务主责，T00发现'),
])
for index,ids in {3:'GAME_RULE:0037,0036',5:'GAME_RULE:0007,0002',6:'GAME_RULE:0042',8:'GAME_RULE:0009',9:'GAME_RULE:0054',10:'GAME_RULE:0037,0036',11:'GAME_RULE:0035'}.items():
    issue=ISSUES[index]
    ISSUES[index]=issue[:3]+(ids+'；'+issue[3],)+issue[4:]


def locations():
    """定位各清单条目的最小包围函数与真实源码行。"""
    result = {}
    for name in ('battle', 'core', 'rng'):
        path = ROOT / 'nrc_core' / (name + '.py')
        source = path.read_text(encoding='utf-8')
        funcs = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        result[f'nrc_core/{name}.py'] = (source.splitlines(), funcs)
    return result


def main():
    """生成逐ID覆盖、问题和方法边界，不将待核验条件冒充通过。"""
    sources = locations()
    with (HERE / 'assigned_inventory.csv').open(encoding='utf-8-sig', newline='') as stream:
        inventory = list(csv.DictReader(stream))
    ranges = [
        (1957,1974,'I01'),(2078,2103,'I01'),(1683,1720,'I02'),
        (607,668,'I11'),(669,727,'I12'),(1360,1408,'I12'),(1438,1445,'I12'),
        (1762,1785,'I05'),(1080,1108,'I06'),(1120,1138,'I06'),
        (1139,1146,'I07'),(1174,1180,'I07'),(761,816,'I08'),(533,542,'I09'),(1162,1167,'I10'),
        (1059,1077,'I13'),(959,962,'I14'),
    ]
    helper_proofs = {
        '_iter_flat_tags': ('配置形态适配；应对容器不得丢失', '空列表无标签；SkillEffect展开effects；原始EffectTag原样保留。逐项静态核对两种输入及循环空路径。'),
        '_has_tag_type': ('配置形态适配', '调用平铺后仅用any比较type；空输入False，存在匹配True，无匹配False。'),
        '_find_tags': ('配置形态适配', '平铺后保留全部且仅保留type匹配标签，无修改输入。'),
        '_ability_name': ('特性描述名适配', '无特性返回空；按冒号和中文括号截取名称，供显式特性匹配。此项仅验证字符串适配，不证明对应特性。'),
        '_is_burst_action': ('data/wiki/game_descriptions.csv:11', '迸发标记与首次行动pending共同控制，首次行动缺省True；仅证明此谓词，不证明蓄力/技能失败等调用方消耗时机。'),
        '_get_current_pokemon': ('data/README.md:19-32', 'a/b各取对应current索引，按当前场上精灵工作；无随机或名称搜索。'),
        '_get_skill_for_action': ('data/README.md:22-29', '非技能动作返回None；越界正索引返回None；正常索引返回当前技能。空动作约束由调用接口承担。'),
        '_skill_has_counter_for': ('data/wiki/game_descriptions.csv:16-18', '物攻魔攻映射attack，状态status、防御defense；逐个匹配ON_COUNTER/filter或旧COUNTER标签。仅谓词，不证明应对执行和扣能。'),
        '_check_pre_interrupt': ('data/wiki/game_descriptions.csv:12,16-18', '仅对应本技能类别的ON_COUNTER中的INTERRUPT使其返回True；无技能/无效果False。仅类别谓词，不证明对手合法或已行动。'),
        'get_priority': ('data/README.md:24-27; data/wiki/game_descriptions.csv:21', '换人99先于技能；聚能0；技能priority_mod加priority_stage。非法索引保护不作为合法动作证明。'),
        '_process_revive_timers': ('特性复活计时具体规则需逐精灵依据', ''),
    }
    questions = {
        '_apply_context_abilities': ('data/部分规则详解/安眠、松弛有度：时间规则.md:3-5', '时间上下文合法取值、安眠切换/夜间重新入场后的能耗恢复与魔术帽作用域需逐原文验证'),
        '_transform_to_guard_queen': ('保卫特性原文及形态数据', '变身的HP/能量/状态重置集合、缺catalog时静默返回、形态唯一映射未逐对象复现'),
        '_has_ko_threat': ('预警等特性原文；data/伤害数值计算.md', '威胁判定未纳动态能耗、天气、全部威力修正与对手实际减伤，需明确预警口径'),
        '_transfer_pokemon_state': ('data/状态分类.md:2-6', '复制状态白名单是否包含全部绑定状态及技能状态，需对照贪婪具体原文逐字段验证'),
        '_apply_pending_skill_transforms': ('data/wiki/game_descriptions.csv:42; data/部分规则详解/共鸣魔法.md:8', '巧变候选池未逐范围证明，需确认愿力冲击等排除项、空候选是否应抛UnsupportedMechanicError'),
        '_transform_scope_matches': ('data/wiki/game_descriptions.csv:42', '巧变范围描述仍由核心字符串解析；相关技能查description及未知scope能否误入候选池需逐原文核验'),
        'turn_end_effects': ('data/README.md:29-31; data/wiki/game_descriptions.csv:2-9,37-39', '此细分状态/特性/天气分支的层数衰减取整、重复次数、死亡阻断、免疫与结算先后需进一步逐原文证明；不能由总流程推为通过'),
        '_execute_with_counter': ('data/README.md:19-31; data/wiki/game_descriptions.csv:8,11,16-18', '此细分能耗/蓄力/迸发/入离场特性的独立条件及失败消耗时机未获逐对象规则证明'),
        '_execute_new_engine': ('data/README.md:24-31; data/伤害数值计算.md:5-21', '应对前置、扣血、击杀、离场与后处理顺序需逐相互作用验证；对手槽位在换人后是否仍指原技能亦需证明'),
        '_resolve_self_counters': ('data/wiki/game_descriptions.csv:16-18', '攻击型应对的原威力倍增层、重复次数、击杀后触发和特性顺序需逐技能原文验证'),
        '_resolve_enemy_counters': ('data/wiki/game_descriptions.csv:16-18', '非攻击应对在被攻击执行中触发，需证明主效果与应对增益、打断、后续离场均满足先结算规则'),
        '_post_skill_effects': ('data/README.md:24-31; data/部分规则详解/传动机制.md', '传动仅见使用后入口，已交T07主问题；其余每次使用永久变化/回复/重放分支需独立技能依据'),
        '_turn_start_skill_display': ('data/伤害数值计算.md:31-33', '面板是否囊括印记、迸发特性能耗、动态威力等全部已知量未逐技能证明，不能仅计算器被调用就判通过'),
        '_display_power': ('data/伤害数值计算.md:31-33', '该预览与实际伤害的所有可预知修正、连击是否一致需额外逐对象验证'),
        'calculate': ('data/伤害数值计算.md:5-21', '该细分特性增伤/木桶/多路径分支需对应特性原文与边界；基础公式通过不外推特性分支'),
    }
    rows = []
    for item in inventory:
        source = item['source']
        line = int(item['line'])
        lines, funcs = sources[source]
        enclosing = sorted((node for node in funcs if node.lineno <= line <= node.end_lineno), key=lambda node: node.end_lineno-node.lineno)
        function = enclosing[0].name if enclosing else '<file>'
        text = lines[line-1].strip()
        conclusion, rule, proof = '规则存疑', 'data/README.md:19-42；具体技能/特性原文待建立', '已完整静态读取；此独立条件尚缺可逐对象核对的规则与边界证据，保守不判通过'
        evidence = f'{source}:{line}：{text}'
        reach = '生产调用链可达；具体条件须按本行predicate满足'
        if function in questions:
            rule, proof = questions[function]
        if function in helper_proofs and helper_proofs[function][1]:
            conclusion = '通过'
            rule, proof = helper_proofs[function]
        if source.endswith('rng.py'):
            conclusion, rule, proof = '通过', 'data/README.md:13；上下文随机源隔离约定', '静态核对ContextVar作用域finally复原、choice固定候选tuple、randrange沿Python半开区间、shuffle原地；repro P01证明同seed相同输出且无越出候选。仅工具语义，不证明调用场景允许随机。'
        if source.endswith('battle.py') and function == 'calculate' and line <= 385:
            conclusion, rule, proof = '通过', 'data/伤害数值计算.md:5-21; data/wiki/game_descriptions.csv:39', '逐式对照37/41、半向上四舍五入再除防御向下取整、保底1、同系1.25与雨天1.75；物魔分别取对应增减益。repro P02中10威力/攻防100独立计算为9。木桶分支只作整体规则存疑。'
            if 316 <= line <= 320:
                conclusion, proof = '规则存疑', '木桶使攻击方和防御方克制同时失效的具体原文需验证，不能由基础公式推导。'
        if function == 'check_winner':
            conclusion, rule, proof = '规则存疑', 'data/README.md:35-42', '正常单方MP清零/单方全灭符合立即终局；但双方同时清零/全灭固定判B缺少裁决依据，且50回合缺失见T04-I03。'
            if 2318 <= line <= 2327:
                conclusion, proof = '通过', '单方MP清零先判负，或单方全队倒下判负，逐式对应README。repro P03：MP A0返回b。此项不外推双方同时败北。'
        related = [issue for start,end,issue in ranges if source.endswith('battle.py') and start <= line <= end]
        if item['kind'] in ('file','code_object'):
            fn_start = enclosing[0].lineno if enclosing else 1
            fn_end = enclosing[0].end_lineno if enclosing else len(lines)
            related = sorted({issue for start,end,issue in ranges if source.endswith('battle.py') and fn_start <= end and start <= fn_end})
            if function == 'check_winner' or (source.endswith('core.py') and function in ('simulate_turn','<file>')):
                related.append('I03')
                if source.endswith('core.py'):
                    related.append('I12')
        if related:
            conclusion = '确认缺陷'
            proof = '；'.join('T04-' + key for key in dict.fromkeys(related)) + '，参见issues.md的规则、最小输入与预期实际；并非本函数全部分支均有缺陷'
            evidence += '；repro.py + repro_output.json'
            rule = '；'.join(issue[3] for issue in ISSUES if issue[0] in related)
            if set(related) == {'I12'}:
                conclusion = '规则存疑'
        if function in ('get_actions','_is_first_action'):
            conclusion, rule, proof, reach = '规则存疑', 'data/README.md:19-31；具体动作规则待证实', 'rg搜索nrc_core/nrc_platform/nrc_server仅有定义，无生产调用；可达性单列，不豁免规则检查。get_actions仍按静态skill.energy_cost过滤，不能代表runtime合法动作；_is_first_action会重新比较顺序，同速可重新随机，尚须独立核验。', '当前生产未引用'
        if source.endswith('core.py') and item['kind']=='code_branch' and 187 <= line <= 188:
            conclusion, rule, proof = '规则存疑', 'data/README.md:27-31; data/wiki/game_descriptions.csv:40', 'T04-I12：回调恒None，先手自力竭后后手动作跳过。术语离场排除力竭，需先裁决自力竭后补位时机，不能外推普通脱离规则。'
        rows.append(dict(item_id=item['item_id'], conclusion=conclusion, rule_basis=rule,
            implementation=f'{source}:{line} {function} | {item["description"]}', objects=function,
            method='完整静态核对；附独立最小复现的条目见evidence', evidence=evidence,
            notes=proof + '；本行方向=' + item['name'], reachability=reach))
    with (HERE/'coverage.csv').open('w',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    data = json.loads((HERE/'repro_output.json').read_text(encoding='utf-8'))
    report = ['# T04 问题记录', '', '所有复现只操作内存状态；业务代码、数据库均未修改。完整输入见repro.py，实际输出见repro_output.json。I01至I11及I13至I14为P1确定规则偏差；I12单列已复现事实与尚待裁决预期。GAME_RULE为稳定数据库规则ID，CSV冒号数字是当前文件物理行，两者不是同一编号。', '']
    for key,severity,title,basis,code,output,steps,behavior,impact,owner in ISSUES:
        report.extend([f'## T04-{key} {title}', '', f'- 严重度：{severity}；主责协同：{owner}', f'- 规则依据/原文行号：{basis}', f'- 代码位置：{code}', f'- 最小输入步骤：{steps}', f'- 预期与实际：{behavior}', f'- 影响范围：{impact}', f'- 证据：repro.py中{output}；repro_output.json对应结果：`{json.dumps(data[output],ensure_ascii=False)}`', ''])
    (HERE/'issues.md').write_text('\n'.join(report),encoding='utf-8')
    counts = dict(Counter(row['conclusion'] for row in rows))
    (HERE/'report.md').write_text(f'''# T04 执行时序、伤害与随机审计

完整静态读取主责nrc_core/battle.py（2330行）、core.py、rng.py；跨文件只追踪runtime补位/终局与executor/handler接口，不代替其他任务完整审计。assigned_inventory共{len(rows)}项，coverage.csv保持每个稳定ID一行；分类计数：{json.dumps(counts,ensure_ascii=False)}。

方法：优先阅读全文data/README.md、伤害数值计算.md、状态分类.md及共鸣/奉献/时间详解；其次按具体子句核对game_descriptions、skills、spirits原文。逐函数和条件阅读全部主责源码，对伤害取整、终局、随机允许范围与中途补位构造内存反例。repro.py集中验证12个独立问题，实际运行退出0；输出同时含3个真实通过证据（固定seed、基础伤害公式、MP清零胜负）。复现无数据库访问，无产品生成输出覆盖。

运行命令：在仓库根目录设置PYTHONIOENCODING=utf-8和PYTHONUTF8=1后，python -m docs.battle_audit.20261112-132335-1bcaab0.tasks.T04.repro。随后运行同路径build_audit模块整理记录。

覆盖边界：逐ID记录表示每行均被静态检查，不等于每个分支已动态执行。通过仅限已建立独立依据的基础公式、结构适配、类别谓词、优先级和随机工具语义。复杂特性/状态细分未逐对象取得原文或边界证明的，明确保留规则存疑并在行内列具体待证点；未将存在代码/旧测试通过当作规则通过。函数级确认缺陷表示其含已确认缺陷，并不宣称所有内部条件都有缺陷。代码行相邻的真假分支共享同一独立规则证明，但保留独立ID与方向。日志/防御性输入分支未获游戏规则依据时亦不冒充规则通过。

发现13项确定问题及1项已复现但规则待裁决的行为，见issues.md。后补湿润跨回合/驱散/换人反例与沙暴全队凭空伤害反例，均实际运行，稳定GAME_RULE ID已附关键原文。50回合四指标全平、双方同时终局、自力竭是否立即补位属于缺少明确规则，见questions.md。减伤证明使用规则公式独立计算，并非回放旧脚本；脱离明确区分普通与紧急。自力竭反例直接经simulate_turn入口复现后手动作跳过，但术语离场排除力竭，因此不冒充已证明规则缺陷。get_actions、_is_first_action当前生产未引用仅记录在reachability，26条仍按规则存疑/待证实保留审计缺口，不视作未上线。

协同：迅捷执行丢弃damage由T07主责；传动仅发现battle.py:2223使用后调用execute_drive，无回合开始入口，已向主协调反馈并交T07主issue，未重复编号。生物电在扣费后退款、蓄力/失败时迸发机会消耗等保留逐对象验证点，未在本任务冒充已完整证明。
''',encoding='utf-8')
    print(json.dumps(dict(items=len(rows), conclusions=counts),ensure_ascii=False))


if __name__ == '__main__':
    main()
