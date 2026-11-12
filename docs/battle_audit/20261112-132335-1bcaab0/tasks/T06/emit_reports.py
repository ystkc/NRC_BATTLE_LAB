"""将可核对差异形成按根因分组的审计报告。"""
from build_report import OBJECTS, ANNOTATIONS, PROBES, OUT, ROOT
import ast
import json
from collections import defaultdict

TITLES = {
    'T06-I01':'生成回退重复包装SkillEffect，8技能在执行时崩溃',
    'T06-I02':'手写技能覆盖保留过期数值，覆盖正确数据源',
    'T06-I03':'生成产物数值和目标陈旧或错误',
    'T06-I04':'固定技能威力误编码为百分比',
    'T06-I05':'“回复”未被“恢复”正则识别，附加回复静默丢失',
    'T06-I06':'应对容器有类别但丢失应对附加效果',
    'T06-I07':'无伤害技能的本次多连击被猜测为全局永久连击增益',
    'T06-I08':'动态条件丢失、状态凭空增加、条件主体改变',
    'T06-I09':'手写复合效果与当前原文不符',
    'T06-I10':'特性手写倍率/固定值与当前原文不符',
    'T06-I11':'特性属性目标/触发阈值和子效果遗漏',
    'T06-I12':'特性的时点、受益者和偷取行为错误',
    'T06-I13':'空技能效果未被拒绝，消耗能量后静默零效果',
    'T06-I14':'先手属性解析后未输出、未注入，默认归零',
    'T06-I15':'蓄力属性解析后未输出、未注入，默认立即攻击',
}

def key_locations(path):
    """提取配置对象位置。"""
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    result[key.value] = key.lineno
    return result

