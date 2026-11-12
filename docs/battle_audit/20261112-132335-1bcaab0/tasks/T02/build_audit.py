"""T02 逐稳定ID记录证据；规则未裁决和未取证分支保留存疑。"""
import ast
import csv
import json
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
ISSUES=[
('I01','P1','构造输入中的力竭精灵被复活',
 'data/README.md:30,35；nrc_core/schema.py CreatureState.hp/status 明确输入；GAME_RULE力竭',
 'nrc_platform/builder.py:459-487；nrc_core/models.py:354-364',
 'I01_zero_hp','完整六维HP1000，state.hp=0、status=fainted，正式BattleBuilder.build。另以真实一窝蜂/虫群鼓舞和其学习表前4技（乘风/信息素/借用/倾泻）复核，仍复活；附I01_real_species_control输入输出。',
 '应保留HP0与力竭；实际HP1000、status=normal、is_fainted=False。builder将0传入Pokemon默认哨兵初始化后未还原，也完全忽略state.status。',
 '显式初始残血/力竭输入、需要保留已知状态的构造边界；不泛化到runtime pickle导入。','T02构造主责；T03模型默认哨兵接口协同'),
('I02','P1','六项正资质被完整接受，缺少最多三项校验',
 'data/属性数值计算.md:30（每个精灵最多拥有三项大于零的资质值）',
 'nrc_platform/builder.py:318-338,363-365,474-487,589-647',
 'I02_six_positive_iv','base.individual_values六项全部8，提供完整六维隔离公式，正式build。',
 '应拒绝六项正资质；实际六项iv_*均8且无异常。这里只核最多三项约束，绝不裁决文档6倍与+8→+40冲突。',
 '所有显式资质输入，非法组合可进入公式；与T03 Float16/倍数问题不同。','T02输入校验主责，T03公式协同'),
('I03','P2','neutral/zero模式实际套用非中性坦率性格',
 'data/属性数值计算.md:6-22（坦率位于生命-/物防+，分别-10%/+20%）；builder的attribute_assumption协议',
 'nrc_platform/builder.py:354-362,398-411',
 'I03_neutral_nature','只提供HP1000，metadata.attribute_assumption=neutral；物防种族27、资质0。',
 'neutral/zero标记应代表无性格修正；实际记录assumption:neutral但nature=坦率、物防98。独立无性格公式round_half_up(round_half_up(27×1.1+10)×1)+50=90；坦率则40×1.2+50=98。游戏没有中性性格，若产品只想任选性格，至少不能将此输出标为neutral。',
 '单HP快捷输入被强制切neutral；zero/all_zero和无分布fallback同样使用坦率。默认应如何选择性格仍另列Q02，不从本问题强推产品默认。','T02默认解析主责；P2内部协议/说明偏差'),
('I04','P2','核心可解析的技能ID被建造校验拒绝，名称路径又重写ID',
 'nrc_core/schema.py:SkillSlotInput.skill_id/name；nrc_core/catalog.py:CoreCatalog.get_skill支持ID；nrc_platform/builder.py接口',
 'nrc_platform/builder.py:442-453,586-587,630-633',
 'I04_id_only','拍击目录ID skill_000303；对照catalog.get_skill(ID)，再以skills=[{skill_id:ID}]正式build。',
 '目录能解析该ID为拍击；build先用names-only集合拒绝unknown skill。仅传name时又将目录稳定ID重写为拍击。应保持名称/ID两种协议一致并保留稳定标识。',
 '所有ID-only输入、需要目录ID的下游关联；目前常用slot动作仍可执行，不夸大为全技能不可用。','T02平台结构化协议主责'),
('I05','P1','输入中多个同属性增益被后项覆盖',
 'data/伤害数值计算.md:15（同方加成和减弱同时存在、层数叠加）',
 'nrc_platform/builder.py:524-538',
 'I05_duplicate_buff','buffs=[物攻10%×2,物攻10%×3]，debuffs={atk:2}，基础物攻100。',
 '应保留五层加成和两层减弱，atk_up=.5、atk_down=.2；实际atk_up=.3、atk_down=.2，有效物攻108.3333而非125。每条setattr覆盖前条而非合并。',
 '同一属性由多个条目给出的输入；增/减两桶本身并存通过。100层不封顶的输入端证据另关联T03-I03，避免重复主问题。','T02状态注入主责，T03状态模型协同'),
('I06','P2','属性值不识别时静默改为普通',
 'nrc_core/models.py Type枚举；nrc_platform/catalog.py _TYPE_ALIASES；AGENTS未知机制不静默降级',
 'nrc_platform/builder.py:422-429',
 'I06_english_combat_types','完整构造输入base.attributes=[fire,water]（核心Type.value与目录解析均使用/接受的名称）。',
 '应识别火/水，或按明确中文输入契约拒绝；实际接受后变成normal/normal，既不保留输入也不报错。中文18系正式目录装载转换已独立通过，不能据此掩盖该显式输入路径。',
 '英文核心枚举回填、拼写错误和未知类型；影响克制、本系与免疫。P2输入适配缺陷，具体公开输入枚举约束另请明确。','T02类型适配主责'),
('I07','P2','嵌套base类型未拒绝，预览请求落入AttributeError',
 'nrc_platform/input.py merge_creature_spec映射协议；HTTP预览结构化参数错误约定（T12端到端）',
 'nrc_platform/input.py:35-49；rooms.py:282-291；codec.py:66-88',
 'I07_preview_invalid_base','RoomService.pokemon_preview({name:迪莫,base:invalid})；并测base=[1]、3。',
 '应以结构化参数错误拒绝。merge将非Mapping的base原样交给下游，三个输入分别触发str/list/int没有get的AttributeError；T12实际HTTP返回500。修正应在输入边界或统一schema拒绝，不把坏参数变成服务器内部错误。',
 '预览及共用merge/codec的嵌套字段；非游戏规则问题、不泛化安全攻击。单HP后缀与坏base组合还会得到不同ValueError，属于同一缺少统一形状校验根因。','T02输入主责；T12 HTTP协同'),
('I08','P1','奉献减耗别名错字使随机初始化崩溃',
 'data/部分规则详解/奉献.md:1-2；nrc_core/engine/handlers_field.py DEVOTION_TYPES；builder初始化契约',
 'nrc_platform/builder.py:30-36,245-257,285-295',
 'I08_devotion_alias','own.devotion指定power_bonus=5、random_draws=1，seed=2，完整双方正式build；seed0..7保留全部输出。',
 '应获得五种中的一种合法奉献。实际随机到假寐后规范化仍是假寐，RANDOM_DEVOTION_CAPS[假寐]抛KeyError。别名和LEGACY_DEVOTION_KEYS使用假寥，正式handler使用假寐。seed1/3/4抽飞断则可成功但超过上限，该独立问题归T10-I01。',
 '随机奉献初始化抽到减耗时；已知canonical cost_reduce输入也被转换成假寥，可能不能被真实假寐消费者读取。前者已实际证实，后者消费者影响需要T10协同。','T02别名/初始化主责；T10奉献消费者协同'),
]


