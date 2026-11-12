"""汇总人工审阅、运行证据和逐对象覆盖，不用非空/可调用推定通过。"""
from __future__ import annotations
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUDIT = HERE.parents[1]
assigned = list(csv.DictReader((HERE / 'assigned_inventory.csv').open(encoding='utf-8-sig')))
extra = list(csv.DictReader((HERE / 'inventory_extra.csv').open(encoding='utf-8-sig')))
browser = json.loads((HERE / 'browser_output.json').read_text(encoding='utf-8'))
supplement = json.loads((HERE / 'supplement_output.json').read_text(encoding='utf-8'))
static = json.loads((HERE / 'static_output.json').read_text(encoding='utf-8'))
fields = ['item_id', 'kind', 'name', 'owner', 'source', 'line', 'parent_id', 'description', 'reachability']

def add(item_id, kind, name, source, line, description):
    """补齐行号相同但语义不同的原始分支。"""
    if not any(row['item_id'] == item_id for row in extra):
        extra.append(dict(zip(fields, [item_id, kind, name, 'T12', source, str(line), 'FILE:' + source, description, '按 coverage 单列'])))

for source, line in [('nrc_server/presentation.py', 72), ('nrc_server/server.py', 27)]:
    repeated = [row for row in assigned if row['source'] == source and row['line'] == str(line) and row['kind'] == 'code_branch']
    conditions = list(dict.fromkeys(row['description'] for row in repeated))
    for number, condition in enumerate(conditions, 1):
        for direction in ['true', 'false']:
            add(f'PYSEM:{source}:{line}:C{number:02}:{direction}', 'semantic_branch', condition + ' / ' + direction, source, line, condition)

routes = [
 ('GET','/','index',66),('GET','/api/catalog/index','catalog_index',71),('GET','/api/catalog','catalog',80),
 ('GET','/api/pokemon/{name}','pokemon_detail',89),('POST','/api/pokemon/preview','pokemon_preview',98),
 ('POST','/api/battles','create_battle',108),('POST','/api/battles/{battle_id}/join','join_battle',120),
 ('GET','/api/battles/{battle_id}','battle_summary',131),('GET','/api/battles/{battle_id}/opponent-roster','opponent_roster',141),
 ('POST','/api/battles/{battle_id}/rosters','set_rosters',151),('GET','/api/battles/{battle_id}/display','display',162),
 ('GET','/api/battles/{battle_id}/matchups','matchups',172),('GET','/api/battles/{battle_id}/actions','actions',182),
 ('GET','/api/battles/{battle_id}/state','public_state',192),('GET','/api/battles/{battle_id}/operation','operation',202),
 ('GET','/api/battles/{battle_id}/events','battle_events',212),('POST','/api/battles/{battle_id}/selection','select_action',222),
]
for method, url, name, line in routes:
    add('HTTP:' + method + ':' + url, 'http_route', name, 'nrc_server/server.py', line, method + ' ' + url)
scenarios = {
 'identity': '独立 context 的稳定身份、八类查询无令牌401/非成员403、固定席位与第三席拒绝',
 'selection': '重复ID相同响应、新ID重复pending409、过期decision409、单次推进',
 'reload': 'pending刷新禁用按钮、正常回合刷新保留历史且无重复动画',
 'replacement': '真实力竭后单方补位、对手无按钮、刷新后可切换并继续',
 'known_roster': '未出场名称不在弹窗，出场后的替补保留公开HP能量特性；窄屏弹窗约束',
 'devotion': '己方奉献分布可见、对方分布隐藏、对方总数缺失归T11-I03',
 'preview_input': 'base=str 的公开HTTP预览返回500，根因T02输入合并',
 'display': '网页技能能耗/威力/合法按钮与核心展示接口一致；不重新证明核心数值公式',
 'exit_race': '摘要响应在途时退出，旧响应回填无令牌房间',
 'nature': '默认性格字段与导出及预览实际性格不一致',
 'autocomplete': '小结果集拼音候选重复',
 'mp_visibility': 'HTTP公共投影有双方MP，但实际战斗/补位全屏与渲染链均未显示，T12-I06',
}
for key, desc in scenarios.items():
    add('SCENARIO:' + key, 'scenario', key, 'nrc_server/static/app.js', 1, desc)

