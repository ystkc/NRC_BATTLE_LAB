import json
import sqlite3

from nrc_core.training import create_backend


def _setup(team_size: int = 1) -> dict:
    connection = sqlite3.connect("data/nrc_wiki.db")
    names = [row[0] for row in connection.execute("SELECT name FROM spirit_forms LIMIT 2")]
    skills = [row[0] for row in connection.execute("SELECT name FROM skill_catalog LIMIT 4")]

    def creature(name: str) -> dict:
        return {
            "name": {"known": True, "exists": True, "value": name},
            "skills": [{"name": {"known": True, "exists": True, "value": skill}} for skill in skills],
        }

    return {
        "own_team": {"active_index": 0, "creatures": [creature(names[0]) for _ in range(team_size)]},
        "opponent_team": {"active_index": 0, "creatures": [creature(names[1]) for _ in range(team_size)]},
        "shared": {"turn": 1, "mp": {"own": 4, "opponent": 4}},
    }


def test_backend_probe_and_snapshot_round_trip():
    backend = create_backend()
    state = backend.new_game(_setup(team_size=2), seed=7)
    assert backend.manifest.environment == "nrc"
    assert backend.decision(state).players == (0, 1)
    snapshot = backend.export_state(state)
    restored = backend.import_state(snapshot)
    assert backend.decision(restored) == backend.decision(state)
    assert backend.observe(restored, 0).data == backend.observe(state, 0).data


def test_single_creature_fainting_reaches_terminal_state():
    backend = create_backend()
    state = backend.new_game(_setup(), seed=11)
    for step in range(32):
        decision = backend.decision(state)
        if decision.terminated:
            break
        actions = {}
        for player in decision.players:
            legal = backend.legal_actions(state, player)
            assert legal
            preferred = next((item.key for item in legal if item.key == "skill:slot=0"), legal[0].key)
            actions[player] = preferred
        state = backend.advance(state, actions, seed=100 + step).state
    assert backend.decision(state).terminated
    assert backend.decision(state).phase == "terminal"
