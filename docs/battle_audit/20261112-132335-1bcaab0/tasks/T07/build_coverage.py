"""把人工静态审阅结论逐项映射至分配清单，不声称动态分支覆盖。"""
import ast
import csv
import json
from collections import Counter
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from nrc_core.effect_models import E, Timing, SkillTiming, SkillEffect
from nrc_core.engine.registry import _HANDLERS, _ABILITY_HANDLER_OVERRIDES
from nrc_core.effect_data import SKILL_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED

FIELDS = ['item_id', 'conclusion', 'rule_basis', 'implementation', 'objects', 'method', 'evidence', 'notes', 'reachability']
STATE = 'data/状态分类.md:2-6'
VIS = 'data/对战过程中的信息遮蔽规则.md:3-7'
PROCESS = 'data/README.md:22-35'
CONTRACT = 'AGENTS.md（用户本轮提供）架构规则：未实现机制显式拒绝'

# 每个注释描述的是实际检查范围；并不以函数共享证据替代每个分支运行。
NOTES = {
 'E': ('通过', CONTRACT, '仅枚举完整性：200原语唯一；199默认注册；INTERRUPT由应对入口特判。不判定处理器内部游戏规则'),
 'Timing': ('通过', PROCESS, '16个枚举均存在核心引用；逐时点顺序属于回合组；本项只检查分发协议与枚举对应'),
 'SkillTiming': ('通过', PROCESS, '6阶段均有执行/收集分支；具体阶段过滤缺口另见I07'),
 'EffectTag': ('规则存疑', STATE, 'Q04：嵌套字典copy共享；不代表生产代码已经修改该对象'),
 'AbilityEffect': ('规则存疑', STATE, 'Q04：effects递归复制而filter仅浅复制'),
 'SkillEffect': ('规则存疑', STATE, 'Q01/Q04：阶段过滤契约及浅拷贝'),
 '__init__': ('通过', STATE, '静态核对参数赋值、None与空字典/列表默认值；默认容器按调用新建，不是类级共享'),
 '__repr__': ('通过', STATE, '仅诊断文本，不改变状态；type/timing要求合法枚举。未知类型应由入口拒绝，见I01'),
 'copy': ('规则存疑', STATE, 'Q04；effects/sub_effects递归复制，params/condition/filter嵌套仍共享；运行证据copy_nested'),
 'Ctx': ('通过', STATE, '无全局状态；传入result即保留同一字典，未传才新建，且保留空字典身份'),
 '_global_skill_cost_sources': ('规则存疑', VIS, '逐handler核对作用域分支；只认显式来源不靠四槽相等猜测。I04为被绕过；数值条件未逐handler规则验证，不能判整函数通过'),
 '_apply_tag': ('确认缺陷', CONTRACT, 'I01：未知handler未拒绝；另核对正反特性覆盖优先级、技能重排槽按对象id对齐、嵌套全局delta扣除。未逐排列动态验证'),
 'EffectExecutor': ('确认缺陷', PROCESS, '聚合I02/I03/I04/I05/I06/I07；各分支逐源静态检查，不代表全部分支动态触达'),
 'execute_skill': ('通过', PROCESS, '仅检查首项类型决定新旧格式、参数转发、返回结果一致；混合格式不是受支持契约'),
 '_execute_skill_legacy': ('规则存疑', PROCESS, '静态核对先非伤害后伤害、post_use标签、吸血与临时攻击消耗；与SE路径吸血顺序差异缺组合规则，不判通过'),
 '_execute_skill_se': ('确认缺陷', PROCESS, 'I07：POST_USE不检查filter已影响极限撕裂；I08嵌套SE崩溃；静态检查其他阶段及伤害延后，阈值取值时点待Q01'),
 'execute_counter_se': ('确认缺陷', VIS, 'I04直调水环handler绕过来源记录；类别匹配与打断/切换特判已核对；重算伤害Q06未完整复演'),
 'execute_counter': ('确认缺陷', VIS, 'I04新旧均绕过来源分发；新格式委派、旧类别匹配和计数顺序静态核对；Q06'),
 'execute_ability': ('规则存疑', VIS, '时点相等后过滤；共享context按设计传递，复用时_is_ability_ctx/_ability_timing会保留；报告前后数值/运行标志/场地差异已读，完整嵌套战报需可见性组复演'),
 'execute_agility_entry': ('确认缺陷', 'data/wiki/game_descriptions.csv:6', 'I02/I03/I06；已动态复现伤害丢失、授予标志不识别、旧格式多次释放'),
 'execute_drive': ('未实现', 'data/部分规则详解/传动机制.md:3-9', 'I05：实现旧含义的后方被动触发而无移位；含空列表/找不到技能guard也只属于旧机制'),
 '_check_ability_filter': ('规则存疑', PROCESS, '静态核对元素单值/集合、能量条件、位置、对手系别；未知键/条件默认放行；skill_element_not_enemy_type只比较主属性，双属性需要特性规则裁决'),
 '_check_runtime_condition': ('规则存疑', PROCESS, 'HP严格大于/小于与换人侧别静态核对；未知condition返回True，其中部分由专用handler消费，不能一概报错；Q01'),
 '_check_skill_filter': ('规则存疑', PROCESS, '逐键读完：HP边界、上回合标志、敌换宠、击杀预测、层数；I07 category提前返回，counter不验证上下文；Q01'),
 '_get_ability_name': ('通过', STATE, '解析半角/全角冒号前名称；无冒号返回原字符串，不作查库'),
 '_promise_modifiers': ('确认缺陷', 'data/wiki/game_descriptions.csv:13-14；data/wiki/spirits.csv:58；'+STATE, 'I10：萌化明确减益却列在buffs，真实退化使王子成本2→1而非3；遗漏技能成本/部分负向技能修正仍需逐源补证；复合特性本身不属于普通增益，不能一概纳入。证据cleanse_probe_output.json#王子萌化分类'),
 '_apply_prince_promise': ('规则存疑', STATE, 'Q03；每种每回合限一次和先比较后记turn静态核对；增减益观察集合需裁决'),
 '_find_skill_index': ('通过', STATE, '按携带技能名线性定位，缺失返回-1；本结论限技能名唯一输入'),
 '_ability_report_snapshot': ('通过', VIS, '快照原始数值/技能值、复制public字典和每槽字典；Pokemon引用仅用于后续比较，不深拷贝整个对局'),
 '_ability_runtime_snapshot': ('通过', VIS, '只抽取受限深度的基础值；排除私有键、lab_metadata/layered_state/battle_context；复合状态只含name/stacks，不公开技能定义'),
 'value_snapshot': ('通过', VIS, '递归深度上限4，非基础对象记None；dict排私有键；只用于判断变化'),
 '_report_ability_changes': ('通过', VIS, '仅静态信息流：公共数值与modifier公开、逐槽减去全局delta后仅owner事件；技能重排按slot比较可能产生私有噪声，未证明泄露'),
 '_share_heal_to_bench': ('规则存疑', PROCESS, 'Q05：随机选一只存活场下，整笔给予并封顶；缺指定权威分配语义'),
 '_share_energy_to_bench': ('规则存疑', PROCESS, 'Q05：随机选一只存活场下，整笔gain_energy；缺分配和溢出语义'),
 '_apply_ability_buff': ('规则存疑', STATE, '把特性buff转复合状态并换算每层；extra按倍数而非stacks扩大，营养液泡应给何种层数需特性规则'),
 '_apply_buff': ('规则存疑', STATE, '逐atk/def/spatk/spdef/speed/all_atk/all_def与镜像分支核对；额外层、镜像对象生命周期需特性组；非该函数的copy污染不扩大'),
 '_apply_debuff': ('通过', STATE, '只检查各属性键写对应_down字段；all_atk/all_def分别同时写双攻/双防；异常状态不在这里处理'),
 '_clear_buffs': ('规则存疑', STATE, '正向字段归零、保留负向skill_power等；没有清除compound_statuses，是否应驱散其中状态取决于类别，不能一概清掉特性'),
 '_clear_debuffs': ('确认缺陷', 'data/wiki/game_descriptions.csv:14（GAME_RULE8）；data/wiki/skills.csv:285,521；'+STATE, 'I09：真实洗礼/除厄完整effects运行后仅五维_down归零，明确属于减益的poison/burn/freeze/leech/cute/electric未清；印记和特性保留控制正确。skill_cost_mod/负威力与临时加耗亦未清，分类与独立来源另述，不以属性赋值成功掩盖完整清除缺口。证据cleanse_probe.py/cleanse_probe_output.json'),
 '_ability_name': ('规则存疑', STATE, '与_get_ability_name不一致：不处理全角冒号而去全角括号；平台目前注入纯名，兼容字符串格式需定契约'),
 '_adjust_cost_delta': ('通过', STATE, '按两个已注入标记依次反转、乘2；不依赖名称查库；仅检查数值原语，不判断各特性授予时点'),
 '_iter_flat_tags_static': ('通过', STATE, '只展开一层SE.effects，旧tag直接yield；空输入迭代为空；sub_effects不递归是当前约定，嵌套应对执行另走execute_counter'),
 '_apply_permanent_mod': ('规则存疑', STATE, 'guard触发器、cost封底0/power封底0/hit_count封底1已核对；未知target静默忽略、per_use必须外部force；所有target支持性属技能组'),
 '_execute_agility_old': ('未上线', 'data/wiki/game_descriptions.csv:6', '旧格式直接扣能和HP、裸buff/dot；没有完整新格式事件流程。平台可用无effects迅捷未证明，I06'),
 '_skill_matches_ability_filter': ('规则存疑', PROCESS, '元素、分类、纯攻击、动态能耗阈值逐条件静态核对；pure_attack用只有单DAMAGE判定是否足够需特性定义'),
 '_apply_matching_skill_mods': ('规则存疑', STATE, 'Q02/Q04；永久百分比绝对重算，授予agility不插标签见I03；status_key分支提前返回，count为0也创建0层状态'),
 '_record_public_skill_modifier': ('通过', VIS, '公开名义全局delta与私有每槽实际变化分别累加；封底后的actual来自before对照；输入before长度需等于当前技能数'),
}


