"""T07 审计最小复现与注册表证据；不修改业务文件。"""
import ast
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from nrc_core.effect_models import E, Timing, SkillTiming, EffectTag, SkillEffect, AbilityEffect
from nrc_core.models import Pokemon, Skill, Type, SkillCategory, BattleState
from nrc_core.engine import EffectExecutor, Ctx, _apply_tag, _HANDLERS, _ABILITY_HANDLER_OVERRIDES
from nrc_core.engine.helpers import _apply_matching_skill_mods, _promise_modifiers, _apply_prince_promise, _apply_ability_buff
from nrc_core.engine.filters import _check_skill_filter

OUT = Path(__file__).resolve().parent


def setup(effects=None, agility=False):
    """构造无随机分支的两只精灵与一项技能。"""
    skill = Skill('审计攻击', Type.NORMAL, SkillCategory.PHYSICAL, 80, 2, agility=agility, effects=effects or [])
    user = Pokemon('甲', Type.NORMAL, 500, 100, 100, 100, 100, 100, skills=[skill])
    enemy = Pokemon('乙', Type.NORMAL, 500, 100, 100, 100, 100, 100)
    return BattleState([user], [enemy]), user, enemy, skill


def run():
    """记录实际输出，不把静态推测伪装成已运行场景。"""
    results = {}
    state, user, enemy, skill = setup()
    _apply_tag(EffectTag('unregistered-audit-effect'), Ctx(state, user, enemy, skill))
    results['unknown_effect'] = {'raised': False, 'expected': 'UnsupportedMechanicError'}
    effects = [SkillEffect(SkillTiming.ON_USE, [EffectTag(E.AGILITY), EffectTag(E.DAMAGE)])]
    state, user, enemy, skill = setup(effects)
    expected = EffectExecutor.execute_skill(state, user, enemy, skill, effects, is_first=True)['damage']
    before = enemy.current_hp
    EffectExecutor.execute_agility_entry(state, user, enemy)
    results['agility_damage'] = {'computed_damage': expected, 'target_hp_before': before, 'target_hp_after': enemy.current_hp, 'energy_after': user.energy}
    state, user, enemy, skill = setup([SkillEffect(SkillTiming.ON_USE, [EffectTag(E.DAMAGE)])])
    _apply_matching_skill_mods(user, enemy, {'grant_agility': True, 'energy_cost_lt': 3})
    EffectExecutor.execute_agility_entry(state, user, enemy)
    results['granted_agility'] = {'agility': skill.agility, 'energy_after': user.energy, 'target_hp_after': enemy.current_hp}
    state, user, enemy, skill = setup()
    tag = EffectTag(E.PASSIVE_ENERGY_REDUCE, {'reduce': 2, 'range': 'all'})
    counter = SkillEffect(SkillTiming.ON_COUNTER, [tag], {'category': 'attack'})
    EffectExecutor.execute_counter(state, user, enemy, skill, counter, skill, 100)
    results['counter_public'] = {'cost': skill.energy_cost, 'public': user.ability_state.get('public_skill_modifiers'), 'private_deltas': user.ability_state.get('_public_skill_modifier_deltas')}
    state, user, enemy, skill = setup()
    _apply_tag(tag, Ctx(state, user, enemy, skill), ability_mode=True)
    results['ability_public_control'] = {'cost': skill.energy_cost, 'public': user.ability_state.get('public_skill_modifiers')}
    for timing in (SkillTiming.ON_USE, SkillTiming.POST_USE):
        state, user, enemy, skill = setup()
        se = SkillEffect(timing, [EffectTag(E.HEAL_ENERGY, {'amount': 1})], {'self_hp_lt': 0.5})
        user.energy = 0
        EffectExecutor.execute_skill(state, user, enemy, skill, [se])
        results['filter_' + timing.name] = {'full_hp': user.current_hp, 'energy_after': user.energy}
    state, user, enemy, skill = setup()
    results['category_filter'] = _check_skill_filter({'category': 'attack', 'self_hp_lt': 0.5}, Ctx(state, user, enemy, skill))
    params = {'power_pct': 0.4, 'element': ['普通']}
    _apply_matching_skill_mods(user, enemy, params)
    first = skill.power
    _apply_matching_skill_mods(user, enemy, params)
    results['matching_repeat'] = {'base': 80, 'first': first, 'second': skill.power}
    original = EffectTag(E.SELF_BUFF, {'buff': {'atk': 0.2}})
    copied = original.copy()
    copied.params['buff']['atk'] = 0.9
    results['copy_nested'] = {'original_after_mutating_copy': original.params}
    user.ability = '王子的诺言'
    before = _promise_modifiers(user)
    _apply_ability_buff(user, {'atk': 0.2})
    _apply_prince_promise(user, before, 1)
    results['promise_compound'] = {'cost': skill.energy_cost, 'compound_statuses': list(user.compound_statuses)}
    state, user, enemy, skill = setup()
    other = Skill('后位', Type.NORMAL, SkillCategory.STATUS, -1, 2)
    user.skills.append(other)
    EffectExecutor.execute_drive(state, user, enemy, skill, 1)
    results['drive_position'] = {'after': [s.name for s in user.skills], 'expected_after_one_shift': ['后位', '审计攻击']}
    state, user, enemy, skill = setup(agility=True)
    user.skills.append(Skill('第二迅捷', Type.NORMAL, SkillCategory.STATUS, -1, 2, agility=True))
    EffectExecutor.execute_agility_entry(state, user, enemy)
    results['legacy_agility_first'] = {'energy_after': user.energy, 'expected': 8}
    from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
    from nrc_core.effect_data import SKILL_EFFECTS
    state, user, enemy, skill = setup()
    user.current_hp = 100
    EffectExecutor.execute_skill(state, user, enemy, skill, SKILL_EFFECTS_GENERATED['极限撕裂'])
    results['live_post_filter'] = {'hp_ratio': 0.2, 'atk_up_after': user.atk_up, 'spatk_up_after': user.spatk_up}
    state, user, enemy, skill = setup()
    try:
        EffectExecutor.execute_skill(state, user, enemy, skill, SKILL_EFFECTS_GENERATED['架势'])
    except Exception as exc:
        results['nested_skill_effect'] = {'exception': type(exc).__name__, 'message': str(exc)}
    results['nested_skill_effect_configs'] = [name for name, effects in {**SKILL_EFFECTS_GENERATED, **SKILL_EFFECTS}.items()
        if any(isinstance(tag, SkillEffect) for se in effects if isinstance(se, SkillEffect) for tag in se.effects)]
    registry_tree = ast.parse((ROOT / 'nrc_core/engine/registry.py').read_text(encoding='utf-8'))
    registries = {}
    for node in ast.walk(registry_tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
            keys = [ast.unparse(key) for key in node.value.keys]
            registries[node.target.id] = {'count': len(keys), 'duplicates': sorted({key for key in keys if keys.count(key) > 1})}
    results['registry'] = registries
    results['unregistered_enum'] = [item.name for item in E if item not in _HANDLERS]
    results['timing_references'] = {}
    code = [(str(path.relative_to(ROOT)), path.read_text(encoding='utf-8')) for path in (ROOT / 'nrc_core').rglob('*.py')]
    for item in Timing:
        results['timing_references'][item.name] = [name for name, source in code if 'Timing.' + item.name in source and name != 'nrc_core\\effect_models.py']
    (OUT / 'probe_output.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
