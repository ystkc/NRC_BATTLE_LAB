"""展示装饰和 HTTP 错误边界的定向审计，不修改业务。"""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
from nrc_core.debug import configure_core_logging
configure_core_logging('')
from nrc_server.server import create_app, _error_response
from nrc_server.presentation import _base_name, _asset_files, _asset, _asset_exact, decorate_response
from nrc_platform.platform import PlatformError
from fastapi.testclient import TestClient

out = {'checks': [], 'http': [], 'lines': {}, 'hashes': {}}
def check(name, actual, expected):
    """保留独立预期和实际输出。"""
    out['checks'].append({'name': name, 'actual': actual, 'expected': expected, 'pass': actual == expected})

def trace(frame, event, arg):
    """记录目标模块实际执行行，仅辅助覆盖，不等价语义通过。"""
    name = Path(frame.f_code.co_filename).as_posix()
    if event == 'line' and '/nrc_server/' in name:
        out['lines'].setdefault(name.split('/nrc_server/')[-1], set()).add(frame.f_lineno)
    return trace

sys.settrace(trace)
assets = HERE / 'probe_assets'
for directory, names in {'spirit_icons': ['pet_main_甲.png', 'pet_main_甲_portrait.png'], 'skill_icons': ['甲.png'], 'dept_icons': ['火.png'], 'icon_dept_relation': ['无.svg', '平衡.svg', '双重抵抗.svg', '抵抗.svg', '克制.svg', '双重克制.svg'], 'icon_blood': ['光.png'], 'icon_aptitudes': ['生命.png']}.items():
    folder = assets / directory
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).touch()
check('base_name_ascii', _base_name('甲(乙)'), '甲')
check('base_name_chinese', _base_name('甲（乙）'), '甲')
check('missing_directory', _asset_files(assets, 'missing'), ())
check('missing_name', _asset(assets, 'spirit_icons', '不存在'), None)
check('form_fallback', _asset(assets, 'spirit_icons', '甲（乙）', portrait=True), '/assets/spirit_icons/pet_main_甲_portrait.png')
check('portrait_false', _asset(assets, 'spirit_icons', '甲'), '/assets/spirit_icons/pet_main_甲.png')
check('exact_present', _asset_exact(assets, 'icon_aptitudes', '生命.png'), '/assets/icon_aptitudes/生命.png')
check('exact_missing', _asset_exact(assets, 'icon_aptitudes', '速度.png'), None)
for value, label in [(None, '无'), (0.25, '双重抵抗'), (0.5, '抵抗'), (1, '平衡'), (2, '克制'), (4, '双重克制')]:
    result = decorate_response({'type_effectiveness': value}, assets)
    check('relation_' + str(value), result['effect_icon'], '/assets/icon_dept_relation/' + label + '.svg')
# 0 免疫与普通1不能混淆；实际核心18属性表能否产0另列可达性。
zero = decorate_response({'type_effectiveness': 0}, assets)
check('immune_zero_icon', zero['effect_icon'], '/assets/icon_dept_relation/无.svg')
original = {'bloodline_attributes': ['光'], 'children': [{'species': '甲', 'types': ['火']}, {'name': '甲', 'power': 10, 'element': '火'}, 1, [], {}]}
before = copy.deepcopy(original)
result = decorate_response(original, assets)
check('input_unmodified', original, before)
check('species_alias', result['children'][0]['name'], '甲')
check('skill_icon', result['children'][1]['icon'], '/assets/skill_icons/甲.png')
check('element_icon', result['children'][1]['type_icon'], '/assets/dept_icons/火.png')
check('bloodline_icon', result['bloodline_icon'], '/assets/icon_blood/光.png')
check('empty_bloodline', decorate_response({'bloodline_attributes': []}, assets)['bloodline_icon'], None)
check('preserve_asset_override', decorate_response({'name': '甲', 'types': [], 'portrait': 'existing'}, assets)['portrait'], 'existing')
for error, status in [(PlatformError('not_found', 'x'), 404), (PlatformError('stale_decision', 'x'), 409), (PlatformError('invalid_roster', 'x'), 422), (ValueError('player token is required'), 401), (ValueError('not a member'), 403), (ValueError('battle not found'), 404), (TypeError('invalid'), 422), (RuntimeError('x'), 500)]:
    check('error_' + str(error), _error_response(error).status_code, status)