def main():
    """为每个文件、函数、分支落地限定范围的结论。"""
    assigned = list(csv.DictReader((OUT / 'assigned_inventory.csv').open(encoding='utf-8-sig')))
    trees = {}
    for row in assigned:
        source = row['source']
        if source not in trees:
            trees[source] = ast.parse((ROOT / source).read_text(encoding='utf-8'))
    rows = []
    static = ['# T07 逐对象静态检查记录', '', '所有分支通过源码逐项定位；没有使用行覆盖率冒充真假分支运行覆盖。共享证据只适用于notes明确限定的函数内部静态范围。', '']
    for row in assigned:
        source, line = row['source'], int(row['line'])
        nodes = [n for n in ast.walk(trees[source]) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.lineno <= line <= n.end_lineno]
        node = min(nodes, key=lambda n: n.end_lineno - n.lineno) if nodes else None
        name = node.name if node else ''
        conclusion, rule, note = NOTES.get(name, ('通过', CONTRACT, '仅模块导入/TYPE_CHECKING静态连通性，不改变运行战斗状态'))
        if row['kind'] == 'file':
            by_file = {'nrc_core/effect_models.py': ('规则存疑', STATE, 'Q04浅拷贝；枚举另有extra逐项登记'),
                       'nrc_core/engine/dispatch.py': ('确认缺陷', CONTRACT, 'I01未知原语静默忽略；I04存在绕过入口'),
                       'nrc_core/engine/executor.py': ('确认缺陷', PROCESS, 'I02-I07；全部阶段与两种格式已静态阅读'),
                       'nrc_core/engine/filters.py': ('规则存疑', PROCESS, 'Q01过滤器契约和未知条件处理'),
                       'nrc_core/engine/helpers.py': ('规则存疑', STATE, 'Q02-Q05；简单赋值和私有事件信息流已静态审阅')}
            conclusion, rule, note = by_file.get(source, ('通过', CONTRACT, '兼容导入与唯一注册映射静态核对，无自身游戏规则'))
        if row['kind'] == 'code_branch':
            # 分支关联整个函数的疑点不等于该真假分支都已确证触发缺陷。
            if conclusion in {'确认缺陷', '未实现'}:
                note += '；本分支只做静态控制流定位，函数问题不代表此分支已动态复现'
                conclusion = '规则存疑'
            if 'TYPE_CHECKING' in row['description']:
                conclusion, rule, note = '未上线', CONTRACT, 'TYPE_CHECKING仅类型检查为真；正常运行false，非游戏规则分支'
        location = f'{source}:{line}'
        rows.append(dict(zip(FIELDS, [row['item_id'], conclusion, rule, location, name or row['name'],
                                     '静态逐项源码审阅；选定问题最小运行复现', 'static_review.md；probe_output.json；issues.md；questions.md',
                                     note + ('；条件：' + row['description'] if row['kind'] == 'code_branch' else ''),
                                     '仅兼容/构造入口，线上可达性未证实' if conclusion == '未上线' else '核心入口可达；具体分支并未全部运行'])))
        if row['kind'] == 'code_object':
            static.append(f'- `{location}` `{name}`：{conclusion}。{note}。范围{node.lineno}-{node.end_lineno}。')
    extra = []
    for cls in (E, Timing, SkillTiming):
        for item in cls:
            item_id = f'EXTRA:T07:{cls.__name__}.{item.name}'
            notes = '枚举值唯一；'
            if cls is E:
                notes += f'默认handler={getattr(_HANDLERS.get(item), "__name__", "无")}；ability_override={getattr(_ABILITY_HANDLER_OVERRIDES.get(item), "__name__", "无")}'
                if item is E.INTERRUPT:
                    notes += '；两种counter入口单独处理，不误判普通注册遗漏为应对未实现'
            else:
                notes += '执行器阶段/分发时点静态引用核对；不包含外层回合先后正确性'
            extra.append({'item_id': item_id, 'kind': 'enum_member', 'name': f'{cls.__name__}.{item.name}', 'owner': 'T07',
                          'source': 'nrc_core/effect_models.py', 'line': str(next(n.lineno for n in ast.walk(trees['nrc_core/effect_models.py']) if isinstance(n, ast.ClassDef) and n.name == cls.__name__)),
                          'parent_id': next(r['item_id'] for r in assigned if r['kind'] == 'code_object' and r['name'] == cls.__name__), 'description': notes, 'reachability': '静态注册/分发可达'})
            rows.append(dict(zip(FIELDS, [item_id, '通过', CONTRACT, 'nrc_core/effect_models.py；engine/registry.py；engine/executor.py', item.name,
                                         '枚举与AST注册表双向对照', 'probe_output.json:registry/unregistered_enum/timing_references', notes, '仅注册协议审查，不代替效果语义审计'])))
    config = {}
    for name, effects in {**SKILL_EFFECTS_GENERATED, **SKILL_EFFECTS}.items():
        for se in effects:
            if isinstance(se, SkillEffect) and se.filter:
                config.setdefault(se.timing.name, []).append({'skill': name, 'filter': se.filter})
    (OUT / 'config_filters.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    unique = {}
    for row in rows:
        if row['item_id'] in unique:
            unique[row['item_id']]['notes'] += '；基线同ID的另一分支记录：' + row['notes']
        else:
            unique[row['item_id']] = row
    rows = list(unique.values())
    for row in rows:
        if row['conclusion'] == '未上线':
            row['conclusion'] = '规则存疑'
            row['notes'] += '；实现待证实：没有文档明确声明尚未上线，可达性不代替规则结论'
    for filename, data, fields in [('coverage.csv', rows, FIELDS), ('inventory_extra.csv', extra, list(assigned[0]))]:
        with (OUT / filename).open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
    (OUT / 'static_review.md').write_text('\n'.join(static) + '\n', encoding='utf-8')
    print(json.dumps({'assigned': len(assigned), 'extra': len(extra), 'coverage': len(rows), 'conclusions': dict(Counter(r['conclusion'] for r in rows)),
                      'filtered_stage_counts': {key: len(value) for key, value in config.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