def read_csv(path):
    """以UTF-8读取稳定清单。"""
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))


def write_csv(path,rows,fields):
    """写审计产物，不写业务目录。"""
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    """生成完整逐ID台账和具有具体待证实点的结论。"""
    inventory=read_csv(HERE/'assigned_inventory.csv')
    outputs=json.loads((HERE/'probe_output.json').read_text(encoding='utf-8'))
    source_data={}
    for source in {r['source'] for r in inventory}:
        text=(ROOT/source).read_text(encoding='utf-8')
        source_data[source]=(text.splitlines(),[n for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.ClassDef))])
    rows=[]
    questions={
      '_layer_entries':'仅认识dict/list，非法或未知层类型会被丢为空；恢复接口究竟要求拒绝还是兼容忽略，缺权威输入形状约定。',
      '_layer_stacks':'分数层使用银行舍入、负数置零；原文只给整数层，分数层输入应拒绝还是舍入未定义。',
      '_layer_unit_value':'数值unit直接作比例，字符串无论有无百分号均除100；纯数字字符串和速度绝对值unit约定待明确。',
      '_normalize_individual_values':'基础资质/最终资质单位及合法范围未统一，超过三项已证实I02；6倍vs5倍明确冲突不裁决。',
      '_bloodline_values':'输入血脉数组允许多个值；原文唯一性和首领/奇异/污染是否需要严格拒绝组合的schema待明确。',
      '_is_boss_bloodline':'中文子串和英文boss/lord/leader识别，未知血脉不拒绝；首领形态实际血脉来源与远古变更缺权威数据字段。',
      '_bloodline_type':'排除三种特殊字符串后按中文子串首个匹配；多值或含特殊标记混合输入被接受，合法唯一血脉的规范输入集合未确定。',
      '_resolve_combat_config':'未知性格/资质取使用率最高的性格和三项60；属性数值计算.md:52称只能观察，full模式是否授权此默认假设待裁决。',
      '_normalize_devotion_counts':'未知键会被过滤而非拒绝；假寐别名I08；满层/合并上限另归T10-I01。',
      '_apply_devotion_input':'随机初始化的别名I08和满池/合并上限T10-I01已证实；未知draws/known-but-absent random_counts的兼容政策仍未裁决。',
      '_build_legacy':'上下文与显式MP/天气/marks映射已静态核对；未知信息默认、初始ON_ENTER责任T05-I09、首领/远古血脉元数据和中途状态完整性不能外推通过。',
      '_creature_to_legacy':'已核对每一项字段注入；HP0、IV、技能ID、buff、类型的具体分支有独立问题；其余隐含默认、status/初始可见元数据、退化链来源见Q，不把构造成功等同规则正确。',
      '_validate_setup':'已执行六种拒绝与两种特性/未上线共鸣拒绝；空效果技能、随机源标记缺失、初始bossified全拒绝等支持边界不能仅因校验函数存在判通过。',
      '_skill_effects':'生成配置优先、手工配置最后覆盖（包括空列表）静态明确；具体覆盖是否规则正确归T06，不能把存在配置判为完整实现。',
      '_choice_options':'正则仅截首个选择句并按或/斜杠/顿号分割；不是所有中文选择语法均可解析，合法两分支原文与额外触发规则见T05-I08/T06，未独立穷举语法。',
      'load_catalog':'直接读取完整580技能625形态；字段转换有P03/P06/P07独立证据，退化来源推断、括号继承与首领映射语义仍见Q05，charge遗漏归T06-I15。',
      'build':'已有正式输入输出证明构造路径、隔离随机域；全知状态声明与未知字段默认存在Q02，不能把入口成功当完整全知通过。',
    }
    good={
      '__init__':('nrc_platform/README.md 每个平台注入独立CoreCatalog','构造函数只保存注入目录和logger，未自行查库或设置全局目录；正式probe为同目录独立builder，P02技能状态未串扰。','P02_instance_isolation'),
      '_canonical_resonance':('data/部分规则详解/共鸣魔法.md:3-48','逐个中文/英文别名核对愿力、首领、光合，未匹配值保留后由validate拒绝；未上线两种实际Unsupported，未当可达性分类。','P01_unsupported_gate'),
      '_distribution_rows':('catalog分布按(spirit_name,kind)分开协议','取特定kind并dict复制；P07全49343行/2376组，blood/nature/skill/talent四类各594组，排序、项目和百分比未串合。','P07_distribution_separation'),
      '_known_skill_names':('CoreCatalog.skills名称索引契约','名称集合本身与目录一致；ID-only拒绝在调用方I04，不能将此集合通过外推名称和ID整个校验。','I04_id_only'),
      '_layer_name':('schema层条目name/status/stat别名约定','依次取name/status/stat并保留非空字符串，缺失标unknown；仅证明结构映射，不证明未知状态合法。','I05_duplicate_buff'),
      '_stat_layer_key':('data/伤害数值计算.md:15；显式状态字段契约','中英五维名与_up/_down后缀映射至对应属性，未将增减两桶混合；P05同方atk_up/.down同时保留。重复同桶覆盖I05另记。','I05_duplicate_buff'),
      '_status_layer_key':('GAME_RULE 中毒/灼烧/冻结/寄生/引电/萌化/连击；schema状态字段','中英状态别名与_stacks后缀对应静态逐项核对；只证明键规范化，不证明恢复施加时应再触发免疫/伤害。','Q03_restore_immunity'),
      'split_creature_spec':('input.py公开name[HP]/name[六维]紧凑输入协议','P05六维顺序hp,atk,def,spatk,spdef,speed；一项HP和空字符串正确，其他数字项数抛ValueError。静态数字后缀循环只吃完整非负整数，名称剩余部分连接。','P05_compact_input'),
      '_lookup':('18属性和四技能分类；data/wiki/skills.csv','P06以独立中文18系与四分类表核对580技type/category/power/cost/id/description均一致；未知字符串的子串容错并未获得权威语义，因此该容错分支单独存疑。','P06_skill_conversion'),
    }
    # 独立分支只绑定实际受影响的一侧；对象/文件汇总另行关联根因。
    issue_branches={
      (328,'true'):['I02'],(329,'body'):['I02'],(365,'true'):['I02'],
      (354,'true'):['I03'],(357,'false'):['I03'],(399,'true'):['I03'],(402,'true'):['I03'],
      (443,'true'):['I04'],(632,'true'):['I04'],
      (530,'body'):['I05'],(532,'true'):['I05'],(533,'true'):['I05'],(533,'false'):['I05'],
      (423,'false'):['I06'],(425,'false'):['I06'],
      (286,'true'):['I08'],(289,'body'):['I08'],(293,'body'):['I08'],
    }
    for item in inventory:
        source=item['source']; line=int(item['line']);lines,nodes=source_data[source]
        containers=sorted((n for n in nodes if n.lineno<=line<=n.end_lineno),key=lambda n:n.end_lineno-n.lineno)
        func=containers[0].name if containers else '<file>'
        conclusion='规则存疑';rule='AGENTS规则优先级；具体见本行待证实点'
        proof=questions.get(func,'对象已逐行静态审阅；文件汇总不等于所有子分支规则正确，具体缺口见本任务issues/questions。')
        evidence='完整静态检查 '+source+':'+str(line);issue_refs=[]
        if func in good:
            rule,proof,key=good[func];conclusion='通过';evidence+='；probe_output.json#'+key
        if source.endswith('catalog.py') and func=='_lookup' and line>=53:
            conclusion='规则存疑';proof='实际目录字段均精确匹配通过；substring容错把notfire识为fire、notphysical识为物攻。坏输入如何拒绝未有明确schema，不能把目录主路径证明外推容错分支。'
        if source.endswith('catalog.py') and func=='load_catalog' and 92<=line<=101:
            conclusion='通过';rule='原始学习关系/分布字段独立映射契约';evidence+='；probe_output.json#P03_learning_table,P07_distribution_separation'
            proof='625形态直读学习表逐形态无差异；四kind分布全量49343行、2376组无串合。分布只供nature/talent默认；skill分布未替代spirit_skills。零条记录分支只产生空集合，不生成猜测条目。'
        if source.endswith('catalog.py') and line==147:
            rule='data/wiki/skills.csv 明示N连击与未明示默认一击';proof='首个数字连击正则的基本转换静态可读；复杂条件连击与永久叠加归T06/T07，未用完整独立多段基数oracle验证580技，保留存疑。'
        if source.endswith('builder.py'):
            if item['kind']=='code_branch':
                issue_refs+=['T02-'+ident for ident in issue_branches.get((line,item['name']),[])]
            if item['kind']=='code_object':
                byfunc={'_normalize_individual_values':['T02-I02'],'_resolve_combat_config':['T02-I03'],
                        '_canonical_devotion_key':['T02-I08'],'_apply_devotion_input':['T02-I08','T10-I01'],
                        '_creature_to_legacy':['T02-I01','T02-I02','T02-I04','T02-I05','T02-I06']}
                issue_refs+=byfunc.get(func,[])
            if (line,item['name']) in {(273,'true'),(276,'true'),(277,'body')}:
                issue_refs.append('T10-I01')
            if 496<=line<=510:
                conclusion='规则存疑';rule='GAME_RULE萌化；T01 evolution_links来源审计'
                proof='拒绝多前阶/循环，预解析仅name/stats。实际262链均adjacent_number_stage推断，尚无权威详情证实，不能以唯一推断当真实退化规则；Float16归T03-I01。'
            if func=='_validate_setup' and item['kind']=='code_branch' and (
                'not request.own_team.creatures' in item['description'] or
                'active_index < 0' in item['description'] or
                item['description'] in {'not db_record','not creature.skills','not self.catalog.get_ability_effects(ability)','skill_name == "愿力冲击"','unsupported'} or
                'resonance in {' in item['description']):
                conclusion='通过';rule='共鸣魔法未上线声明/结构化完整输入/未实现抛Unsupported'
                proof='P01实际拒绝整点报时/未知特性与闪焰/节流；P08实际拒绝空队、越界首发、无技能、未知精灵、愿力携带、非完整六维。此行只证明具体显式拒绝，不外推完整能力覆盖。';evidence+='；probe_output.json#P01_unsupported_gate,P08_reject_inputs'
            if line in (304,308,313,525):
                conclusion='通过';rule='左右方及增/减桶独立映射协议'
                proof='静态逐字段核对a/b分别写对应devotion、specified、draws、random_counts；up/down分别写buffs/debuffs，未混桶。P05实际atk_up/.down并存，随机初始化I08与上限T10在赋值之前的独立问题。';evidence+='；probe_output.json#I05_duplicate_buff,I08_devotion_alias'
            if line in (609,):
                conclusion='规则存疑';rule='data/部分规则详解/共鸣魔法.md:28'
                proof='bossified=True无条件判未支持，P Q06实际Unsupported；常驻首领迪莫合法，究竟此入口只接普通初始形态还是需支持常驻首领待裁决。'
        if source.endswith('input.py') and func=='merge_creature_spec':
            if item['kind']=='code_object' or (line,item['name'])==(44,'false'):
                issue_refs=['T02-I07']
            elif (line,item['name']) in {(39,'true'),(42,'false'),(44,'true')}:
                conclusion='通过';rule='input.py公开紧凑字段合并协议'
                proof='P05实际Maybe结构name原样保留、纯数值后缀按顺序合并并覆盖对应原stats且保留其他项。该分支只证明合法合并；没有后缀时坏base穿透的另一分支I07单列。';evidence+='；probe_output.json#P05_compact_input'
            else:
                conclusion='规则存疑';proof='合法name合并已运行，但此条件本身不能证明所有嵌套shape均已校验；缺少统一坏base拒绝的路径见I07。'
        if item['kind']=='file':
            conclusion='确认缺陷';issue_refs=({'nrc_platform/builder.py':['T02-'+r[0] for r in ISSUES if r[0]!='I07'],
                                            'nrc_platform/catalog.py':['T06-I15'], 'nrc_platform/input.py':['T02-I07']}[source])
            proof='文件已完整静态检查；该汇总结论来自列出问题，其他分支各自有独立结论；catalog主缺陷T06主责、此处为装载接口证据。'
        if issue_refs:
            conclusion='确认缺陷'
            proof+='；关联问题 '+','.join(dict.fromkeys(issue_refs))+'，具体预期实际和复现见issues.md；本行其他语义不自动判通过。'
            evidence+='；issues.md#'+','.join(dict.fromkeys(issue_refs))
        rows.append(dict(item_id=item['item_id'],conclusion=conclusion,rule_basis=rule,
                         implementation=f'{source}:{line} '+(lines[line-1].strip() if line<=len(lines) else ''),
                         objects=func,method='完整静态检查；按说明关联正式入口复现/独立源数据核对',evidence=evidence,
                         notes=proof+'；清单条件='+item['description'],reachability='生产入口可达；非法输入/空集合防御按各分支条件可达，不以可达性替代规则结论'))
    extras=[]
    with (ROOT/'data/wiki/skills.csv').open(encoding='utf-8-sig',newline='') as stream:
        skillrows=list(csv.DictReader(stream))
    learn_names=[]
    # 实际P03逐个迭代625形态；名称来自稳定T00只读冻结产物，不重开产品数据库。
    forms=json.loads((HERE.parent/'T00/spirit_forms.json').read_text(encoding='utf-8'))
    if isinstance(forms,dict):forms=forms.get('rows',forms.get('items',[]))
    for record in forms:
        if isinstance(record,dict) and record.get('name'):learn_names.append(record['name'])
    for index,name in enumerate(learn_names):
        ident=f'EXTRA:T02:LEARNING:{index:04d}'
        extras.append(dict(item_id=ident,kind='semantic_case',name=name,owner='T02',source='nrc_platform/catalog.py',line=92,parent_id='FILE:nrc_platform/catalog.py',description='逐形态学习表装载一致性；括号继承仅作现有转换契约，不证实学习资格',reachability='生产目录可达'))
        rows.append(dict(item_id=ident,conclusion='通过',rule_basis='data/nrc_wiki.db只读spirit_skills权威关系作为装载源；T01 CSV/DB一致性',implementation='nrc_platform/catalog.py:92,126,134-140',objects=name,method='正式load_catalog+独立只读查询逐形态比对',evidence='probe_output.json#P03_learning_table',notes='625形态转换比较无差异；仅证明目录与源关系表一致。空关系的括号前基名继承是否权威合法另列Q05；未知form关系归T01，不据此宣告未上线。',reachability='生产目录可达'))
    for index,record in enumerate(skillrows):
        ident=f'EXTRA:T02:SKILL_FIELDS:{index:04d}'; name=record['名称']
        extras.append(dict(item_id=ident,kind='semantic_case',name=name,owner='T02',source='nrc_platform/catalog.py',line=148,parent_id='FILE:nrc_platform/catalog.py',description='六字段独立CSV对照：type/category/power/cost/stable-id/description',reachability='生产目录可达'))
        rows.append(dict(item_id=ident,conclusion='通过',rule_basis='data/wiki/skills.csv原始六字段（T01已验证DB一致）',implementation='nrc_platform/catalog.py:148-158',objects=name,method='独立中文18系与四分类映射；全部580技逐字段比对',evidence='probe_output.json#P06_skill_conversion',notes='全部580技六字段0差异；愿力无wiki_id采用数据库数字id606作明确fallback。效果正确性、charge、随机源、选择与多段不在该通过边界。',reachability='生产目录可达'))
    semantic=[
      ('ZERO_HP','确认缺陷','I01_zero_hp','T02-I01','HP0/status丢失'),
      ('IV_LIMIT','确认缺陷','I02_six_positive_iv','T02-I02','最多三项独立于倍数冲突'),
      ('NEUTRAL','确认缺陷','I03_neutral_nature','T02-I03','仅neutral语义/诊断P2，不裁默认政策'),
      ('SKILL_ID','确认缺陷','I04_id_only','T02-I04','ID-only与名称ID保持'),
      ('BUFF_MERGE','确认缺陷','I05_duplicate_buff','T02-I05','同桶累加/增减并存'),
      ('TYPE_INPUT','确认缺陷','I06_english_combat_types','T02-I06','未知类型不能静默普通'),
      ('PREVIEW_SHAPE','确认缺陷','I07_preview_invalid_base','T02-I07','非Mapping嵌套base协议P2'),
      ('DEVOTION_ALIAS','确认缺陷','I08_devotion_alias','T02-I08','假寐/假寥错字'),
      ('CHARGE','确认缺陷','X01_charge_turn','T06-I15','主问题归T06；5技charge=False，升龙首次直接扣180'),
      ('DEVOTION_CAP','确认缺陷','X02_devotion_over_cap','T10-I01','主问题归T10；正式初始化power14与满层仍抽'),
      ('INSTANCE','通过','P02_instance_isolation','','同名技能/效果实例独立'),
      ('DISTRIBUTION','通过','P07_distribution_separation','','四类49343行2376组未串合'),
      ('REJECT','通过','P08_reject_inputs','','具体六种明确拒绝，不外推全部unsupported'),
      ('BLOODLINE','规则存疑','Q01_bloodline','','唯一性、特殊血脉、英文接受政策Q01'),
      ('UNKNOWN','规则存疑','Q02_unknown_defaults','','全知与显式unknown默认Q02'),
      ('RESTORE_STATUS','规则存疑','Q03_restore_immunity','','恢复状态是否需要重判免疫Q03'),
      ('POOL_METADATA','规则存疑','Q04_no_skill_pool_metadata','','skill_pool未从目录注入Q04'),
      ('BOSS_CHAIN','规则存疑','Q05_boss_devolution','','退化来源和首领映射Q05'),
      ('INITIAL_BOSS','规则存疑','Q06_initial_boss','','合法常驻首领输入被Unsupported的支持边界Q06'),
    ]
    for key,conclusion,evidence,ref,note in semantic:
        ident='EXTRA:T02:'+key
        extras.append(dict(item_id=ident,kind='semantic_case',name=key,owner='T02',source='nrc_platform/builder.py',line=1,parent_id='FILE:nrc_platform/builder.py',description=note,reachability='正式入口或明确结构输入可达'))
        rows.append(dict(item_id=ident,conclusion=conclusion,rule_basis=ref or 'report.md/questions.md具体依据',implementation='详见issues.md/questions.md',objects=key,method='正式入口最小输入实际运行；独立源数据/静态结合',evidence='probe_output.json#'+evidence,notes=note+'；主责='+ref,reachability='正式入口可达；不以缺少生产调用判未上线'))
    fields=['item_id','conclusion','rule_basis','implementation','objects','method','evidence','notes','reachability']
    write_csv(HERE/'coverage.csv',rows,fields)
    write_csv(HERE/'inventory_extra.csv',extras,list(inventory[0]))
    issues=['# T02 问题记录','', '本目录只审计，不改业务。T06-I15、T10-I01、T05-I03/I09与T03公式/复制问题均保留接口证据，不重复计主问题。','']
    for ident,severity,title,rule,code,key,steps,result,scope,owner in ISSUES:
        issues += [f'## T02-{ident}｜确认缺陷｜{severity}｜{title}','',f'- 主责协同：{owner}',f'- 规则依据/原文行号：{rule}',f'- 代码位置：{code}',f'- 最小输入步骤：{steps}',f'- 预期与实际：{result}',f'- 影响范围：{scope}',f'- 证据：`probe.py` 实际运行；`probe_output.json#{key}`。','']
    issues += ['## 跨任务接口证据（不重复主问题）','',
      '- T06-I15：目录5个前缀蓄力技能均charge=False；升龙咆哮首回合能量10→7、对方HP1000→820，charging_skill_idx=-1；原文要求先蓄力1回合。证据X01_charge_catalog/X01_charge_turn。',
      '- T10-I01：指定power5且random_draws1，seed1/3/4仍抽power并合成6；指定9+已知随机5合成14，未统一封顶/满池排除。证据I08_devotion_alias/X02_devotion_over_cap。',
      '- T03-I03：build输入100层物攻加成保留atk_up=10而非99层9.9。证据I05_over_cap；有效属性又被模型40层限制，属于T03两处根因，不重复报。',
      '- T05-I03：目录首领记录含types，但builder只注入boss_form名，运行时首领化不更新types，主根因在T05；远古血脉字段和映射权威性保留Q05。',
      '- T05-I09：builder将首发entry_count至少置1，但不执行ON_ENTER，runtime也未初始调用；不因entry_count存在就认为入场效果已落实。',
      '- T11-I01：direct builder对空effects特性明确拒绝，P01已实际验证；上层_Catalog抹掉名称绕过校验归T11，不重复。','']
    (HERE/'issues.md').write_text('\n'.join(issues),encoding='utf-8')
    questions_text='''# T02 待裁决问题

## Q01 血脉唯一性与规范输入

问题：共鸣详解20行称血脉唯一，并排除首领/奇异/污染；schema用数组，builder接受多个并取首个中文系别。冲突依据：共鸣魔法.md:20、26-30，属性克制表.md:43与当前宽松子串解析。需裁决：应强制恰一血脉还是兼容历史多标签；英文枚举和特殊标签的规范值。影响：愿力、首领合法动作和花宝等。当前行为：火|水→fire；首领|火同时boss=True/type=fire；奇异火/污染水无系别。确认后验证：规范三特殊血脉拒绝愿力，18系逐一可用；多值/未知值按裁决拒绝或明确转换，不随机猜测。

## Q02 full建造是否允许把明确unknown当默认值

问题：属性数值计算.md:52称性格/资质只能观察得出，AGENTS将平台作为全知/非全知分界；build说明返回不含未知占位。需裁决：fresh缺省和显式unknown是否不同，以及是否允许使用率第一性格/三项60资质的确定猜测。影响：未知HP/能量/性格/资质/特性。当前行为：明确hp/energy unknown变满血/10；未知性格按分布第一、资质取前三项60；unknowns只返回私有_LegacyBuild随后被build丢弃，核心看不到假设来源以外的unknown。确认后验证：fresh默认的授权范围、显式unknown拒绝/待补全、输入值优先与来源标注。neutral错误单列I03，不用该问题给任意默认方案背书。

## Q03 状态恢复与施加必须区分

问题：builder直接设置整数statuses，绕过施加免疫和事件；冰系输入冻结2仍保留。冲突依据：GAME_RULE冻结的冰系免疫与可持有的历史状态/形态变化可能不同；不能仅因冰系有冻结就判缺陷。需裁决：此setup是全新施加还是允许恢复已有状态。影响：免疫、引电2层即时伤害、萌化退化和组合状态。当前行为：原始层数写入，不触发除冻结阈值外的事件；state.status完全丢弃已在I01。确认后验证：恢复不重复扣血/事件，新施加按免疫；对组合状态和未知状态不得静默丢失。

## Q04 完整全知元数据的必填/补全边界

问题：目录有学习表但缺省skill_pool只写None，evolution_stage/bossified也仅保留显式输入，不回填目录；source/known_to_observer/nature_modifiers等协议字段未进入模型。依据：信息遮蔽规则.md:5技能池/性格/资质可API提供，核心全知架构与schema字段。需裁决：哪些字段仅供上层展示，哪些必须供规则执行；技能随机/变形池应是精灵学习表、属性池还是全目录。影响：变形/复写与初始观测。当前行为：技能实例独立，但池与来源未补全。确认后验证：每种池选择与变形规则使用明确权威数据，不以使用率替代学习表，不按未知推测。

## Q05 退化链、括号技能继承与首领映射来源

问题：T01已发现262条退化链都为adjacent_number_stage推断，尚未详情证实；catalog忽略inference_method即纳入previous_forms。同编号唯一lord自动映射23普通形态，其他需metadata.boss_form。依据：GAME_RULE萌化退化、共鸣魔法.md:28-30；本地数据并不等同已证实规则。需裁决：各形态真实退化链、括号变体学习技能继承、lord与普通形态映射，以及远古血脉激活条件/字段。影响：萌化数值、共鸣变身、技能资格。当前行为：多前阶/循环会拒绝，唯一推断被接受；链只注入name/stats；首领记录没有远古血脉字段。确认后验证：权威例逐条链、迪莫多首领指定、types与血脉变化分别检查。首领types运行时丢失归T05-I03，不重复。

## Q06 常驻首领的输入支持

问题：共鸣魔法.md:28明确S3迪莫可常驻首领，builder却对bossified=True一律Unsupported。需裁决：build是否承担此合法初始状态，还是明示由另一已存在入口承接；不能以缺支持当文档未上线。影响：常驻首领及导入的已首领化状态。当前行为：Q06实际拒绝；直接输入lord名字但不标bossified可能通过且元数据None。确认后验证：初始实际形态/数值/特性/属性与不允许对局中切换其他首领、共鸣使用次数等一致。

## Q07 分数层/纯数unit与输入形状

问题：_layer_stacks使用round银行舍入，_layer_unit_value数值0.1原样、字符串0.1除100，未知层类型丢为空。依据：整数层与绝对速度/百分比增益原文，schema目前Any。需裁决：严格合法形状、层数须整数、unit为比例还是百分数字、未知状态如何拒绝。影响：输入状态与面板一致性。当前行为：同桶覆盖I05已确认，其他不规范输入转换尚无明确约定。确认后验证：合法整数、百分单位、绝对速度分开，坏输入统一结构化错误；不编造分数游戏机制。

## Q08 缺配置/空配置技能的拒绝策略

问题：验证只拒绝未配置特性和random_source已标记技能；catalog创建所有技能但大多数random_source默认空，空效果技能可继续进入。依据：AGENTS未实现抛Unsupported；T05-I08真实补觉空分支证据；T06具体配置审计。需裁决：显式已支持能力清单和已知空效果是否可合法无操作，随机技能是否确实全部支持。影响：借用/取念/复写及选择等。当前行为：存在字段不等于已支持；不把所有空effects统一判缺陷。确认后验证：逐个明确能力要么实际执行完整规则，要么Unsupported，不静默消失。
'''
    (HERE/'questions.md').write_text(questions_text,encoding='utf-8')
    counts=Counter(r['conclusion'] for r in rows);assigned_counts=Counter(r['conclusion'] for r in rows[:len(inventory)])
    report=f'''# T02 目录装载、输入与建造审计

已完成 nrc_platform/catalog.py、builder.py、input.py 全文件静态读取，346/346 assigned ID 均有且仅有一行coverage；额外{{len(extras)}}个语义/逐对象条目，共{{len(rows)}}条。源文件冻结HEAD以主baseline.json的a393307为准；目录旧短码不代表实际HEAD。只写本任务目录、未改业务。

本地独立主问题8项（P1四项：I01/I02/I05/I08；P2四项：I03/I04/I06/I07）。T06-I15蓄力、T10-I01奉献封顶、T03状态上限、T05首领types/初始化、T11空特性绕过均按主责归并，协同证据保留。

逐ID统计：assigned {dict(assigned_counts)}；含extra {dict(counts)}。这些是代码/语义条目计数，不是独立缺陷数。规则存疑逐行写具体待证实点；没有因当前生产未引用而标未上线。

检查方法：沿原始数据→load_catalog→结构化codec→BattleBuilder.build→CoreCatalog实例→simulate_turn逐边界追踪；现行权威data/*.md优先，详解其次，再技能/特性原文；旧测试与历史对局不作正确oracle。所有实际目录连接由probe只读包装强制SQLite URI mode=ro；固定内存输入隔离特性/数值公式，正式build或RoomService预览运行。Python显式UTF8，中文补丁仅原生apply_patch。

实际验证：625形态学习表逐项一致；580技能type/category/power/cost/id/description与独立CSV映射无差异（愿力原始wiki_id空，明示采用DB数字id606）；49343分布记录按2376组，blood/nature/skill/talent各594组，未串合。skills使用直接学习关系，不用skill分布替代；nature/talent默认确实使用分布并见Q02。P02同名技能及首层effect不同实例，改甲技能威力/能耗后乙与目录均不变。空队、越界首发、无技能、未知form、携带愿力、缺项六维六种实际拒绝；未实现特性与未上线共鸣实际Unsupported。

重要实际反例：HP0→满血；六项正资质进入；neutral套非中性坦率；ID-only被拒且name-only重写ID；两个物攻增益条目只保留后项；英文属性静默普通；坏base三个类型使预览AttributeError；随机奉献seed2抽假寐KeyError。协同反例：升龙咆哮首回合直接扣180；奉献power5满层仍可随机得到第6层，输入指定9+随机5最终14。

覆盖边界：六字段转换通过不证明效果配置、charge/选择/迅捷/随机源完整；学习表转换通过不裁括号继承资格与44未知form来源。退化链推断来源、远古血脉、首领多映射、unknown默认和skill_pool完整性保留问题。不重复T03全量Float32公式；不把pickle可信本地快照提成公开安全问题。P2接口/诊断偏差与P1游戏状态缺陷明确区分。

复现命令（PowerShell）：设置PYTHONIOENCODING=utf-8、PYTHONUTF8=1、PYTHONPATH=.后运行python docs/battle_audit/20261112-132335-1bcaab0/tasks/T02/probe.py；然后运行同目录build_audit.py。probe_output.json记录原始最小输入和实际输出。首次运行发现模块路径/取方法名等脚本问题均已修正，最终probe退出0；没有因工具诊断误读中文文件。
'''
    report=report.replace('{len(extras)}',str(len(extras))).replace('{len(rows)}',str(len(rows)))
    (HERE/'report.md').write_text(report,encoding='utf-8')
    print(json.dumps(dict(assigned=len(inventory),extra=len(extras),coverage=len(rows),counts=counts,assigned_counts=assigned_counts),ensure_ascii=False))


if __name__=='__main__':main()