def write_csv(name, rows, columns):
    """显式 UTF-8 保存审计表。"""
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

write_csv('inventory_extra.csv', extra, fields)

# 以下是按函数阅读后的判断。子方向未取得定向证据时仍单列规则存疑。
notes = {}
def note(file, names, text, evidence='browser_output.json', conclusion='通过'):
    for name in names.split():
        notes[(file, name)] = (text, evidence, conclusion)

note('app.js', 'toast', '使用textContent；计时器替换旧提示；已观测导入/锁定/错误提示。')
note('app.js', 'baseName pokemonRow formFor skillMeta asset typeKey typeIcon relationIcon', '从公开catalog按名称/形态取资源；正常1007和直接HP搜索均取正确名称类型；缺值回退分支另列。')
note('app.js', 'battleLocked isLegalAction actionsOfKind', 'pending/submitting/syncing/resolving/terminal聚合锁；技能前缀只匹配整槽分隔符；真实pending及replacement合法列表对照。')
note('app.js', 'relationBadge freezeState', '关系取后端index；冻结取唯一status并按每层5%限制进度条；1007霜降场景有显示，不证明核心冻结结算。')
note('app.js', 'hydrateOwnRoster normalizeSelectedStart updateSelectedStart', '本人阵容按索引恢复、首发越界回0；导入及刷新首发0实测，非0及越界方向待证。')
note('app.js', 'searchRows parseCreatureQuery renderSuggestions', '名称尾部只接受1或6个正整数；本次1HP路径成功；其它数量、六维和快捷技能检索未定向运行。', conclusion='规则存疑')
note('app.js', 'getTeamCard renderTeamCard renderTeam renderSetup', '名称/提示经过esc，队伍签名优化；双方创建、加入、确认、等待、初始化正常；确认后编辑行为未单独复演。')
note('app.js', 'rosterPayload exportRoster', '按当前本人状态导出JSON并限制资质数量；当前导入导出实测，导出保留HP；Base64提示文字与实际JSON不同但不报战斗缺陷。')
note('app.js', 'storeAuth createBattle joinBattle submitRoster startBattle enterBattle', '令牌来自响应，确认仅本人roster，进入战斗先刷新再轮询；1007从创建到双方确认、补位刷新完成。')
note('app.js', 'refreshLobby refreshOpponentRoster startLobbyPolling', '按服务端身份读准备摘要，准备阶段公开全队名存在规则范围疑问Q01；刷新失效与准备阶段异常方向未定向运行。', conclusion='规则存疑')
note('app.js', 'startBattlePolling', 'operation响应检查请求前后房间ID/decision及锁状态，正常回合与对手pending实测；网络乱序/终局方向未穷举。')
note('app.js', 'mergeObservation renderSide', '按平台视角own/opponent替换，activeIndex来自公开active；公开名称HP/能量/冻结和已知圆点；出场后替补和未知弹窗实测。')
note('app.js', 'stateEffects effectsMarkup drawerEffects', '只展示公开投影的修正/状态/技能冷却/marks/devotion，己方分布显示、对方分布不显示；缺对方总数为T11-I03。', 'supplement_output.json')
note('app.js', 'switchCardMarkup renderSpiritDrawer', '切换按钮须非active/非fainted且合法action；真实主动切换及力竭补位正常，具体卡片数字由投影提供。')
note('app.js', 'renderSkills updateBattleMeta updateBattleLock setResolving', '锁变动才渲染；技能槽、能耗威力直接取核心display；初始、pending、动画、刷新、replacement均核对。缓存相同锁下单独换display未验证。')
note('app.js', 'renderDrawer closeDrawer', '只渲染已转义内容并控制hidden；精灵/共鸣菜单打开关闭实测。')
note('app.js', 'renderEvents appendEvent playResolution sleep', '按游标添加事件，首次建立历史后不播放；退出用resolutionToken中断动画；刷新前后11条相等。DOM事件ID按type/turn/team可能重复，未用于规则决策。')
note('app.js', 'showSkillTooltip hideSkillTooltip showEffectTip', '描述取核心/目录并esc；本次未针对悬浮和边缘坐标逐方向验证。', conclusion='规则存疑')
note('app.js', 'reset restoreSession', 'clearSession清认证/事件/计时器并恢复准备屏；普通恢复与退出在途刷新问题分别见证据。restoreSession无损坏JSON保护未模拟。')
note('app.js', 'handleSearchInput onInputChange copyBattleId', '首候选确认、资质1..10截断、复制房间ID。搜索确认已跑；键盘Tab/Enter、权限拒绝剪贴板和非整数资质未定向运行。', conclusion='规则存疑')
note('app.js', 'buffIcon formatDisplayNumber', '当前没有调用点；仅静态读映射/数字格式，不因不可达算通过。', conclusion='规则存疑')
note('api.js', 'headers api', '每次请求从state取当前token；错误携带HTTP status，toast不解释错误正文为HTML；401/403/409/422及正常请求均实测。非JSON响应未验证。')
note('battle.js', 'createBattleSync', '注入显示回调，返回同步函数；独立双context完整运行。')
note('battle.js', 'fetchMatchups', '正常取得关系；任何失败清为空数组避免展示旧关系；网络失败方向未定向运行。', conclusion='规则存疑')
note('battle.js', 'syncEvents', '游标在读取后推进；无新事件返回false，动画用token中断；正常11条历史刷新保持11条，API尾游标空。')
note('battle.js', 'submitAction', '前端锁避免重复HTTP；服务器用request_id/decision拒绝重复与过期。真实点击与HTTP重复/过期已跑；401/终局toast方向未验证。')
note('opponent-roster.js', 'createOpponentRoster render show hideLater hide', '只取known条目并esc，不查隐藏技能；实际一已知→两已知、移入弹窗保持、Escape隐藏、560窄屏边界已观察。')
note('presentation.js', 'relationLabel effectName eventText', '15类真实字段/人工定向事件已核对完整文字；应对类型依赖平台事件内容，前端不自行推断；fallback/缺值方向单列。', 'supplement_output.json#formatter')
note('roster.js', 'createRosterEditor aptitudeField aptitudeName selectedAptitudes aptitudeEditorMarkup selectedSkills normalizedBase skillEditorMarkup', '资质字段双向映射；只导出最多3个正值并夹到1..10，技能名称保留槽次序；真实1007导入导出及直接HP输出已记录。')
note('roster.js', 'editorFieldMarkup editorChoices renderEditorSuggestions applyEditorOption editorPosition', '候选来自目录，技能排重但借用例外；菜单选择分别修改资质/技能/base；开编辑器与候选已运行，选择/边缘方向未穷举。', conclusion='规则存疑')
note('roster.js', 'closeCreatureEditor updateCreatureBase setForm addAptitude removeAptitude addSkill removeSkill', '编辑只改本人状态后保存；最多3资质、4技能、借用例外；未做每项增删/形态切换真实点击，静态已读，保守存疑。', conclusion='规则存疑')
note('roster.js', 'previewPosition previewPayload renderCreaturePreview previewForms loadCreaturePreview showCreaturePreview cyclePreviewForm hideCreaturePreview', '预览通过同一base规范化接口；requestId+anchor防止旧预览覆盖，空格循环形态会改变实际选择；本次预览成功但旧响应/形态循环未定向验证。', conclusion='规则存疑')
note('roster.js', 'natureBonusText', '从小数性格加成显示0.2/-0.1而不写%单位；默认性格与实际未提交的矛盾由renderCreatureEditor确认；是否改为20%仅展示需求。', 'supplement_output.json', '规则存疑')
note('session.js', 'saveSession clearSession', '仅已有battle+token才保存当前标签页；恢复pending身份不变，清理认证/事件/token计时器；clear后actions/display保留但一般新刷新会覆盖。')