client = TestClient(create_app())
for method, url, body in [('GET', '/', None), ('GET', '/api/catalog/index', None), ('GET', '/api/catalog?kind=invalid', None), ('GET', '/api/pokemon/不存在', None), ('POST', '/api/pokemon/preview', {}), ('POST', '/api/pokemon/preview', []), ('POST', '/api/pokemon/preview', {'name': '迪莫', 'base': 'invalid'}), ('POST', '/api/battles', {'mode': 'invalid'}), ('POST', '/api/battles', []), ('POST', '/api/battles/missing/join', {}), ('GET', '/api/battles/missing', None)]:
    response = client.request(method, url, **({} if body is None else {'json': body}))
    try:
        data = response.json()
    except ValueError:
        data = response.text[:100]
    if '/catalog/index' in url and response.status_code == 200:
        data = {'pokemon': len(data.get('pokemon', [])), 'skills': len(data.get('skills', []))}
    out['http'].append({'method': method, 'url': url, 'input': body, 'status': response.status_code, 'output': data})

def call(method, url, token='', payload=None):
    """在真实路由栈中保存身份固定后的成功请求。"""
    response = client.request(method, url, headers={'X-Player-Token': token}, **({} if payload is None else {'json': payload}))
    data = response.json()
    out['http'].append({'method': method, 'url': url, 'input': payload, 'status': response.status_code, 'output': data})
    return data

created = call('POST', '/api/battles', payload={'mode': 'full', 'seed': 1007})
bid, token_a = created['battle_id'], created['player_token']
joined = call('POST', f'/api/battles/{bid}/join', payload={})
token_b = joined['player_token']
for token, filename in [(token_a, '1007A.json'), (token_b, '1007B.json')]:
    roster = json.loads((ROOT / filename).read_text(encoding='utf-8'))['roster']
    call('POST', f'/api/battles/{bid}/rosters', token, {'roster': roster, 'confirm': True})
for route in ['', '/opponent-roster', '/display', '/matchups', '/actions', '/state', '/operation?since=-1', '/events?since=0']:
    call('GET', f'/api/battles/{bid}{route}', token_a)
    call('GET', f'/api/battles/{bid}{route}', token_b)
normal = call('GET', f'/api/battles/{bid}/state', token_a)
spoofed = call('GET', f'/api/battles/{bid}/state?side=opponent', token_a)
check('query_side_does_not_spoof', spoofed, normal)
call('POST', f'/api/battles/{bid}/selection', token_a, {'action_key': 'charge', 'request_id': 'T12-static-a', 'decision_index': 0})
call('POST', f'/api/battles/{bid}/selection', token_b, {'action_key': 'charge', 'request_id': 'T12-static-b', 'decision_index': 0})
call('GET', '/api/pokemon/迪莫')
call('POST', '/api/pokemon/preview', payload={'name': '迪莫'})
call('GET', '/api/catalog?kind=pokemon&q=dm')
outsider = call('POST', '/api/battles', payload={'mode': 'full'})['player_token']
for route, payload in [('/rosters', {'roster': []}), ('/selection', {'action_key': 'charge'})]:
    call('POST', f'/api/battles/{bid}{route}', '', payload)
    call('POST', f'/api/battles/{bid}{route}', outsider, payload)
sys.settrace(None)
out['lines'] = {key: sorted(value) for key, value in out['lines'].items()}
out['hashes'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'nrc_server').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def redact(value):
    """测试令牌不写入证据，保留等价性断言。"""
    if isinstance(value, dict):
        return {key: '<audit-token-redacted>' if key in {'player_token', 'token', 'ta', 'tb'} else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value

(HERE / 'static_output.json').write_text(json.dumps(redact(out), ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'checks': len(out['checks']), 'failed': [x['name'] for x in out['checks'] if not x['pass']], 'http': [(x['url'], x['status']) for x in out['http']]}, ensure_ascii=False))
