"""来源校正后的明确特性差异补证，不调用伤害计算器生成期望。"""
import json
from pathlib import Path
from probe import setup
from nrc_core.models import Pokemon, Type
from nrc_core.effect_models import Timing
from nrc_core.engine import EffectExecutor

OUT=Path(__file__).resolve().parent
output={}
for ability in ('虫群突袭','虫群鼓舞'):
    state,user,enemy,skill=setup(ability)
    state.team_a.append(Pokemon('虫队友',Type.BUG,500,100,100,100,100,80))
    EffectExecutor.execute_ability(state,user,enemy,Timing.ON_ENTER,user.ability_effects)
    entry=str(user.compound_statuses)
    EffectExecutor.execute_ability(state,user,enemy,Timing.PASSIVE,user.ability_effects)
    output[ability]={'input':'1只其他存活虫精灵；入场后再执行当前PASSIVE配置','after_on_enter':entry,
                    'after_passive':str(user.compound_statuses),'expected_attributes':['atk','spatk','def','spdef','speed']}
state,user,enemy,skill=setup('毒牙')
enemy.poison_stacks=1
EffectExecutor.execute_ability(state,user,enemy,Timing.ON_USE_SKILL,user.ability_effects,context={'skill':skill})
output['毒牙']={'input':'敌预有1毒，本次仅普通攻击未施毒','actual':{key:getattr(enemy,key) for key in ('atk_down','speed_down','spatk_down','spdef_down')},
                'expected':'本次未成功施毒不应新增；成功施毒也应物攻-40%/速度-40而非魔攻魔防'}
state,user,enemy,skill=setup('毒腺')
skill.energy_cost=3
EffectExecutor.execute_ability(state,user,enemy,Timing.ON_USE_SKILL,user.ability_effects,context={'skill':skill})
output['毒腺']={'input_cost':3,'expected_poison':0,'actual_poison':enemy.poison_stacks}
for attack in (100,200):
    state,user,enemy,skill=setup('刺肤')
    user.attack=attack
    EffectExecutor.execute_ability(state,user,enemy,Timing.ON_TAKE_HIT,user.ability_effects,context={'skill':skill})
    output['刺肤_'+str(attack)]={'source_attack':attack,'target_defense':enemy.defense,'before_hp':500,'after_hp':enemy.current_hp,
                              'expected_relation':'50威力物理伤害在相同其他条件下应随反击者物攻改变；本项不猜未说明系别，也不以计算器作期望'}
(OUT/'source_correction_probe_output.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(output,ensure_ascii=False))
