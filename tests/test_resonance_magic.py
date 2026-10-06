import sqlite3
import unittest

from nrc_core.training import create_backend


def _catalog_setup(resonance=None, bloodline=None, metadata=None):
    connection = sqlite3.connect("data/nrc_wiki.db")
    names = [row[0] for row in connection.execute("SELECT name FROM spirit_forms LIMIT 2")]
    skills = [row[0] for row in connection.execute("SELECT name FROM skill_catalog LIMIT 4")]
    connection.close()

    def creature(name):
        value = {
            "name": name,
            "skills": [{"name": skill} for skill in skills],
            "metadata": {"attribute_assumption": "neutral"},
        }
        if bloodline:
            value["base"] = {"bloodline_attributes": [bloodline]}
        if metadata:
            value["metadata"].update(metadata)
        return value

    return {
        "own_team": {
            "active_index": 0,
            "resonance_magic": resonance,
            "creatures": [creature(names[0])],
        },
        "opponent_team": {
            "active_index": 0,
            "creatures": [creature(names[1])],
        },
        "shared": {"turn": 1, "mp": {"own": 4, "opponent": 4}},
    }


class ResonanceMagicTests(unittest.TestCase):
    def test_boss_alias_is_recognized(self):
        backend = create_backend()
        state = backend.new_game(_catalog_setup(None, 'boss'), seed=1)
        self.assertTrue(backend._simulator._is_boss_bloodline(state.battle.team_a[0]))
        self.assertTrue(backend._simulator._is_boss_bloodline(state.battle.team_a[0]))

    def test_willpower_replaces_first_skill_and_enters_cooldown(self):
        backend = create_backend()
        state = backend.new_game(_catalog_setup("willpower", "火血脉"), seed=1)
        resonance_action = next(
            action.key for action in backend.legal_actions(state, 0)
            if action.key.endswith("|resonance=willpower")
        )
        opponent_action = backend.legal_actions(state, 1)[0].key
        transition = backend.advance(state, {0: resonance_action, 1: opponent_action}, seed=2)

        self.assertEqual(transition.state.battle.resonance_uses_a, 1)
        self.assertEqual(transition.state.battle.resonance_cooldown_a, 2)
        self.assertNotEqual(transition.state.battle.team_a[0].skills[0].name, "愿力冲击")
        self.assertTrue(any(event.get("skill") == "愿力冲击" for event in transition.events))

    def test_solar_heal_has_three_end_turn_ticks(self):
        backend = create_backend()
        state = backend.new_game(_catalog_setup("solar_heal"), seed=1)
        state.battle.team_a[0].current_hp = 1000
        action = next(
            item.key for item in backend.legal_actions(state, 0)
            if item.key.endswith("|resonance=solar_heal")
        )
        opponent_action = backend.legal_actions(state, 1)[0].key
        transition = backend.advance(state, {0: action, 1: opponent_action}, seed=2)

        self.assertTrue(transition.state.battle.resonance_solar_heal_used_a)
        self.assertEqual(transition.state.battle.team_a[0].ability_state["resonance_solar_heal_remaining"], 2)

    def test_boss_resonance_is_once_per_battle(self):
        connection = sqlite3.connect("data/nrc_wiki.db")
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT s.name AS normal, l.name AS boss
            FROM spirit_forms s
            JOIN spirit_forms l
              ON s.catalog_number = l.catalog_number AND l.is_lord = 1
            WHERE s.is_lord = 0
            GROUP BY s.name
            HAVING count(l.id) = 1
            LIMIT 1
            """
        ).fetchone()
        connection.close()
        self.assertIsNotNone(row)
        backend = create_backend()
        setup = _catalog_setup("boss", "首领血脉", {"boss_form": row["boss"]})
        setup["own_team"]["creatures"][0]["name"] = row["normal"]
        state = backend.new_game(setup, seed=1)
        action = next(
            item.key for item in backend.legal_actions(state, 0)
            if item.key.endswith("|resonance=boss")
        )
        opponent_action = backend.legal_actions(state, 1)[0].key
        transition = backend.advance(state, {0: action, 1: opponent_action}, seed=2)

        self.assertTrue(transition.state.battle.resonance_evolution_used_a)
        self.assertFalse(any(item.key.endswith("|resonance=boss") for item in backend.legal_actions(transition.state, 0)))


if __name__ == "__main__":
    unittest.main()
