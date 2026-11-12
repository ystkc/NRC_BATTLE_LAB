"""只读运行配置探针及内存重生成比对，不改业务文件。"""
from extract import ROOT, OUT, plain
import copy
import json
import re
import sqlite3
from nrc_core.models import Pokemon, BattleState, Skill, Type, SkillCategory
from nrc_core.effect_data import SKILL_EFFECTS, ABILITY_EFFECTS
from nrc_core.skill_effects_generated import SKILL_EFFECTS_GENERATED
from nrc_core.engine import EffectExecutor
from nrc_core.effect_models import Timing
from nrc_core.debug import configure_core_logging
from scripts import generate_skill_effects as gen

def pokemon(name):
    """构造不带其他机制的定值精灵。"""
    return Pokemon(name, Type.NORMAL, 1000, 100, 100, 100, 100, 100, current_hp=500, energy=3)

def snapshot(p):
    """记录可核对的状态。"""
    fields = ['current_hp', 'energy', 'atk_up', 'def_up', 'spatk_up', 'spdef_up', 'speed_up', 'atk_down', 'spatk_down', 'def_down', 'spdef_down', 'speed_down', 'poison_stacks', 'burn_stacks', 'freeze_stacks', 'leech_stacks', 'skill_power_bonus', 'skill_power_pct_mod', 'skill_cost_mod', 'hit_count_mod']
    return {**{k: getattr(p, k) for k in fields}, 'compound_statuses': {k: {'name':v.name, 'stacks':v.stacks, 'modifiers':v.modifiers} for k,v in p.compound_statuses.items()}}

def main():
    """运行每项技能的中性场景，并记录手写参数反例。"""
    configure_core_logging('')
    conn = sqlite3.connect((ROOT / 'data/nrc_wiki.db').as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT s.*, e.name AS element FROM skill_catalog s LEFT JOIN elements e ON e.id=s.element_id').fetchall()
    merged = {**SKILL_EFFECTS_GENERATED, **SKILL_EFFECTS}
    results = []
    for row in rows:
        a, b = pokemon('A'), pokemon('B')
        skill = Skill(row['name'], gen._TYPE_MAP.get(row['element'], Type.NORMAL), gen._CAT_MAP.get(row['category'], SkillCategory.STATUS), power=row['power'] or 0, energy_cost=row['energy_cost'] or 0)
        skill.description = row['description'] or ''
        hit = re.search(r'(\d+)连击', skill.description)
        skill.hit_count = int(hit.group(1)) if hit else 1
        skill.effects = copy.deepcopy(merged.get(skill.name, []))
        a.skills = [skill]
        state = BattleState([a], [b])
        result = {'name': skill.name, 'input': {'user_hp':500, 'target_hp':500, 'energy':3, 'power':skill.power, 'cost':skill.energy_cost, 'effects':plain(skill.effects)}}
        try:
            got = EffectExecutor.execute_skill(state, a, b, skill, skill.effects, is_first=True)
            result['output'] = {'damage':got.get('damage'), 'counter_effects':plain(got.get('counter_effects', [])), 'user':snapshot(a), 'target':snapshot(b)}
        except Exception as exc:
            result['exception'] = type(exc).__name__ + ': ' + str(exc)
        results.append(result)
    (OUT / 'skill_probe.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    ability_results = []
    for name, timing in [('图书守卫者', Timing.ON_ENTER), ('构装契约者', Timing.ON_ENTER), ('毒腺', Timing.ON_USE_SKILL), ('毒牙', Timing.ON_USE_SKILL), ('蓄电池', Timing.ON_ENTER), ('超级电池', Timing.ON_ENTER), ('鼓气', Timing.ON_USE_SKILL), ('三鼓作气', Timing.ON_USE_SKILL), ('腐植循环', Timing.ON_TURN_END), ('大捞一笔', Timing.ON_ENTER), ('小偷小摸', Timing.ON_ENTER), ('自由飘', Timing.PASSIVE)]:
        a, b = pokemon('A'), pokemon('B')
        a.ability = name
        b.poison_stacks = 1
        a.ability_effects = copy.deepcopy(ABILITY_EFFECTS.get(name, []))
        skill = Skill('探针', Type.NORMAL, SkillCategory.PHYSICAL, power=40, energy_cost=3)
        a.skills = [skill]
        state = BattleState([a], [b], mp_a=1, mp_b=1)
        before = {'user':snapshot(a), 'target':snapshot(b)}
        try:
            got = EffectExecutor.execute_ability(state, a, b, timing, a.ability_effects, team='a', context={'skill':skill})
            ability_results.append({'name':name, 'timing':timing.name, 'input':before, 'output':{'user':snapshot(a), 'target':snapshot(b)}})
        except Exception as exc:
            ability_results.append({'name':name, 'exception':repr(exc)})
    (OUT / 'ability_probe.json').write_text(json.dumps(ability_results, ensure_ascii=False, indent=2), encoding='utf-8')
    mapping, stats = gen.generate_mapping(rows)
    regenerated = gen.render_generated_file(mapping)
    namespace = {}
    exec(compile(regenerated, '<audit regenerated>', 'exec'), namespace)
    new = namespace['SKILL_EFFECTS_GENERATED']
    diffs = [{'name':n, 'old':plain(SKILL_EFFECTS_GENERATED.get(n)), 'new':plain(new.get(n))} for n in sorted(set(new) | set(SKILL_EFFECTS_GENERATED)) if plain(new.get(n)) != plain(SKILL_EFFECTS_GENERATED.get(n))]
    (OUT / 'regeneration_diff.json').write_text(json.dumps({'stats':plain(stats), 'differences':diffs}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'skill_count':len(results), 'skill_exceptions':sum('exception' in r for r in results), 'ability_exceptions':sum('exception' in r for r in ability_results), 'regeneration_differences':len(diffs)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
