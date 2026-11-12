"""T02 只读目录和独立边界输入；不覆盖数据库或业务生成物。"""
import copy
import csv
import json
import random
import sqlite3
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from nrc_platform.catalog import load_catalog, _lookup, _TYPE_ALIASES, _CATEGORY_ALIASES, _choice_options
from nrc_platform.builder import BattleBuilder
from nrc_platform.input import split_creature_spec, merge_creature_spec
from nrc_core.catalog import CoreCatalog
from nrc_core.models import Type, SkillCategory
from nrc_core.debug import configure_core_logging
from nrc_core.core import simulate_turn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
configure_core_logging('')


def main():
    """运行原始目录装载、构造与有限规则边界复现。"""
    original_connect = sqlite3.connect
    opened = []

    def read_only(database, *args, **kwargs):
        """强制所有目录数据库调用使用SQLite只读URI。"""
        uri = Path(database).resolve().as_uri() + '?mode=ro'
        opened.append(uri)
        return original_connect(uri, uri=True)

    with patch('nrc_platform.catalog.sqlite3.connect', side_effect=read_only):
        catalog = load_catalog(ROOT / 'data')
    builder = BattleBuilder(catalog=catalog)
    names = list(catalog.pokemon)
    chosen = next(n for n in names if catalog.pokemon[n].get('previous_forms') == [])
    skillname = '拍击' if '拍击' in catalog.skills else next(iter(catalog.skills))
    dims = dict(hp=1000, atk=100, spatk=100, **{'def':100, 'spdef':100, 'speed':100})

    def creature(**extra):
        """隔离特性及数值公式，其他字段保留正式构造路径。"""
        result = dict(name=chosen, ability={'name':''}, base={'stats':dict(dims)},
                      skills=[skillname], state={'hp':1000,'energy':10})
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key].update(value)
            else:
                result[key] = value
        return result

    def build(a=None, b=None, **shared):
        """完整双方结构的正式build入口。"""
        return builder.build(dict(own_team={'creatures':[a or creature()]},
                                  opponent_team={'creatures':[b or creature()]}, shared=shared), seed=73)

    def capture(fn):
        """保留拒绝类型与文本，不把异常吞作通过。"""
        try:
            return dict(accepted=True, value=fn())
        except Exception as error:
            return dict(accepted=False, error_type=type(error).__name__, error=str(error))

    out = {'read_only_connections':opened, 'catalog_counts':dict(forms=len(catalog.pokemon),skills=len(catalog.skills)),
           'base_input':creature(), 'chosen':chosen, 'skill':skillname}
    p = build(creature(state={'hp':0,'status':'fainted'})).team_a[0]
    out['I01_zero_hp'] = dict(input_hp=0, input_status='fainted', hp=p.current_hp,
                             status=p.status.value, is_fainted=p.is_fainted)
    actual_ability=catalog.pokemon[chosen]['ability']
    legal_loadout=[n for n in catalog.pokemon[chosen]['skills'] if catalog.get_skill(n) and n!='愿力冲击'][:4]
    legal_control=creature(ability={'name':actual_ability},skills=legal_loadout,state={'hp':0,'status':'fainted'})
    out['I01_real_species_control']=dict(input=legal_control,
        result=capture(lambda:dict(hp=build(legal_control).team_a[0].current_hp,
                                    is_fainted=build(legal_control).team_a[0].is_fainted)))
    iv = {key:8 for key in dims}
    p = build(creature(base={'individual_values':iv})).team_a[0]
    out['I02_six_positive_iv'] = dict(input_iv=iv,accepted_iv={key:getattr(p,'iv_'+key) for key in dims})
    neutral = creature(base={'stats':{'hp':1000}}, metadata={'attribute_assumption':'neutral'})
    p = build(neutral).team_a[0]
    out['I03_neutral_nature'] = dict(nature=p.nature, hp=p.hp, defense=p.defense,
                                   config=p.ability_state['lab_metadata']['attribute_calculation'])
    ident = catalog.skills[skillname].skill_id
    out['I04_id_only'] = dict(id=ident, catalog_resolves=catalog.get_skill(ident).name,
                             builder=capture(lambda:build(creature(skills=[{'skill_id':ident}])).team_a[0].skills[0].name))
    p = build().team_a[0]
    out['I04_name_id_rewritten'] = dict(catalog_id=ident,built_id=p.skills[0].skill_id)
    buffs = [{'name':'物攻','unit':'10%','stacks':2},{'name':'物攻','unit':'10%','stacks':3}]
    p = build(creature(state={'buffs':buffs,'debuffs':{'atk':2}})).team_a[0]
    out['I05_duplicate_buff'] = dict(input_buffs=buffs,atk_up=p.atk_up,atk_down=p.atk_down,
                                   actual_attack=p.effective_atk(),expected_atk_up=.5)
    p = build(creature(state={'buffs':[{'name':'物攻','unit':'10%','stacks':100}]})).team_a[0]
    out['I05_over_cap'] = dict(stacks=100,atk_up=p.atk_up)
    charge = {n:s for n,s in catalog.skills.items() if '蓄力' in s.description}
    out['X01_charge_catalog'] = {n:dict(charge=s.charge,description=s.description,
                                       effects=[str(e) for e in s.effects]) for n,s in charge.items()}
    state = build(creature(skills=['升龙咆哮']))
    result = simulate_turn(state, (0,None),(-1,None), seed=73)
    p = result.state.team_a[0]
    out['X01_charge_turn'] = dict(energy=p.energy,charging_skill_idx=p.charging_skill_idx,
                                 enemy_hp=result.state.team_b[0].current_hp,
                                 expected_enemy_hp=1000, description=catalog.skills['升龙咆哮'].description)
    blood = {}
    for values in (['火'],['首领'],['首领','火'],['奇异火'],['污染水'],['fire'],['火','水'],['unknown']):
        p = build(creature(base={'bloodline_attributes':values})).team_a[0]
        meta = p.ability_state['lab_metadata']
        blood['|'.join(values)] = dict(boss=meta['resolved_boss_bloodline'],
                                      type=getattr(meta['resolved_bloodline_type'],'value',None),
                                      raw=meta['bloodline_attributes'])
    out['Q01_bloodline'] = blood
    p = build(creature(base={'attributes':['fire','water']})).team_a[0]
    out['I06_english_combat_types'] = dict(input=['fire','water'],actual=[v.value for v in p.pokemon_types])
    p = build(creature(state={'hp':{'known':False},'energy':{'known':False}})).team_a[0]
    out['Q02_unknown_defaults'] = dict(hp=p.current_hp,energy=p.energy)
    p = build(creature(base={'attributes':['冰']},state={'statuses':{'冻结':2}})).team_a[0]
    out['Q03_restore_immunity'] = dict(type=p.pokemon_type.value,freeze=p.freeze_stacks)
    out['Q04_no_skill_pool_metadata'] = dict(catalog_skill_pool_count=len(catalog.pokemon[chosen]['skills']),
                                             built_skill_pool=build().team_a[0].ability_state['lab_metadata']['skill_pool'])
    from nrc_platform.platform import BattlePlatform
    from nrc_platform.rooms import RoomService
    with patch('nrc_platform.platform.load_catalog', return_value=catalog):
        service=RoomService(BattlePlatform())
    out['I07_preview_invalid_base'] = {
        str(value):capture(lambda value=value:service.pokemon_preview({'name':'迪莫','base':value}))
        for value in ('invalid', [1], 3)
    }
    out['I07_merge_invalid_base'] = merge_creature_spec({'name':'迪莫','base':'invalid'})
    out['Q06_initial_boss'] = capture(lambda:build(creature(bossified=True)).team_a[0].name)
    devotion_setup=dict(own_team={'creatures':[creature()], 'devotion':{'specified_counts':{'power_bonus':5},'random_draws':1}},
                        opponent_team={'creatures':[creature()]})
    draws=[]
    for seed in range(8):
        try:
            state=builder.build(devotion_setup, seed=seed)
            draws.append(dict(seed=seed,counts=state.devotion_a,random_counts=state.random_devotion_counts_a))
        except Exception as error:
            draws.append(dict(seed=seed,error_type=type(error).__name__,error=str(error)))
    out['I08_devotion_alias'] = dict(input=devotion_setup['own_team']['devotion'],results=draws,
                                    normalized_familiar=builder._canonical_devotion_key('假寐'),
                                    normalized_misspelling=builder._canonical_devotion_key('假寥'))
    devotion_setup['own_team']['devotion']={'random_draws':45}
    out['X02_devotion_fortyfive'] = capture(lambda:builder.build(devotion_setup,seed=0).devotion_a)
    devotion_setup['own_team']['devotion']={'specified_counts':{'power_bonus':9},'random_counts':{'power_bonus':5}}
    state=builder.build(devotion_setup,seed=0)
    out['X02_devotion_over_cap'] = dict(input=devotion_setup['own_team']['devotion'],counts=state.devotion_a)
    unsupported = {}
    for name in ('整点报时','不存在的特性'):
        unsupported[name] = capture(lambda name=name:build(creature(ability={'name':name})).team_a[0].ability)
    for name in ('闪焰爆发','节流术'):
        setup=dict(own_team={'creatures':[creature()],'resonance_magic':name},opponent_team={'creatures':[creature()]})
        unsupported[name] = capture(lambda setup=setup:builder.build(setup))
    out['P01_unsupported_gate'] = unsupported
    state=build(); a=state.team_a[0].skills[0]; b=state.team_b[0].skills[0]
    before=(b.power,b.energy_cost,catalog.skills[skillname].power,catalog.skills[skillname].energy_cost)
    a.power+=37; a.energy_cost+=3
    out['P02_instance_isolation'] = dict(distinct=a is not b, before=before,
                                       after=(b.power,b.energy_cost,catalog.skills[skillname].power,catalog.skills[skillname].energy_cost),
                                       effects_distinct=not a.effects or a.effects[0] is not b.effects[0])
    conn=original_connect((ROOT/'data/nrc_wiki.db').resolve().as_uri()+'?mode=ro',uri=True)
    relation={}
    for name, record in catalog.pokemon.items():
        expected=tuple(r[0] for r in conn.execute('SELECT skill_name FROM spirit_skills WHERE spirit_name=? ORDER BY id',(name,)))
        if not expected:expected=tuple(r[0] for r in conn.execute('SELECT skill_name FROM spirit_skills WHERE spirit_name=? ORDER BY id',(name.split('（',1)[0],)))
        if record['skills']!=expected:relation[name]=dict(actual=record['skills'],expected=expected)
    out['P03_learning_table'] = dict(forms=len(catalog.pokemon),mismatches=relation,
                                     distribution_kinds=[r[0] for r in conn.execute('SELECT DISTINCT distribution_kind FROM distribution_records')])
    out['P04_aliases'] = dict(types={k:_lookup(_TYPE_ALIASES,k,None).value for k in _TYPE_ALIASES},
                              categories={k:_lookup(_CATEGORY_ALIASES,k,None).value for k in _CATEGORY_ALIASES},
                              actual_categories=[r[0] for r in conn.execute('SELECT DISTINCT category FROM skill_catalog')],
                              malformed_type=_lookup(_TYPE_ALIASES,'notfire',Type.NORMAL).value,
                              malformed_category=_lookup(_CATEGORY_ALIASES,'notphysical',SkillCategory.STATUS).value)
    type_oracle=dict(zip(('普通','火','水','草','电','冰','武','毒','地','翼','幻','虫','幽','龙','恶','机械','萌','光'),
                        ('normal','fire','water','grass','electric','ice','fighting','poison','ground','flying','psychic','bug','ghost','dragon','dark','steel','fairy','light')))
    categories={'物攻':'物攻','魔攻':'魔攻','防御':'防御','状态':'状态'}
    converted=[]
    with (ROOT/'data/wiki/skills.csv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            s=catalog.get_skill(row['名称'])
            actual=[s.skill_type.value,s.category.value,s.power,s.energy_cost,s.skill_id,s.description]
            stable_id=row['技能目录ID'] or str(conn.execute('SELECT id FROM skill_catalog WHERE name=?',(row['名称'],)).fetchone()[0])
            expected=[type_oracle[row['属性'].removesuffix('系')],categories[row['分类']],int(row['威力']),int(row['耗能']),stable_id,row['描述']]
            converted.append(dict(name=row['名称'],matches=actual==expected,actual=actual,expected=expected))
    out['P06_skill_conversion'] = dict(count=len(converted),mismatches=[r for r in converted if not r['matches']])
    distribution_rows=conn.execute('SELECT spirit_name,distribution_kind,item_name,percentage,position FROM distribution_records').fetchall()
    distribution_groups={}
    for name,kind,item,pct,pos in distribution_rows:
        distribution_groups.setdefault((name,kind),[]).append((str(item),float(str(pct or 0).replace('%','')),int(pos or 0)))
    distribution_errors=[]
    for (name,kind), rows in distribution_groups.items():
        expected=sorted(rows,key=lambda r:(-r[1],r[2]))
        actual=[(r['item'],r['percentage'],r['position']) for r in catalog.get_distribution(name,kind)]
        if actual!=expected:distribution_errors.append([name,kind])
    out['P07_distribution_separation'] = dict(rows=len(distribution_rows),groups=len(distribution_groups),
                                              kinds=dict(Counter(kind for _,kind in distribution_groups)),
                                              mismatches=distribution_errors)
    out['P05_compact_input'] = dict(six=split_creature_spec('名字 100 101 102 103 104 105'),
                                    hp=split_creature_spec('名字，100'),empty=split_creature_spec(''),
                                    bad_count=capture(lambda:split_creature_spec('名字 1 2')),
                                    mapping=merge_creature_spec({'name':{'known':False},'base':{'stats':{'hp':7}}}),
                                    merged=merge_creature_spec({'name':'名字 100','base':{'stats':{'hp':7,'atk':8}}}))
    out['Q05_boss_devolution'] = dict(boss_mapping=len(catalog.boss_forms),
                                      multi_previous={n:r['previous_forms'] for n,r in catalog.pokemon.items() if len(r['previous_forms'])>1},
                                      source_columns=[r[1] for r in conn.execute('PRAGMA table_info(evolution_links)')],
                                      lord_forms=sum(r['is_lord'] for r in catalog.pokemon.values()))
    out['P08_reject_inputs'] = dict(
        missing_team=capture(lambda:builder.build({'own_team':{'creatures':[]},'opponent_team':{'creatures':[creature()]}})),
        bad_active=capture(lambda:builder.build({'own_team':{'creatures':[creature()],'active_index':8},'opponent_team':{'creatures':[creature()]}})),
        missing_skill=capture(lambda:build(creature(skills=[]))),
        missing_form=capture(lambda:build(creature(name='不存在的精灵'))),
        resonance_only=capture(lambda:build(creature(skills=['愿力冲击']))),
        partial_stats=capture(lambda:build(creature(base={'stats':{'hp':1000,'atk':100}}))))
    conn.close()
    (HERE/'probe_output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k in {'I01_zero_hp','I02_six_positive_iv','I04_id_only','I05_duplicate_buff','X01_charge_turn','I07_preview_invalid_base','I08_devotion_alias','X02_devotion_over_cap','P06_skill_conversion','P07_distribution_separation','P08_reject_inputs'}},ensure_ascii=False,indent=2,default=str))


if __name__ == '__main__':
    main()
