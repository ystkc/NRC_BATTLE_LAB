"""合并已取得的具名协同证据，保留冻结原件及局部证据的边界。"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
TASKS = OUT.parent


def read_csv(path):
    """读取带中文的UTF-8台账。"""
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    """写入新增台账，不触碰原件。"""
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    """记录冻结证据的字节哈希。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


OBJECTS = json.loads((OUT / 'objects.json').read_text(encoding='utf-8'))
PRIOR = {r['item_id']: r for r in read_csv(OUT / 'object_review.csv')}
T08 = {r['item_id']: r for r in read_csv(TASKS / 'T08/object_resolution.csv')}
T09 = read_csv(TASKS / 'T09/clause_review.csv')
T10 = read_csv(TASKS / 'T10/semantic_review.csv')
FORMS = json.loads((TASKS / 'T10/unsupported_ability_forms.json').read_text(encoding='utf-8'))
BY_ID = {o['item_id']: o for o in OBJECTS}
BY_NAME = {o['name']: o for o in OBJECTS}
CLAUSES = defaultdict(list)
for index, row in enumerate(T09, 2):
    CLAUSES[row['ability']].append((index, row))

# 这些映射均指报告中明确的具名对象，不把同一handler全部action一起判错。
FINDINGS = defaultdict(list)


def add(names, issue, scope, evidence, config=False):
    """保存人工复核的具体反例和生效范围。"""
    for name in names.split('、'):
        if name not in BY_NAME:
            raise ValueError('对象名称未在822清单中找到：' + name)
        FINDINGS[name].append(dict(issue=issue, scope=scope, evidence=evidence, config=config))


add('丢冰块', 'T08:object_probe', '速度固定-30被配置为比例/错误数值；实际speed_down=0，不是预期30。', 'T08/object_probe.json#SKILL:0007', True)
add('乘风', 'T08:object_probe', '原文速度+120；中性执行speed_up=1.2，单位不符。', 'T08/object_probe.json#SKILL:0013', True)
add('超导加速', 'T08:object_probe', '原文固定速度+30；实际speed_up=0.3，固定点数被当比例。', 'T08/object_probe.json#SKILL:0480', True)
add('撕裂', 'T08-I01', '完整真实应对状态回合counter_success=true且造成76伤害，吸血100%却回复0；只证实应对吸血子句。', 'T08/probe_output.json#actual_counter_drain_撕裂')
add('汲取、蝙蝠、暗突袭', 'T08-I01', '配置连接LIFE_DRAIN通用消费者；其在最终实际伤害之前按原始伤害治疗，50%减伤通用反例吸90而实际伤45。是共享执行路径反例，未逐个完整回合运行，也不证明其他子句。', 'T08/parameter_review.csv; T08/probe_output.json#drain_before_reduction')
add('惊雷', 'T08-I03', '配置雷鸣存在，正常回合天气白名单阻止进入雷鸣末尾分支，双方引电0而应各1。', 'T08/probe_output.json#thunder_guard')
add('焚烧烙印', 'T08-I04', '将印记转灼烧的共享分支直接写层数，绕过火系免疫；通用每印记3层输入，火系带2印记被赋6灼烧。真实本技能参数每印记5层经同一分支，尚未独立运行此参数；仅转换免疫被证明。T08报告另称炎爆术不在本822清单，不扩造对象。', 'T08/probe_output.json#convert_fire_immune; T08/parameter_review.csv')
add('感染病、疫病吐息', 'T08-I05', '实际配置POISON_MARK直写普通负面印记，不走负面单槽替换；通用1层同参数反例保留spirit_mark=2同时赋poison_mark=1。感染病另有ON_HIT条件尚未完整回合实跑；其他子句不因此通过。', 'T08/probe_output.json#poison_mark_slot_bypass; T08/parameter_review.csv')
add('蚀刻', 'T08-I05', 'CONVERT_POISON_TO_MARK也直接写poison_mark且不执行通用负面印记单槽替换；静态完整写入分支与已实测POISON_MARK旁路相同，尚未独立运行本特性转换参数。仅单槽限制明确断链，时点/转换比例未升级通过。', 'T08/issues.md#T08-I05; T08/parameter_review.csv; nrc_core/engine/handlers_skill.py:592')
add('心灵洞悉', 'T08-I06', '星陨印记被实现为精灵meteor_stacks=2及3回合倒计时，阵营meteor_mark未赋。', 'T08/probe_output.json#marks_to_meteor_kind')
add('伪造账单', 'T08-I07', '回血反转倍数2在消费者中仅作布尔量；100治疗应损200，实际损100。', 'T08/probe_output.json#anti_heal_multiplier')
add('能量守恒', 'T08-I08', 'ON_COUNTER两侧永久减耗range=adjacent被应对专用handler忽略；[4,2,3]不变而应[3,2,2]。', 'T08/probe_output.json#adjacent_counter_reduce')
add('听桥', 'T08-I09', '反击直接镜像对手原始伤害90，未按自身物攻及武系等威力计算；独立有理数规则期望288。', 'T08/probe_output.json#mirror_raw_damage; T08/independent_oracle_output.json')
add('冰锋横扫、钢钻', 'T08-I10', '真实配置动态威力condition没有handler分支，基础占位威力1直接造成1伤害；两条件为enemy_total_cost/adjacent_power_sum。', 'T08/probe_output.json#actual_dynamic_冰锋横扫; T08/probe_output.json#actual_dynamic_钢钻')
add('洗礼、除厄', 'T07-I09', '真实完整effects只清atk_down；毒/烧/冻/寄生/萌化/引电和全局加耗/负威力均保留。印记及特性组合状态保留控制正确。', 'T07/cleanse_probe_output.json; T08/object_resolution.csv')
add('退化、王子的诺言', 'T07-I10', '真实退化赋萌化给王子特性，萌化被快照分类为增益，2耗变1；按减益应变3。仅此组合分类反例，不证明所有萌化来源。', 'T07/cleanse_probe_output.json; T07/issues.md#T07-I10')