defect_functions = {
 ('app.js','ensureDefaultCustomization'): ('T12-I01', '直接HP及空资质导入均自动注入最多三个8资质。'),
 ('app.js','addCreature'): ('T12-I01', 'base.stats只有HP时仍调用默认资质注入，违背Direct stat input约定。'),
 ('app.js','importRoster'): ('T12-I01', '显式individual_values={}导入再导出改变为三个8。'),
 ('app.js','actionLabel'): ('T12-I02', '只返回primary.skill_name，两个不同resonance行动显示同名假寐。'),
 ('app.js','renderBagDrawer'): ('T12-I02', '完整合法复合行动直接提交但标签不包含共鸣魔法类型。'),
 ('battle.js','refreshBattle'): ('T12-I03', '摘要await后不复核房间ID/认证/取消token；退出后回填旧房间。'),
 ('roster.js','renderCreatureEditor'): ('T12-I04', 'base.nature缺省时显示目录第一性格，但预览和提交仍为None。'),
 ('roster.js','choiceMatches'): ('T12-I05', '少于5个结果时把已匹配pinyin候选再次追加；莽撞变两项。'),
 ('app.js','renderSide'): ('T12-I06', '只渲染精灵HP/能量及状态，不消费shared.mp.own/opponent；真实全屏截图未显示双方MP。'),
}
for (file, name), (issue, text) in defect_functions.items():
    notes[(file,name)] = (issue + '；' + text, 'issues.md#' + issue, '确认缺陷')

