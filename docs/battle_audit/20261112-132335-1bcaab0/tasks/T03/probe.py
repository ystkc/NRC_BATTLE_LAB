"""T03 独立公式、类型矩阵与状态复制证据；数据库只读。"""
import contextlib
import csv
import io
import json
import math
import re
import sqlite3
from pathlib import Path
import numpy as np
from nrc_core.catalog import calc_combat_stats, CoreCatalog
from nrc_core.models import Pokemon, Skill, Type, SkillCategory, BattleState, get_type_effectiveness, add_electric_stacks
from nrc_core.compound_status import CompoundStatus
from nrc_core.pokemon_nature_table import NATURE_BONUSES
from nrc_core.engine.helpers import _apply_buff, _apply_matching_skill_mods
from nrc_core.core import simulate_turn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FIELDS = ['hp','atk','spatk','def','spdef','speed']
TYPE_NAMES = {'普通':'normal','草':'grass','火':'fire','水':'water','光':'light','地':'ground','冰':'ice','龙':'dragon','电':'electric','毒':'poison','虫':'bug','武':'fighting','翼':'flying','萌':'fairy','幽':'ghost','恶':'dark','机械':'steel','幻':'psychic'}


def pokemon(name='A', skills=None):
    """中性状态，使用整数基础六维。"""
    return Pokemon(name,Type.NORMAL,1000,100,100,100,100,100,skills=skills or [])


def nature_reference():
    """直接从权威md表格取加减项，不读取产品映射求期望。"""
    table = {}
    for line in (ROOT/'data/属性数值计算.md').read_text(encoding='utf-8').splitlines():
        if not re.match('^(生命|物攻|魔攻|物防|魔防|速度)-',line):
            continue
        parts = line.split()
        down = {'生命-':'hp','物攻-':'atk','魔攻-':'spatk','物防-':'def','魔防-':'spdef','速度-':'speed'}[parts[0]]
        for up,name in zip(FIELDS,parts[1:]):
            if name != '/':
                table[name] = {key:(.2 if key==up else -.1 if key==down else 0.) for key in FIELDS}
    return table


def reference(bases,bonus):
    """严格Float32分步运算；IV0隔离资质倍数矛盾。"""
    result = {}
    for key,base in zip(FIELDS,bases):
        mul = np.float32(1.7 if key=='hp' else 1.1)
        value = np.float32(np.float32(mul*np.float32(base)) + np.float32(70 if key=='hp' else 10))
        first = math.floor(float(value)+.5)
        final = np.float32(np.float32(first)*np.float32(1+bonus[key]))
        result[key] = math.floor(float(final)+.5)+(100 if key=='hp' else 50)
    return result


