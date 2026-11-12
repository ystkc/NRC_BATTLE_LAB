"""整理已逐屏审阅的配置差异与可复现证据，不自动将非空配置判通过。"""
from extract import OUT, ROOT
import ast
import csv
import json
import re
from collections import Counter

OBJECTS = json.loads((OUT / 'objects.json').read_text(encoding='utf-8'))
PROBES = {x['name']:x for x in json.loads((OUT / 'skill_probe.json').read_text(encoding='utf-8'))}
ANNOTATIONS = {}
SIMPLE_CONFIG_MATCH = {'力量增效','加固','润泽','魔法增效','鼓劲','锐利眼神','霜降','霜冻','毒孢子','星轨裂变','超维投射','疫病吐息','主场优势','光合作用','打湿','棘刺','蓄势待发','降灵','风起','增程电池','甩水','耀眼','贪婪','勾魂'}
QUESTIONS = {'以重制重':'T06-Q01；体重到威力的定量映射未给出；当前只DAMAGE且无动态权重标签。','吨位压制':'T06-Q01；体重到威力的定量映射未给出；当前只DAMAGE且无动态权重标签。','砂糖弹球':'T06-Q01；双方体重差到威力的定量映射未给出；当前只DAMAGE且无动态权重标签。','闪击':'T06-Q02；速度比值到威力定量映射未知；当前只有DAMAGE。','鸣沙陷阱':'T06-Q02；物防比值到威力定量映射未知；当前只有DAMAGE。'}

def annotate(names, issue, notes):
    """保存人工复核后的对象差异。"""
    for name in names.split('、'):
        ANNOTATIONS[name] = (issue, notes)

