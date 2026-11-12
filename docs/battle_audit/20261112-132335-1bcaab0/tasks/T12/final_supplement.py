"""从既有真实状态、截图及只读渲染源码保存MP缺失证据。"""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
data = json.loads((HERE / 'supplement_output.json').read_text(encoding='utf-8'))
paths = ['nrc_server/static/app.js', 'nrc_server/static/battle.js', 'nrc_server/static/index.html', 'nrc_server/static/state.js', 'nrc_server/static/opponent-roster.js', 'nrc_server/static/presentation.js']
pattern = re.compile(r'\bmp\b|\bMP\b|mp_own|mp_opponent|魔力')
matches = []
for path in paths:
    for number, text in enumerate((ROOT / path).read_text(encoding='utf-8').splitlines(), 1):
        if pattern.search(text):
            matches.append({'file': path, 'line': number, 'text': text})


def snippet(path, first, last):
    """保留带精确行号的渲染链片段。"""
    lines = (ROOT / path).read_text(encoding='utf-8').splitlines()
    return {'file': path, 'lines': [{'line': n, 'text': lines[n - 1]} for n in range(first, last + 1)]}


captures = []
for perspective in ['a', 'b']:
    captures.append({'source': 'supplement_output.json', 'json_path': f'$.devotion.{perspective}.mp', 'value': data['devotion'][perspective]['mp'], 'origin': '既有独立Chrome双context真实HTTP投影经mergeObservation进入state.shared，由supplement_probe.js记录；本轮仅只读提取'})
shots = []
for name in ['07_resonance_choices.png', '05_replacement.png']:
    content = (HERE / name).read_bytes()
    shots.append({'file': name, 'sha256': hashlib.sha256(content).hexdigest(), 'visual_review': '已人工复看完整截图：双方栏有名字、HP、能量、状态/圆点，无双方MP数值；分别为正常战斗共鸣抽屉与replacement补位画面'})
rule_path = 'data/对战过程中的信息遮蔽规则.md'
rule_line = (ROOT / rule_path).read_text(encoding='utf-8').splitlines()[2]
evidence = {'issue': 'T12-I06', 'severity': 'P2', 'rule': {'file': rule_path, 'line': 3, 'text': rule_line}, 'captures': captures, 'screenshots': shots,
            'static_search': {'files': paths, 'pattern': pattern.pattern, 'matches': matches, 'excludes_import_noise': '使用独立单词mp/MP及具体字段，不把import、empty、autocomplete误作MP消费者'},
            'render_chain': [snippet('nrc_server/static/battle.js', 49, 65), snippet('nrc_server/static/app.js', 420, 430), snippet('nrc_server/static/app.js', 433, 481), snippet('nrc_server/static/index.html', 21, 34)],
            'expected': '两视角均可直接看见双方当前MP数值', 'actual': '公开状态shared.mp.own/opponent存在且两方均4，页面没有读取和渲染它们的链路；两个真实全屏均无MP',
            'limits': '本轮未启动服务器/浏览器，未另取DOM快照；截图、捕获状态来自既有真实运行，源码验证同步与显示字段。没有推断终局数值，也不把精灵能量或圆点当MP。',
            'nature_scope_correction': 'T12-I04只确认显示莽撞但base未提交nature且preview nature=null；不再推导实际中性数值，T02的neutral构造回退需分别评价。'}
assert not matches
assert captures[0]['value'] == {'own': 4, 'opponent': 4}
assert captures[1]['value'] == {'own': 4, 'opponent': 4}
(HERE / 'missing_mp_evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'issue': evidence['issue'], 'captures': captures, 'mp_consumers_found': len(matches), 'screenshots': [x['file'] for x in shots], 'new_server_or_browser': False}, ensure_ascii=False))