add('涂鸦、目空、夺目、绒粉星光、偏振、缩壳', 'T09-I02', '当前具名倍率/分类分支使用旧模型字段或不存在.types模块；PASSIVE无skill早退且不安装持续标记，带skill则前四类报错；缩壳字符串比较枚举导致防御减耗不生效。各原语具体输入见T09，不把错误扩及其他action。', 'T09/probe_output.json#non_stab/non_light/non_weakness/resist_same_type/defense_enum; T09/issues.md')
add('灰色肖像', 'T09-I03', 'debuff_stack_bonus=3只写无消费者；ON_ENTER后普通atk-.1仍.1，未触发已有减益+3。完整攻击事件未另跑。', 'T09/probe_output.json#gray_portrait; T09/clause_review.csv')
add('变形活画', 'T09-I03', 'handler写bonus_pct_per_cost，伤害读取bonus_pct_per_layer默认0；敌10层增益伤害90仍90，速度仅展示无计算。不是仍按敌能耗计算。', 'T09/probe_output.json#paint; T09/clause_review.csv')
add('圣火骑士、起飞加速、振奋虫心、囤积、全神贯注、月牙雪糕、威慑、破空、顺风', 'T09-I04', '具名原语写持久flag或PASSIVE临时context但标准回合没有消费者；圣火骑士/破空有运行反例，其余为全核心写读搜索的直接静态断链，未各跑完整回合。不能据同名替代compute action推及全部first_strike。', 'T09/issues.md#T09-I04; T09/static_review.md; T09/probe_output.json#double_next/first_strike_context')
add('观星、坠星', 'T09-I04', 'PASSIVE写context.power_multiplier，下一次攻击不消费该上下文；已有T06数值缺陷之外，临时倍率链也不连通。', 'T09/issues.md#T09-I04; T09/static_review.md')
add('防过载保护、奔波命、警惕、星地善良', 'T09-I05', '写auto_switch_eot/force_switch而标准切换消费其他键；防过载flag真仍不切换，其余同消费者键错配静态证明，另保留行动后/回合后时点差异。', 'T09/probe_output.json#auto_switch; T09/issues.md#T09-I05')
add('最好的伙伴', 'T09-I06', '无伤害火系STATUS对草系，ON_USE_SKILL仍+1层和2能，违反造成克制伤害后；真实0伤害攻击组合未跑。', 'T09/probe_output.json#best_partner_status', True)
add('双向光速、电流刺激、连续负荷、超负荷、陨落', 'T09-I07', '固定被动在重复PASSIVE中用+=累加；双向光速真实两回合repeat1→2，电流刺激40→80、连续负荷1→2；另两项同明确+=分支静态关联，后续迸发全流程未逐项实跑。', 'T09/issues.md#T09-I07; T09/probe_output.json#repeat_accumulates')
add('充分燃烧', 'T09-I09', '灼烧1→2后按4%而非2%触发，1000最大HP多扣至80而应40。', 'T09/probe_output.json#burn_tick')
add('衡量', 'T09-I10', '复制敌增益漏全技能威力/吸血等且额外取max当前能量；敌能10/威力+20，己方能变10但威力0。已有同类max或叠加仍存疑。', 'T09/probe_output.json#balance; T09/clause_review.csv')
add('虫群突袭、虫群鼓舞', 'T09-I11', '原文入场攻防速15%/10%；配置PASSIVE且handler只加双攻，ON_ENTER无效果。虫存活/力竭计数另未完整验证。', 'T09/source_correction_probe_output.json; T09/clause_review.csv', True)
add('毒牙、毒腺', 'T09-I11/T06-I11', '毒牙对已有毒但本次未施毒的普通攻击错误减魔攻魔防，原文成功施毒减物攻速度；毒腺<=1配置为<5，实测3耗仍加4毒。基础/实际成本细节另限。', 'T09/source_correction_probe_output.json', True)
add('刺肤', 'T09-I12', '50威力物理被直接作为固定50HP；反击者物攻100/200目标均500→450。未知系别不影响威力与固定HP不同的反例。', 'T09/source_correction_probe_output.json#刺肤_100/200')