annotate('丰饶', 'T06-I02', '原文双攻+140%；手写双攻1.3，仅130%。')
annotate('冰蛋壳', 'T06-I02', '原文减伤70%；手写pct=0.6。')
annotate('吓退', 'T06-I02', '原文减伤60%；手写pct=0.7。')
annotate('啮合传递', 'T06-I02', '原文速度+30且1/3号物攻+80%；配置speed=0.8、atk=1.0，两个数值均错。')
annotate('嘲弄', 'T06-I02', '原文魔攻+90%；手写spatk=0.7。')
annotate('恶意逃离', 'T06-I02', '原文应对防御使攻击技能能耗+4；手写amount=6。')
annotate('放晴', 'T06-I02', '原文光系永久威力50%/100%；手写两次0.4，变成40%/80%。')
annotate('气势一击', 'T06-I02', '原文上回合应对成功威力+180；手写bonus=240。')
annotate('水刃', 'T06-I02', '原文应对状态永久能耗-3；手写delta=-4。')
annotate('水环', 'T06-I02', '原文减伤60%；手写pct=0.7。')
annotate('沙涌', 'T06-I02', '原文沙暴8回合；手写turns=5。')
annotate('泡沫幻影', 'T06-I02', '原文减伤80%；手写pct=0.7。')
annotate('流星火雨', 'T06-I02', '原文每次击败永久威力+85；手写delta=75。')
annotate('火焰护盾', 'T06-I02', '原文应对攻击6灼烧；手写stacks=4。')
annotate('示弱', 'T06-I02', '原文萌化速度永久+130；手写speed=150。')
annotate('落雷', 'T06-I02', '原文每入场永久威力+40；手写delta=20。')
annotate('齿轮扭矩', 'T06-I02', '原文位置变化永久威力+15；手写delta=20。')
annotate('孢子', 'T06-I03', '原文3层寄生；生成stacks=1。')
annotate('咆哮', 'T06-I03', '原文敌物攻-60%及速度-60；生成atk=1.3，未配置速度。')
annotate('破防', 'T06-I03', '原文双防-70%；生成双防1.3，且应对冷却2回合为空。')
annotate('电离爆破', 'T06-I03', '原文敌魔攻-20%、速度-20、2连击；生成只有自身hit_count+3，目标/数值/附效均不符。')
annotate('芳香诱引', 'T06-I03', '原文连击数+2；生成+3；应对眩晕遗漏。')
annotate('聒噪', 'T06-I03', '原文攻击技能能耗+2持续3回合；生成amount=3。')
annotate('防反', 'T06-I03', '原文减伤70%及应对双攻+70%；生成60%和双攻40%。')
annotate('龙吟', 'T06-I03', '原文双攻150%速度80；生成双攻100%速度60，且蓄力未保留。')
annotate('力量吞噬、化劲、提气、盛开、羽化加速、防御反击', 'T06-I04', '原文全技能威力为固定点数；生成stat=power_pct并除100，改变为百分比。提气另漏换人额外+50；盛开另漏应对额外+30。')
annotate('偷师、寸拳、抓挠、火苗、种子弹、藤绞、虫网、风吹雪、鬼火、魔爪', 'T06-I05', '原文造成伤害并回复能量；当前生成只有DAMAGE，回复子句未配置。生成器基础回复匹配“恢复”而数据使用“回复”。')
annotate('氧输送', 'T06-I05', '原文回复4能量并魔攻70%；当前仅魔攻70%，无回能。')
annotate('移花接木', 'T06-I05', '原文回复15%生命后脱离；当前只有FORCE_SWITCH，漏治疗。')
annotate('不动如山、二律背反、冥想、冰墙、冰天雪地、冰点、剧毒、壁垒、天火、应激反应、强制重启、恶作剧、惊吓盒子、报复、持续高温、散手、有效预防、极寒领域、泥浆铠甲、淤泥表皮、淬火、炙热波动、热身、电磁偏转、羽翼庇护、虫结阵、蜡质膜、血气、追打、酶浓度调整、错乱、镜像反射、集中、雪替身、龙息环爆、龙血', 'T06-I06', '原文应对冒号后的非空附加效果，在ON_COUNTER中effects为空；仅保留了应对类别，成功应对不会产生这些效果。')
annotate('地陷', 'T06-I06', '应对状态配置威力翻倍，但原文额外物防+70%未配置。')
annotate('截拳', 'T06-I06', '应对只配置INTERRUPT，遗漏按被打断技能能耗回复能量。')
annotate('摇篮曲', 'T06-I06', '应对只配置INTERRUPT，遗漏敌方下回合眩晕。')
annotate('龙卷风', 'T06-I06', '原文应对状态威力1.5倍；ON_COUNTER为空；生成器倍数正则仅接受整数。')
annotate('滚雪球', 'T06-I06', '应对状态只配置威力翻倍，遗漏额外2层冻结。')
annotate('三连破、冰捆缚、星链、花炮', 'T06-I07', '原文本技能多连击效果被生成器转换为永久自身hit_count_mod加成；无DAMAGE的状态技能也应按本技能段数重复本技能效果，而非增强后续全部技能。')
annotate('多维击打、碎冰冰、腐化、鸩毒', 'T06-I08', '原文以已有印记/冻结/中毒为缩放条件；生成错误新增1层对应状态，且未配置所述动态连击/威力/减益缩放。')
annotate('坍缩、砂石冲撞', 'T06-I08', '原文增益有击败/敌方换人条件；生成PRE_USE无条件SELF_BUFF，提前且条件丢失。')
annotate('怒火、石肤术、钧势、跌落、炎打', 'T06-I08', '原文自身负面属性效果未配置；只保留正面属性/伤害/应对正面效果。')
annotate('燃尽', 'T06-I08', '原文按敌方失去生命缩放；生成condition=self_missing_hp_step，主体变为自己。')
annotate('回旋踢、坟场搏击、埋伏、反击拳、当头棒喝、灵光、疾风刺、破罐破摔、筛管奔流、背袭、贮藏、草虫冲击、虫击、触底强击、霜天、超新星馈赠', 'T06-I08', '原文动态条件/额外效果没有对应标签；当前只保留基础伤害/固定增益/固定状态。详见本对象完整原文与结构对照。')
annotate('山火', 'T06-I09', '原文每其他火技能使威力永久翻倍；手写delta=15的固定加法，增长规律错误。')
annotate('无畏之心', 'T06-I09', '原文应对把减免伤害转治疗并能耗+2；配置固定治疗30%最大生命，且POST_USE能耗+2无应对条件。')
annotate('生日蛋糕', 'T06-I09', '原文驱散己方减益并增益翻倍；配置却萌化降全技能能耗4，无清除或翻倍。')
annotate('赤子之心', 'T06-I09', '原文自己萌化且全技能能耗永久-2；配置场下全体萌化+自己40%治疗+4能量，无所述永久降耗。')
annotate('甜心续航', 'T06-I09', '原文双方萌化各回复40%生命；配置只对自己HEAL_HP并额外回复4能量。')
annotate('聚盐', 'T06-I09', '原文2连击各回复8%生命；手写只有一次5%治疗及额外1能量；后续hit_count+1未指定触发但本技能重复行为缺失。')
annotate('绵里藏针', 'T06-I09', '原文自己上回合未用攻击技，永久威力+20；配置delta30且trigger=per_enemy_no_damage_last_turn，条件主体错误。')
annotate('图书守卫者、构装契约者', 'T06-I10', '原文MP=1增益100%；配置buff=0.5，少一半。MP条件处理器直接使用此参数，无补偿。')
annotate('观星、坠星', 'T06-I10', '原文每星陨印记威力20%；配置bonus_pct_per_mark=0.15。观星另缺仅地系技能过滤。')
annotate('斗技', 'T06-I10', '原文应对后全技能威力永久+30；配置delta=20。')
annotate('蓄电池', 'T06-I10', '原文每入场永久双攻30%；配置20%，且永久保存机制需T09协同。')
annotate('超级电池', 'T06-I10', '原文每入场永久双攻40%；配置30%，且永久保存机制需T09协同。')
annotate('洄游', 'T06-I10', '原文每次蓄力永久能耗-2；配置reduce=1。')
annotate('指挥家', 'T06-I10', '原文应对成功永久双攻30%；配置只有atk=0.2，漏魔攻且物攻值错。')
annotate('自由飘', 'T06-I10', '原文每萌化连击+3；配置per=2。')
annotate('三鼓作气、鼓气', 'T06-I11', '原文双攻双防20%；buff仅atk和def各0.2，未配置spatk/spdef。')
annotate('毒牙', 'T06-I11', '原文成功施毒时敌物攻-40%速度-40；配置ON_USE_SKILL且spatk/spdef-40%，触发与目标属性均错。')
annotate('毒腺', 'T06-I11', '原文使用能耗≤1的技能；配置阈值5且handler使用actual_cost<5，能耗2/3/4也施毒。')
annotate('大捞一笔', 'T06-I12', '原文入场偷敌方场上所有精灵3能量；配置ON_TURN_END amount2。')
annotate('小偷小摸', 'T06-I12', '原文入场偷敌方场上所有精灵2能量；配置ON_ENEMY_SWITCH扣新入场精灵2能量，没有转给自身。')
annotate('吉利丁片', 'T06-I12', '原文离场给替换精灵双防20%冻结免疫；配置ON_ENTER给自己效果，目标及时点均反。')
annotate('先发制人、后发制人、伪造账单、天旋地转', 'T06-I14', '原文先手±1；生成/手写效果未编码自身优先级，平台仅初始化默认priority_mod=0；生成器解析出的priority_mod未输出。')
annotate('升龙咆哮、吹炎、怨力打击、龙之利爪', 'T06-I15', '原文需要蓄力；生成器解析skill.charge=True但skill_to_tags未输出此字段，平台不注入charge，技能在默认charge=False下立即使用。怨力打击同时遗漏蓄力期间受攻后的动态威力。')