js_functions = {row['item_id']: row for row in extra if row['kind'] == 'js_function'}
def function_context(row):
    """找到语义分支最近的具名函数，不丢掉匿名回调本身。"""
    current = row if row['kind'] == 'js_function' else js_functions.get(row.get('parent_id'))
    while current and current['name'].endswith('callback'):
        current = js_functions.get(current.get('parent_id'))
    return current['name'] if current else 'module'

def js_review(row):
    file = Path(row['source']).name
    context = function_context(row)
    summary, evidence, conclusion = notes.get((file, context), ('模块初始化/事件委托回调已逐段静态阅读；对应输入或时间窗口尚未定向运行。', 'browser_probe.js；supplement_probe.js', '规则存疑'))
    if row['kind'] == 'js_branch':
        # 不把同一函数被调用等价为所有控制方向都经过规则验证。
        conclusion = '规则存疑'
        summary += ' 本行是独立方向；静态已读，现有场景不足以证明此方向及其全部参数组合。'
        if (file, context) in defect_functions:
            summary += ' 所属函数已有确认问题，但不据此把每个无关方向判缺陷。'
    elif row['name'].endswith('callback'):
        conclusion = '规则存疑'
        summary += ' 匿名回调逐段已读；未对该回调单独留调用参数与返回证据，不能由外层路径通过推定通过。'
    elif conclusion == '通过':
        summary += ' 通过仅覆盖上述已核对契约；未验证子方向另列，不表示全参数穷举。'
    return summary, evidence, conclusion

python_success = {'_error_response','_identity','_token_for','_payload','index','catalog_index','catalog','pokemon_detail','create_battle','join_battle','battle_summary','opponent_roster','set_rosters','display','matchups','actions','public_state','operation','battle_events','select_action'}
coverage = []
review = []
unique_assigned = {}
for row in assigned:
    unique_assigned.setdefault(row['item_id'], row)

def record(row, conclusion, basis, implementation, evidence, notes_text='', reachability='可由合法/错误HTTP输入或本次Chrome操作到达'):
    coverage.append({'item_id': row['item_id'], 'conclusion': conclusion, 'rule_basis': basis, 'implementation': implementation, 'objects': row.get('name',''), 'method': '逐段静态阅读；定向输入对照' if conclusion != '规则存疑' else '逐段静态阅读；未定向运行方向明确保留', 'evidence': evidence, 'notes': notes_text, 'reachability': reachability})

