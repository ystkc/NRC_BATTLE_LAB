"""整理T03逐ID结论；引用独立公式和实际状态证据。"""
import ast
import csv
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
ISSUES=[
 ('I01','Float16替代权威Float32导致六维错误','data/属性数值计算.md:47-50','nrc_core/catalog.py:20-23,39-57; nrc_core/constant.py:3-5','stats_IV0','全量DB625形态、30性格、六维均IV0，以md总结公式构造严格Float32分步期望。','112500个标量比较中12325个不一致；例如丢丢沙地形态防御种族55、逞强（防御无修正）应121实120。Float16常数与性格小数均可偏移半数边界。','全部六维计算；IV0已隔离6倍/5倍歧义，不能用该歧义解释差异。','T03主责，T01数据构建协同'),
 ('I02','双攻双防有效属性截断为40层提升/9层降低，违反99层规则','data/伤害数值计算.md:9,15,19','nrc_core/models.py:387-420','I02_caps','基础攻击/防御100，分别设atk_up=9.9、def_down=9.9；附加速度同值用于观察但不由双攻双防段落推导速度上限。','99层物攻提升应1090实500，99层物防降低应约9.174实52.632；增减益并存样例125正确。速度也经过同一clamp，但其99层上限是否同属该规则保留待裁决。','effective_atk/def/spatk/spdef直接调用方；计算器伤害直接读calculation_modifier，和有效属性接口不一致。','T03主责，T04执行顺序、T09/T10赋予协同'),
 ('I03','原始增减益与计算入口未执行99层上限','data/伤害数值计算.md:15','nrc_core/models.py:422-424,440-454; nrc_core/engine/helpers.py:217-276','I03_max99','对普通精灵调用_apply_buff100次，每次atk=.1，读取calculation_modifier。','应封顶9.9；实际9.99999999999998，battle.DamageCalculator不经_clamp直接读取，100层可进入伤害公式。','普通五维独立状态及复制状态输入；与I02低上限是两条不同路径错误。','T03模型计算主责，T09/T10状态赋予协同'),
 ('I04','Skill.copy遗漏技能威力基准，复制后入场特性重复放大','data/状态分类.md:4; data/wiki/spirits.csv:613','nrc_core/models.py:208-268; nrc_core/engine/helpers.py:475-477','I04_skill_copy','100威力1能耗技能应用挺起胸脯对应power_pct=.5，再copy_state，对原对象和副本分别再次应用同一入场修正。','两者均应保持150；原对象150、副本225。Skill.copy未复制_ability_base_power；其他非显式动态字段也需逐来源核查。','挺起胸脯、国王威严、勇敢、不移等使用技能基准修正的特性；simulate_turn默认克隆也经过该方法。','T03复制主责，T06配置协同，T09/T10应用原语协同'),
 ('I05','分精灵深拷贝破坏跨精灵状态引用，衡量增益写向游离副本','data/wiki/spirits.csv:30-31; data/状态分类.md:2','nrc_core/models.py:546-548,688-692','I05_graph_copy','B.ability_state镜像引用A公平鸽；BattleState.deep_copy后给B+10%攻击。','副本B引用应指副本A，副本A应+0.1；实际指向另一个游离公平鸽，对其+0.1而场上A仍0。','simulate_turn默认clone=True与单独deep_copy；runtime.clone采用整体copy.deepcopy，此入口保留共享引用，不能把本问题无差别套用runtime。','T03复制主责，T04 simulate_turn、特性handler协同'),
 ('I06','引电扣血未执行冻结实时力竭','data/wiki/game_descriptions.csv:5,51','nrc_core/models.py:579-590','I06_electric_freeze','HP1000、当前270、冻结1层；施加2层引电。','25%生命扣250后剩20低于冻结阈值50，应力竭；实际20存活。不是阈值相等争议。','引电与冻结相互作用、即时MP和终局；与T04毒印漏检查为不同扣血入口。','T03主责，T04统一伤害后检查协同'),
 ('I07','BattleState.deep_copy复制天气id键却未映射新技能','data/wiki/game_descriptions.csv:37','nrc_core/models.py:688-704; nrc_core/battle.py:969-978','I07_weather_copy','沙暴剩1回合，地系技能当前耗2，记录原耗5；simulate_turn默认clone=True双方聚能。','天气结束应恢复5；副本技能id不在旧id字典中，实际保持2。','直接simulate_turn默认克隆接口；runtime.clone/new_game/export有天气键重建兜底，已明确入口差异。','T03模型复制主责，T04天气还原协同'),
]
ISSUES[5]=ISSUES[5][:2]+('GAME_RULE:0007,0021；'+ISSUES[5][2],)+ISSUES[5][3:]
ISSUES[6]=ISSUES[6][:2]+('GAME_RULE:0030；'+ISSUES[6][2],)+ISSUES[6][3:]


