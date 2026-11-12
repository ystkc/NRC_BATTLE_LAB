"""根据逐函数审阅与123个探针生成证据台账和问题报告。"""
from probe import ROOT, OUT
import ast
import csv
import json
from collections import Counter

ISSUES = [
('T10-I01','随机奉献未剔除满层候选，指定奉献绕过上限',22,55,'data/部分规则详解/奉献.md:1-3','devotion_grant_random/on_hit及指定技能','随机飞断5层时仍候选五种并选中飞断，实际总层数不变；应保证从未满四种中增加1。指定飞断5→6、其他10→11，超过规则上限。全满仍进行无效随机选择。','_h_devotion_grant_random_capped、_h_devotion_on_hit_capped、devotion_all_full、devotion_explicit_cap_*','P1'),
('T10-I02','折射按系别去重且排除本技能，丢失独立效果',58,67,'data/部分规则详解/折射效果.md:1','技能折射','携带折射（光）、火1、火2，预期魔攻+30%、灼烧8；实际魔攻0、灼烧4。set把两个同系技能折为一种，skill is not ctx.skill排除自身；仅另携光技能时才+30%。','refraction_duplicate_fire、refraction_LIGHT以及其余17类型case','P1'),
('T10-I03','折射幻系写入星陨状态而非星陨印记',99,101,'data/部分规则详解/折射效果.md:19','技能折射携幻技能','预期敌方场地meteor_mark+1；实际target.meteor_stacks=1、marks_b={}。两者为完全不同机制（状态倒计时与印记受攻击触发）。','refraction_PSYCHIC','P1'),
('T10-I04','折射漏火毒同系免疫，地系固定减速误作比例',89,119,'data/部分规则详解/折射效果.md:1,7,4,12；data/wiki/game_descriptions.csv:2-3','折射火/毒/地','火系目标仍得4灼烧，毒系目标仍得2中毒；原文同系免疫。冰通过add_freeze_stacks检查，独立对照确实保持0。地对速度200的目标写speed_down=.4，后续变成除1.4的比例，而应固定-40。','refraction_type_immunity_FIRE、POISON、ICE；refraction_GROUND','P1'),
('T10-I05','契约前三种球把速度百分比当固定点数，淘沙球也误用比例',174,187,'data/部分规则详解/契约的形状.md:2-4,12','契约的形状：普通/高级/国王/淘沙球','基础速度200，普通球应+5%=10而实际+5（speed_up=.025）；高级应+20实+10，国王应+30实+15。淘沙原文-40却写speed_down=.4。','contract_普通咕噜球、contract_高级咕噜球、contract_国王球、contract_淘沙球','P1'),
('T10-I06','柔软球单效果错误复用常规球整包，9个分支效果超额或目标错误',164,239,'data/部分规则详解/契约的形状.md:14-32','柔软咕噜球18候选','逐一固定候选18种：skill_power额外敌双攻-30%；heal额外己魔攻40%；slow_combo额外敌物防-40%且速度单位错；speed额外敌中毒；def应敌物防-40%却自己双防30%并敌星陨印记；atk额外敌魔防-40%；combo额外全技能耗-1；freeze额外4灼烧；energy额外30%吸血。其余9候选的单效果与原文匹配。','soft_*全部18case','P1'),
('T10-I07','稀兽花宝只实现萌血脉，17分支缺失且入口固定萌',244,250,'data/部分规则详解/稀兽花宝.md:1-18','稀兽花宝全部血脉','18类型逐一传element，只有萌使敌双攻减60%，其余17均零效果；effect_data.py固定element=萌，既不读取resolved_bloodline_type也不按实际血脉分支。普通应技能威力+40等全部未实现。','bloodline_*全部18case；跨模块搜索resolved_bloodline_type','P1'),
('T10-I08','解除或转移萌化只清层数，不恢复形态属性',322,336,'data/wiki/game_descriptions.csv:7；反弹技能原文','反弹/逆向演化及CUTE_CLEAR_SELF接口','A由1000HP/200速退化为幼1（900HP/180速），转移后cute_stacks=0但仍幼1、900/180；B正确进入自身幼1。预期解除该退化效果后恢复基础形态数值；恢复生命比例等细节另Q02。','_h_cute_transfer、_h_cute_clear_self','P1'),
('T10-I09','萌化覆盖基础速度导致永久速度增益下次退化丢失',264,277,'示弱原文“速度永久+130”；data/wiki/game_descriptions.csv:7','示弱后再次萌化','先退化、以参数130获得永久速度后user.speed=290，下一次退化直接覆盖为140，永久+130完全丢失；应新形态基础140再保留130=270。参数默认150陈旧另归T06-I02。','cute_permanent_speed_next_gain','P1'),
('T10-I10','月光合奏把本次连击数永久写回技能，重复使用累加',384,391,'月光合奏原文“本次技能连击数+1”','月光合奏','敌1层萌化，总层数始终1，本技能基础1连击；调用两次应每次2连击、基础保持1。实际ctx.skill.hit_count依次2、3，脱离本次修正生命周期。','cute_team_power_twice','P1'),
('T10-I11','化茧未免疫致命伤害、主动降为1生命且缺2次上限',395,403,'化茧原文“获得1层萌化，并免疫此次伤害（最多触发2次）”','化茧','A500/1000HP面对600伤：原语把HP改1并写context.blocked_lethal；execute_ability返回独立result未带flag，battle读result未阻止扣600，实际HP0力竭。handler连续3次仍触发萌化3层，没有次数限制；即使修传递也会错误由500降1。','cute_lethal_once、cute_lethal_three_calls、cute_lethal_consumer；executor.py:463,543及battle.py:2097','P1'),
('T10-I12','传动扩展标志写入后无消费者',122,139,'data/部分规则详解/传动机制.md:3-9；翼轴/机械变式原文','翼轴、机械变式','extra_drives与drive_on_position_change_reduce只在此写入，无核心读取；翼轴同时只设skill.agility=True，现迅捷入口不识别。回合开始移位缺失根因由T07-I05主责，动态迅捷由T07-I03主责，此处只补消费者证据，不重复计算。','drive_flags、drive_slot_outside；rg全core两个字段只有本文件写入','P1'),
('T10-I13','系统发育在回合消费者中向每只场下精灵复制全额收益',155,157,'系统发育原文“等量…随机分配给场下的精灵”','系统发育','A本次获100生命，两个场下初始各500；_apply_share_gains让每只都600，总增200。原文等量总收益只应100并随机分配。HEAL_HP/ENERGY原语另有随机分配调用，完整回合再调用该函数可重复。','share_gains_consumer；battle.py:1213-1234、1362/1383；handlers_skill.py:195/207','P1'),
]

