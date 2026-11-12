"""T05 运行接口独立输入；只读CSV/内存目录，不修改产品或数据库。"""
import csv
import io
import json
import pickle
import random
import re
from pathlib import Path
from nrc_core.catalog import CoreCatalog
from nrc_core.models import Pokemon, Skill, Type, SkillCategory, BattleState, StatusType
from nrc_core.effect_models import E, EffectTag, AbilityEffect, Timing
from nrc_core.effect_data import SKILL_EFFECTS, ABILITY_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
from nrc_core.runtime import BattleRuntime
from nrc_core.actions import ActionIntent, ItemKind
from nrc_core.debug import configure_core_logging
from nrc_core.codec import battle_request_from_dict
from nrc_core.schema import BattleRequest,TeamInput
from nrc_core.unknown import Maybe
from nrc_core.contracts import action_map, LegalAction

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
configure_core_logging('')


def skill(name='审计',cost=1,power=40):
    """仅伤害效果的完整技能。"""
    return Skill(name,Type.NORMAL,SkillCategory.PHYSICAL,power,cost,effects=[EffectTag(E.DAMAGE)])


def pokemon(name='A',skills=None,speed=100):
    """固定六维并显式提供完整技能。"""
    return Pokemon(name,Type.NORMAL,1000,100,100,100,100,speed,skills=skills or [skill()])