def decision(obj):
    """应用逐项人工差异、空配置证据和已验证的基本攻击判据。"""
    name, kind, config = obj['name'], obj['kind'], obj['config']
    if name in ANNOTATIONS:
        issue, note = ANNOTATIONS[name]
        return '确认缺陷', issue + '；' + note
    if kind == 'skill' and 'exception' in PROBES[name]:
        return '确认缺陷', 'T06-I01；' + PROBES[name]['exception'] + '；effects内嵌SkillEffect而非EffectTag。'
    if not config:
        if kind == 'ability':
            return '未实现', '配置不存在；直接builder.py:626会拒绝保留原名的特性。但platform.py:159可能先抹去名称绕过拒绝，T11正在复现；此处不授予平台正确拒绝结论。'
        return '确认缺陷', 'T06-I13；完整原文有规则但实际effects=[]；技能存在即允许进入对战，执行零效果而未抛UnsupportedMechanicError。'
    if kind == 'skill' and re.fullmatch(r'对敌方精灵造成(?:物理|魔法)伤害。|造成(?:物伤|魔伤)，\d+连击。|造成(?:物伤|魔伤)，1连击。', obj['description']):
        result = PROBES[name]
        if config == [{'timing':'ON_USE', 'effects':[{'type':'DAMAGE'}]}] and result.get('output', {}).get('damage', 0) > 0:
            return '通过', '仅有伤害规则：核对DB类别/威力、平台连击元数据、单DAMAGE配置与实际伤害输出；未包含附加子句。'
    if kind == 'ability' and name == '秋收':
        return '规则存疑', 'T06-Q03；详解“秋收：草系环境.md”只说目前无草系环境、推测特殊天气；无法据此判整个特性明确未上线。当前环境条件不可达，空ON_TURN_START为保留接口。'
    if name in QUESTIONS:
        return '规则存疑', QUESTIONS[name]
    tags = [tag for entry in config for tag in entry.get('effects',[]) if 'type' in tag]
    types = {tag['type'] for tag in tags}
    if 'DRIVE' in types:
        return '确认缺陷', '协同T07-I05/T04：详解传动机制.md要求回合开始移位；当前配置POST_USE的DRIVE消费为后位被动触发，不移位；实证tasks/T07/probe_output.json:drive_position。'
    if kind=='skill' and 'AGILITY' in types and 'DAMAGE' in types:
        return '确认缺陷', '协同T07-I02：迅捷换入路径只计算DAMAGE返回值却不结算伤害；实证tasks/T07/probe_output.json:agility_damage。'
    if name in {'暴食','快锤'}:
        return '确认缺陷', '协同T07-I03：grant_agility只设置skill.agility=True，迅捷入口有effects时仅扫描E.AGILITY；实证tasks/T07/probe_output.json:granted_agility。'
    if name=='极限撕裂':
        return '确认缺陷', '协同T07-I07：配置self_hp_gt=0.5正确，但POST_USE入口不检查过滤，低HP仍惩罚；tasks/T07/probe_output.json:live_post_filter。'
    if name=='石头大餐':
        return '确认缺陷', '协同T04-I02：最大1000HP、能量1、耗4时以150HP补足后再次扣4能量，实际energy=-4；tasks/T04/repro_output.json:I02_hp_for_energy。'
    if name=='速冻':
        return '确认缺陷', '协同T04-I09：赋2减速印记配置本身匹配，但印记按比例替代每层速度-10，消费语义错误；tasks/T04/repro_output.json:I09_slow_mark。'
    if name=='龙威':
        return '确认缺陷', '协同T04-I10：赋龙噬配置匹配，但印记错误要求5耗即时增伤，未实现3耗后双攻40%；tasks/T04/repro_output.json:I10_dragon_mark。'
    if kind=='skill' and name in SIMPLE_CONFIG_MATCH:
        return '通过', '逐一核对原文单一数值/目标与配置，核对对应实际skill_probe输出；本项只授予本技能所述施加/回复效果，不宣称未来印记结算或全局免疫路径均正确。'
    return '检查受阻', '已逐条比较原文与完整时点/目标/参数结构；仍需处理器主责联审确认专名补偿、生命周期及全部条件路径，不能据非空或中性探针判通过。'