add('游弋', 'T09:专名核对', 'PASSIVE无条件双防100%，没有蓄力时自由选择任一携带技能，防御获得条件亦丢失。', 'T09/clause_review.csv; T09/static_review.md', True)
add('腐植循环', 'T09:专名核对', '按回合末固定回复5%生命，不消费每回复1能量事件。', 'T09/clause_review.csv; T09/static_review.md', True)
add('耐活王、仁心', 'T09:专名核对', '依自身HP和敌异常层数回复，不取敌实际中毒/灼烧伤害事件的等量值。', 'T09/clause_review.csv; T09/static_review.md', True)
add('慢热型、地脉、散热', 'T09:专名核对', '入场set_to=0并监听自身之后ON_USE/ON_COUNTER，不累计入场前己方对应成功应对/地火技能事件。', 'T09/clause_review.csv; T09/static_review.md', True)
add('贪心算法', 'T09:专名核对', '没有1号位过滤/传动1授予；当前任意槽使用后可灼烧。', 'T09/clause_review.csv; T09/static_review.md', True)
add('夺目', 'T09:专名核对', '缺额外获得3个未携带随机技能，只配NON_LIGHT且此倍率消费者也断链。随机池细节不影响整个授予分支缺失。', 'T09/clause_review.csv; T09/issues.md#T09-I02', True)

add('假寐、飞断、虫茧、捆缚、虫群过境', 'T10-I01', '指定奉献不检上限，飞断5→6或其他10→11；只确认指定奉献上限，非每个其他子句。', 'T10/probe_output.json#devotion_explicit_cap_假寐/飞断/虫茧/捆缚/虫群过境')
add('花精灵、坚韧铠甲', 'T10-I01', '随机候选未剔除满层，5层飞断仍被选浪费；全满仍抽。仅随机授予共用分支，具体触发条件另待验证。', 'T10/probe_output.json#_h_devotion_grant_random_capped/_h_devotion_on_hit_capped/devotion_all_full')
add('折射', 'T10-I02/I03/I04', '系别set去重并排除自身光，多个同系技能只触发一次；幻写精灵星陨而非印记，火毒绕免疫，地固定-40误比例。18分支见逐候选表。', 'T10/semantic_review.csv; T10/probe_output.json#refraction_duplicate_fire/refraction_PSYCHIC/refraction_type_immunity_FIRE')
add('契约的形状', 'T10-I05/I06', '前三球速度百分比作固定值；淘沙固定减速作比例；柔软18候选中9候选复用整包而非单效果，随机重入生命周期仍存疑。', 'T10/semantic_review.csv; T10/probe_output.json#contract_普通咕噜球/soft_skill_power')
add('稀兽花宝', 'T10-I07', '18血脉仅萌分支，其他17没有对应效果，配置入口固定fairy。不是因无当前配置称未上线。', 'T10/semantic_review.csv; T10/probe_output.json#bloodline_普通', True)
add('反弹', 'T10-I08', '转移萌化只清层数，不恢复本体形态和属性；合法链退化后转移可复现。', 'T10/probe_output.json#_h_cute_transfer')
add('示弱', 'T10-I09', '萌化永久速度叠加后下次退化覆盖基础速度导致永久增益丢失，独立于T06配置150vs130。', 'T10/probe_output.json#cute_permanent_speed_next_gain')
add('月光合奏', 'T10-I10', '本次连击加成写回skill.hit_count，重复使用永久累加，影响队伍场下技能。', 'T10/probe_output.json#cute_team_power_twice')
add('化茧', 'T10-I11', '致命免疫结果blocked_lethal未传播，预先置HP1又结算伤害，且没有2次上限；并非已正确免疫。', 'T10/probe_output.json#cute_lethal_consumer/cute_lethal_three_calls')
add('翼轴、机械变式', 'T10-I12', 'extra_drives/drive_on_position_change_reduce写入无消费者，协同T07传动主问题；未实现不得静默。', 'T10/probe_output.json#drive_flags; T10/issues.md')
add('系统发育', 'T10-I13', '100治疗完整回合向3只场下各复制100，总300；并非将实际收益分配。', 'T10/probe_output.json#share_gains_full_turn')