def get_catalog():
    """从CSV与现有硬编码效果重建少量原文对象。"""
    effects={**SKILL_EFFECTS_GENERATED,**SKILL_EFFECTS}
    wanted={'愿力冲击','隐藏条款','补觉','流沙','石锁'}
    skills={}
    with (ROOT/'data/wiki/skills.csv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            values=list(row.values())
            if values[0] not in wanted:
                continue
            name=values[0]
            cat={'物攻':SkillCategory.PHYSICAL,'魔攻':SkillCategory.MAGICAL,'状态':SkillCategory.STATUS,'防御':SkillCategory.DEFENSE}[values[2]]
            sk=Skill(name,Type.NORMAL,cat,int(values[4]),int(values[3]),effects=[e.copy() for e in effects.get(name,[])])
            sk.description=values[5]
            match=re.search(r'选择[:：]?\s*([^。；;]+)',sk.description)
            if match:
                sk.choice_options=tuple(x.strip() for x in re.split('或|/|、',match.group(1)))
            skills[name]=sk
    boss=dict(name='首领',types=['火','龙'],ability='新特性',base_hp=200,base_attack=200,base_magic_attack=200,base_defense=200,base_magic_defense=200,base_speed=200)
    return CoreCatalog(skills=skills,pokemon={'首领':boss},ability_effects={k:tuple(v) for k,v in ABILITY_EFFECTS.items()},boss_forms={'A':(boss,)})


def bloodline(p):
    """平台已经解析出的系别血脉。"""
    p.ability_state['lab_metadata']={'resolved_bloodline_type':Type.FIRE}
    return p


def keys(runtime,state,player=0):
    """只取动作键方便审计输出。"""
    return [x.key for x in runtime.legal_actions(state,player)]


def main():
    """验证限制、还原、补位和只读边界。"""
    out={}; catalog=get_catalog(); runtime=BattleRuntime(catalog=catalog)
    a=bloodline(pokemon(skills=[skill(cost=8)])); a.energy=3
    state=runtime.new_game(BattleState([a],[pokemon('B')],resonance_magic_a='willpower'),seed=7)
    out['I01_willpower_legal']=dict(energy=3,original_cost=8,actual_keys=keys(runtime,state),expected='应能用能耗2愿力首槽，但原技能先按8耗过滤，愿力动作消失')
    state=runtime.new_game(BattleState([bloodline(pokemon(skills=[skill('原首槽'),skill('原二槽')]))],[pokemon('B')],resonance_magic_a='willpower'),seed=7)
    out['I01_unused_willpower']=dict(actual_keys=keys(runtime,state),expected='应允许愿力本回合替换但不使用愿力，详解明确即便未使用下回合也替换回')
    # 真实交换技能可在愿力后将临时首槽移至对方，非假设传动已实现。
    a=bloodline(pokemon(skills=[skill('A原技能')],speed=50))
    b=pokemon('B',[catalog.get_skill('隐藏条款')],speed=200)
    state=runtime.new_game(BattleState([a],[b],resonance_magic_a='willpower'),seed=7)
    changed=runtime.advance(state,{0:'skill:slot=0|resonance=willpower',1:'skill:slot=0'},seed=8).state
    out['I02_restore_swap']=dict(actual_skills_a=[s.name for s in changed.battle.team_a[0].skills],actual_skills_b=[s.name for s in changed.battle.team_b[0].skills],expected_a=['隐藏条款'],expected_b=['A原技能'])
    a=pokemon(); a.ability_state['lab_metadata']={'resolved_boss_bloodline':True}
    state=runtime.new_game(BattleState([a],[pokemon('B')],resonance_magic_a='boss'),seed=7)
    changed=runtime.advance(state,{0:'charge|resonance=boss',1:'charge'},seed=8).state
    boss=changed.battle.team_a[0]
    out['I03_boss_types']=dict(actual_name=boss.name,actual_types=[t.value for t in boss.pokemon_types],expected_types=['fire','dragon'],skills=[s.name for s in boss.skills],expected_skill='审计',hp=boss.hp,attack=boss.attack,bossified=boss.ability_state['lab_metadata'].get('bossified'))
    dead=pokemon('已死'); dead.current_hp=0; dead.status=StatusType.FAINTED; dead.ability_state['faint_processed']=True
    incoming=pokemon('入场即死'); incoming.current_hp=40
    healthy=pokemon('第三只')
    state=runtime.new_game(BattleState([dead,incoming,healthy],[pokemon('B')],mp_a=3,marks_a={'thorn_mark':1}),seed=7)
    changed=runtime.advance(state,{0:'switch:index=1'},seed=8).state
    out['I04_entry_faint_mp']=dict(actual_phase=changed.phase,actual_players=changed.players,actual_fainted=changed.battle.team_a[1].is_fainted,actual_mp=changed.battle.mp_a,expected_mp=2,next_legal=keys(runtime,changed))
    # 真实入场冻结导致对方力竭，并检查双方链式补位的MP。
    freezing=pokemon('抓到你了'); freezing.ability_effects=[x.copy() for x in ABILITY_EFFECTS['抓到你了']]
    b=pokemon('B低血'); b.current_hp=80
    state=runtime.new_game(BattleState([dead,freezing],[b,pokemon('B替补')],mp_a=3),seed=7)
    changed=runtime.advance(state,{0:'switch:index=1'},seed=8).state
    out['I04_enemy_entry_faint_mp']=dict(actual_fainted_b=changed.battle.team_b[0].is_fainted,actual_mp_b=changed.battle.mp_b,expected_mp_b=3,actual_phase=changed.phase,actual_players=changed.players)
    # 盲拧是正式ON_TURN_START随机配置；固定对战seed改变进程random状态。
    random_before=random.getstate(); orders=[]
    for ambient_seed in (1,2,3):
        random.seed(ambient_seed)
        a=pokemon(skills=[skill('一'),skill('二'),skill('三'),skill('四')]); a.ability_effects=[x.copy() for x in ABILITY_EFFECTS['盲拧']]
        state=runtime.new_game(BattleState([a],[pokemon('B')]),seed=77)
        orders.append([s.name for s in state.battle.team_a[0].skills])
    random.setstate(random_before)
    out['I05_seed_new_game']=dict(fixed_seed=77,ambient_seeds=[1,2,3],actual_orders=orders,expected_equal=True)
    # 契约的形状柔软球是替补阶段真实随机ON_ENTER配置。
    random_before=random.getstate(); balls=[]
    for ambient_seed in (1,2,3):
        random.seed(ambient_seed)
        a=pokemon('契约'); a.ability_effects=[x.copy() for x in ABILITY_EFFECTS['契约的形状']]; a.ability_state['gulu_ball']='柔软咕噜球'
        state=runtime.new_game(BattleState([dead,a],[pokemon('B')],mp_a=3),seed=77)
        changed=runtime.advance(state,{0:'switch:index=1'},seed=78).state
        balls.append(changed.battle.team_a[1].ability_state.get('contract_random_ball'))
    random.setstate(random_before)
    out['I05_seed_replacement']=dict(fixed_seed=78,ambient_seeds=[1,2,3],actual_balls=balls,expected_equal=True)
    state=runtime.new_game(BattleState([pokemon('A',[skill('一'),skill('二')]),pokemon('替补')],[pokemon('B')]),seed=7)
    state.battle.team_a[0].ability_state['skill_slot_lock']=[0]
    out['I06_slot_lock']=dict(actual_keys=keys(runtime,state),expected_no_slot1=True)
    a=pokemon('A',[catalog.get_skill('流沙')]); b=pokemon('B',speed=50)
    state=runtime.new_game(BattleState([a],[b,pokemon('B替补')]),seed=7)
    changed=runtime.advance(state,{0:'skill:slot=0',1:'charge'},seed=8).state
    out['I07_ban_switch']=dict(actual_b_keys=keys(runtime,changed,1),actual_b_state=changed.battle.team_b[0].ability_state,expected='流沙施加禁足3回合后应禁止switch，或未实现时显式抛UnsupportedMechanicError')
    choices=[]
    for choice in (0,1):
        a=pokemon('A',[catalog.get_skill('补觉')]); a.current_hp=500; a.energy=3
        state=runtime.new_game(BattleState([a],[pokemon('B')]),seed=7)
        action=f'skill:slot=0:choice={choice}'
        changed=runtime.advance(state,{0:action,1:'charge'},seed=8).state
        choices.append(dict(choice=choice,hp=changed.battle.team_a[0].current_hp,energy=changed.battle.team_a[0].energy,selected=changed.battle.team_a[0].skills[0].selected_choice))
    out['I08_choice']=dict(actual=choices,expected='第0分支恢复25%生命即750HP/能量1；第1分支恢复8能量即500HP/能量9，不能只记录字符串')
    a=pokemon('初始入场'); a.ability_effects=[x.copy() for x in ABILITY_EFFECTS['抓到你了']]
    state=runtime.new_game(BattleState([a],[pokemon('B')]),seed=7)
    out['I09_initial_enter']=dict(actual_enemy_freeze=state.battle.team_b[0].freeze_stacks,actual_enemy_cost=state.battle.team_b[0].skills[0].energy_cost,expected_enemy_freeze=2,expected_enemy_cost=2,actual_entry_count=state.battle.team_a[0].entry_count)
    # 共鸣锁定、使用次数、后台光合持续3次及只读/快照的真实通过证据。
    a=pokemon('A'); a.current_hp=200
    state=runtime.new_game(BattleState([a,pokemon('替补')],[pokemon('B')]),seed=7)
    started=runtime.advance(state,{0:'charge|resonance=solar_heal',1:'charge'},seed=8).state
    values=[started.battle.team_a[0].current_hp]
    switched=runtime.advance(started,{0:'switch:index=1',1:'charge'},seed=9).state; values.append(switched.battle.team_a[0].current_hp)
    ended=runtime.advance(switched,{0:'charge',1:'charge'},seed=10).state; values.append(ended.battle.team_a[0].current_hp)
    fourth=runtime.advance(ended,{0:'charge',1:'charge'},seed=11).state; values.append(fourth.battle.team_a[0].current_hp)
    out['P01_solar']=dict(hp_by_turn=values,expected=[500,650,800,800],remaining=ended.battle.team_a[0].ability_state.get('resonance_solar_heal_remaining'),carried=started.battle.resonance_magic_a,forbidden_other_magic=not any('resonance=willpower' in k or 'resonance=boss' in k for k in keys(runtime,started)),solar_reuse_absent=not any('resonance=solar_heal' in k for k in keys(runtime,started)))
    a=pokemon(); b=pokemon('B'); b.ability_state['mirror_buff_to']=a
    ground=skill(); a.skills=[ground]
    state=runtime.new_game(BattleState([a],[b]),seed=7)
    state.battle.sandstorm_original_costs[id(state.battle.team_a[0].skills[0])]=5
    before=pickle.dumps(state); rng_before=random.getstate()
    runtime.display(state,0); runtime.preview_damage(state,0,0)
    after=pickle.dumps(state)
    imported=runtime.import_state(runtime.export_state(state))
    cloned=runtime.clone(state)
    out['P02_clone_preview_snapshot']=dict(preview_unchanged=before==after,ambient_rng_unchanged=rng_before==random.getstate(),clone_graph_correct=cloned.battle.team_b[0].ability_state['mirror_buff_to'] is cloned.battle.team_a[0],import_graph_correct=imported.battle.team_b[0].ability_state['mirror_buff_to'] is imported.battle.team_a[0],weather_id_correct=id(imported.battle.team_a[0].skills[0]) in imported.battle.sandstorm_original_costs,observations_equal=runtime.observe(state,0).data['decision']==runtime.observe(imported,0).data['decision'])
    req=BattleRequest(TeamInput(),TeamInput()); req.shared.weekend=Maybe.from_value(False)
    out['P03_codec']=dict(roundtrip_false_preserved=battle_request_from_dict(req.to_json()).shared.weekend.value is False,unknown_vs_absent=Maybe.unknown().to_json()!=Maybe.absent().to_json(),action_payload_roundtrip=ActionIntent.skill(slot=0,choice='明').to_json()['choice']=='明')
    bad_keys=[]
    for test in ([LegalAction('x'),LegalAction('x')],[LegalAction('')]):
        try: action_map(test)
        except ValueError: bad_keys.append(True)
    out['P04_contract']=dict(duplicate_and_empty_rejected=bad_keys==[True,True])
    a=bloodline(pokemon()); b=pokemon('B'); b.hp=b.current_hp=10000
    state=runtime.new_game(BattleState([a],[b],resonance_magic_a='willpower'),seed=7)
    after_one=runtime.advance(state,{0:'skill:slot=0|resonance=willpower',1:'charge'},seed=8).state
    one=dict(uses=after_one.battle.resonance_uses_a,cooldown=after_one.battle.resonance_cooldown_a,restored_name=after_one.battle.team_a[0].skills[0].name,can_reuse=any('resonance=willpower' in k for k in keys(runtime,after_one)))
    wait1=runtime.advance(after_one,{0:'charge',1:'charge'},seed=9).state
    wait2=runtime.advance(wait1,{0:'charge',1:'charge'},seed=10).state
    two=runtime.advance(wait2,{0:'skill:slot=0|resonance=willpower',1:'charge'},seed=11).state
    out['P05_willpower_limits']=dict(after_first=one,after_two_wait_cooldown=wait2.battle.resonance_cooldown_a,after_second_uses=two.battle.resonance_uses_a,third_use_absent=not any('resonance=willpower' in k for k in keys(runtime,two)),expected='首次uses1/CD2；等待2整回合后CD0；第二次uses2且无第三次')
    a=pokemon(); a.current_hp=100
    state=runtime.new_game(BattleState([a],[pokemon('B')],resonance_magic_a='solar_heal'),seed=7)
    started=runtime.advance(state,{0:'charge|resonance=solar_heal',1:'charge'},seed=8).state
    started.battle.team_a[0].current_hp=0; started.battle.team_a[0].status=StatusType.FAINTED
    from nrc_core.battle import turn_end_effects
    turn_end_effects(started.battle)
    out['P06_solar_dead']=dict(actual_hp=started.battle.team_a[0].current_hp,remaining=started.battle.team_a[0].ability_state.get('resonance_solar_heal_remaining'),expected_hp=0,expected_remaining=1)
    # 步进后回合开始同样不在seed作用域，采用同一会话副本避免初始差异。
    a=pokemon(skills=[skill('一'),skill('二'),skill('三'),skill('四')]); a.ability_effects=[x.copy() for x in ABILITY_EFFECTS['盲拧']]
    random_before=random.getstate(); random.seed(0)
    state=runtime.new_game(BattleState([a],[pokemon('B')]),seed=77)
    orders=[]
    for ambient_seed in (1,2):
        random.seed(ambient_seed)
        changed=runtime.advance(state,{0:'charge',1:'charge'},seed=78).state
        orders.append([s.name for s in changed.battle.team_a[0].skills])
    random.setstate(random_before)
    out['I05_seed_next_turn']=dict(fixed_seed=78,actual_orders=orders,expected_equal=True)
    import os
    log_stream=io.StringIO(); old_env=os.environ.get('NRC_CORE_LOG')
    os.environ['NRC_CORE_LOG']=''
    categories=configure_core_logging(None,stream=log_stream)
    from nrc_core.debug import core_log
    core_log('damage','audit')
    if old_env is None: os.environ.pop('NRC_CORE_LOG',None)
    else: os.environ['NRC_CORE_LOG']=old_env
    configure_core_logging('')
    out['I10_logging_docs']=dict(env_disabled='',actual_categories=sorted(categories),actual_output=log_stream.getvalue(),expected='README默认无日志，环境变量为空应关闭；实现固定damage')
    (HERE/'probe_output.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':
    main()
