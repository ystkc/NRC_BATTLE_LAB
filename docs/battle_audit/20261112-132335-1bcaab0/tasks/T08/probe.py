"""T08 技能原语边界与逐对象补证；所有输出限定在本任务目录。"""
import copy
import csv
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
from nrc_core.models import Pokemon, Skill, BattleState, Type, SkillCategory
from nrc_core.effect_models import E, EffectTag, SkillEffect, SkillTiming
from nrc_core.effect_data import SKILL_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
from nrc_core.engine import Ctx, EffectExecutor
from nrc_core.engine import handlers_skill as handlers
from nrc_core.battle import execute_full_turn, turn_end_effects
from nrc_core.debug import configure_core_logging


def setup():
    """固定两只1000最大HP精灵，避免随机先后与其他特性。"""
    skill = Skill('审计攻击', Type.NORMAL, SkillCategory.PHYSICAL, 80, 0)
    user = Pokemon('甲', Type.NORMAL, 1000, 100, 100, 100, 100, 200, skills=[skill],current_hp=500,energy=0)
    enemy = Pokemon('乙', Type.NORMAL, 1000, 100, 100, 100, 100, 100,current_hp=500)
    return BattleState([user],[enemy]),user,enemy,skill


def run():
    """运行少量高风险跨阶段反例及可完整匹配的简单原文。"""
    configure_core_logging('')
    output={}
    state,user,enemy,skill=setup()
    enemy.energy=1
    handlers._h_steal_energy(EffectTag(E.STEAL_ENERGY,{'amount':3}),Ctx(state,user,enemy,skill))
    output['steal_available']={'user_energy':user.energy,'enemy_energy':enemy.energy,'enemy_before':1,'amount':3}
    state,user,enemy,skill=setup()
    enemy.pokemon_type=Type.FIRE;enemy.pokemon_types=[Type.FIRE]
    state.marks_b={'attack_mark':2}
    handlers._h_convert_marks_to_burn(EffectTag(E.CONVERT_MARKS_TO_BURN,{'ratio':3}),Ctx(state,user,enemy,skill))
    output['convert_fire_immune']={'burn_stacks':enemy.burn_stacks,'remaining_marks':state.marks_b}
    state,user,enemy,skill=setup()
    enemy.pokemon_types=[Type.POISON]
    handlers._h_poison(EffectTag(E.POISON,{'stacks':2,'target':'self'}),Ctx(state,user,enemy,skill))
    output['self_poison_wrong_immunity']={'self_type':user.pokemon_type.value,'enemy_types':[t.value for t in enemy.pokemon_types],'self_poison':user.poison_stacks}
    state,user,enemy,skill=setup()
    state.marks_b={'attack_mark':1}
    handlers._h_solar_mark(EffectTag(E.SOLAR_MARK,{'target':'enemy','stacks':1}),Ctx(state,user,enemy,skill))
    handlers._h_poison_mark(EffectTag(E.POISON_MARK,{'stacks':1}),Ctx(state,user,enemy,skill))
    handlers._h_spirit_mark(EffectTag(E.SPIRIT_MARK,{'stacks':1}),Ctx(state,user,enemy,skill))
    output['mark_slots']={'marks':state.marks_b}
    state,user,enemy,skill=setup()
    state.weather='sandstorm'
    state.team_a.append(Pokemon('场下',Type.NORMAL,1000,100,100,100,100,100,current_hp=100))
    handlers._apply_weather_damage(state)
    output['sand_invented_damage']={'active_hp':user.current_hp,'bench_hp':state.team_a[1].current_hp}
    state,user,enemy,skill=setup()
    state.weather='thunder';state.weather_turns=8
    turn_end_effects(state)
    output['thunder_guard']={'user_electric':user.electric_stacks,'enemy_electric':enemy.electric_stacks}
    state,user,enemy,skill=setup()
    skill.skill_type=Type.GROUND;skill.energy_cost=4
    ctx=Ctx(state,user,enemy,skill)
    for _ in range(2):handlers._h_weather(EffectTag(E.WEATHER,{'type':'sandstorm','turns':5}),ctx)
    output['sand_reapply']={'base_cost':4,'actual_cost':skill.energy_cost}
    state,user,enemy,skill=setup()
    skill.effects=[SkillEffect(SkillTiming.ON_USE,[EffectTag(E.DAMAGE),EffectTag(E.LIFE_DRAIN,{'pct':1.0})])]
    defense=Skill('审计防御',Type.NORMAL,SkillCategory.DEFENSE,-1,0,effects=[SkillEffect(SkillTiming.ON_USE,[EffectTag(E.DAMAGE_REDUCTION,{'pct':0.5})])])
    enemy.skills=[defense]
    execute_full_turn(state,(0,),(0,))
    output['drain_before_reduction']={'user_hp_before':500,'user_hp_after':user.current_hp,'enemy_hp_before':500,'enemy_hp_after':enemy.current_hp,'events':state.turn_report}
    state,user,enemy,skill=setup()
    se=SkillEffect(SkillTiming.ON_COUNTER,[EffectTag(E.LIFE_DRAIN,{'pct':1.0})],{'category':'status'})
    status=Skill('状态',Type.NORMAL,SkillCategory.STATUS,-1,0)
    result=EffectExecutor.execute_counter(state,user,enemy,skill,se,status,90)
    output['counter_drain']={'user_hp':user.current_hp,'counter_result':result}
    state,user,enemy,skill=setup()
    user.next_attack_power_bonus=70
    effects=[SkillEffect(SkillTiming.ON_USE,[EffectTag(E.DAMAGE),EffectTag(E.DAMAGE)])]
    result=EffectExecutor.execute_skill(state,user,enemy,skill,effects)
    output['multiple_damage_next_attack']={'result':result,'next_bonus_after':user.next_attack_power_bonus}
    state,user,enemy,skill=setup()
    user.skills=[Skill('左',Type.NORMAL,SkillCategory.STATUS,-1,4),skill,Skill('右',Type.NORMAL,SkillCategory.STATUS,-1,3)]
    skill.energy_cost=2
    se=SkillEffect(SkillTiming.ON_COUNTER,[EffectTag(E.PASSIVE_ENERGY_REDUCE,{'reduce':1,'range':'adjacent'})],{'category':'attack'})
    EffectExecutor.execute_counter(state,user,enemy,skill,se,skill,90)
    output['adjacent_counter_reduce']={'costs_before':[4,2,3],'costs_after':[s.energy_cost for s in user.skills]}
    state,user,enemy,skill=setup()
    state.marks_b={'spirit_mark':2}
    handlers._h_poison_mark(EffectTag(E.POISON_MARK,{'stacks':1}),Ctx(state,user,enemy,skill))
    output['poison_mark_slot_bypass']={'marks_before':{'spirit_mark':2},'marks_after':state.marks_b}
    state,user,enemy,skill=setup()
    user.ability_state['anti_heal_multiplier']=2
    handlers._h_heal_hp(EffectTag(E.HEAL_HP,{'pct':0.1}),Ctx(state,user,enemy,skill))
    output['anti_heal_multiplier']={'hp_before':500,'max_hp':1000,'heal_pct':0.1,'multiplier':2,'hp_after':user.current_hp}
    state,user,enemy,skill=setup()
    state.marks_b={'attack_mark':2}
    handlers._h_marks_to_meteor(EffectTag(E.MARKS_TO_METEOR),Ctx(state,user,enemy,skill))
    output['marks_to_meteor_kind']={'marks_after':state.marks_b,'individual_meteor_stacks':enemy.meteor_stacks,'meteor_countdown':enemy.meteor_countdown}
    state,user,enemy,skill=setup()
    user.attack=200
    exact=Fraction(80)*2*200*Fraction(37,41)
    rounded=(exact.numerator*2+exact.denominator)//(exact.denominator*2)
    expected=rounded//100
    handlers._h_mirror_damage(EffectTag(E.MIRROR_DAMAGE),Ctx(state,user,enemy,skill,damage=90))
    output['mirror_raw_damage']={'incoming_raw_damage':90,'counter_power':80,'counter_expected_from_own_attack':expected,'target_hp_after':enemy.current_hp,'actual_damage':500-enemy.current_hp}
    state,user,enemy,skill=setup()
    for condition in ('enemy_total_cost','adjacent_power_sum','unknown_audit_condition'):
        ctx=Ctx(state,user,enemy,skill)
        handlers._h_power_dynamic(EffectTag(E.POWER_DYNAMIC,{'condition':condition,'bonus':70}),ctx)
        output['power_condition_'+condition]={'result':ctx.result,'exception':None}
    state,user,enemy,skill=setup()
    skill.energy_cost=2;user.energy=3
    defense=Skill('打断测试',Type.NORMAL,SkillCategory.DEFENSE,-1,1,effects=[SkillEffect(SkillTiming.ON_COUNTER,[EffectTag(E.INTERRUPT)],{'category':'attack'})])
    enemy.skills=[defense];enemy.energy=3
    execute_full_turn(state,(0,),(0,))
    output['interrupted_cost_counts']={'attacker_energy_after':user.energy,'attacker_uses':state.skill_use_counts_a,'counter_count':state.counter_count_b,'events':state.turn_report}
    (OUT/'probe_output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    merged={**SKILL_EFFECTS_GENERATED,**SKILL_EFFECTS}
    state,user,enemy,skill=setup()
    skill.name='撕裂';skill.skill_type=Type.DARK;skill.power=85;skill.energy_cost=3;skill.effects=copy.deepcopy(merged['撕裂']);user.energy=5
    enemy.skills=[Skill('原地等待',Type.NORMAL,SkillCategory.STATUS,-1,0,effects=[])];enemy.energy=3
    execute_full_turn(state,(0,),(0,))
    output['actual_counter_drain_撕裂']={'user_hp_before':500,'user_hp_after':user.current_hp,'enemy_hp_before':500,'enemy_hp_after':enemy.current_hp,'events':state.turn_report}
    original=list(csv.DictReader((OUT.parent/'T06/object_review.csv').open(encoding='utf-8-sig')))
    inputs={r['name']:r['input'] for r in json.loads((OUT.parent/'T06/skill_probe.json').read_text(encoding='utf-8'))}
    for name in ('冰锋横扫','钢钻'):
        state,user,enemy,skill=setup()
        meta=inputs[name]
        skill.name=name;skill.power=meta['power'];skill.energy_cost=meta['cost']
        skill.category=SkillCategory.MAGICAL if name=='冰锋横扫' else SkillCategory.PHYSICAL
        user.skills=[Skill('左侧',Type.NORMAL,SkillCategory.PHYSICAL,120,2),skill,Skill('右侧',Type.NORMAL,SkillCategory.PHYSICAL,60,2)]
        enemy.skills=[Skill('敌技能',Type.NORMAL,SkillCategory.PHYSICAL,80,4)]
        result=EffectExecutor.execute_skill(state,user,enemy,skill,copy.deepcopy(merged[name]))
        output['actual_dynamic_'+name]={'original_power':meta['power'],'expected_dynamic_power':40 if name=='冰锋横扫' else 60,'result':result}
    state,user,enemy,skill=setup()
    baseline=EffectExecutor.execute_skill(state,user,enemy,skill,[SkillEffect(SkillTiming.ON_USE,[EffectTag(E.DAMAGE)])])
    user.hit_count_mod=2
    modified=EffectExecutor.execute_skill(state,user,enemy,skill,[SkillEffect(SkillTiming.ON_USE,[EffectTag(E.DAMAGE)])])
    output['single_hit_buff']={'base_hit_count':skill.hit_count,'hit_count_mod':2,'baseline_damage':baseline['damage'],'modified_damage':modified['damage']}
    (OUT/'probe_output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    verified=[]
    for row in original:
        if not row['item_id'].startswith('SKILL:') or row['conclusion']!='检查受阻':continue
        description=row['description']
        match=re.fullmatch(r'(造成(?:物|魔)伤，)?(自己|敌方)获得(物攻|魔攻|物防|魔防|速度)([+-]\d+)(%)?。',description)
        dot=re.fullmatch(r'(造成(?:物|魔)伤，)?敌方获得(\d+)层(中毒|灼烧|冻结)。',description)
        if not (match or dot):continue
        state,user,enemy,skill=setup()
        meta=inputs[row['name']]
        skill.name=row['name'];skill.power=meta['power'];skill.energy_cost=meta['cost'];user.energy=3
        skill.category=SkillCategory.MAGICAL if '魔伤' in description else SkillCategory.PHYSICAL if description.startswith('造成') else SkillCategory.STATUS
        skill.effects=copy.deepcopy(merged.get(skill.name,[]))
        result=EffectExecutor.execute_skill(state,user,enemy,skill,skill.effects)
        if match:
            target=user if match[2]=='自己' else enemy
            prefix={'物攻':'atk','魔攻':'spatk','物防':'def','魔防':'spdef','速度':'speed'}[match[3]]
            value=float(match[4])/(100 if match[5] else 1)
            field=prefix+('_up' if value>0 else '_down')
            actual=getattr(target,field);expected=abs(value)
        else:
            field={'中毒':'poison_stacks','灼烧':'burn_stacks','冻结':'freeze_stacks'}[dot[3]]
            actual=getattr(enemy,field);expected=int(dot[2])
        verified.append({'item_id':row['item_id'],'name':skill.name,'description':description,'field':field,'expected':expected,'actual':actual,'damage':result.get('damage'),
                         'full_description_matched':True,'matches':actual==expected and (not description.startswith('造成') or result.get('damage',0)>0),
                         'limits':'中性非免疫场景；每对象原文无其他子句；基础伤害数值及平台扣能不在此单测升级范围'})
    (OUT/'object_probe.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'repros':len(output),'object_probes':len(verified),'matched':sum(r['matches'] for r in verified)},ensure_ascii=False))


if __name__=='__main__':run()
