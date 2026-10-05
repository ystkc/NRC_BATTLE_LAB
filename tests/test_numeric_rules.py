import unittest

from src.battle import DamageCalculator
from src.models import Pokemon, Skill, SkillCategory, Type, get_type_effectiveness
from src.pokemon_db import calc_combat_stats


class NumericRulesTests(unittest.TestCase):
    def test_dual_type_effectiveness_matches_data_rule(self):
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.GRASS, Type.ICE]), 3.0)
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.GRASS, Type.WATER]), 1.0)
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.FIRE, Type.WATER]), 0.5)
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.FIRE, Type.FIRE]), 1.0)

    def test_damage_formula_uses_pvp_stab_and_37_over_41(self):
        attacker = Pokemon("attacker", Type.FIRE, 100, 100, 100, 100, 100, 100)
        defender = Pokemon("defender", Type.GRASS, 100, 100, 100, 100, 100, 100)
        skill = Skill("test", Type.FIRE, SkillCategory.PHYSICAL, 100, 1)
        self.assertEqual(DamageCalculator.calculate(attacker, defender, skill), 225)

    def test_pvp_stat_formula_applies_intermediate_rounding_and_nature(self):
        stats = calc_combat_stats(100, 100, 100, 100, 100, 100, {
            "hp": 0, "atk": 0, "spatk": 0, "def": 0, "spdef": 0, "speed": 0,
        }, "坦率")
        self.assertEqual(stats, {"hp": 316, "atk": 170, "spatk": 170, "def": 194, "spdef": 170, "speed": 170})


if __name__ == "__main__":
    unittest.main()
