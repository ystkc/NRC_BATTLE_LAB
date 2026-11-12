"""以完整回合复现空技能、嵌套配置、固定威力和连击错误。"""
from extract import ROOT, OUT, plain
from probe import pokemon, snapshot
import json
import copy
import sqlite3
from nrc_core.battle import execute_full_turn
from nrc_core.models import Skill, Type, BattleState
from nrc_core.debug import configure_core_logging
from nrc_core.effect_data import SKILL_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
from scripts import generate_skill_effects as gen

def main():
    """保持数据只读，只将输入输出写至审计目录。"""
    configure_core_logging('')
    conn = sqlite3.connect((ROOT/'data/nrc_wiki.db').as_uri()+'?mode=ro',uri=True)
    conn.row_factory = sqlite3.Row
    output = []
    for name in ['可爱','化劲','休息回复','三连破','先发制人','升龙咆哮']:
        row = conn.execute('SELECT s.*,e.name AS element FROM skill_catalog s LEFT JOIN elements e ON e.id=s.element_id WHERE s.name=?',(name,)).fetchone()
        a,b = pokemon('A'),pokemon('B')
        a.speed,b.speed = 200,100
        a.energy=20
        s = Skill(name,gen._TYPE_MAP[row['element']],gen._CAT_MAP[row['category']],power=row['power'] or 0,energy_cost=row['energy_cost'] or 0)
        s.effects=copy.deepcopy({**SKILL_EFFECTS_GENERATED,**SKILL_EFFECTS}.get(name,[]))
        s.description=row['description']
        a.skills=[s]
        state=BattleState([a],[b])
        before={'user':snapshot(a),'target':snapshot(b),'description':row['description'],'skill':{'power':s.power,'charge':s.charge,'priority':s.priority_mod,'effects':plain(s.effects)},'actions':[[0],[-1]]}
        record={'name':name,'input':before}
        try:
            execute_full_turn(state,(0,),(-1,))
            record['output']={'user':snapshot(a),'target':snapshot(b),'report':state.turn_report,'charging_skill_idx':a.charging_skill_idx}
        except Exception as exc:
            record['exception']=type(exc).__name__+': '+str(exc)
        output.append(record)
    (OUT/'minimal_repros.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'name':r['name'],'exception':r.get('exception'),'user_energy':r.get('output',{}).get('user',{}).get('energy'),'target_hp':r.get('output',{}).get('target',{}).get('current_hp')} for r in output],ensure_ascii=False))

if __name__ == '__main__':
    main()
