"""真实洗礼/除厄验证清除；退化验证王子对萌化的分类。"""
import copy
import json
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT))
from nrc_core.models import Pokemon, Skill, Type, SkillCategory, BattleState
from nrc_core.compound_status import CompoundStatus
from nrc_core.effect_data import SKILL_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
from nrc_core.engine import EffectExecutor
from nrc_core.debug import configure_core_logging


def snapshot(user,state):
    """只输出判断清除范围所需的原始状态。"""
    return {'statuses':{key:getattr(user,key) for key in ('poison_stacks','burn_stacks','freeze_stacks','leech_stacks','cute_stacks','electric_stacks')},
            'atk_down':user.atk_down,'skill_cost_mod':user.skill_cost_mod,'skill_power_bonus':user.skill_power_bonus,
            'temporary_skill_cost_mods':copy.deepcopy(user.ability_state['temporary_skill_cost_mods']),
            'marks':copy.deepcopy(state.marks_a),'ability':user.ability,
            'compound_statuses':{key:{'name':value.name,'stacks':value.stacks,'modifiers':value.modifiers} for key,value in user.compound_statuses.items()}}


output={}
configure_core_logging('')
merged={**SKILL_EFFECTS_GENERATED,**SKILL_EFFECTS}
for name in ('洗礼','除厄'):
    skill=Skill(name,Type.WATER if name=='洗礼' else Type.FIRE,SkillCategory.STATUS if name=='洗礼' else SkillCategory.MAGICAL,-1 if name=='洗礼' else 60,1 if name=='洗礼' else 2)
    user=Pokemon('甲',Type.NORMAL,1000,100,100,100,100,200,skills=[skill],current_hp=800,energy=10,ability='最好的伙伴')
    enemy=Pokemon('乙',Type.NORMAL,1000,100,100,100,100,100,current_hp=800)
    state=BattleState([user],[enemy]);state.marks_a={'poison_mark':2}
    user.poison_stacks=1;user.burn_stacks=2;user.freeze_stacks=1;user.leech_stacks=1;user.cute_stacks=1;user.electric_stacks=1
    user.atk_down=0.3;user.skill_cost_mod=2;user.skill_power_bonus=-20
    user.ability_state['temporary_skill_cost_mods']=[{'amount':2,'filter':'all','turns':3}]
    user.compound_statuses['best_partner']=CompoundStatus('最好的伙伴',1,{'atk_up':0.2})
    before=snapshot(user,state)
    result=EffectExecutor.execute_skill(state,user,enemy,skill,copy.deepcopy(merged[name]))
    output[name]={'rule_basis':'data/wiki/game_descriptions.csv:14（GAME_RULE8）；data/wiki/skills.csv:285,521；data/状态分类.md:2-6',
                  'effects_source':'nrc_core/skill_effects_generated.py:318,595（由当前手写覆盖合并后实际读取）',
                  'before':before,'after':snapshot(user,state),'result':result,
                  'expected':'poison/burn/freeze/leech/cute/electric这些明确减益均清0；印记与特性身份、特性复合状态保留；技能负向修正另需区分洗礼自身-1与旧加耗来源'}
skill=Skill('退化',Type.FAIRY,SkillCategory.STATUS,-1,3)
user=Pokemon('施法者',Type.NORMAL,1000,100,100,100,100,200,skills=[skill])
enemy=Pokemon('王子',Type.WATER,1000,100,100,100,100,100,ability='王子的诺言',skills=[Skill('成本控制',Type.NORMAL,SkillCategory.STATUS,-1,2)])
enemy.devolution_forms=[{'name':'退化王子','stats':{'hp':1000,'atk':100,'def':100,'spatk':100,'spdef':100,'speed':100}}]
state=BattleState([user],[enemy])
result=EffectExecutor.execute_skill(state,user,enemy,skill,copy.deepcopy(merged['退化']))
output['王子萌化分类']={'rule_basis':'data/wiki/game_descriptions.csv:14；data/wiki/spirits.csv:58',
                       'input':'真实退化完整effects；王子有一退化形态，未触发过本回合增减益，技能成本2',
                       'expected_cost':3,'actual_cost':enemy.skills[0].energy_cost,'cute_stacks':enemy.cute_stacks,
                       'promise_flags':{key:value for key,value in enemy.ability_state.items() if key.startswith('prince_promise')},'result':result}
(OUT/'cleanse_probe_output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(output,ensure_ascii=False))