def main():
    """输出缺陷明细、限制和需用户明确的规则点。"""
    locations = {p:key_locations(ROOT/p) for p in ['nrc_core/effect_data.py','nrc_core/skill_effects_generated.py']}
    review = list(__import__('csv').DictReader((OUT/'object_review.csv').open(encoding='utf-8-sig')))
    group = defaultdict(list)
    for row in review:
        if row['notes'].startswith('T06-I'):
            group[row['notes'].split('；',1)[0]].append(row)
    issues = ['# T06 配置与生成审计缺陷', '', '以下只将结构或最小执行证据已确认的差异编号。严重度P1表示直接改变战斗结果或导致操作异常。每项中的对象表给出精确规则行（DB稳定ID及原文）、配置位置、参数差异；同根因合并，不将相似对象逐项制造重复问题。', '', '重现环境：Python项目原有环境；`python .../tasks/T06/probe.py`和`minimal_repros.py`；数据库只读URI；业务源码与生成文件没有修改。输入输出分别保存在同目录JSON。', '']
    for issue,title in TITLES.items():
        items = group[issue]
        issues += ['## '+issue+' '+title,'', '严重度：P1。主责：T06；协同：T07（执行器/原语）、T08（平台目录/构建），特性另协同T09/T10。', '']
        if issue=='T06-I01':
            issues += ['规则依据：对应8项技能说明要求治疗、回能、减速或换人；不允许以AttributeError代替可执行规则。代码根因：`scripts/generate_skill_effects.py:1130`、`:1147`回退；`:1212`把已提交`SE(...)`逐行取回后再次包入`SEEntry("ON_USE", base_tags)`；`nrc_core/engine/executor.py:188`读取内层tag.type崩溃。', '', '最小输入/步骤：1000最大HP、当前500HP、20能量的A携带“休息回复”，B聚能；执行`execute_full_turn(state,(0,),(-1,))`。预期回复300HP；实际抛`AttributeError: SkillEffect object has no attribute type`。`skill_probe.json`对全部8项逐一复现同异常。内存重生成“休息回复”嵌套从2层增至3层，见`regeneration_diff.json`。影响：技能无法结算；重新生成会继续加深损坏。','']
        elif issue=='T06-I13':
            issues += ['规则依据：表中每个对象的完整原文。调用链：`nrc_platform/builder.py:630`只检查技能存在、选项和random_source，不检查效果完整性；`nrc_core/battle.py:1788`全部进入效果引擎；空列表通过legacy分支返回damage0。', '', '最小输入/步骤：A 500/1000HP、20能量，携带“可爱”（能耗3、魔法攻击），B聚能。执行完整回合；预期造成DB威力对应魔法伤害；实际A能量20→17、B生命500→500，未报UnsupportedMechanicError。证据`minimal_repros.json`。影响：整个技能规则静默失效；选择技能即使有合法选项仍没有分支效果。','']
        elif issue=='T06-I14':
            issues += ['代码位置：`scripts/generate_skill_effects.py:494`解析priority_mod；`:994`输出遗漏；`nrc_platform/catalog.py:151`Skill构造未注入该字段。最小输入：携带“先发制人”；预期priority_mod=1；实际完整回合输入快照priority=0。证据`minimal_repros.json`。','']
        elif issue=='T06-I15':
            issues += ['代码位置：`scripts/generate_skill_effects.py:493`识别蓄力但`:994`不输出；平台Skill构造保留charge=False。最小输入：“升龙咆哮”，A先行动；预期本回合进入蓄力、无直接伤害；实际B生命500→320、charging_skill_idx仍-1。证据`minimal_repros.json`。','']
        else:
            issues += ['规则依据：下表稳定对象ID及逐字规则；实现以对象配置行和完整结构为准，不从旧注释反推新规则。最小输入/步骤：使用`probe.py`固定精灵夹具（双方500/1000HP、3能量、无其他特性），执行技能或表述时点的特性；应对项追加匹配类别的敌方技能，动态项分别令条件成立/不成立。预期按原文参数与子句执行；实际配置和已运行输出如下。未执行到的条件分支，以结构缺失及调用链为证据，不声称已完整实战覆盖。', '']
        if issue=='T06-I04':
            issues += ['具体例：化劲原文全技能威力+40；实际`skill_power_bonus=0`、`skill_power_pct_mod=0.4`。对基础威力100似乎相同，但基础威力50时应+40而实际仅+20。`minimal_repros.json`保存完整回合输出；根因`generate_skill_effects.py:789`、`:597`将全技能固定威力交给power_pct。','']
        if issue=='T06-I07':
            issues += ['具体例：三连破原文“自己获得物攻+30%，3连击”，没有授予后续全部技能永久连击+3；实际一次增益且hit_count_mod永久+3。生成器`:1071`的注释明确以“更接近”作未经规则授权的猜测。本次重复次数细节不影响“凭空全局永久加连击”的反例。`minimal_repros.json`给出完整回合输出。','']
        if issue=='T06-I10':
            issues += ['具体例：图书守卫者在己方MP=1入场，组合状态每层atk_up/spatk_up均0.5；预期各1.0。蓄电池/超级电池分别0.2/0.3，原文分别0.3/0.4。`ability_probe.json`记录完整输入输出及组合状态，未误读未展开的原始*_up字段。','']
        if issue=='T06-I11':
            issues += ['具体例：毒腺使用能耗3技能，敌方中毒1→5；预期该能耗不触发。毒牙在敌有1层中毒时使用普通攻击技能，敌魔攻/魔防各减40%而物攻/速度未减；原文应成功施毒时施加物攻和速度减益。鼓气/三鼓作气组合状态只含atk_up/def_up各0.2。证据`ability_probe.json`；消费这些参数的handler在`handlers_ability.py:781`、`:792`。','']
        if issue=='T06-I12':
            issues += ['具体例：大捞一笔/小偷小摸在ON_ENTER执行后双方能量仍3，预期从敌方偷3/2；结构中的实际阶段分别为ON_TURN_END/ON_ENEMY_SWITCH。证据`ability_probe.json`。','']
        issues += ['| 对象/规则行 | 原文 | 配置位置 | 差异/实际 |','|---|---|---|---|']
        for item in items:
            source='nrc_core/effect_data.py' if item['name'] in locations['nrc_core/effect_data.py'] else 'nrc_core/skill_effects_generated.py'
            loc=str(locations[source].get(item['name'],'缺项'))
            issues.append('| '+item['item_id']+' '+item['name']+' | '+item['description'].replace('|','/').replace('\n',' ')+' | '+source+':'+loc+' | '+item['notes'].replace('|','/').replace('\n',' ')+' |')
        issues += ['', '证据：`object_review.csv`逐项保留原文和完整配置JSON；`skill_comparison.txt`/`ability_comparison.txt`便于按行复核；实际运行记录`skill_probe.json`/`ability_probe.json`/`minimal_repros.json`。', '']
    (OUT/'issues.md').write_text('\n'.join(issues),encoding='utf-8')
    checkpoint=json.loads((OUT/'checkpoint.json').read_text(encoding='utf-8'))
    report = '''# T06 审计报告

审计主责：`nrc_core/effect_data.py`、`nrc_core/skill_effects_generated.py`、`scripts/generate_skill_effects.py`。未改业务文件、数据库、正式生成产物；所有提取和输出均在本任务目录。数据库访问使用`mode=ro`。未使用网络及旧审计结论作为规则。

已对全部580技能、242特性逐屏展示原文与完整配置，检查手写优先级、生成缺失、数值、目标、条件、应对分支和附加效果。全部580技能运行中性效果入口，12项特性运行指定时点，6项运行完整回合。上述探针不是全部对局路径的替代；149项通过包括125个原文仅描述伤害且数值调用已观察到的基本攻击和24个已对照参数、目标与实际输出的简单施加/回复技能，未将非空配置或有handler当作通过依据。

确认15个本任务根因组，详见issues.md，并将T07/T04已实证结果关联至16个复杂配置对象，未重复增加问题编号。其中8个嵌套SE会执行崩溃；大量手写参数陈旧、回复/应对附效遗漏；空技能可扣能量后零效果。70个空特性归为未实现；直接builder保留原名时会拒绝，但实际平台规范化可能抹去名称而绕过，T11负责验证，不授予实际平台正确拒绝结论。秋收保守归为规则存疑，当前草系环境条件不可达。

生成器只在内存重生成：当前DB580，手写129；生成451，其中433非空、18空，其“covered_total=562”只衡量非空，不是语义覆盖率。重生成与当前文件有143个映射差异，且回退会增加已有SE嵌套层级；不能用一次直接重生成修复所有问题。

`assigned_inventory.csv`共2199行，全部在coverage.csv有行；额外1556个同句语义片段在inventory_extra.csv及coverage.csv有行。每段保留完整原文以避免逗号分割丢失条件归属。对象存在缺陷时子句保守继承对象风险，notes明确说明并非每个子句均已单独证实出错；对象表是定位具体差异的依据。

审计限制：复杂对象仍需T07/T09/T10的处理器、专名逻辑和生命周期结果交叉确认；源码独立分支未逐项完成边界实证，已保守标记检查受阻。不能将本检查点称为全部规则逐路径通过。当前检查受阻表示证据不足并待协同，不是文件权限/数据库不可读。

文件：objects.json（原文完整结构）、object_review.csv（逐对象结论）、skill_comparison.txt/ability_comparison.txt（逐行展示）、skill_probe.json/ability_probe.json（输入输出）、minimal_repros.json（完整回合反例）、regeneration_diff.json（内存再生成差异）、coverage.csv（分配及补充分支台账）。

当前计数：
'''+json.dumps(checkpoint,ensure_ascii=False,indent=2)
    (OUT/'report.md').write_text(report,encoding='utf-8')

if __name__ == '__main__':
    main()
