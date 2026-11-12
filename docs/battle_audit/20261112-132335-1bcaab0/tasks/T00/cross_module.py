"""独立补核四项终局指标及初始/终局边界，不裁决全平规则。"""

import json
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from nrc_core.core import simulate_turn
from nrc_core.battle import check_winner, DamageCalculator, _apply_enemy_damage_reduction, _apply_ability_damage_reduction
from nrc_core.debug import configure_core_logging
from nrc_core.models import BattleState, Pokemon, Type, Skill, SkillCategory
from nrc_core.effect_models import AbilityEffect, EffectTag, Timing, E


def pokemon(name, current_hp=1000, energy=10):
    """显式六维保持固定，避免用待审计公式构造预期。"""
    result = Pokemon(name, Type.NORMAL, 1000, 100, 100, 100, 100, 100)
    result.current_hp = current_hp
    result.energy = energy
    return result


def metrics(state):
    """按原文四指标直接统计，不调用终局计算产生期望。"""
    result = {}
    for side in ("a", "b"):
        team = getattr(state, f"team_{side}")
        alive = [member for member in team if member.current_hp > 0]
        result[side] = {"mp": getattr(state, f"mp_{side}"), "alive": len(alive), "hp": sum(member.current_hp for member in team), "energy": sum(member.energy for member in team)}
    return result


def main():
    """逐个低优先级指标固定高优先级为平局。"""
    configure_core_logging("")
    outputs = []
    states = {
        "mp": BattleState([pokemon("A")], [pokemon("B")], turn=50, mp_a=4, mp_b=3),
        "alive": BattleState([pokemon("A"), pokemon("A2")], [pokemon("B")], turn=50, mp_a=3, mp_b=3),
        "hp": BattleState([pokemon("A", 900)], [pokemon("B", 800)], turn=50, mp_a=3, mp_b=3),
        "energy": BattleState([pokemon("A", energy=5)], [pokemon("B", energy=0)], turn=50, mp_a=3, mp_b=3),
        "all_equal": BattleState([pokemon("A")], [pokemon("B")], turn=50, mp_a=3, mp_b=3),
    }
    for name, state in states.items():
        result = simulate_turn(state, (-1,), (-1,), seed=51)
        actual_metrics = metrics(result.state)
        expected = None if name == "all_equal" else "a"
        outputs.append({"case": name, "before": metrics(state), "after": actual_metrics, "expected": expected, "expectation_status": "规则存疑：四项全平不得猜结果" if expected is None else "README四指标依次比较，高优先级均平局时本项A较高", "actual_winner": result.winner, "next_turn": result.state.turn, "match": None if expected is None else result.winner == expected})
    both_zero = BattleState([pokemon("A")], [pokemon("B")], mp_a=0, mp_b=0)
    both_down = BattleState([pokemon("A", 0)], [pokemon("B", 0)])
    out = {"rule_basis": "data/README.md:35-43", "turn50": outputs, "simultaneous_unknown": [{"case": "both_mp_zero", "actual": check_winner(both_zero), "expected": "需用户裁决，不设预期"}, {"case": "both_teams_down", "actual": check_winner(both_down), "expected": "需用户裁决，不设预期"}], "deduplication": "四个确定反例均属于T04-I03；全平及同时终局归T00-Q01。"}
    reductions = []
    for power, hits, attack in ((10, 3, 100), (1, 1, 1)):
        a, b = pokemon("A"), pokemon("B")
        for member in (a, b):
            member.pokemon_type = Type.FIRE
            member.pokemon_types = [Type.FIRE]
        a.attack = attack
        move = Skill("审计多重减伤", Type.NORMAL, SkillCategory.PHYSICAL, power, 0, hit_count=hits, effects=[EffectTag(E.DAMAGE)])
        guard = Skill("审计防御", Type.NORMAL, SkillCategory.DEFENSE, 0, 0, damage_reduction=0.8)
        b.ability_effects = [AbilityEffect(Timing.ON_TAKE_HIT, [EffectTag(E.DAMAGE_REDUCTION, {"pct": 0.5})])]
        state = BattleState([a], [b])
        raw = DamageCalculator.calculate(a, b, move)
        after_guard = _apply_enemy_damage_reduction(guard, raw)
        actual = _apply_ability_damage_reduction(state, a, b, move, after_guard, "b")
        exact = Fraction(power * attack * 37, 41) * Fraction(1, 5) * Fraction(1, 2)
        rounded = (exact.numerator * 2 + exact.denominator) // (exact.denominator * 2)
        expected = max(rounded // b.defense, 1) * hits
        reductions.append({"input": {"power": power, "attack": attack, "defense": b.defense, "hits": hits, "defense_reduction": "80%", "ability_reduction": "50%", "stab": 1, "effectiveness": 1}, "expected_from_fraction_formula": expected, "actual_base": raw, "after_defense": after_guard, "actual_after_ability": actual, "match": expected == actual})
    out["multiple_reductions"] = {"rule_basis": "data/伤害数值计算.md:7-9,21（减伤连乘后取整且最低1）", "cases": reductions, "deduplication": "与T04-I01同一最终整数后减伤根因，不重复计数。"}
    (HERE / "cross_module_output.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"decisive_cases": 4, "matched": sum(row["match"] is True for row in outputs), "unknown_cases": 3, "business_files_changed": False}))


if __name__ == "__main__":
    main()