for row in unique_assigned.values():
    source, kind = row['source'], row['kind']
    line = int(row['line'])
    conclusion, evidence = '规则存疑', 'static_output.json；browser_output.json'
    summary = '文件完整静态已读；具体通过和未运行方向由子对象覆盖，不以文件可加载推定规则正确。'
    if source.endswith('__init__.py'):
        conclusion, summary = '通过', '仅包描述字符串，无可执行规则或分支。'
    elif source.endswith('presentation.py'):
        conclusion, summary = '通过', '资源缺目录/缺名/形态回退/portrait选择/精确路径、递归字典列表标量、deepcopy、保留既有路径及六档关系均有定向对照。'
        if line == 72:
            conclusion = '规则存疑'
            summary = '此原ID重名涵5个三元条件，见独立PYSEM。None/.25/.5/1/2/4实测；人工0输入显示平衡，当前NRC属性矩阵无0，不上升当前规则缺陷。'
    elif source.endswith('server.py'):
        if kind == 'code_object' and row['name'] in python_success:
            conclusion, summary = '通过', '真实HTTP路由成功输入及身份绑定对照；只评价HTTP契约，不替被调用规则模块背书。'
        elif kind == 'code_object' and row['name'] == 'pokemon_preview':
            conclusion, summary = '确认缺陷', '合法预览200；嵌套base字符串500 AttributeError，T02输入合并主责，本层协同。'
        elif kind == 'code_object' and row['name'] == 'create_app':
            conclusion, summary = '通过', '17路由注册、/static与/assets装配、独立app会话表；实际服务与TestClient均加载。'
        elif kind == 'code_branch' and line in {21,25,27,34,36,51}:
            conclusion, summary = '通过', '相应纯错误对象或HTTP缺令牌/有效令牌/首次签发/非对象/对象输入均有实测，条件由static_output及browser_output逐值定位。'
        elif kind == 'code_branch' and row['name'] == 'exception' and line in {94,104,116,127,137,147,158,168,178,188,198,208,218,229}:
            conclusion, summary = '通过', '该路由异常路径已由未知对象、非法payload或缺/非成员令牌触发并保留相应状态码；不代表所有异常类别穷举。'
        elif line in {238,246}:
            summary = 'CLI main参数与uvicorn入口静态已读；本次为了关闭诊断日志使用uvicorn.run(app)隔离入口，未执行python -m的两个方向。'
    if source.endswith('app.js') or source.endswith('roster.js') or source.endswith('battle.js'):
        conclusion = '确认缺陷'
        summary = '文件有本任务确认问题，逐函数/分支结论见JS补清单；不把整文件其余内容判错。'
        evidence = 'issues.md；browser_output.json；supplement_output.json'
    if source.endswith('README.md'):
        summary = '身份、双人准备、事件增量、合法动作与补位契约有实测；Direct stat input约定被I01违反。'
        conclusion = '确认缺陷'
    record(row, conclusion, 'AGENTS.md；nrc_server/README.md；data/对战过程中的信息遮蔽规则.md:3-7；data/部分规则详解/战报.md:1-5', source + ':' + str(line), evidence, summary)

for row in extra:
    if row['kind'] in {'js_function','js_branch'}:
        summary,evidence,conclusion = js_review(row)
        record(row,conclusion,'nrc_server/README.md；data/部分规则详解/战报.md:5；data/对战过程中的信息遮蔽规则.md:3-7',row['source']+':'+str(row['line'])+'；'+row['description'],evidence,summary)
        if row['kind']=='js_function':
            review.append({'item_id':row['item_id'],'source':row['source'],'line':row['line'],'function':row['name'],'conclusion':conclusion,'review':summary,'evidence':evidence})
    elif row['kind']=='semantic_branch':
        record(row,'通过' if 'server.py' in row['source'] else '规则存疑','HTTP状态映射/展示档位契约',row['source']+':'+str(row['line'])+'；'+row['description'],'static_output.json','逐条件消歧；server每种优先状态均跑。presentation数值档位跑，但0的适用输入域另列限制。')
    elif row['kind']=='http_route':
        outcome = '确认缺陷' if row['name']=='pokemon_preview' else '通过'
        record(row,outcome,'HTTP路由声明；nrc_server/README.md；AGENTS未实现显式拒绝',row['description'],'route_coverage.csv；static_output.json；browser_output.json','成功方法均实测；预览非法base=string的500为T02主责，其他成功结论只限HTTP身份/投影交付，不担保下层规则。')
    else:
        name=row['name']
        conclusion='确认缺陷' if name in {'devotion','preview_input','exit_race','nature','autocomplete','mp_visibility'} else '通过'
        if name == 'mp_visibility':
            record(row,conclusion,'data/对战过程中的信息遮蔽规则.md:3 双方MP值均可见',row['description'],'missing_mp_evidence.json；07_resonance_choices.png；05_replacement.png','T12-I06：真实双方投影shared.mp均有own/opponent=4，页面渲染链没有读取，无MP数值显示；复用已完成截图/状态，本轮未另开Chrome。')
        else:
            record(row,conclusion,'data/对战过程中的信息遮蔽规则.md；data/部分规则详解/奉献.md:5；nrc_server/README.md',row['description'],'browser_output.json；supplement_output.json；pure_js_output.json','奉献总数T11-I03；非法预览T02主，其余独立本层问题见issues。')

