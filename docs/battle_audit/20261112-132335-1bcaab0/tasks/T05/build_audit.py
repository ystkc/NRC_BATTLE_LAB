"""T05稳定清单合并同ID碰撞并记录独立规则证据。"""
import ast
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
ISSUES=[
 ('I01','确认缺陷','P1','愿力动作按原首槽过滤且无法选择替换后不用','data/部分规则详解/共鸣魔法.md:7-22','nrc_core/runtime.py:319-337,346-357',['I01_willpower_legal','I01_unused_willpower'],'能量3，原首槽耗8，携愿力；另用双技能完整状态枚举动作。','应可将首槽变为能耗2愿力，实际仅charge；原首槽合法时也仅允许使用首槽，无法配合charge或其他技能，违反即使未使用仍消耗次数与到期还原的子句。','全部愿力与原槽耗能/冷却/多次使用交叉；共鸣后应重新计算合法动作。','T05主责'),
 ('I02','确认缺陷','P1','愿力还原按原主人固定首槽，交换后临时技能遗留','data/部分规则详解/共鸣魔法.md:14,18; data/wiki/skills.csv:523','nrc_core/rules_support.py:166-174,186-188',['I02_restore_swap'],'A慢于B，A用愿力，B真实隐藏条款先交换双方整套技能。','回合结束B仍永久持有愿力冲击，A被覆盖回A原技能；至少临时愿力必须在下一回合消失。按交换语义预期A保留隐藏条款、B得到A原技能，但跨交换精确归属仍需确认，不影响当前遗留临时技能事实。','愿力和技能交换/替换交叉；传动当前未实现移动，本证据不假设传动已运行。','T05还原主责，T07技能交换协同'),
 ('I03','确认缺陷','P1','首领化更新六维和特性但未更新战斗属性','data/部分规则详解/共鸣魔法.md:24-36','nrc_core/rules_support.py:115-137',['I03_boss_types'],'已解析首领血脉A普通系，唯一目标record为火/龙，使用进化之力。','首领名称/六维/特性已变、原技能保留，但pokemon_type/pokemon_types仍normal，应跟随首领火龙战斗属性。血脉远古变更没有充分字段规则，另列questions。','所有首领形态与基础形态属性不同的记录；克制、本系、免疫等计算仍按旧属性。','T05主责，T03数值公式另有I01'),
 ('I04','确认缺陷','P1','替补入场与连锁入场力竭不扣MP','data/README.md:30,35; nrc_core/models.py:604-606','nrc_core/runtime.py:404-423,441-443,252-276',['I04_entry_faint_mp','I04_enemy_entry_faint_mp'],'已死A已扣MP剩3，选择HP40替补，在荆刺1层下入场即死；另选抓到你了替补令B80HP获得冻结2层死亡。','本方再次力竭应MP3→2，实际仍3；敌方新力竭应MP4→3，实际仍4。虽然进入下一replacement阶段，整个补位流程没有调用扣MP/ON_FAINT结算；若继续替补，死亡者可永远不再被检查。','入场印记伤害、入场攻击/冻结造成双方连锁死亡，可能逃过MP败北/复活触发。','T05补位主责，T04扣MP入口协同'),
 ('I05','确认缺陷','P1','初始化、补位和下一回合准备在种子随机域之外','nrc_core/README.md:公开入口/规则模块；rng.py作用域契约；data/README.md:19','nrc_core/runtime.py:68-72,225-226,441-443,480',['I05_seed_new_game','I05_seed_replacement','I05_seed_next_turn'],'固定new_game seed77，用正式盲拧ON_TURN_START改变进程random种子1/2/3；固定advance seed78，用柔软球替补入场；并从同一会话advance后准备下一回合。','同对战seed应相同；实际盲拧顺序、柔软球随机效果随进程random改变。_isolated_rng定义未在这些入口使用，simulate_turn只包技能回合的内部。','初始/替补/回合准备的全部随机机制；共鸣首领入场也在同一未包裹区域，具体随机特性可达性逐配置另核。','T05主责，T04 rng工具通过不外推调用方'),
 ('I06','确认缺陷','P1','技能槽锁定未进入合法动作过滤','正位宝剑/宝剑王牌原文与effect_data SKILL_SLOT_LOCK；nrc_core/README.md:advance只接受合法动作','nrc_core/runtime.py:319-337; nrc_core/battle.py:1626-1631',['I06_slot_lock'],'当前skill_slot_lock=[0]且携两个能量足技能，枚举合法动作。','slot1仍被列为可选，且附带光合组合动作；实际执行则静默改聚能。应不列锁定槽动作，或按明确协议展示聚能。','正位宝剑/宝剑王牌；合法动作和真正执行不一致，影响用户/搜索。','T05主责，T06配置协同'),
 ('I07','未实现','P1','禁足机制未表示，流沙执行后仍可离场','GAME_RULE禁足；data/wiki/game_descriptions.csv:52; data/wiki/skills.csv:287,354','nrc_core/runtime.py:333-337; nrc_core/effect_models.py/全core检索禁足机制缺失',['I07_ban_switch'],'使用真实流沙原文/硬编码效果，目标有健康替补，执行后读取状态和合法动作。','未获得禁足且可switch；原文禁止离场3回合。未实现也没有UnsupportedMechanicError，不能静默忽略。','流沙、石锁及一切禁足来源；再次施加免疫与持续回合均缺。','T05合法动作协同，T06技能原文生成/状态handler主责'),
 ('I08','未实现','P1','选择类仅保存选项字符串，两个分支效果未执行','data/部分规则详解/选择类技能.md:3-5; data/wiki/skills.csv:441','nrc_core/runtime.py:323-330; nrc_core/rules_support.py:203; 全core selected_choice引用',['I08_choice'],'真实补觉，两分支分别从HP500/能量3开始执行。','第0分支应HP750/能量1、第1分支HP500/能量9；实际都HP500/能量1，只有selected_choice字符串不同。全core没有读取selected_choice的效果分发，不应假装已支持。','所有选择技能、加尔额外触发及选择计数；具体技能效果若另缺也不掩盖分支协议缺口。','T05选择接口主责，T07/T06效果配置协同'),
 ('I09','确认缺陷','P1','新对局未触发初始精灵入场特性','data/README.md:22; data/wiki/spirits.csv 抓到你了原文；nrc_core/README.md new_game初始化','nrc_core/runtime.py:211-227,279-283',['I09_initial_enter'],'完整状态A带正式抓到你了ON_ENTER配置，B完整，调用new_game。','应使B冻结2层、全技能耗+1；实际冻结0、耗1不变、entry_count0。new_game仅battle_start和turn_start，未发ON_ENTER；平台builder也无该事件调用。','开局仅定义ON_ENTER的特性，以及初始入场计数与入场印记；中途导入既有战局不能重复触发，需区分初始化责任。','T05初始化主责，T01构建入口协同'),
 ('I10','确认缺陷','P2','默认日志与环境变量行为不符README','nrc_core/README.md:验证与诊断末段；nrc_core/debug.py函数说明','nrc_core/debug.py:10,37-38',['I10_logging_docs'],'NRC_CORE_LOG环境变量设为空，configure_core_logging(None)后记录damage事件。','README称默认不输出并由环境变量控制；实际读取硬编码NRC_CORE_LOG="damage"，仍输出一条日志。此为公开诊断接口偏差，不作为游戏规则缺陷。','所有默认import与日志配置，无需假设敏感信息攻击风险。','T05诊断文档主责'),
]


