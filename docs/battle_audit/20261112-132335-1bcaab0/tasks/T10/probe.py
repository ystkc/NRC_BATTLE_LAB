"""场地原语逐分支探针：只操作内存，保存输入输出和期望差异。"""
from pathlib import Path
import copy
import json
import sys

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from nrc_core.models import Pokemon, Skill, Type, SkillCategory, BattleState
from nrc_core.effect_models import EffectTag, E, Timing, SkillTiming
from nrc_core.effect_data import ABILITY_EFFECTS, SE
from nrc_core.engine.context import Ctx
from nrc_core.engine import handlers_field as field
from nrc_core.engine import EffectExecutor
from nrc_core.debug import configure_core_logging
from nrc_core.battle import _apply_ability_damage_reduction, _apply_damage_to_enemy, execute_full_turn, _apply_share_gains

RESULTS = []
FIELDS = ['name','hp','current_hp','energy','attack','defense','sp_attack','sp_defense','speed','atk_up','spatk_up','def_up','spdef_up','speed_up','atk_down','spatk_down','def_down','spdef_down','speed_down','skill_power_bonus','skill_cost_mod','hit_count_mod','life_drain_mod','poison_stacks','burn_stacks','freeze_stacks','meteor_stacks','cute_stacks','charging_skill_idx']

def skill(name='审计', kind=Type.NORMAL):
    """构造固定技能。"""
    return Skill(name, kind, SkillCategory.PHYSICAL, power=50,energy_cost=4)

def pokemon(name='A'):
    """构造固定数值与退化链。"""
    p=Pokemon(name,Type.NORMAL,1000,200,200,200,200,200,current_hp=500,energy=5)
    p.skills=[skill()]
    p.devolution_forms=[{'name':'幼'+str(i),'stats':{'hp':1000-i*100,'atk':200-i*20,'def':200-i*20,'spatk':200-i*20,'spdef':200-i*20,'speed':200-i*20}} for i in range(1,5)]
    return p

def setup():
    """建立可直接调用原语的上下文。"""
    a,b=pokemon(),pokemon('B')
    state=BattleState([a],[b])
    return Ctx(state,a,b,skill=a.skills[0],execute_ability=EffectExecutor.execute_ability)

def snapshot(ctx):
    """保存双方属性、技能及场地。"""
    def p(poke):
        return {**{k:getattr(poke,k) for k in FIELDS},'skills':[{'name':s.name,'type':s.skill_type.name,'power':s.power,'cost':s.energy_cost,'hits':s.hit_count,'agility':s.agility} for s in poke.skills],'ability_state':copy.deepcopy(poke.ability_state)}
    return {'user':p(ctx.user),'target':p(ctx.target),'team_a':[p(x) for x in ctx.state.team_a],'team_b':[p(x) for x in ctx.state.team_b],'marks_a':dict(ctx.state.marks_a),'marks_b':dict(ctx.state.marks_b),'devotion_a':dict(ctx.state.devotion_a),'devotion_b':dict(ctx.state.devotion_b),'random_a':dict(ctx.state.random_devotion_counts_a),'random_b':dict(ctx.state.random_devotion_counts_b),'result':{k:v for k,v in ctx.result.items() if isinstance(v,(str,int,float,bool,list,dict))}}

def run(name,ctx,action,expected=None):
    """记录调用前后，不把无异常当作通过。"""
    entry={'case':name,'input':snapshot(ctx),'expected':expected}
    visited=set()
    def trace(frame,event,arg):
        if event=='line' and Path(frame.f_code.co_filename).resolve()==Path(field.__file__).resolve():
            visited.add(frame.f_lineno)
        return trace
    try:
        sys.settrace(trace)
        action()
        sys.settrace(None)
        entry['output']=snapshot(ctx)
    except Exception as exc:
        sys.settrace(None)
        entry['exception']=type(exc).__name__+': '+str(exc)
    entry['field_lines']=sorted(visited)
    RESULTS.append(entry)
    return entry