write_csv('coverage.csv',coverage,['item_id','conclusion','rule_basis','implementation','objects','method','evidence','notes','reachability'])
write_csv('function_review.csv',review,['item_id','source','line','function','conclusion','review','evidence'])
route_rows=[]
route_errors={
 'index':'未注入HTML文件缺失错误；匿名200',
 'catalog_index':'匿名200；未注入catalog不可用错误',
 'catalog':'kind=invalid仍200，返回默认目录；没有约定其必须报错',
 'pokemon_detail':'未知精灵422 invalid_roster',
 'pokemon_preview':'空name404；顶层数组422；非法JSON422；base字符串500(T02主)',
 'create_battle':'无效mode422、非对象payload422；匿名创建签发身份',
 'join_battle':'不存在房间404、第三席422；同身份恢复固定席位200',
 'set_rosters':'缺令牌401、非成员403；side注入422；不完整技能槽422',
 'select_action':'缺令牌401、非成员403；pending新ID409、stale decision409；相同ID200相同响应',
}
for method,url,name,line in routes:
    route_rows.append({'method':method,'route':url,'implementation':f'nrc_server/server.py:{line}','success':'200，static_output.http或Chrome实际页面','errors':route_errors.get(name,'缺令牌401、已有非成员403；有效两席均200'),'evidence':'static_output.json；browser_output.json','limits':'目录内容/核心公式不在HTTP成功结论中；preview base字符串500归T02' if name=='pokemon_preview' else '未逐一枚举底层所有业务异常'})
write_csv('route_coverage.csv',route_rows,['method','route','implementation','success','errors','evidence','limits'])

baseline=list(csv.DictReader((AUDIT/'baseline_files.csv').open(encoding='utf-8-sig')))
unchanged=[]
for row in baseline:
    if row['owner']=='T12':
        actual=hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()
        unchanged.append({'path':row['path'],'baseline':row['sha256'],'actual':actual,'unchanged':actual==row['sha256']})
(HERE/'source_hashes.json').write_text(json.dumps(unchanged,ensure_ascii=False,indent=2),encoding='utf-8')
summary={'assigned_rows':len(assigned),'assigned_unique_ids':len(unique_assigned),'baseline_duplicate_ids':{key:value for key,value in Counter(row['item_id'] for row in assigned).items()if value>1},'extra':len(extra),'coverage':len(coverage),'missing':sorted(set(unique_assigned)|{row['item_id']for row in extra}- {row['item_id']for row in coverage}),'duplicate_coverage_ids':[key for key,value in Counter(row['item_id']for row in coverage).items()if value>1],'conclusions':dict(Counter(row['conclusion']for row in coverage)),'business_sources_unchanged':all(row['unchanged']for row in unchanged),'browser_checks':len(browser['checks']),'supplement_checks':len(supplement['checks']),'static_checks':len(static['checks'])}
# 运算括号明确，防止集合并/差优先级误报。
summary['missing']=sorted((set(unique_assigned)|{row['item_id']for row in extra})-{row['item_id']for row in coverage})
(HERE/'checkpoint.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