def write_csv(path, rows, fields):
    """写UTF-8台账。"""
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def main():
    """保存每个分配项和补充分支的检查状态。"""
    inventory = list(csv.DictReader((OUT / 'assigned_inventory.csv').open(encoding='utf-8-sig', newline='')))
    by_id = {o['item_id']:o for o in OBJECTS}
    by_name = {(o['kind'], o['name']):o for o in OBJECTS}
    fields = ['item_id','conclusion','rule_basis','implementation','objects','method','evidence','notes','reachability']
    cover, extra = [], []
    comparison_rows = []
    for obj in OBJECTS:
        conclusion, note = decision(obj)
        table = obj['kind'] + '_comparison.txt'
        line = 1 + sum(1 for o in OBJECTS[:OBJECTS.index(obj)] if o['kind'] == obj['kind'])
        source = 'nrc_core/effect_data.py' if obj['config_source'] == 'manual' else 'nrc_core/skill_effects_generated.py'
        comparison_rows.append({'item_id':obj['item_id'], 'name':obj['name'], 'description':obj['description'], 'config':json.dumps(obj['config'],ensure_ascii=False), 'conclusion':conclusion, 'notes':note, 'evidence':f'{table}:{line}'})
        obj['_evidence'] = f'{table}:{line}; objects.json; ' + ('skill_probe.json' if obj['kind']=='skill' else 'ability_probe.json（仅选定12项）')
        obj['_source'] = source
        obj['_decision'] = conclusion, note
        # 同一句中的逗号/选择分支单独列出，并保留完整句，避免丢失条件归属。
        parts = re.split(r'[，；。]|或(?=自己|敌方|应对|回复|连击|物攻|魔防|物防|获得|能耗)', obj['description'])
        if len([p for p in parts if p.strip()]) > 1:
            for index, part in enumerate((p for p in parts if p.strip()), 1):
                extra.append({'item_id':obj['item_id']+f':S{index:02d}', 'kind':obj['kind']+'_semantic_branch', 'name':obj['name'], 'owner':'T06', 'source':obj['source'], 'line':obj['line'], 'parent_id':obj['item_id'], 'description':part.strip() + '【完整规则：' + obj['description'] + '】', 'reachability':'继承对象；语义依赖完整条件，非独立自动通过'})
    for row in inventory + extra:
        item_id = row['item_id']
        base_id = row['parent_id'] or item_id
        while base_id not in by_id and ':' in base_id:
            base_id = base_id.rsplit(':',1)[0]
        obj = by_id.get(base_id)
        if obj:
            conclusion, notes = obj['_decision']
            implementation, evidence = obj['_source'], obj['_evidence']
            method = '原文逐屏审阅；完整结构展开；参数/目标/时点核对；技能中性执行；存在缺陷的对象子句保守继承，详见notes'
            reachability = '平台技能可选择；效果入口可达' if obj['kind']=='skill' else ('直接builder拒绝；平台规范化抹名绕过由T11核实' if not obj['config'] else '配置阶段可达；生命周期须协同')
            if item_id != obj['item_id']:
                notes += '；本子句继承对象级风险，不代表每个子句均单独出错；未对未触发路径授予通过。'
        else:
            conclusion, notes = '检查受阻', '已阅读完整文件与函数；独立源码分支未逐一完成输入边界实证。具体已确认问题见issues.md，不能按邻近函数或文件总体结论自动通过。'
            implementation, evidence, method, reachability = row['source'], '生成器全量内存比对regeneration_diff.json', '源码阅读与再生成比对', '开发脚本或配置工厂入口'
            source = row['source']
            line = int(row['line'] or 0)
            if source.endswith('generate_skill_effects.py') and (1130 <= line <= 1164 or 1212 <= line <= 1254):
                conclusion, notes = '确认缺陷', 'T06-I01；fallback把已是SE(...)的字符串当T(...)再次包ON_USE，导致嵌套SkillEffect，当前8技能执行异常。'
        cover.append(dict(zip(fields,[item_id,conclusion,row['source']+':'+row['line']+' '+row['description'],implementation,row['name'],method,evidence,notes,reachability])))
    write_csv(OUT/'coverage.csv', cover, fields)
    write_csv(OUT/'inventory_extra.csv', extra, list(inventory[0]))
    write_csv(OUT/'object_review.csv', comparison_rows, list(comparison_rows[0]))
    summary = {'assigned':len(inventory), 'extra':len(extra), 'coverage':len(cover), 'objects':dict(Counter(o['kind'] for o in OBJECTS)), 'object_conclusions':dict(Counter(r['conclusion'] for r in comparison_rows)), 'coverage_conclusions':dict(Counter(r['conclusion'] for r in cover))}
    (OUT/'checkpoint.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__ == '__main__':
    main()