add('隐藏条款、愿力冲击', 'T05-I02', '愿力替换后隐藏条款交换首槽，再按原主人固定位置还原，临时愿力技能遗留对方，原交换结果被覆盖；仅此组合。', 'T05/probe_output.json; T05/issues.md#T05-I02')
add('愿力冲击', 'T05-I01', '愿力合法动作先按原首槽成本过滤；原8耗/能3仍只允许蓄力，不能选择替换后的2耗技能，也不能自由不用。', 'T05/probe_output.json; T05/issues.md#T05-I01')
add('正位宝剑、宝剑王牌', 'T05-I06', 'skill_slot_lock没有进入合法动作过滤，非首槽仍合法但执行后静默改蓄力。', 'T05/probe_output.json; T05/issues.md#T05-I06')
add('流沙、石锁', 'T05-I07', '禁足状态/合法动作限制未表示；真实流沙执行后有健康替补仍可主动离场。石锁为同无禁足实现静态关联，未各完整回合运行。', 'T05/probe_output.json; T05/issues.md#T05-I07', True)
add('补觉', 'T05-I08', '仅保存selected_choice字符串；真实两个选项均无对应治疗/回能，实际HP500能1。', 'T05/probe_output.json; T05/issues.md#T05-I08')
add('抓到你了', 'T05-I04/I09', '真实新对局未触发初始ON_ENTER冻结/加耗；替补入场冻结力竭不扣MP。只证实入口和入场力竭交易，非特性所有条件。', 'T05/probe_output.json; T05/issues.md#T05-I04/T05-I09')
add('盲拧、契约的形状', 'T05-I05', '初始化/补位/下一回合准备随机在局部种子域外；相同局部seed受外部全局random状态影响。只指已有具名shuffle/softball入口。', 'T05/probe_output.json; T05/issues.md#T05-I05')
add('拍击', 'T02-I04', 'catalog可解析稳定ID skill_000303，但builder仅传该ID拒绝；名称路径又改写ID。不是核心DAMAGE配置反例。', 'T02/probe_output.json; T02/issues.md#T02-I04')
add('假寐', 'T02-I08', '奉献cost_reduce规范化为不存在名称假寥，seed2随机初始化KeyError；与指定奉献层上限是独立问题。', 'T02/probe_output.json; T02/issues.md#T02-I08')


