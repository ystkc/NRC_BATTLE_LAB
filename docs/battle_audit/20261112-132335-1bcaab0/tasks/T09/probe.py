"""T09 特性处理器最小输入与实际输出。"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
from nrc_core.effect_models import E, EffectTag, Timing
from nrc_core.effect_data import ABILITY_EFFECTS
from nrc_core.models import Pokemon, Skill, Type, SkillCategory
from nrc_core.models import BattleState
from nrc_core.engine import EffectExecutor, Ctx
from nrc_core.engine import handlers_ability as handlers
from nrc_core.battle import DamageCalculator, turn_end_effects


def setup(ability=''):
    """生成500HP、80威力、2能耗的固定场景。"""
    skill = Skill('审计技能', Type.NORMAL, SkillCategory.PHYSICAL, 80, 2)
    user = Pokemon('甲', Type.NORMAL, 500, 100, 100, 100, 100, 100, ability=ability, skills=[skill])
    enemy = Pokemon('乙', Type.NORMAL, 500, 100, 100, 100, 100, 100, skills=[skill.copy()])
    user.ability_effects = [ae.copy() for ae in ABILITY_EFFECTS.get(ability, [])]
    state = BattleState([user], [enemy])
    return state, user, enemy, skill


def run():
    """仅在有明确疑点时运行核心，不生成镜像实现测试。"""
    output = {}
    for name, primitive in [('non_stab', E.DAMAGE_MOD_NON_STAB), ('non_light', E.DAMAGE_MOD_NON_LIGHT),
                             ('non_weakness', E.DAMAGE_MOD_NON_WEAKNESS), ('resist_same_type', E.DAMAGE_RESIST_SAME_TYPE)]:
        state, user, enemy, skill = setup()
        ctx = Ctx(state, user, enemy, skill)
        try:
            getattr(handlers, {'non_stab': '_h_damage_mod_non_stab', 'non_light': '_h_damage_mod_non_light',
                    'non_weakness': '_h_damage_mod_non_weakness', 'resist_same_type': '_h_damage_resist_same_type'}[name])(EffectTag(primitive), ctx)
            output[name] = {'context': ctx.result}
        except Exception as exc:
            output[name] = {'exception': type(exc).__name__, 'message': str(exc)}
    state, user, enemy, skill = setup('变形活画')
    base = DamageCalculator.calculate(user, enemy, skill)
    enemy.atk_up = 1.0
    EffectExecutor.execute_ability(state, user, enemy, Timing.PASSIVE, user.ability_effects)
    output['paint'] = {'state': user.ability_state.get('enemy_tech_total_power'), 'base_damage': base, 'damage_with_ten_enemy_buff_layers': DamageCalculator.calculate(user, enemy, skill)}
    state, user, enemy, skill = setup('最好的伙伴')
    skill.skill_type = Type.FIRE
    skill.category = SkillCategory.STATUS
    enemy.pokemon_type = Type.GRASS
    enemy.pokemon_types = [Type.GRASS]
    user.energy = 0
    result = EffectExecutor.execute_ability(state, user, enemy, Timing.ON_USE_SKILL, user.ability_effects, context={'skill': skill})
    output['best_partner_status'] = {'energy': user.energy, 'status_stacks': user.compound_statuses['best_partner'].stacks, 'triggered': result['triggered']}
    state, user, enemy, skill = setup('双向光速')
    user.poison_stacks = 1
    turn_end_effects(state)
    first = {'hp': user.current_hp, 'repeat': user.ability_state.get('turn_end_repeat')}
    turn_end_effects(state)
    output['repeat_accumulates'] = {'first': first, 'second': {'hp': user.current_hp, 'repeat': user.ability_state.get('turn_end_repeat')}}
    state, user, enemy, skill = setup('灰色肖像')
    EffectExecutor.execute_ability(state, user, enemy, Timing.ON_ENTER, user.ability_effects)
    from nrc_core.engine.helpers import _apply_debuff
    _apply_debuff(enemy, {'atk': 0.1})
    output['gray_portrait'] = {'marker': enemy.ability_state.get('debuff_stack_bonus'), 'atk_down': enemy.atk_down}
    state, user, enemy, skill = setup('衡量')
    user.energy = 0
    enemy.energy = 10
    enemy.skill_power_bonus = 20
    EffectExecutor.execute_ability(state, user, enemy, Timing.ON_ENTER, user.ability_effects)
    output['balance'] = {'user_energy': user.energy, 'user_power_bonus': user.skill_power_bonus, 'enemy_power_bonus': enemy.skill_power_bonus}
    state, user, enemy, skill = setup('缩壳')
    skill.category = SkillCategory.DEFENSE
    ctx = Ctx(state, user, enemy, skill)
    handlers._h_skill_cost_reduction_type(EffectTag(E.SKILL_COST_REDUCTION_TYPE, {'cost_reduction': 2}), ctx)
    output['defense_enum'] = {'result': ctx.result, 'skill_cost': skill.energy_cost}
    state, user, enemy, skill = setup('破空')
    context = {'skill': skill, 'is_first': True}
    result = EffectExecutor.execute_ability(state, user, enemy, Timing.PASSIVE, user.ability_effects, context=context)
    output['first_strike_context'] = {'power_multiplier': context.get('power_multiplier'), 'damage': DamageCalculator.calculate(user, enemy, skill), 'persistent_flag': user.ability_state.get('first_strike_power_bonus')}
    state, user, enemy, skill = setup()
    ctx = Ctx(state, user, enemy, skill)
    handlers._h_ability_compute(EffectTag(E.ABILITY_COMPUTE, {'action': 'unknown-audit-action'}), ctx)
    output['unknown_compute_action'] = {'raised': False}
    state, user, enemy, skill = setup('圣火骑士')
    EffectExecutor.execute_ability(state, user, enemy, Timing.ON_COUNTER_SUCCESS, user.ability_effects)
    output['double_next'] = {'flag': user.ability_state.get('double_damage_next'), 'damage': DamageCalculator.calculate(user, enemy, skill)}
    from nrc_core.battle import ability_auto_switch
    state, user, enemy, skill = setup('防过载保护')
    user.entry_count = 1
    state.turn = 3
    state.team_a.append(Pokemon('队友', Type.NORMAL, 500, 100, 100, 100, 100, 100))
    EffectExecutor.execute_ability(state, user, enemy, Timing.ON_TURN_END, user.ability_effects)
    output['auto_switch'] = {'auto_switch_eot': user.ability_state.get('auto_switch_eot'), 'switched': ability_auto_switch(state, 'a', 'every_turn'), 'current_index': state.current_a}
    from nrc_core.models import add_freeze_stacks
    state, user, enemy, skill = setup('捉迷藏')
    add_freeze_stacks(enemy, 2, user, state=state, team='a')
    output['freeze_success'] = {'stacks': enemy.freeze_stacks, 'enemy_cost': enemy.skills[0].energy_cost}
    state, user, enemy, skill = setup('双向光速')
    ctx = Ctx(state, user, enemy, skill)
    enemy.hp = 1000
    enemy.burn_stacks = 1
    handlers._h_ability_compute(EffectTag(E.ABILITY_COMPUTE, {'action': 'double_enemy_burn_and_tick'}), ctx)
    output['burn_tick'] = {'burn_stacks': enemy.burn_stacks, 'hp_after': enemy.current_hp, 'hp_before': 500, 'expected_damage_at_2pct': 40}
    for ability, key, primitive in [('电流刺激', 'burst_power_bonus', E.BURST_POWER_BONUS), ('连续负荷', 'burst_extend', E.BURST_EXTEND)]:
        state, user, enemy, skill = setup(ability)
        for _ in range(2):
            EffectExecutor.execute_ability(state, user, enemy, Timing.PASSIVE, user.ability_effects)
        output[ability] = user.ability_state.get(key)
    (OUT / 'probe_output.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