def writer(path,rows,fields):
    """统一UTF-8 CSV。"""
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(rows)

def classify(line,kind,description):
    """依逐函数已检查语义归类，保留规则缺口。"""
    if line==10:
        return '通过','TYPE_CHECKING仅类型导入，运行不影响效果；静态检查两分支。','静态'
    if 22<=line<=55:
        return '确认缺陷','T10-I01；五种上限、随机满层候选未过滤、指定类型无上限。未知类型接口静默return只标可达性，不据此扩大线上缺陷。','devotion_*'
    if 58<=line<=119:
        return '确认缺陷','T10-I02/I03/I04；完整18类型、同系重复、排自身和免疫已逐项核对，具体错误归属见issues。各无关否分支不单独声称出错。','refraction_*'
    if 122<=line<=139:
        return '确认缺陷','T10-I12协同T07-I03/I05；标记无消费者；有效/无槽探针均已跑。','drive_flags、drive_slot_outside'
    if 143<=line<=151:
        return '通过','标记写入及消费已验证；charge_cost_reduce=2时进入蓄力全技能4→2；charge_free_skill允许改选技能。洄游当前配置reduce=1与原文2不符由T06-I10登记。蓄力异常时点由T04/T03负责，不能从此局部通过外推。','charge_cost_consumer、charge_free_consumer、_h_charge_*'
    if 155<=line<=157:
        return '确认缺陷','T10-I13；标记写入正确但回合消费向每个场下全额复制，违反总量随机分配。','share_gains_consumer'
    if 160<=line<=239:
        return '确认缺陷','T10-I05/I06；常规12球和柔软18候选已逐一运行，正确/错误子分支见semantic_review.csv；同函数结论不意味每一单效果都错。柔软重入固定首次抽取需Q01。','contract_*、soft_*'
    if 244<=line<=250:
        return '确认缺陷','T10-I07；18血脉只有萌分支，且配置固定萌；不能据唯一存在分支把整个特性通过。','bloodline_*'
    if 253<=line<=258:
        return '规则存疑','T10-Q02；默认3层、无上限999且受退化链长限制；3层上限缺权威规则依据，真实现有链较短不抹去疑问。','cute_default_cap、cute_no_cap'
    if 262<=line<=278:
        return '确认缺陷','T10-I09；正常退化形态数值与不可退化拒加已验证，但直接覆盖基础速度会丢永久速度。HP如何恢复另Q02。','cute_add、cute_no_previous、cute_permanent_speed_next_gain'
    if 282<=line<=317:
        return '通过','自身/敌方/双方/己方全队各目标已跑有退化链和无退化链正反，场下力竭者不加、对方未被全队原语误加；只通过目标分发，不覆盖内部退化永久属性缺陷及赤子配置错误T06-I09。','_h_cute_gain_*、_h_cute_enemy_gain_*、_h_cute_both_*、cute_team_bench'
    if 322<=line<=336:
        return '确认缺陷','T10-I08；无萌化早退正常，但有层数时清层后不恢复形态/属性。CUTE_CLEAR_SELF接口无当前配置不等于未上线。','_h_cute_transfer、_h_cute_clear_self、cute_transfer_zero'
    if 340<=line<=344:
        return '通过','有萌化时仅向本次ctx.result._power_bonus加60，无萌化时不加；已运行正反分支。','_h_cute_if_power_bonus_True/False'
    if 348<=line<=360:
        return '规则存疑','T10-Q03；实际状态技能power=0也增加为10（s.power>=0），但全技能威力是否包括无威力技能需说明；无实际萌化增加时不加已验证。','cute_power_perm、_h_cute_on_gain_power_perm_no_gain'
    if 363<=line<=370:
        return '通过','只有实际增加萌化才降每个技能能耗且不低0；没有链时不降，已运行。生日蛋糕与赤子之心配置错由T06负责；当前reduce默认4不冒充原文2。','_h_cute_on_gain_cost_reduce_True/False'
    if 374<=line<=380:
        return '确认缺陷','T10-I09；本次加到基础speed，后续退化被覆盖，永久性不成立；无实际加层早退已验证。','cute_permanent_speed_next_gain、_h_cute_on_gain_speed_perm_no_gain'
    if 384<=line<=391:
        return '确认缺陷','T10-I10；零层不变正常，但正层数本次增益永久累加技能基础连击。','cute_team_power_twice、cute_team_power_zero'
    if 395<=line<=403:
        return '确认缺陷','T10-I11；致命/非致命与连续3次及上层消费分别复现，首次实战仍力竭。','cute_lethal_*'
    if 407<=line<=409:
        return '规则存疑','T10-Q02；no_cap标记生效但受退化链约束；是否突破链或仅突破默认上限未知。','cute_no_cap'
    if 413<=line<=417:
        return '通过','标记本身保存per，handlers_skill.py:95按萌化层数添加到本次hit_count且不写永久hit_count；当前配置per=2与原文3已由T06-I10登记，不据接口局部通过覆盖配置错误。','_h_cute_hit_per_stack_True/False及静态消费者'
    if 421<=line<=429:
        return '通过','己方场下其他存活精灵萌化数之和减全技能耗；排自身/排力竭，零和早退，正例队友2层使4→2；参数与守护者原文一致。','_h_cute_bench_cost_reduce_True/False'
    return '检查受阻','文件整体由逐函数覆盖，不能给文件整体通过；各独立分支结论见对应行。','全部探针'