def walk_tags(value):
    """展开嵌套效果，保留参数和结构。"""
    if isinstance(value, dict):
        if 'type' in value:
            yield value
        for child in value.values():
            yield from walk_tags(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_tags(child)


def code_index():
    """只用AST建立当前原语到函数位置，不导入业务模块。"""
    functions, handlers, names = {}, {}, {}
    for path in (ROOT / 'nrc_core/engine').glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[node.name] = f'{path.relative_to(ROOT).as_posix()}:{node.lineno}:{node.name}'
        if path.name == 'registry.py':
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if isinstance(key, ast.Attribute) and isinstance(value, ast.Name):
                            handlers[key.attr] = value.id
    for relative in ['nrc_core/effect_data.py', 'nrc_core/skill_effects_generated.py']:
        tree = ast.parse((ROOT / relative).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in BY_NAME:
                names.setdefault((relative, node.value), node.lineno)
    return functions, handlers, names


FUNCTIONS, HANDLERS, NAME_LINES = code_index()


def implementation(obj):
    """列出本对象实际配置的消费者，不将存在性作为通过证据。"""
    file = 'nrc_core/effect_data.py' if obj['config_source'] == 'manual' else 'nrc_core/skill_effects_generated.py'
    parts = [f"{file}:{NAME_LINES.get((file, obj['name']), 1)}"]
    for tag in walk_tags(obj['config']):
        name = tag['type']
        fn = HANDLERS.get(name)
        part = FUNCTIONS.get(fn, f'{name}:未在registry注册（需核对battle特判，INTERRUPT不能直接判缺失）')
        if part not in parts:
            parts.append(part)
    return '；'.join(parts)


def validation_plan(obj):
    """按具名配置参数给出尚缺的最小边界输入，不再等待其他任务。"""
    tags = list(walk_tags(obj['config']))
    types = {t['type'] for t in tags}
    plans = []
    if obj['kind'] == 'ability':
        plans.append('同一特性初始入场/替补再入场；同回合触发0/1/2次；双方HP500/1000与能量0/1/5/10，分别比较事件前后和下回合持久值')
    if types & {'DAMAGE', 'CONDITIONAL_POWER', 'LIFE_DRAIN', 'GRANT_LIFE_DRAIN'}:
        plans.append('自身攻100/200、目标防100；单击/多击原始元数据；全局连击+2；50%减伤与低HP过量伤害；核对最终扣血/吸血及命中后时点')
    if any('BUFF' in t or 'DEBUFF' in t or 'MOD' in t or 'STACK' in t for t in types):
        plans.append('对应属性0/98/99层；已有正负同类复合状态；赋予后清除/复制/换入换出；只清普通可驱散项，核对固定点数和百分比单位')
    if any('HEAL' in t or 'ENERGY' in t or 'DRAIN' in t for t in types):
        plans.append('HP500/950/1000与能量0/9/10，分别有无2倍反转/收益复制；比较实际量与溢出量，双阵营及场下分配')
    if any('MARK' in t for t in types):
        plans.append('双阵营各已有普通正/负印记及独立吟游来源；施加替换、转移、清除与换人继承；核对阵营印记和精灵异常字段')
    if any('POISON' in t or 'BURN' in t or 'FREEZE' in t for t in types):
        plans.append('普通/毒/火/冰系及相应免疫特性分别为目标；0/1/多层及转换，核对成功施加事件和持续伤害消费者')
    if any('CUTE' in t or 'BLOODLINE' in t for t in types):
        plans.append('注入合法三级退化链及无前态链，自己/敌方/双方/全队含未出场；0/1/多层、上限、清除恢复、永久增益再萌化')
    if any('DEVOTION' in t or 'CONTRACT' in t or 'SHUFFLE' in t for t in types):
        plans.append('固定候选序列/seed，空候选/部分满层/全满层；阵营持久及再入场；跨两个runtime隔离，逐随机候选核对参数')
    if any(e.get('timing') == 'ON_COUNTER' for e in obj['config']):
        plans.append('能量足够且选择匹配/非匹配应对类别；目标先后手、打断成功/失败；逐ON_COUNTER附效与后置过滤器验证')
    if any('PERM' in t or 'PASSIVE' in t or 'AGILITY' in t or 'DRIVE' in t or 'CHARGE' in t for t in types):
        plans.append('同条件重复两回合及换位/迅捷换入/蓄力；核对修改只发生约定次数、恢复/永久边界和调度标志实际被消费')
    actions = [t.get('params', {}).get('action') for t in tags if t.get('params', {}).get('action')]
    if actions:
        plans.append('逐action=' + ','.join(actions) + '的条件真/假，合法/无合法目标，位置0/1/末位；对照完整原文独立计算，未识别参数须显式拒绝')
    if obj['name'] in {'借用', '取念', '复写', '盲从'}:
        plans.append('携带3个不同合法技能和无可借技能；场上/场下目标、各槽及非幻/幻系成本<=2边界；盲从multiple_borrow及额外-2确有分支，逐槽核对而非报整个功能缺失')
    if not plans:
        plans.append('按本行原文与配置逐条件真/假、目标双方、效果前后时点构造完整回合；当前只有结构静态证据，无独立全条件输出')
    return '；'.join(plans)


def norm(text):
    """仅为定位同一子句消除标点，不推断语义同义。"""
    return re.sub(r'[\W_]+', '', text)


def main():
    """生成822对象收口表、子句增补及完整性证据。"""
    frozen_names = ['object_review.csv', 'coverage.csv', 'inventory_extra.csv', 'assigned_inventory.csv', 'objects.json', 'report.md', 'issues.md', 'questions.md']
    frozen = {name: digest(OUT / name) for name in frozen_names}
    final = []
    for obj in OBJECTS:
        item, name = obj['item_id'], obj['name']
        prior = PRIOR[item]
        findings = FINDINGS[name]
        clause_rows = CLAUSES.get(name, []) if obj['kind'] == 'ability' else []
        config_json = json.dumps(obj['config'], ensure_ascii=False, separators=(',', ':'))
        confirmed = [x['scope'] for x in findings]
        issues = [x['issue'] for x in findings]
        evidence = ['T06/' + prior['evidence'], 'T06/object_review.csv#' + item]
        if obj['kind'] == 'skill':
            evidence.append('T06/skill_probe.json#' + name + '（仅中性输入，不含全条件）')
        if item in T08:
            evidence += ['T08/object_resolution.csv#' + item, 'T08/parameter_review.csv#' + item]
        for line, row in clause_rows:
            evidence.append(f'T09/clause_review.csv:{line}')
            if row['conclusion'] == '确认缺陷':
                confirmed.append('仅子句“' + row['clause'] + '”：' + row['assessment'])
        evidence += [x['evidence'] for x in findings]
        config_conclusion = '规则存疑'
        config_scope = '完整原文/时点/过滤器/参数结构已展开；尚不能据非空配置证明全部子句语义。'
        if prior['conclusion'] == '通过':
            config_conclusion = '通过'
            config_scope = '仅原局部配置及中性输出范围：' + prior['notes'] + '；此通过不包含共享执行边界。'
        elif prior['conclusion'] == '确认缺陷' and re.search(r'T06-I\d+', prior['notes']):
            config_conclusion = '确认缺陷'
            config_scope = prior['notes']
        elif name in {'极限撕裂', '速冻', '龙威'}:
            config_conclusion = '通过'
            config_scope = '仅配置过滤器/层数或所赋标记与原文匹配；具体消费者另有确认缺陷。'
        if any(x['config'] for x in findings):
            config_conclusion = '确认缺陷'
            config_scope += '；' + '；'.join(x['scope'] for x in findings if x['config'])
        execution = overall = '规则存疑'
        exec_scope = '实现待证实：关联handler已静态阅读，参数位置已列；中性探针或局部参数样本不足以证明本对象所有条件、独立分支和生命周期。'
        if prior['conclusion'] == '确认缺陷':
            overall = '确认缺陷'
            confirmed.insert(0, prior['notes'])
            issues = re.findall(r'T\d+-I\d+', prior['notes']) + issues
            if re.search(r'T06-I(?:0[2-9]|1[0-5])\b', prior['notes']):
                exec_scope = '配置层已确认至少一处差异；中性输出/静态链不等于全部执行条件已验证。'
            else:
                execution = '确认缺陷'
                exec_scope = prior['notes']
        if findings or any(row['conclusion'] == '确认缺陷' for _, row in clause_rows):
            execution = overall = '确认缺陷'
            exec_scope = '；'.join(confirmed)
        empty = obj['kind'] == 'ability' and not obj['config']
        direct = '有配置；未对本行所有构造输入独立验证拒绝边界。'
        platform = '有配置路径可达；不以正常开始推断其效果正确。'
        reachability = '技能名称配置可选，正常ON_USE/应对/回合阶段按本行配置触发；不保证每分支已实测。' if obj['kind'] == 'skill' else '特性已配置；时点与过滤器按本行完整结构；分支可达性与正确性分开。'
        required = validation_plan(obj)
        limitation = '未核实完整共享边界和各独立条件两侧；本行确认缺陷只表示至少一个已证实反例，其余子句不因对象有错而自动判错或通过。'
        if empty:
            config_conclusion = execution = overall = '未实现'
            config_scope = 'effects=[]，70种空特性之一；完整原文非空，未提供实现。'
            exec_scope = '核心特性机制未实现；直接拒绝与平台前处理绕过分别记录，不称生产路径正确拒绝。'
            direct = '保留真实特性名直接BattleBuilder构造，抛UnsupportedMechanicError；T11已以整点报时实证，其他空名经同一显式空配置检查。'
            platform = 'T11-I01：_normalize_creature将空配置特性name改为空串，effects=[]且正常创建/开始；70种共152形态映射。'
            reachability = '直接构造拒绝；Web平台规范化后失去特性名而静默放行。形态：' + '、'.join(FORMS[name]['forms'])
            confirmed = ['空实现及平台抹名绕过；此处总体未实现，不以平台可开始标通过。']
            issues = ['T06:empty_ability', 'T11-I01']
            evidence += ['T11/probe_output.json#unsupported_ability_bypass', 'T10/unsupported_ability_forms.json#' + name]
            required = '补齐该原文所有子句后分别经direct builder与平台原名输入验证；在实现前平台也应保留真实名称并明确拒绝。'
            limitation = '平台抹名由明确公共规范化链及70名称/152形态精确映射证明，未逐152形态运行；直接builder代表名实跑、其余同一拒绝分支静态覆盖。'
        elif prior['conclusion'] == '规则存疑':
            limitation += '；原具体规则疑问：' + prior['notes']
        if name == '无忧无虑':
            limitation += '；T10-Q02：默认3层/无限999上限与退化链关系需明确，现有链边界探针不代表规则已确定。'
            evidence += ['T10/probe_output.json#cute_default_cap/cute_no_cap', 'T10/questions.md']
        if name == '撒娇':
            limitation += '；T10-Q03：0威力状态技能是否接受全技能永久威力增益待规则确认。'
            evidence += ['T10/questions.md', 'T10/probe_output.json#cute_power_perm']
        if name in {'嫉妒', '守护者'}:
            limitation += '；T10局部参数/目标消费匹配，仅此局部已验证，不能扩展为全对象通过。'
            evidence += ['T10/report.md末段', 'T10/probe_output.json']
        rule = f"{obj['source']}:{obj['line']} 原文：{obj['description']}；优先级data根md→部分规则详解→game_descriptions；DB/skills及用户授权spirits原文用于具名规则。"
        if clause_rows:
            rule += '；' + '；'.join(dict.fromkeys(row['basis'] for _, row in clause_rows))
        final.append(dict(item_id=item, kind=obj['kind'], name=name, description=obj['description'], config=config_json,
                          prior_conclusion=prior['conclusion'], config_conclusion=config_conclusion, config_scope=config_scope,
                          execution_conclusion=execution, execution_scope=exec_scope, overall_conclusion=overall,
                          rule_basis=rule, implementation=implementation(obj), evidence='；'.join(dict.fromkeys(evidence)),
                          confirmed_scope='；'.join(dict.fromkeys(confirmed)) or '无本对象全部条件的独立正确性证明；不作完整通过。',
                          current_behavior=config_json + '；' + exec_scope, required_inputs=required,
                          nextstep='按本行required_inputs逐子句运行真实配置，独立推导期望并记录双侧状态；先核对本行已确认错误，再覆盖尚未证实边界。' if not empty else required,
                          limitations=limitation, reachability=reachability, direct_builder_behavior=direct,
                          platform_behavior=platform, related_issues='；'.join(dict.fromkeys(issues)) or '未新增具名反例；共享风险见T03/T04/T07/T08，不能据此直接判本对象所有子句错误。'))
    final_by_id = {r['item_id']: r for r in final}
    # 不将对象的一处失败机械继承给全部粗分子句；精确T09子句另建稳定分支。
    inventory = read_csv(OUT / 'assigned_inventory.csv') + read_csv(OUT / 'inventory_extra.csv')
    inventory_by_id = {r['item_id']: r for r in inventory}
    cover = []
    for old in read_csv(OUT / 'coverage.csv'):
        item = old['item_id']
        base = ':'.join(item.split(':')[:2])
        obj = final_by_id.get(base)
        row = dict(old)
        row['prior_conclusion'] = old['conclusion']
        row['config_conclusion'] = obj['config_conclusion'] if item == base and obj else '规则存疑'
        row['execution_conclusion'] = obj['execution_conclusion'] if item == base and obj else '规则存疑'
        row['overall_conclusion'] = obj['overall_conclusion'] if item == base and obj else '规则存疑'
        row['required_inputs'] = obj['required_inputs'] if obj else '对应源码条件真/假、合法/非法参数分别运行；参照原台账及已确认生成器反例，不以文件阅读代替语义实测。'
        if obj:
            row['implementation'] = obj['implementation']
            row['evidence'] = obj['evidence']
            row['reachability'] = obj['reachability']
            row['method'] = '冻结原件保留；逐对象合并具名静态/探针证据；本行条件未覆盖则明确待证实'
            if item == base:
                row['conclusion'] = obj['overall_conclusion']
                row['notes'] = obj['execution_scope'] + '；限制：' + obj['limitations']
            elif obj['overall_conclusion'] == '未实现':
                row['conclusion'] = row['overall_conclusion'] = row['config_conclusion'] = row['execution_conclusion'] = '未实现'
                row['notes'] = '空特性原文子句无实现；direct builder拒绝而平台抹名绕过。' + obj['limitations']
            else:
                desc = inventory_by_id.get(item, {}).get('description', '').split('【完整规则：')[0]
                exact = [(line, x) for line, x in CLAUSES.get(obj['name'], []) if x['conclusion'] == '确认缺陷' and len(norm(x['clause'])) >= 5 and norm(x['clause']) in norm(desc)]
                if exact:
                    row['conclusion'] = row['overall_conclusion'] = row['execution_conclusion'] = '确认缺陷'
                    row['notes'] = '仅本行明确匹配子句：' + '；'.join(x['clause'] + '：' + x['assessment'] for _, x in exact) + '；其他邻接子句无自动结论。'
                else:
                    row['conclusion'] = '规则存疑'
                    row['notes'] = '实现待证实：本子句独立条件/参数尚未完整证实；对象总体=' + obj['overall_conclusion'] + '，具体确认范围见final_object_review.csv，不将对象一处错误扩展到本子句。原文子句：' + desc
        else:
            if old['conclusion'] == '确认缺陷':
                row['conclusion'] = row['overall_conclusion'] = row['config_conclusion'] = '确认缺陷'
                row['notes'] = old['notes'] + '；只保留已证实生成器嵌套结构分支反例。'
            else:
                row['conclusion'] = '规则存疑'
                row['notes'] = '源码已静态读取；对应分支输入/输出尚无完整独立语义证明。已确认具名配置问题和生成回退见issues.md；本行不能按同文件自动判通过/失败。'
        cover.append(row)
    extra = []
    per_name = Counter()
    for line, source in enumerate(T09, 2):
        obj = BY_NAME[source['ability']]
        per_name[obj['name']] += 1
        item = obj['item_id'] + f":T09C{per_name[obj['name']]:02d}"
        inv = dict(item_id=item, kind='ability_exact_collaboration_clause', name=obj['name'], owner='T06', source='tasks/T09/clause_review.csv', line=str(line), parent_id=obj['item_id'], description=source['clause'], reachability='继承当前具名配置；已跑与静态断链范围见source assessment')
        extra.append(inv)
        con = '确认缺陷' if source['conclusion'] == '确认缺陷' else '规则存疑'
        cover.append(dict(item_id=item, conclusion=con, rule_basis=source['basis'] + '；子句：' + source['clause'], implementation=source['implementation'], objects=obj['name'], method='精确具名子句协同；不合并相邻条件', evidence=f'T09/clause_review.csv:{line}; T09/issues.md; T09/probe_output.json; T09/source_correction_probe_output.json', notes=source['assessment'] + '；' + source['rule_gap'], reachability=inv['reachability'], prior_conclusion='新增精确子句', config_conclusion='规则存疑', execution_conclusion=con, overall_conclusion=con, required_inputs=final_by_id[obj['item_id']]['required_inputs']))
    write_csv(OUT / 'final_object_review.csv', final)
    write_csv(OUT / 'coverage_addendum.csv', cover)
    write_csv(OUT / 'inventory_addendum.csv', extra)
    frozen_after = {name: digest(OUT / name) for name in frozen_names}
    required_fields = list(final[0])
    idset = {o['item_id'] for o in OBJECTS}
    empty = [r for r in final if r['overall_conclusion'] == '未实现']
    blocked = [r for r in final if r['prior_conclusion'] == '检查受阻']
    local = [r for r in final if r['prior_conclusion'] == '通过']
    validation = dict(object_count=len(final), stable_id_count=len(set(r['item_id'] for r in final)), ids_match_original822={r['item_id'] for r in final} == idset, kinds=dict(Counter(r['kind'] for r in final)),
                      overall_conclusions=dict(Counter(r['overall_conclusion'] for r in final)), config_conclusions=dict(Counter(r['config_conclusion'] for r in final)), execution_conclusions=dict(Counter(r['execution_conclusion'] for r in final)),
                      formerly_blocked317=dict(Counter(r['overall_conclusion'] for r in blocked)), former_local149_overall=dict(Counter(r['overall_conclusion'] for r in local)), former_local149_config=dict(Counter(r['config_conclusion'] for r in local)),
                      empty_ability_count=len(empty), empty_ability_form_count=sum(len(FORMS[r['name']]['forms']) for r in empty), empty_names_match=set(FORMS) == {r['name'] for r in empty},
                      empty_required_fields=[(r['item_id'], key) for r in final for key in required_fields if not str(r[key]).strip()],
                      addendum_rows=len(cover), added_exact_T09_clauses=len(extra), original_coverage_ids_preserved={r['item_id'] for r in read_csv(OUT / 'coverage.csv')} <= {r['item_id'] for r in cover}, unique_addendum_ids=len({r['item_id'] for r in cover}) == len(cover),
                      exact_T09_conclusions=dict(Counter(r['conclusion'] for r in cover if ':T09C' in r['item_id'])), final_no_blocked=all(r['overall_conclusion'] != '检查受阻' for r in final), frozen_hashes_before=frozen, frozen_hashes_after=frozen_after, frozen_unchanged=frozen == frozen_after,
                      source_rows=dict(T08=len(T08), T09=len(T09), T10=len(T10)), command='PYTHONIOENCODING=utf-8 PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 python docs/battle_audit/20261112-132335-1bcaab0/tasks/T06/finalize_review.py', new_business_or_database_execution='无；只读证据及源码AST，不连接DB，不导入业务，不重跑580技能')
    assert validation['ids_match_original822'] and len(final) == 822 and not validation['empty_required_fields']
    assert len(blocked) == 317 and len(local) == 149 and len(empty) == 70
    assert validation['empty_ability_form_count'] == 152 and validation['empty_names_match']
    assert validation['frozen_unchanged'] and validation['unique_addendum_ids'] and validation['original_coverage_ids_preserved']
    (OUT / 'final_validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# T06 跨组协同最终增补', '', '本增补只写T06新增文件；原object_review.csv、coverage.csv、report/issues/questions及原始inventory均保持字节不变，哈希见final_validation.json。最终822对象稳定ID与原清单完全一致（580技能、242特性）。', '',
             'final_object_review.csv逐对象保留原文、完整配置、配置/执行/总体六分类、当前行为、明确已证实范围、具体待跑输入、代码消费者、证据及可达性。总体“确认缺陷”只表示至少一处有明确反例，不表示其他子句全部失败。', '',
             '总体结论：' + json.dumps(validation['overall_conclusions'], ensure_ascii=False) + '。',
             '原317待协同对象现为：' + json.dumps(validation['formerly_blocked317'], ensure_ascii=False) + '；不再以等待handler为阻塞理由，未闭合的是具体实现/条件输入证据，逐行有required_inputs及nextstep。',
             '原149局部通过的配置结论：' + json.dumps(validation['former_local149_config'], ensure_ascii=False) + '；其总体结论：' + json.dumps(validation['former_local149_overall'], ensure_ascii=False) + '。单伤害/固定参数及中性输出未覆盖最终扣血、全局连击、免疫/减伤、复制、99层/清除等共享边界，不再冒充全条件通过。', '',
             '70空特性总体均为未实现；direct builder保留原名拒绝，实际平台先抹名再正常创建/开始，T11-I01已证实。70名称精确映射152形态；并未逐152形态运行，静态共同规范化及目录映射与代表名实跑范围分列。', '',
             'coverage_addendum.csv保留原3755个ID并追加T09精确321子句（34确认缺陷、287规则存疑）；新增ID见inventory_addendum.csv。原粗分子句不再机械继承对象缺陷：仅明确匹配T09已证明原文者确认，其余记实现待证实，并引用对象具名反例范围。原生成器已确认回退分支继续保留。', '',
             '新增具名证据来自T08全部611对象与656参数台账、T09当前321子句和I10/I11/I12新探针、T10十八类型/球/血脉与生命周期语义表及末段、T05愿力/禁足/选择/入场/RNG、T02拍击ID和奉献别名、T07清除与王子萌化分类，以及T11空特性抹名。各共享handler静态反例与真实对象完整回合实跑在confirmed_scope中区分，未将handler存在、无独立配置或中性不崩溃等同通过或未上线。', '',
             '规则仍待明确：体重/比值动态威力映射、秋收草环境、无忧无虑层数/退化链上限、0威力技能是否接全技能威力等；原questions.md保留，新增关联疑问引用T09/T10 questions，无需重复授权特性原文。盲从multiple_borrow及非幻额外-2确有实现分支，不报整个借用功能缺失；变形活画纠正为参数key错配；未把同一compute的不同action一并判错。', '',
             '本轮为新增证据合并，未重跑全部580技能；复现输入/输出复用已保存且具名定位的T07/T08/T09/T10/T05/T02/T11文件。仅执行finalize_review.py进行字段、ID、计数、空特性映射和冻结哈希验证。没有修改业务或数据库。', '',
             '复核命令：`$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"; $env:PYTHONDONTWRITEBYTECODE="1"; python docs/battle_audit/20261112-132335-1bcaab0/tasks/T06/finalize_review.py`。输出见final_validation.json。']
    (OUT / 'final_addendum_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in validation.items() if not k.startswith('frozen_hashes')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