def read_csv(path):
    """显式UTF-8读取清单。"""
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    """覆盖稳定ID，重复IfExp记录原始行号与条件。"""
    inventory=read_csv(HERE/'assigned_inventory.csv'); grouped=defaultdict(list)
    for item in inventory: grouped[item['item_id']].append(item)
    sources={}
    for item in inventory:
        source=item['source']
        if source in sources: continue
        path=ROOT/source
        text=path.read_text(encoding='utf-8'); lines=text.splitlines()
        sources[source]=(lines,[n for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.ClassDef))] if path.suffix=='.py' else [])
    proofs={
      '_weather_backups':('nrc_core/README.md 快照/clone完整状态','按side/index/slot记录真实技能id对应原耗；P02快照重建后new skill id被正确映射，未泛化T03手工deep_copy。'),
      '_restore_weather_backups':('nrc_core/README.md 快照/clone完整状态','先清旧id字典，再按side/index/slot生成新对象id；合法索引恢复，越界项不恢复。P02 actual weather_id_correct=True。'),
      'clone':('nrc_core/README.md clone深复制','整体deepcopy会话并专门重建天气id；P02 graph指向本副本场上精灵、原始状态不变，区别于T03分精灵复制。'),
      'display':('nrc_core/README.md 只读显示','克隆后算面板；P02以pickle字节比较前后状态相同，ambient random状态相同。具体面板数值完整性由T04审计，不因只读通过外推。'),
      'preview_damage':('nrc_core/README.md 只读预览','调用副本display，检查slot下界/上界并dict复制返回。P02真实slot0只读；非法slot ValueError静态路径明确。'),
      'export_state':('nrc_core/README.md 快照','只序列化可信本地同版本会话；在克隆上清id备份另行储存，不污染原会话。P02往返图引用/天气/决策一致。'),
      'import_state':('nrc_core/README.md 快照','先format/manifest校验再解码，_check_state复验类型/版本；重建天气id。P02合法往返通过，pickle被限定可信本地，不提出泛安全缺陷。'),
      '_is_boss_bloodline':('data/部分规则详解/共鸣魔法.md:24-32','读取平台resolved_boss_bloodline，不从名称猜测；False/缺失均不可进化，True才允许。形态变换完整性I03另记。'),
      '_bloodline_type':('data/部分规则详解/共鸣魔法.md:12,20','仅接受平台解析的Type，不按名字推断；缺失None、已解析Type原样返回；入场后血脉变化定义另列问题。'),
      '_team':('nrc_core/contracts.py player协议','0取A、1取B及其当前index，其他值抛ValueError，逐路径静态核验。'),
      '_check_state':('nrc_core/README.md 同版本会话','非BattleSession抛TypeError，manifest不等抛VersionMismatchError；一致返回原会话，无状态修改。'),
      'decision':('nrc_core/contracts.py Decision','取会话决策index/turn/phase/players/terminated/winner逐字段映射，无随机或变更；P02往返decision相等。'),
      'action_map':('nrc_core/contracts.py 动作键唯一协议','重复/空键立即ValueError，不覆盖静默丢动作；P04两种反例均实际被拒绝。'),
      '_to_legacy_action':('nrc_core/README.md 完整动作；actions主动作互斥','聚能/PASS映射-1，switch必须有index，skill必须给合法slot并保存choice。选择仅传递字符串通过不证明效果；I08另记。'),
    }
    rows=[]
    for ident,items in grouped.items():
        item=items[0]; source=item['source']; line=int(item['line'])
        lines,nodes=sources[source]
        containers=sorted([n for n in nodes if n.lineno<=line<=n.end_lineno],key=lambda n:n.end_lineno-n.lineno)
        function=containers[0].name if containers else '<file>'
        conclusion='规则存疑'; rule='nrc_core/README.md 公开协议；具体规则见notes'
        proof='已完整静态读取此条件；仍缺独立规则边界证明，不以函数存在判通过。'
        related=[]; reach='生产可达；非法输入防御分支另列条件'
        if function in proofs:
            conclusion='通过'; rule,proof=proofs[function]
        if source.endswith(('schema.py','codec.py','unknown.py','actions.py','contracts.py','devotion.py','__init__.py')):
            conclusion='通过'; rule='nrc_core/README.md 结构化协议；data/部分规则详解/奉献.md；data/部分规则详解/选择类技能.md'
            proof='逐字段静态核对构造与to_json字段保持，Maybe区分known/exists而非按真假补值，actions保留slot/choice/items。P03实际False与未知/不存在、choice往返；P04空/重复键拒绝。此项只证明结构映射，不证明平台补全和技能执行。'
            if function in {'validate_primary','validate'}:
                proof='逐分支核对SKILL至少name/id/slot之一，slot0按is not None保留；SWITCH缺index报错；ITEM不能作primary，items须ITEM。PASS是否能当聚能为约定边界另列Q。'
            if source.endswith('devotion.py'):
                proof='5种奉献潜变量与上限5/10/10/10/10吻合详解；random_is_unresolved只在draws已知>0且分布未确定时True，不猜具体分配。采样权重与上限实际授予在handler任务，不由此协议通过外推。'
        if source.endswith('runtime.py'):
            if function in {'legal_actions','_with_resonance_actions'}: related=['I01','I06']
            if function in {'_replacement','_pending_players'}: related=['I04']
            if function in {'new_game','_prepare_decision'}: related=['I05','I09']
            if function=='advance': related=['I04','I05']
            if function in {'_skill_json','_pokemon_json','observe','_report_state'}:
                rule='nrc_core/README.md observe为全知数据，正式遮蔽在平台；data/对战过程中的信息遮蔽规则.md'
                proof='静态检查正式遮蔽归平台，因此核心opponent_team携全阵容本身不判泄露；但是快照状态类别/层数可见性与事件私有修正须对照平台最终输出，不能在此把全部字段正确性判通过。'
        if source.endswith('rules_support.py'):
            if function=='_apply_boss_resonance': related=['I03']
            if function=='_restore_resonance_items': related=['I02']
            if function=='_apply_resonance_items':
                if 156<=line<=174: related=['I02']
                else:
                    rule='data/部分规则详解/共鸣魔法.md:3-42'
                    proof='P01实际无carried首次solar后锁定、禁止其他及再次使用、后台三回合与P06死亡不复活；P05愿力两次/CD递减和普通不交换还原通过。缺catalog愿力None、boss属性、交换还原、未使用动作等仍独立检查，不能外推所有共鸣分支。'
                    if 177<=line<=182 or 144<=line<=155:
                        conclusion='通过'
            if function in {'_snapshot_layers','_snapshot_statuses','_snapshot_marks','_snapshot_ability_states','_state_change_events'}:
                rule='data/状态分类.md；data/部分规则详解/战报.md；data/对战过程中的信息遮蔽规则.md'
                proof='逐字段静态核对；状态记录中的特性身份、负数层数、public_skill_modifier扣除和同名精灵/技能归属需与平台战报实际输出联合证明，未仅凭快照代码判全部通过。'
        if source.endswith('debug.py') or source.endswith('README.md'):
            related=['I10']
        if item['kind']=='file':
            if source.endswith('runtime.py'): related=['I01','I04','I05','I06','I09']
            if source.endswith('rules_support.py'): related=['I02','I03']
        if related:
            conclusion='确认缺陷'; rule='；'.join(i[4] for i in ISSUES if i[0] in related)
            proof='；'.join('T05-'+key for key in related)+'，见issues与真实probe输出；文件/函数级含缺陷不代表所有分支都错。'
        if function=='_isolated_rng':
            conclusion='通过'; rule='rng_scope作用域约定'
            proof='定义本身RLock与Random(seed)作用域正确，finally退出通过rng_scope复原。当前生产未引用单列可达性；实际调用方未包seed属于I05，不能以未引用豁免缺口。'; reach='当前生产未引用；只有定义，入口未调用'
        if function in {'_layer_entries','_layer_name','_layer_stacks'}:
            reach='当前规则构造链未引用或仅旧层输入适配；可达性不改变规则存疑结论'
        rows.append(dict(item_id=ident,conclusion=conclusion,rule_basis=rule,implementation=f'{source}:{line} {function} | '+ ' / '.join(i['description'] for i in items),objects=function,method='完整静态核对；实际内存输入/只读回归见probe',evidence=f'{source}:{line}: {lines[line-1].strip()}；probe_output.json',notes=proof+'；ID原始条数='+str(len(items))+'；方向='+' / '.join(i['name'] for i in items),reachability=reach))
    output=json.loads((HERE/'probe_output.json').read_text(encoding='utf-8'))
    extra=[]
    for key,value in output.items():
        match=next((issue for issue in ISSUES if key in issue[6]),None)
        ident='SEMANTIC:T05:'+key
        extra.append(dict(item_id=ident,kind='semantic_check',name=key,owner='T05',source='tasks/T05/probe.py',line=1,parent_id='',description='实际执行完整输入并比较独立规则期望',reachability='对应生产公开接口可达'))
        rows.append(dict(item_id=ident,conclusion=match[1] if match else ('规则存疑' if key=='P05_willpower_limits' else '通过'),rule_basis=match[4] if match else 'nrc_core/README.md公开协议；data/部分规则详解/共鸣魔法.md',implementation='probe.py:'+key,objects=key,method='实际执行内存输入；输出保留实际值和预期',evidence='probe_output.json:'+key,notes='T05-'+match[0] if match else ('次数限制/普通还原通过；冷却3起算口径仍Q07，实际轨迹不假装唯一文义' if key=='P05_willpower_limits' else '输出期望与实际一致；仅证明该具体路径'),reachability='公开runtime接口或诊断配置可达'))
    with (HERE/'inventory_extra.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(extra[0])); writer.writeheader(); writer.writerows(extra)
    with (HERE/'coverage.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    issues=['# T05 问题记录','','10项中I07/I08为已知规则机制未实现且静默跳过，其他为确定偏差；I10仅诊断文档P2，游戏规则问题均P1。T04普通脱离暂停不在本任务重复编号。','']
    for key,classification,severity,title,basis,code,outputs,steps,behavior,impact,owner in ISSUES:
        issues += [f'## T05-{key} {title}','','- 结论：'+classification+'；严重度：'+severity+'；主责协同：'+owner,'- 规则依据/原文行号：'+basis,'- 代码位置：'+code,'- 最小输入步骤：'+steps,'- 预期与实际：'+behavior,'- 影响范围：'+impact,'- 证据：probe.py；'+ '；'.join('probe_output.json:'+k+' `'+json.dumps(output[k],ensure_ascii=False)+'`' for k in outputs),'']
    (HERE/'issues.md').write_text('\n'.join(issues),encoding='utf-8')
    counts=dict(Counter(r['conclusion'] for r in rows)); dupes={key:len(v) for key,v in grouped.items() if len(v)>1}
    (HERE/'report.md').write_text(f'''# T05 运行接口、动作、共鸣与协议审计

完整静态读取runtime/rules_support/actions/codec/contracts/schema/unknown/devotion/debug/__init__.py及nrc_core/README.md，原始assigned清单{len(inventory)}行、唯一ID{len(grouped)}个；同一IfExp生成ID碰撞合并到一行，notes保留原条数/条件，待T00拆稳定后缀。额外{len(extra)}项实际语义验证列入inventory_extra和coverage。coverage每个唯一ID恰一行。分类计数：{json.dumps(counts,ensure_ascii=False)}。碰撞清单见id_collisions.json。

实际运行probe.py退出0。用CSV原文+现有效果表构建完整内存目录，不使用产品loader写数据库。验证真实技能补觉两分支、隐藏条款技能交换、流沙禁足，正式盲拧/契约的形状随机配置，首领resolved record，愿力合法动作/次数/冷却/还原与光合后台/死亡时长，替补入场荆刺与对方入场冻结连锁力竭。只读、快照与clone使用pickle字节前后、对象身份、天气新技能id直接比较，不泛化T03错误复制接口。

10个问题分别有实际输入输出；其中8项确认缺陷，2项规则机制未实现。初始化当前不触发初始ON_ENTER，正式抓到你了没有入场效果；入场引起双方力竭有replacement但无MP扣除；种子实际覆盖技能结算内部，new_game/replacement/下一回合准备未受seed隔离。首领化六维受T03 Float32缺陷影响，本任务独立确认types没有更新，不重复数值根因。

真实通过证据：P01光合HP轨迹500/650/800/800（立即+三次，每次150；切到后台继续），P06死亡不被治疗且倒数递减；首次无carried自动锁定solar、之后禁其他和再用。P05愿力首次uses1/CD2，等待两回合CD0，第二次uses2且无第三次，普通未换技能场景正确还原。P02预览状态字节与环境随机不变、整体clone与快照图引用/天气id正确。P03未知/不存在/False/choice结构转换；P04动作键重复和空拒绝。通过仅限明确的结构映射或实测路径，不宣称所有共鸣/非法输入/隐藏信息都完整正确。

重点边界：普通脱离需即时真实选择的问题沿用T04-I11，不重复统计；自力竭后后手是否继续沿用T04-Q00待裁决。愿力交换还原用真实隐藏条款，未假设传动已移动；传动移动缺失由T07主责。双人同时共鸣/补位速度顺序、蓄力是否禁止手动换人、首领血脉远古变化、缺catalog未实现错误类别等具体未明处见questions，不据可达性或函数存在刷通过。快照明确可信本地使用，不提出泛pickle安全问题。

全部输出限tasks/T05，未改业务或数据。复现命令：设置PYTHONIOENCODING=utf-8、PYTHONUTF8=1后运行python -m docs.battle_audit.20261112-132335-1bcaab0.tasks.T05.probe及build_audit。
''',encoding='utf-8')
    (HERE/'id_collisions.json').write_text(json.dumps(dupes,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(raw=len(inventory),unique=len(grouped),counts=counts,collisions=dupes),ensure_ascii=False))


if __name__=='__main__':
    main()
