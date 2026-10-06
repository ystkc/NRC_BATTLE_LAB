import unittest

from nrc_core.battle import DamageCalculator
from nrc_core.models import Pokemon, Skill, SkillCategory, Type, get_type_effectiveness
from nrc_core.pokemon_db import calc_combat_stats
from nrc_core.skill_db import get_skill


class NumericRulesTests(unittest.TestCase):
    def test_dual_type_effectiveness_matches_data_rule(self):
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.GRASS, Type.ICE]), 3.0)
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.GRASS, Type.WATER]), 1.0)
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.FIRE, Type.WATER]), 0.5)
        self.assertEqual(get_type_effectiveness(Type.FIRE, [Type.FIRE, Type.FIRE]), 1.0)
        self.assertEqual(get_type_effectiveness(Type.GHOST, Type.DARK), 0.5)

    def test_skill_description_supplies_multihit_count(self):
        self.assertEqual(get_skill("连续爪击").hit_count, 2)
        self.assertEqual(get_skill("反击拳").hit_count, 2)

    def test_transformed_paint_counts_stat_buff_layers(self):
        attacker = Pokemon("attacker", Type.NORMAL, 100, 100, 100, 100, 100, 100)
        defender = Pokemon("defender", Type.DARK, 100, 100, 100, 100, 100, 100)
        defender.atk_up = 1.0
        attacker.ability_state["enemy_tech_total_power"] = {"bonus_pct_per_layer": 0.1}
        skill = Skill("test", Type.NORMAL, SkillCategory.PHYSICAL, 30, 1)

        DamageCalculator.calculate(attacker, defender, skill)

        details = attacker.ability_state["_last_damage_details"]
        self.assertEqual(details["enemy_positive_buff_layers"], 10)
        self.assertEqual(details["ability_power_multiplier"], 2.0)

    def test_transformed_paint_counts_lifesteal_buff_layers(self):
        attacker = Pokemon("attacker", Type.NORMAL, 100, 100, 100, 100, 100, 100)
        defender = Pokemon("defender", Type.DARK, 100, 100, 100, 100, 100, 100)
        defender.atk_up = 1.0
        defender.life_drain_mod = 1.0
        attacker.ability_state["enemy_tech_total_power"] = {"bonus_pct_per_layer": 0.1}
        skill = Skill("test", Type.NORMAL, SkillCategory.PHYSICAL, 30, 1)

        DamageCalculator.calculate(attacker, defender, skill)

        details = attacker.ability_state["_last_damage_details"]
        self.assertEqual(details["enemy_positive_buff_layers"], 20)
        self.assertEqual(details["ability_power_multiplier"], 3.0)

    def test_manual_damage_values_use_display_power_without_combo(self):
        attack_stats = calc_combat_stats(0, 147, 0, 0, 0, 0, {
            "hp": 0, "atk": 40, "spatk": 0, "def": 0, "spdef": 0, "speed": 0,
        }, "坦率")
        defense_stats = calc_combat_stats(0, 0, 0, 128, 0, 0, {
            "hp": 0, "atk": 0, "spatk": 0, "def": 50, "spdef": 0, "speed": 0,
        }, "坦率")
        self.assertEqual(attack_stats["atk"], 244)
        self.assertEqual(defense_stats["def"], 264)

        attacker = Pokemon("attacker", Type.NORMAL, 100, 244, 100, 100, 100, 100,
                            pokemon_types=[Type.NORMAL, Type.FIGHTING])
        defender = Pokemon(
            "defender", Type.DARK, 100, 100, 264, 100, 100, 100,
            pokemon_types=[Type.DARK],
        )
        defender.atk_up = 1.0
        defender.life_drain_mod = 1.0
        attacker.ability_state["enemy_tech_total_power"] = {"bonus_pct_per_layer": 0.1}
        skill = Skill("反击拳", Type.FIGHTING, SkillCategory.PHYSICAL, 25, 2, hit_count=2)

        DamageCalculator.calculate(attacker, defender, skill)

        details = attacker.ability_state["_last_damage_details"]
        self.assertEqual(details["enemy_positive_buff_layers"], 20)
        self.assertEqual(details["effective_power"], 187.5)
        self.assertEqual(details["type_multiplier"], 2.0)
        self.assertEqual(details["path"]["damage_per_hit"], 156)
        self.assertEqual(details["damage"], 312)

    def test_damage_formula_uses_pvp_stab_and_37_over_41(self):
        attacker = Pokemon("attacker", Type.FIRE, 100, 100, 100, 100, 100, 100)
        defender = Pokemon("defender", Type.GRASS, 100, 100, 100, 100, 100, 100)
        skill = Skill("test", Type.FIRE, SkillCategory.PHYSICAL, 100, 1)
        self.assertEqual(DamageCalculator.calculate(attacker, defender, skill), 225)
        details = attacker.ability_state["_last_damage_details"]
        self.assertEqual(details["formula"], "floor(floor(raw_damage + 0.5) / defense_used) * hits")
        self.assertEqual(details["formula_inputs"]["constant"], "37/41")
        self.assertEqual(details["path"]["category"], SkillCategory.PHYSICAL.value)
        self.assertEqual(details["post_processing"] if "post_processing" in details else None, None)

    def test_pvp_stat_formula_applies_intermediate_rounding_and_nature(self):
        stats = calc_combat_stats(100, 100, 100, 100, 100, 100, {
            "hp": 0, "atk": 0, "spatk": 0, "def": 0, "spdef": 0, "speed": 0,
        }, "坦率")
        self.assertEqual(stats, {"hp": 316, "atk": 170, "spatk": 170, "def": 194, "spdef": 170, "speed": 170})

    def test_damage_debug_uses_matching_defense_modifier_for_each_category(self):
        attacker = Pokemon("attacker", Type.FIRE, 100, 100, 100, 200, 200, 100)
        defender = Pokemon("defender", Type.GRASS, 100, 100, 200, 100, 200, 100)
        defender.def_down = 0.9
        defender.spdef_down = 0.2
        skill = Skill("magic", Type.FIRE, SkillCategory.MAGICAL, 100, 1)
        DamageCalculator.calculate(attacker, defender, skill)
        details = attacker.ability_state["_last_damage_details"]
        self.assertEqual(details["path"]["base_defense"], 200)
        self.assertEqual(details["path"]["defense_modifier_down"], 0.2)


if __name__ == "__main__":
    unittest.main()