def main():
    """枚举全部球、系别和萌化行为。"""
    configure_core_logging('')
    original_choice=field.rng_choice
    for handler in [field._h_devotion_grant_random,field._h_devotion_on_hit]:
        ctx=setup()
        ctx.state.devotion_a={'飞断':5}
        pools=[]
        field.rng_choice=lambda pool:(pools.append(list(pool)) or '飞断')
        item=run(handler.__name__+'_capped',ctx,lambda:handler(EffectTag(E.DEVOTION_GRANT_RANDOM),ctx),'飞断满5应从候选剔除；其余4种任一增加1')
        item['choice_pools']=pools
    ctx=setup()
    ctx.state.devotion_a=field.DEVOTION_CAPS.copy()
    pools=[]
    field.rng_choice=lambda pool:(pools.append(list(pool)) or pool[0])
    item=run('devotion_all_full',ctx,lambda:field._h_devotion_grant_random(EffectTag(E.DEVOTION_GRANT_RANDOM),ctx),'全满无需抽取，不能丢异常或虚报获得')
    item['choice_pools']=pools
    for dtype in field.DEVOTION_TYPES:
        ctx=setup()
        ctx.state.devotion_b={dtype:field.DEVOTION_CAPS[dtype]}
        ctx.team='b'
        run('devotion_explicit_cap_'+dtype,ctx,lambda:field._grant_devotion(ctx.state,'b',dtype),'明确指定也受文档上限约束；A不变B不超限')
    ctx=setup()
    run('devotion_unknown',ctx,lambda:field._grant_devotion(ctx.state,'a','未知'),'不应伪造已支持奉献类型；现调用方仅五种')
    field.rng_choice=original_choice
    for type_value in Type:
        ctx=setup()
        ctx.user.skills=[skill('折射',Type.LIGHT),skill('携带',type_value)]
        ctx.skill=ctx.user.skills[0]
        run('refraction_'+type_value.name,ctx,lambda:field._h_refraction(EffectTag(E.REFRACTION),ctx),'详解折射效果.md对应类型效果；含折射本身光系+30%魔攻')
    ctx=setup()
    ctx.user.skills=[skill('折射',Type.LIGHT),skill('火1',Type.FIRE),skill('火2',Type.FIRE)]
    ctx.skill=ctx.user.skills[0]
    run('refraction_duplicate_fire',ctx,lambda:field._h_refraction(EffectTag(E.REFRACTION),ctx),'火各4层合计8灼烧；自身光系+30%魔攻')
    for type_value,status in [(Type.FIRE,'burn_stacks'),(Type.POISON,'poison_stacks'),(Type.ICE,'freeze_stacks')]:
        ctx=setup()
        ctx.target.pokemon_type=type_value
        ctx.target.pokemon_types=[type_value]
        ctx.user.skills=[skill('折射',Type.LIGHT),skill('携带',type_value)]
        ctx.skill=ctx.user.skills[0]
        run('refraction_type_immunity_'+type_value.name,ctx,lambda:field._h_refraction(EffectTag(E.REFRACTION),ctx),f'原文同系免疫，应{status}=0')
    ctx=setup()
    ctx.target.ability_state={'burn_immune':True,'freeze_immune':True,'poison_immune':True,'debuff_immune':True,'energy_immune':True}
    ctx.user.skills=[skill('折射',Type.LIGHT)]+[skill(t.name,t) for t in Type]
    ctx.skill=ctx.user.skills[0]
    run('refraction_ability_immunity',ctx,lambda:field._h_refraction(EffectTag(E.REFRACTION),ctx),'各免疫分支不施加敌方负面效果，自己效果仍生效')
    balls=['普通咕噜球','高级咕噜球','国王球','美妙球','好战球','光合球','网兜球','暗星球','调温球','绝缘球','淘沙球','变幻球']
    for ball in balls:
        ctx=setup()
        run('contract_'+ball,ctx,lambda:field._h_contract_entry(EffectTag(E.CONTRACT_ENTRY,{'ball':ball}),ctx),'详解契约的形状.md该行全部效果')
    for option in ['skill_power','heal','burn','skill_cost','spatk','slow_combo','speed','poison','def','atk','combo','enemy_atk','spdef','meteor','freeze','enemy_spdef','energy','drain']:
        ctx=setup()
        field.rng_choice=lambda pool:option
        run('soft_'+option,ctx,lambda:field._h_contract_entry(EffectTag(E.CONTRACT_ENTRY,{'ball':'柔软咕噜球'}),ctx),'仅文档列出的该单个效果；不携带常规球的配对效果')
    ctx=setup()
    choices=iter(['burn','heal'])
    field.rng_choice=lambda pool:next(choices)
    run('soft_reentry',ctx,lambda:[field._h_contract_entry(EffectTag(E.CONTRACT_ENTRY,{'ball':'柔软咕噜球'}),ctx) for _ in range(2)],'是否每次入场独立抽取需规则说明；记录实际固定首次随机且仍消耗随机选择')
    field.rng_choice=original_choice
    for element in ['普通','草','火','水','光','地','冰','龙','电','毒','虫','武','翼','萌','幽','恶','机械','幻']:
        ctx=setup()
        run('bloodline_'+element,ctx,lambda:field._h_bloodline_entry(EffectTag(E.BLOODLINE_ENTRY,{'element':element}),ctx),'稀兽花宝.md对应血脉全部效果')
    ctx=setup()
    run('cute_add',ctx,lambda:field._cute_add(ctx.user,1),'增加1层并降低种族属性到上一阶；类型/技能/特性不在原文要求内')
    ctx=setup()
    ctx.user.devolution_forms=[]
    run('cute_no_previous',ctx,lambda:field._cute_add(ctx.user,1),'不可退化不得获得萌化')
    ctx=setup()
    run('cute_default_cap',ctx,lambda:field._cute_add(ctx.user,8),'当前默认最多3层；4阶链是否应允许4层需说明')
    ctx=setup()
    field._h_cute_no_cap(EffectTag(E.CUTE_NO_CAP),ctx)
    run('cute_no_cap',ctx,lambda:field._cute_add(ctx.user,8),'无忧无虑按可退化链长度限制；不能凭空生成形态')
    for function in [field._h_cute_clear_self,field._h_cute_transfer]:
        ctx=setup()
        field._cute_add(ctx.user,1)
        run(function.__name__,ctx,lambda:function(EffectTag(E.CUTE_CLEAR_SELF),ctx),'移除自身萌化应恢复基础形态与属性；转移时目标按自身退化链结算')
    ctx=setup()
    field._cute_add(ctx.user,1)
    field._h_cute_on_gain_speed_perm(EffectTag(E.CUTE_ON_GAIN_SPEED_PERM,{'speed':130}),ctx)
    run('cute_permanent_speed_next_gain',ctx,lambda:field._cute_add(ctx.user,1),'永久速度+130应在后续退化后保留')
    ctx=setup()
    ctx.user.skills=[skill('攻击'),Skill('状态',Type.NORMAL,SkillCategory.STATUS,power=0,energy_cost=4)]
    run('cute_power_perm',ctx,lambda:field._h_cute_on_gain_power_perm(EffectTag(E.CUTE_ON_GAIN_POWER_PERM,{'delta':10}),ctx),'原文全技能威力永久+10；没有威力的状态技不应获得攻击威力字段10')
    ctx=setup()
    ctx.state.team_a += [pokemon('队友'),pokemon('力竭')]
    ctx.state.team_a[-1].current_hp=0
    run('cute_team_bench',ctx,lambda:field._h_cute_all_bench(EffectTag(E.CUTE_ALL_BENCH),ctx),'全队及自身、排除力竭；对方不变')
    ctx=setup()
    ctx.target.cute_stacks=1
    run('cute_team_power_twice',ctx,lambda:[field._h_cute_team_power(EffectTag(E.CUTE_TEAM_POWER),ctx) for _ in range(2)],'本次连击加1，每次都相同；不能使技能基础hit_count连续永久增加')
    ctx=setup()
    ctx.result['damage']=600
    run('cute_lethal_once',ctx,lambda:field._h_cute_lethal_shield(EffectTag(E.CUTE_LETHAL_SHIELD),ctx),'原文免疫本次伤害；应不把原500HP主动设为1')
    ctx=setup()
    ctx.result['damage']=600
    run('cute_lethal_three_calls',ctx,lambda:[field._h_cute_lethal_shield(EffectTag(E.CUTE_LETHAL_SHIELD),ctx) for _ in range(3)],'化茧原文最多2次，第三次不得触发')
    ctx=setup()
    ctx.user.ability='化茧'
    ctx.user.ability_effects=ABILITY_EFFECTS['化茧']
    def lethal_consumer():
        damage=_apply_ability_damage_reduction(ctx.state,ctx.target,ctx.user,ctx.target.skills[0],600,'a')
        ctx.result['post_ability_damage']=damage
        _apply_damage_to_enemy(ctx.state,ctx.user,damage,attacker=ctx.target,skill=ctx.target.skills[0])
    run('cute_lethal_consumer',ctx,lethal_consumer,'完整消费：首次致命攻击应被免疫并有萌化；实际blocked_lethal是否从context返回至ability_result')
    ctx=setup()
    ctx.user.ability_state['charge_cost_reduce']=2
    ctx.user.skills[0].charge=True
    run('charge_cost_consumer',ctx,lambda:execute_full_turn(ctx.state,(0,),(-1,)),'进入蓄力时全技能永久能耗-2，charging_skill_idx=0')
    ctx=setup()
    ctx.user.charging_skill_idx=0
    ctx.user.ability_state['charge_free_skill']=True
    ctx.user.skills.append(skill('普通'))
    run('charge_free_consumer',ctx,lambda:execute_full_turn(ctx.state,(1,),(-1,)),'蓄力期间嫉妒可改选非蓄力技能；记录蓄力标志是否复位')
    ctx=setup()
    run('drive_flags',ctx,lambda:[field._h_drive_position_shift(EffectTag(E.DRIVE_POSITION_SHIFT),ctx),field._h_drive_on_position_change(EffectTag(E.DRIVE_ON_POSITION_CHANGE),ctx)],'extra_drives/drive_on_position_change_reduce应有消费者；全core搜索仅写入，无移位循环')
    ctx=setup()
    ctx.state.team_a += [pokemon('队友1'),pokemon('队友2')]
    field._h_share_gains(EffectTag(E.SHARE_GAINS),ctx)
    ctx.user.current_hp+=100
    run('share_gains_consumer',ctx,lambda:_apply_share_gains(ctx.state,'a',500,5),'共100生命应随机分配给场下；实际每人均获得100，共200')
    for func,enum in [(field._h_cute_gain,E.CUTE_GAIN),(field._h_cute_enemy_gain,E.CUTE_ENEMY_GAIN),(field._h_cute_both,E.CUTE_BOTH),(field._h_cute_if_power_bonus,E.CUTE_IF_POWER_BONUS),(field._h_cute_on_gain_cost_reduce,E.CUTE_ON_GAIN_COST_REDUCE),(field._h_cute_hit_per_stack,E.CUTE_HIT_PER_STACK),(field._h_cute_bench_cost_reduce,E.CUTE_BENCH_COST_REDUCE)]:
        for applied in [False,True]:
            ctx=setup()
            if applied:
                ctx.user.cute_stacks=1
                ctx.state.team_a.append(pokemon('场下'))
                ctx.state.team_a[-1].cute_stacks=2
            elif func in [field._h_cute_gain,field._h_cute_enemy_gain,field._h_cute_both,field._h_cute_on_gain_cost_reduce]:
                ctx.user.devolution_forms=[]
                ctx.target.devolution_forms=[]
            run(func.__name__+'_'+str(applied),ctx,lambda:func(EffectTag(enum),ctx),'核对有/无萌化或可退化条件；逐函数对应正反分支')
    for func,enum in [(field._h_cute_on_gain_power_perm,E.CUTE_ON_GAIN_POWER_PERM),(field._h_cute_on_gain_speed_perm,E.CUTE_ON_GAIN_SPEED_PERM)]:
        ctx=setup()
        ctx.user.devolution_forms=[]
        run(func.__name__+'_no_gain',ctx,lambda:func(EffectTag(enum),ctx),'无实际增加萌化，不得获得永久修正')
    ctx=setup()
    run('cute_transfer_zero',ctx,lambda:field._h_cute_transfer(EffectTag(E.CUTE_TRANSFER),ctx),'无萌化不转移')
    ctx=setup()
    run('cute_team_power_zero',ctx,lambda:field._h_cute_team_power(EffectTag(E.CUTE_TEAM_POWER),ctx),'全场无萌化，不增加连击')
    ctx=setup()
    ctx.result['damage']=100
    run('cute_lethal_nonlethal',ctx,lambda:field._h_cute_lethal_shield(EffectTag(E.CUTE_LETHAL_SHIELD),ctx),'非致命攻击不触发')
    for enum,func in [(E.CHARGE_COST_REDUCE,field._h_charge_cost_reduce),(E.CHARGE_FREE_SKILL,field._h_charge_free_skill),(E.DRIVE_ON_POSITION_CHANGE,field._h_drive_on_position_change)]:
        ctx=setup()
        run(func.__name__,ctx,lambda:func(EffectTag(enum),ctx),'标记值与默认参数一致，实际消费见独立case及rg证据')
    ctx=setup()
    run('drive_slot_outside',ctx,lambda:field._h_drive_position_shift(EffectTag(E.DRIVE_POSITION_SHIFT,{'slot':2}),ctx),'当前无该槽位时不修改技能')
    ctx=setup()
    run('devotion_explicit_normal',ctx,lambda:field._h_devotion_grant(EffectTag(E.DEVOTION_GRANT,{'type':'假寐'}),ctx),'A假寐+1；B不变；非随机计数不变')
    ctx=setup()
    ctx.state.team_a += [pokemon('场下1'),pokemon('场下2')]
    ctx.user.ability_state['share_gains']=True
    ctx.user.skills[0].power=0
    ctx.user.skills[0].category=SkillCategory.STATUS
    ctx.user.skills[0].effects=[SE(SkillTiming.ON_USE,EffectTag(E.HEAL_HP,{'pct':0.1}))]
    run('share_gains_full_turn',ctx,lambda:execute_full_turn(ctx.state,(0,),(-1,)),'A回复100生命，场下总额应只分配100；实际helper分配100加回合消费者每只100，总300')
    (OUT/'probe_output.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'cases':len(RESULTS),'exceptions':[{'case':x['case'],'exception':x['exception']} for x in RESULTS if 'exception' in x]},ensure_ascii=False))

if __name__=='__main__':
    main()
