"""T04 最小审计复现：只构造独立内存状态，不修改产品数据。"""
import json
import math
import random
from pathlib import Path
from nrc_core.models import Pokemon, Skill, BattleState, Type, SkillCategory
from nrc_core.effect_models import E, EffectTag, AbilityEffect, Timing
from nrc_core.battle import (
    DamageCalculator, _apply_enemy_damage_reduction, _execute_with_counter,
    _random_disengage, get_mark_damage_modifiers, check_winner, turn_end_effects, _compare_action_order, _apply_moisture_mark,
)
from nrc_core.core import simulate_turn
from nrc_core.rng import rng_scope, choice


def pokemon(name, skills=None, speed=100):
    """使用中性属性与固定六维排除额外机制。"""
    return Pokemon(name, Type.FIRE, 1000, 100, 100, 100, 100, speed, skills=skills or [])


def skill(cost=0, hits=1):
    """创建仅伤害原语的普通系技能。"""
    return Skill('审计攻击', Type.NORMAL, SkillCategory.PHYSICAL, 10, cost,
                 hit_count=hits, effects=[EffectTag(E.DAMAGE)])


def run():
    """汇总实际行为与依据规则独立计算的期望。"""
    out = {}
    a, b = pokemon('A'), pokemon('B')
    sk = skill(hits=3)
    guard = Skill('减伤', Type.NORMAL, SkillCategory.DEFENSE, 0, 0, damage_reduction=.5)
    raw = DamageCalculator.calculate(a, b, sk)
    out['I01_reduction'] = dict(base=raw, actual=_apply_enemy_damage_reduction(guard, raw),
        expected=max(1, math.floor(math.floor(10 * .5 * 100 * 37 / 41 + .5) / 100)) * 3)
    a, b = pokemon('A', [skill(4)]), pokemon('B')
    a.energy = 1
    a.ability_state['hp_for_energy'] = True
    state = BattleState([a], [b])
    _execute_with_counter(state, 'a', (0,), 'b', (-1,), True)
    out['I02_hp_for_energy'] = dict(actual_energy=a.energy, expected_energy=0, hp=a.current_hp, expected_hp=850)
    a, b = pokemon('A'), pokemon('B')
    state = BattleState([a], [b], turn=50, mp_a=4, mp_b=3)
    result = simulate_turn(state, (-1,), (-1,), seed=1)
    out['I03_turn50'] = dict(next_turn=result.state.turn, actual_winner=result.winner, expected_winner='a')
    a, b = pokemon('A'), pokemon('B')
    state = BattleState([a, pokemon('A2'), pokemon('A3')], [b], turn=7)
    a.entry_count = 1
    state.burst_entry_turn_a[a.name] = 7
    with rng_scope(random.Random(1)):
        changed = _random_disengage(state, 'a')
    out['I04_entry_immunity'] = dict(actual_changed=changed, actual_index=state.current_a, expected_changed=False)
    a, b = pokemon('A', [skill()]), pokemon('B')
    a.skills[0].devotion_affected = True
    state = BattleState([a], [b], devotion_a={'飞断': 1})
    powers = []
    for _ in range(2):
        _execute_with_counter(state, 'a', (0,), 'b', (-1,), True)
        powers.append(a.skill_power_bonus)
    out['I05_devotion'] = dict(actual_permanent_bonus=powers, expected_each=20)
    a, b = pokemon('A'), pokemon('B')
    a.freeze_stacks = 1
    a.current_hp = 70
    state = BattleState([a], [b], marks_a={'poison_mark': 1})
    turn_end_effects(state)
    out['I06_freeze_mark'] = dict(actual_hp=a.current_hp, actual_fainted=a.is_fainted, expected_fainted=True)
    a, b = pokemon('A'), pokemon('B')
    state = BattleState([a], [b], turn=2, marks_a={'charge_mark': 1})
    a.ability_state['charge_mark_entry_turn'] = 1
    a.ability_state['_burst_pending'] = True
    out['I07_charge_mark'] = dict(actual_bonus=get_mark_damage_modifiers(state,'a',True,skill())['power_bonus'], expected_bonus=10)
    a, b = pokemon('A'), pokemon('B')
    a.current_hp = 20
    a.poison_stacks = 1
    a.ability_effects = [AbilityEffect(Timing.ON_TURN_END, [EffectTag(E.HEAL_HP, {'pct': .05})])]
    state = BattleState([a], [b])
    turn_end_effects(state)
    out['I08_end_order'] = dict(actual_hp=a.current_hp, actual_fainted=a.is_fainted, expected_fainted=True)
    a, b = pokemon('A', speed=200), pokemon('B', speed=185)
    state = BattleState([a], [b], marks_a={'slow_mark': 1})
    out['I09_slow_mark'] = dict(actual_first=_compare_action_order(state, (-1,), (-1,)), expected_first=-1)
    state = BattleState([pokemon('A',[skill(3)])], [pokemon('B')], marks_a={'dragon_mark': 1})
    _execute_with_counter(state,'a',(0,),'b',(-1,),True)
    out['I10_dragon_mark'] = dict(actual_attack_buff_after_3cost=state.team_a[0].atk_up,
        actual_spattack_buff_after_3cost=state.team_a[0].spatk_up,
        actual_multiplier_for_5cost=get_mark_damage_modifiers(state,'a',True,skill(5))['atk_mult'],
        expected_both_buff_after_3cost=.4, expected_multiplier_for_5cost=1)
    selections = []
    for seed in range(5):
        leave = Skill('移花接木', Type.GRASS, SkillCategory.STATUS, -1, 2, effects=[EffectTag(E.FORCE_SWITCH)])
        state = BattleState([pokemon('A',[leave]),pokemon('A2'),pokemon('A3')],[pokemon('B')])
        with rng_scope(random.Random(seed)):
            _execute_with_counter(state,'a',(0,),'b',(-1,),True)
        selections.append(state.current_a)
    out['I11_ordinary_disengage'] = dict(actual_indices_by_seed=selections, actual_pending=state.pending_switch_requests, expected='暂停等待用户选择其他存活精灵')
    comet = skill()
    comet.name = '彗星'
    comet.effects.append(EffectTag(E.SELF_KO))
    state = BattleState([pokemon('A',[comet],speed=200),pokemon('A2')],[pokemon('B',[skill(2)],speed=100)])
    result = simulate_turn(state,(0,),(0,),seed=1)
    out['I12_midturn_replacement'] = dict(next_turn=result.state.turn,
        pending=result.state.pending_switch_requests, active_a=result.state.current_a,
        b_energy=result.state.team_b[0].energy,
        skill_teams=[item['team'] for item in result.report if item['type']=='skill'],
        expected='待裁决：若自力竭要求立即补位，则须先选A2再恢复B；术语离场排除力竭，不能仅套用普通脱离规则')
    with rng_scope(random.Random(17)):
        first = [choice([0, 1]) for _ in range(20)]
    with rng_scope(random.Random(17)):
        second = [choice([0, 1]) for _ in range(20)]
    out['P01_rng'] = dict(equal=first == second, support=sorted(set(first)))
    a, b = pokemon('A'), pokemon('B')
    out['P02_damage_base'] = dict(actual=DamageCalculator.calculate(a,b,skill()), expected=9)
    out['P03_winner'] = dict(actual=check_winner(BattleState([a],[b],mp_a=0)), expected='b')
    a,bench,b=pokemon('A',[skill(5)]),pokemon('后排',[skill(5)]),pokemon('B')
    state=BattleState([a,bench],[b],marks_a={'moisture_mark':1})
    _apply_moisture_mark(state)
    first=dict(mark=state.marks_a['moisture_mark'],cost_a=a.skills[0].energy_cost,cost_bench=bench.skills[0].energy_cost)
    state.turn+=1
    _apply_moisture_mark(state)
    second=dict(mark=state.marks_a['moisture_mark'],cost_a=a.skills[0].energy_cost)
    state.marks_a.clear()
    a.on_switch_out()
    state.current_a=1
    _apply_moisture_mark(state)
    out['I13_moisture']=dict(after_first=first,after_second=second,after_dispel_and_switch=dict(mark_exists=bool(state.marks_a),cost_new_active=bench.skills[0].energy_cost,cost_old_active=a.skills[0].energy_cost),expected='印记应持续存在并在生效期间全技能耗-1，驱散后失去该修正；原文没有消费或永久写入')
    state=BattleState([pokemon('A'),pokemon('后排')],[pokemon('B')],weather='sandstorm',weather_turns=2)
    turn_end_effects(state)
    out['I14_sandstorm']=dict(actual_hp_a=state.team_a[0].current_hp,actual_hp_bench=state.team_a[1].current_hp,actual_hp_b=state.team_b[0].current_hp,expected_each=1000)
    target = Path(__file__).with_name('repro_output.json')
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
