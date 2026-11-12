"""只读提取技能、特性原文与实际结构，生成审计证据。"""
from pathlib import Path
import csv
import dataclasses
import enum
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from nrc_core.effect_data import SKILL_EFFECTS, ABILITY_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED

OUT = Path(__file__).parent

def plain(value):
    """展开效果结构，保留参数、条件和时点。"""
    if hasattr(value, '__slots__'):
        return {k: plain(getattr(value, k)) for k in value.__slots__ if getattr(value, k) not in (None, [], {})}
    if dataclasses.is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items() if v not in (None, [], {})}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value

def main():
    """从只读数据库构造逐项核对文件。"""
    conn = sqlite3.connect((ROOT / 'data/nrc_wiki.db').as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    inventory = list(csv.DictReader((OUT / 'assigned_inventory.csv').open(encoding='utf-8-sig', newline='')))
    rows = []
    for item in inventory:
        if item['kind'] not in ('skill', 'ability'):
            continue
        name = item['name']
        kind = item['kind']
        mapping = ABILITY_EFFECTS if kind == 'ability' else {**SKILL_EFFECTS_GENERATED, **SKILL_EFFECTS}
        source = 'manual' if kind == 'ability' or name in SKILL_EFFECTS else 'generated'
        row = {**item, 'config_source': source, 'config': plain(mapping.get(name, []))}
        rows.append(row)
    (OUT / 'objects.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    for kind in ('skill', 'ability'):
        lines = [f"{x['item_id']} {x['name']} | {x['description']} | {x['config_source']} {json.dumps(x['config'], ensure_ascii=False, separators=(',', ':'))}" for x in rows if x['kind'] == kind]
        (OUT / f'{kind}_comparison.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('ROOT', ROOT, 'objects', len(rows), 'inventory', len(inventory))
    conn.close()

if __name__ == '__main__':
    main()