def load_csv(path):
    """统一UTF-8读取稳定审计表。"""
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    """根据已检查源码和独立证据写逐项覆盖。"""
    assigned=load_csv(HERE/'assigned_inventory.csv')
    extra=load_csv(HERE/'inventory_extra.csv')
    output=json.loads((HERE/'probe_output.json').read_text(encoding='utf-8'))
    sources={}
    for path in (ROOT/'nrc_core').glob('*.py'):
        if path.name not in {'models.py','compound_status.py','catalog.py','constant.py','pokemon_nature_table.py'}:
            continue
        text=path.read_text(encoding='utf-8')
        sources['nrc_core/'+path.name]=(text.splitlines(),[n for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.ClassDef))])
    proofs={
      'get_type_effectiveness':('data/属性克制表.md:1-43','6156个独立矩阵全部匹配；覆盖18×18单属性与18³有序双属性，包含双克3、双抗.25、互抵1；期望从权威md重新解析，不引用TYPE_CHART。'),
      'has_type':('data/属性克制表.md:43','静态检查仅检索pokemon_types，不读血脉；__post_init__为空时注入主属性，主属性缺失时补到首位。'),
      'calculation_modifier':('data/状态分类.md:2; data/伤害数值计算.md:9,15','组合状态只在读取时展开，普通字段不回写；probe pass_state得到.6且原atk_up为0，副本层数独立。但99层上限问题见I03。'),
      'skill_modifier':('data/状态分类.md:2-4','逐状态乘层数并按技能系别过滤，负威力状态技能排除power/power_pct；probe组合状态3层×power5=15，未改技能面板原值。'),
      'modifier':('data/状态分类.md:2','显式层数乘该字段单层修正，不缓存不消耗；probe .2×3=.6。'),
      'observation':('data/对战过程中的信息遮蔽规则.md:3-7','只导出状态本身名称/层数/说明，不泄露派生属性或技能分布；字段映射静态可直接核验。'),
      'buff_modifiers':('data/伤害数值计算.md:15,19','逐项核对atk/spatk/def/spdef/speed与all_atk/all_def展开对应字段，同字段相加，双攻不误写防御。未知缩写抛KeyError，合法配置输入范围由调用方提供。'),
      'get_skill':('data/状态分类.md:4','目录按名或id返回copy；probe同名两次获取修改one能耗不改变two。复制全部动态状态的正确性另见I04，不外推本通过项。'),
      'all_skills':('data/状态分类.md:4','每个返回技能调用独立copy并新建字典，避免同名技能共享常规持久值；动态字段遗漏仍见I04。'),
      'is_fainted':('data/README.md:35','current_hp<=0或显式FAINTED标记判力竭；只检查谓词，不证明所有扣血入口及时设置，I06另记。'),
      'freeze_threshold':('data/wiki/game_descriptions.csv:5','最大生命×层数×5%，由源层数计算不缓存。阈值恰相等行为留问题，不影响公式本身。'),
      'get_current':('data/README.md:22-31','a/b各取对应team和current索引，无名称查找或状态变化。'),
      '_get_devotion':('data/部分规则详解/奉献.md:4','按队伍返回同方奉献记录，两队字段分离；不进行随机、不清除且切换不重置。'),
    }
    rows=[]
    for item in assigned+extra:
        source=item['source']; line=int(item['line'] or 0)
        conclusion='规则存疑'; rule='data/状态分类.md；具体技能/特性原文待逐对象证明'
        proof='完整静态检查；本项具体条件未取得独立规则证明，不能仅因代码存在或输出看似合理判通过。'
        function=item['name']; evidence='probe.py / probe_output.json；具体代码或对象见implementation'
        reach='生产可达；具体输入约束另列'
        related=[]
        if source in sources:
            lines,nodes=sources[source]
            containers=sorted([n for n in nodes if n.lineno<=line<=n.end_lineno],key=lambda n:n.end_lineno-n.lineno)
            function=containers[0].name if containers else '<file>'
            evidence=f'{source}:{line}: {lines[line-1].strip()}'
            if function in proofs:
                conclusion='通过'; rule,proof=proofs[function]
            if source.endswith('pokemon_nature_table.py'):
                conclusion='通过'; rule='data/属性数值计算.md:7-23'; proof='从md独立解析30个非对角性格，名字及每个升降维度均匹配；没有中性性格，is_neutral_nature对这30项均False符合矩阵。数值Float16精度偏差另记I01。'
                if function=='NatureBonus':
                    conclusion='规则存疑'; proof='TypedDict内部再次定义NatureBonus，类型声明与实际dict注解约束是否满足开发接口待静态类型验证；未影响已运行公式，不作为规则通过。'
            if source.endswith('constant.py') or (source.endswith('catalog.py') and (function in {'calc_combat_stats','rounded','other'} or line<=23)):
                related=['I01']
                if source.endswith('constant.py') and line>=7:
                    related=[]; rule='data/属性数值计算.md:30-32'; proof='文本6倍与+8→+40示例冲突，常量选6不得擅自裁决；IV0全量验证已隔离此争议。'
            if source.endswith('models.py'):
                if function in {'_clamp_up','_clamp_down','_effective_attribute','effective_atk','effective_def','effective_spatk','effective_spdef','effective_speed'}:
                    related=['I02']
                if function in {'calculation_modifier','apply_self_buff','apply_enemy_debuff'}:
                    related=['I03']
                if function=='copy': related=['I04']
                if function=='copy_state': related=['I04','I05']
                if function=='deep_copy': related=['I04','I05','I07']
                if function=='add_electric_stacks': related=['I06']
                if function in {'on_switch_out','reset_mods'}:
                    rule='data/状态分类.md:2-6; data/wiki/game_descriptions.csv:7'
                    proof='实际probe确认普通up清零、组合状态全部清零、冻结与萌化保留；但data/状态分类只规定绑定对象不明确所有清除集合，组合特性是否均可下场清除仍须逐原文。不能由观察结果证明全部清除正确。'
                if function=='add_compound_status':
                    rule='data/状态分类.md:2; 具体组合特性原文'
                    proof='同key只初始化第一次modifiers，后续只加层；当前原语可能每次传入不同per_stack值，需要逐真实特性验证；特性是否也受普通属性99层上限不可直接推断。'
                if function=='add_freeze_stacks':
                    rule='data/wiki/game_descriptions.csv:5；冻结成功特性原文'
                    proof='静态核对冰系/免疫/非正数/已死早退与层数增加；<=与原文低于有边界差异待裁决，EXTRA_FREEZE与ON_INFLICT_FREEZE嵌套顺序未逐特性证明。'
                if function=='__post_init__':
                    rule='data/属性数值计算.md:47-50；构建/复制接口'
                    proof='round采用Python偶数舍入且current_hp=0被解释为满血；需区分初始占位与复制真实0HP，未判通过。性格和IV字段没有本层校验，三项约束见questions。'
        if item['kind']=='element':
            conclusion='通过'; rule='data/属性克制表.md:5-39'; proof='18种元素全部在独立6156矩阵中覆盖；只证明枚举与克制关系，不证明所有元素专属技能。'; evidence='type_matrix.csv；mismatches=0'
        if item['item_id'].startswith('MATRIX:'):
            conclusion='通过'; rule='data/属性克制表.md:5-43'; proof='对应type_matrix.csv同item_id的expected/actual相等，期望由权威md独立解析。'; evidence='type_matrix.csv:'+item['item_id']
        if item['item_id'].startswith('SEMANTIC:'):
            key=item['name']; evidence='probe_output.json:'+key
            if key in {'stats_IV0','I02_caps','I03_max99','I04_skill_copy','I05_graph_copy','I06_electric_freeze','I07_weather_copy'}:
                related=[{'stats_IV0':'I01','I02_caps':'I02','I03_max99':'I03','I04_skill_copy':'I04','I05_graph_copy':'I05','I06_electric_freeze':'I06','I07_weather_copy':'I07'}[key]]
            else:
                conclusion='通过'; rule='data/属性数值计算.md:7-23; data/状态分类.md:2-4'; proof='独立性格矩阵或组合状态/同名技能隔离输入与预期相符，详见输出；不外推所有复制字段。'
        if item['kind'] in {'file','code_object'} and function in {'<file>','Pokemon','Skill','BattleState','CoreCatalog'}:
            if source.endswith('models.py'): related=['I02','I03','I04','I05','I06','I07']
            elif source.endswith('catalog.py'): related=['I01']
        if related:
            conclusion='确认缺陷'
            rule='；'.join(i[2] for i in ISSUES if i[0] in related)
            proof='；'.join('T03-'+key for key in related)+'，具体输入与预期实际见issues.md；函数/文件级含缺陷不代表每个内部条件都错误。'
            evidence+='；probe_output.json'
        rows.append(dict(item_id=item['item_id'],conclusion=conclusion,rule_basis=rule,implementation=f'{source}:{line} {function} | {item["description"]}',objects=function,method='完整静态核对；独立公式/矩阵/内存反例见证据',evidence=evidence,notes=proof+'；方向='+item['name'],reachability=reach))
    with (HERE/'coverage.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    issues=['# T03 问题记录','','所有条目已由probe.py实际运行。仅审计，不修改业务代码；证据读库使用mode=ro。P1为可改变规则数值/战果的确定缺陷。','']
    for ident,title,basis,code,key,steps,behavior,impact,owner in ISSUES:
        issues += [f'## T03-{ident} {title}','','- 严重度：P1；主责协同：'+owner,'- 规则依据/原文行号：'+basis,'- 代码位置：'+code,'- 最小输入步骤：'+steps,'- 预期与实际：'+behavior,'- 影响范围：'+impact,'- 证据：probe.py；probe_output.json:'+key+'；实际摘要：`'+json.dumps(output[key],ensure_ascii=False)+'`','']
    (HERE/'issues.md').write_text('\n'.join(issues),encoding='utf-8')
    counts=dict(Counter(row['conclusion'] for row in rows))
    (HERE/'report.md').write_text(f'''# T03 模型与数值审计

完整静态读取models.py、compound_status.py、catalog.py、constant.py、pokemon_nature_table.py。稳定清单{len(assigned)}项全部逐ID写入coverage.csv；额外语义清单{len(extra)}项（含6156克制矩阵）也写入coverage.csv。总计分类：{json.dumps(counts,ensure_ascii=False)}。

独立验证实际运行退出0：以data/属性克制表.md重建期望，18×18单属性与18³有序双属性（含同属性重复输入与主副交换）共6156项全匹配；输出type_matrix.csv。以data/属性数值计算.md重建30性格矩阵，名字及升降维度均匹配；随后625形态×30性格×6维、IV0，严格Float32逐步计算，共112500标量比较，12325项与实现不一致，详见stat_mismatches.csv。IV0使资质倍率不影响此结论，不裁决文本6倍/示例5倍冲突。对所有30性格比较并不等于其Float16数值精度通过，后者属于I01。

状态验证包括普通增减益并存、99层和100层、组合状态3层展开/复制不回写、同名技能目录副本隔离、技能持久基准复制、跨精灵引用复制、引电与冻结、沙暴技能能耗id备份复制。7项确定缺陷见issues.md；其中天气id问题在simulate_turn默认克隆复现为到期耗2未还原5，而runtime.clone/new_game/导出另有修复入口，明确保留边界。镜像引用问题属于分精灵copy_state/deep_copy，整体runtime deepcopy并未据此判缺陷。

规则存疑并不表示尚未读源码：每项已静态查看，但未知规则、输入责任层、具体特性清除/叠层定义或非法输入边界不足以给通过。questions.md列出倍率、三项资质、状态清除、冻结相等阈值与默认参数吞错等具体问题。未依赖旧测试、历史对局或代码自身计算期望，也未把“当前未调用”当作未上线。模型静态字段的陈旧注释（25性格/坦率中性、毒灼下场注释）记录为维护线索，不替代运行规则证据。

跨模块协同：T06提供挺起胸脯、不移、勇敢等真实配置归属；赋予/清除handler仍由其主责任务核对。T03不完整代审handler，但用真实同原语输入证明复制与封顶问题。数据库仅打开file:data/nrc_wiki.db?mode=ro，读取625形态；未写库，未生成或覆盖业务文件。

复现：设置PYTHONIOENCODING=utf-8、PYTHONUTF8=1，在仓库根运行python -m docs.battle_audit.20261112-132335-1bcaab0.tasks.T03.probe，然后同路径build_audit。所有输出均在本目录。
''',encoding='utf-8')
    print(json.dumps(dict(assigned=len(assigned),extra=len(extra),counts=counts),ensure_ascii=False))


if __name__=='__main__':
    main()