def main():
    """全量矩阵与必要反例统一保存。"""
    summary = {}
    extras, matrix = [], []
    invfields = ['item_id','kind','name','owner','source','line','parent_id','description','reachability']
    text = (ROOT/'data/属性克制表.md').read_text(encoding='utf-8')
    table = {}
    for line in text.splitlines():
        if '：' not in line or line.startswith('说明'):
            continue
        name,desc = line.split('：',1)
        if name not in TYPE_NAMES:
            continue
        row = {}
        for part in desc.replace('；','，').replace('、','').replace('幽灵','幽').split('，'):
            multiplier = 2 if '克制' in part else .5 if '抵抗' in part else 1
            for cn,en in TYPE_NAMES.items():
                if cn in part:
                    row[en] = multiplier
        table[TYPE_NAMES[name]] = row
    for attack in Type:
        for d1 in Type:
            for d2 in [None,*Type]:
                first = table[attack.value].get(d1.value,1)
                second = table[attack.value].get(d2.value,1) if d2 else 1
                expected = 3 if d2 and first==second==2 else first*second
                actual = get_type_effectiveness(attack,[d1,d2] if d2 else d1)
                ident = f'MATRIX:{attack.value}:{d1.value}:{d2.value if d2 else "single"}'
                matrix.append(dict(item_id=ident,expected=expected,actual=actual,match=actual==expected))
                extras.append(dict(zip(invfields,[ident,'semantic_matrix',ident,'T03','data/属性克制表.md',1,'FILE:nrc_core/models.py','18×18单属性及18×18×18有序双属性独立矩阵','生产可达'])))
    with (HERE/'type_matrix.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(matrix[0])); writer.writeheader(); writer.writerows(matrix)
    summary['types'] = dict(total=len(matrix),mismatches=sum(not row['match'] for row in matrix))
    with sqlite3.connect('file:data/nrc_wiki.db?mode=ro',uri=True) as connection:
        forms=connection.execute('SELECT id,name,base_hp,base_attack,base_magic_attack,base_defense,base_magic_defense,base_speed FROM spirit_forms ORDER BY id').fetchall()
    natures = nature_reference()
    summary['natures'] = dict(reference_count=len(natures),implementation_count=len(NATURE_BONUSES),names_match=set(natures)==set(NATURE_BONUSES),sign_mismatches=[])
    for name,bonus in natures.items():
        for key,value in bonus.items():
            if np.sign(NATURE_BONUSES[name][key]) != np.sign(value):
                summary['natures']['sign_mismatches'].append([name,key])
    mismatches=[]
    checked=0
    for ident,name,*bases in forms:
        for nature,bonus in natures.items():
            expected=reference(bases,bonus)
            actual=calc_combat_stats(*bases,iv_config=dict.fromkeys(FIELDS,0),nature_name=nature)
            checked+=6
            for key in FIELDS:
                if actual[key]!=expected[key]:
                    mismatches.append(dict(form_id=ident,form=name,nature=nature,field=key,base=bases[FIELDS.index(key)],actual=actual[key],expected=expected[key]))
    with (HERE/'stat_mismatches.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['form_id','form','nature','field','base','actual','expected']); writer.writeheader(); writer.writerows(mismatches)
    summary['stats_IV0'] = dict(forms=len(forms),natures=len(natures),scalar_comparisons=checked,mismatch_count=len(mismatches),first_examples=mismatches[:8])
    summary['I01_dtype'] = dict(constants_dtype=str(type(__import__('nrc_core.catalog',fromlist=['MUL_BASE_HP']).MUL_BASE_HP)),nature_dtype=str(type(NATURE_BONUSES['坦率']['def'])))
    a=pokemon(); a.speed_up=9.9
    b=pokemon(); b.speed_down=9.9
    c=pokemon(); c.speed_up=.5; c.speed_down=.2
    summary['I02_caps'] = dict(up99_actual=a.effective_speed(),up99_expected=1090,down99_actual=b.effective_speed(),down99_expected=100/10.9,both_actual=c.effective_speed(),both_expected=100*1.5/1.2)
    a.atk_up=9.9
    b.def_down=9.9
    summary['I02_caps'].update(atk99_actual=a.effective_atk(),atk99_expected=1090,defdown99_actual=b.effective_def(),defdown99_expected=100/10.9)
    a=pokemon()
    for _ in range(100):
        _apply_buff(a,{'atk':.1})
    summary['I03_max99'] = dict(actual_modifier=a.calculation_modifier('atk_up'),expected_max=9.9)
    sk=Skill('同名',Type.NORMAL,SkillCategory.PHYSICAL,100,1)
    a=pokemon('A',[sk]); enemy=pokemon('B')
    _apply_matching_skill_mods(a,enemy,{'power_pct':.5,'energy_cost_eq':1})
    cloned=a.copy_state()
    has_base_before=hasattr(cloned.skills[0],'_ability_base_power')
    _apply_matching_skill_mods(a,enemy,{'power_pct':.5,'energy_cost_eq':1})
    _apply_matching_skill_mods(cloned,enemy,{'power_pct':.5,'energy_cost_eq':1})
    summary['I04_skill_copy'] = dict(original_power=a.skills[0].power,cloned_power=cloned.skills[0].power,expected_both=150,cloned_has_base_before_reapply=has_base_before)
    a,b=pokemon('公平鸽'),pokemon('对手')
    b.ability_state['mirror_buff_to']=a
    state=BattleState([a],[b]); copied=state.deep_copy()
    _apply_buff(copied.team_b[0],{'atk':.1})
    summary['I05_graph_copy'] = dict(ref_points_to_copied_active=copied.team_b[0].ability_state['mirror_buff_to'] is copied.team_a[0],actual_active_buff=copied.team_a[0].atk_up,detached_buff=copied.team_b[0].ability_state['mirror_buff_to'].atk_up,expected_active_buff=.1)
    a=pokemon(); a.freeze_stacks=1; a.current_hp=270
    add_electric_stacks(a,2)
    summary['I06_electric_freeze']=dict(actual_hp=a.current_hp,actual_fainted=a.is_fainted,expected_fainted=True)
    ground=Skill('地系',Type.GROUND,SkillCategory.PHYSICAL,40,2)
    state=BattleState([pokemon('A',[ground])],[pokemon('B')],weather='sandstorm',weather_turns=1)
    state.sandstorm_original_costs[id(ground)]=5
    copied=state.deep_copy()
    result=simulate_turn(state,(-1,),(-1,),seed=1)
    summary['I07_weather_copy']=dict(new_skill_key_present=id(copied.team_a[0].skills[0]) in copied.sandstorm_original_costs,expected=True,actual_cost_after_weather_ends=result.state.team_a[0].skills[0].energy_cost,expected_cost_after_weather_ends=5)
    a=pokemon(); a.compound_statuses['组合']=CompoundStatus('组合',3,{'atk_up':.2},skill_modifiers={'power':5},skill_types=('normal',))
    a.atk_down=.1; a.skills=[sk.copy()]
    copied=a.copy_state(); copied.compound_statuses['组合'].stacks+=1
    catalog=CoreCatalog(skills={'同名':sk}); one,two=catalog.get_skill('同名'),catalog.get_skill('同名'); one.energy_cost+=2
    summary['pass_state']=dict(derived=a.calculation_modifier('atk_up'),expected=.6,raw_stays_zero=a.atk_up==0,compound_copy_independent=a.compound_statuses['组合'].stacks==3,skill_modifier=a.skill_modifier(a.skills[0],'power'),expected_skill_modifier=15,catalog_same_name_isolated=two.energy_cost==1)
    a=pokemon(); a.freeze_stacks=2; a.cute_stacks=1; a.compound_statuses['x']=CompoundStatus('x',2,{'atk_up':.1}); a.atk_up=.2; a.on_switch_out()
    summary['switch_observation']=dict(freeze_kept=a.freeze_stacks,cute_kept=a.cute_stacks,compound_cleared=not a.compound_statuses,ordinary_up_cleared=a.atk_up==0)
    with contextlib.redirect_stderr(io.StringIO()):
        invalid=calc_combat_stats(*[100]*6,iv_config=dict.fromkeys(FIELDS,0),nature_name='不存在')
        default=calc_combat_stats(*[100]*6)
    summary['invalid_inputs']=dict(unknown_nature_result=invalid,default_call_result=default)
    for key in ('stats_IV0','natures','pass_state','I02_caps','I03_max99','I04_skill_copy','I05_graph_copy','I06_electric_freeze','I07_weather_copy'):
        extras.append(dict(zip(invfields,[f'SEMANTIC:{key}','semantic_check',key,'T03','tasks/T03/probe.py',1,'','独立规则公式或内存输入验证','生产可达；非法输入另列'])))
    with (HERE/'inventory_extra.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=invfields); writer.writeheader(); writer.writerows(extras)
    (HERE/'probe_output.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