def main():
    """记录分支覆盖和精确已知限制。"""
    probes=json.loads((OUT/'probe_output.json').read_text(encoding='utf-8'))
    inventory=list(csv.DictReader((OUT/'assigned_inventory.csv').open(encoding='utf-8-sig',newline='')))
    fields=['item_id','conclusion','rule_basis','implementation','objects','method','evidence','notes','reachability']
    coverage=[]
    for row in inventory:
        line=int(row['line'])
        conclusion,note,case=classify(line,row['kind'],row['description'])
        hits=[x['case'] for x in probes if line in x.get('field_lines',[])]
        coverage.append({'item_id':row['item_id'],'conclusion':conclusion,'rule_basis':'issues.md及questions.md按原语列出权威规则原文/行号；'+row['description'],'implementation':row['source']+':'+str(line),'objects':row['name'],'method':'完整文件逐行静态检查；123探针；消费者全core字段搜索；line trace仅说明执行触达，不当成规则通过','evidence':'probe_output.json:'+case+'；执行该源码行的case='+','.join(hits),'notes':note,'reachability':'当前配置或公开EffectTag执行接口；未挂配置的接口单列，不能据此称未上线'})
    extra=[]; semantic=[]
    for probe in probes:
        name=probe['case']
        if not name.startswith(('contract_','soft_','bloodline_','refraction_')):
            continue
        if name.startswith('refraction_'):
            conclusion='确认缺陷';issue='T10-I02（排自身全类型）及I03/I04具体分支'
        elif name.startswith('bloodline_'):
            conclusion='通过' if name=='bloodline_萌' else '未实现';issue='萌分支双攻-.6匹配；其余17分支T10-I07，接口无效果而不拒绝'
        elif name.startswith('soft_'):
            opt=name[5:]
            conclusion='确认缺陷' if opt in {'skill_power','heal','slow_combo','speed','def','atk','combo','freeze','energy'} else ('规则存疑' if opt=='reentry' else '通过')
            issue='T10-I06；仅判断此候选的基础效果是否匹配，随机再次抽取Q01及免疫路径单列'
        else:
            conclusion='确认缺陷' if name in {'contract_普通咕噜球','contract_高级咕噜球','contract_国王球','contract_淘沙球'} else '通过'
            issue='T10-I05；仅本球中性目标下全部效果数值核对，不外推免疫/反制'
        iid='FIELD:'+name
        extra.append({'item_id':iid,'kind':'semantic_branch','name':name,'owner':'T10','source':'nrc_core/engine/handlers_field.py','line':'58' if name.startswith('refraction') else ('244' if name.startswith('bloodline') else '160'),'parent_id':'FILE:nrc_core/engine/handlers_field.py','description':probe['expected'],'reachability':'参数分支接口可达；血脉当前配置固定萌，但其他分支需支持，非未上线'})
        semantic.append({'item_id':iid,'case':name,'conclusion':conclusion,'expected':probe['expected'],'notes':issue,'evidence':'probe_output.json:'+name})
        coverage.append(dict(zip(fields,[iid,conclusion,probe['expected'],'nrc_core/engine/handlers_field.py',name,'固定输入逐分支执行，核对双方字段和阵营印记，不以无异常当通过','probe_output.json:'+name,issue,extra[-1]['reachability']])))
    writer(OUT/'coverage.csv',coverage,fields)
    writer(OUT/'inventory_extra.csv',extra,list(inventory[0]))
    writer(OUT/'semantic_review.csv',semantic,list(semantic[0]))
    docs=['# T10 场地原语审计问题','', '所有输入见probe.py，完整前后状态见probe_output.json；均为内存调用，不修改业务或数据库。123个探针覆盖常规12球、柔软18候选、18血脉、18折射类型及重复/免疫/萌化/消费者。数值夹具：HP1000当前500，四攻防与速度200，能量5，技能威力50耗4。','']
    for iid,title,start,end,basis,objects,difference,cases,severity in ISSUES:
        docs += ['## '+iid+' '+title,'','严重度：'+severity+'；主责：T10；协同：T06配置、T07执行器、T04回合消费者；T10-I12归并T07主问题不重复。','', '规则依据/原文行号：'+basis+'。', '', '代码位置：nrc_core/engine/handlers_field.py:'+str(start)+'（截至'+str(end)+'的函数/分支），消费者位置见下文。', '', '对象：'+objects+'。','', '最小输入步骤：调用probe.py中的`'+cases+'`，输入快照保留全部双方字段、技能、阵营场地与参数对应场景。随机池以固定choice记录候选，不修改业务。','', '预期与实际：'+difference,'', '影响：'+objects+'的规则结果，不能据接口无异常或技能能执行而认为已支持。','', '证据：probe_output.json按case检索；semantic_review.csv保留每个球/血脉/折射分支结论；coverage.csv关联源码行与实测line trace。','']
    (OUT/'issues.md').write_text('\n'.join(docs),encoding='utf-8')
    summary={'assigned':len(inventory),'extra':len(extra),'coverage':len(coverage),'cases':len(probes),'conclusions':dict(Counter(x['conclusion'] for x in coverage)),'missing':sorted({r['item_id'] for r in inventory}-{r['item_id'] for r in coverage})}
    (OUT/'checkpoint.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    main()
