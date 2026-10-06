import json
import sqlite3

from nrc_ai.belief import Particle, ParticleBelief
from nrc_ai.opponent import UniformOpponentPolicy
from nrc_ai.search import BeliefTreeSearch
from nrc_ai.population_prior import PopulationPrior
from nrc_core.training import create_backend


def _setup(team_size: int = 2) -> dict:
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


def test_real_observation_hides_opponent_private_skills():
    backend = create_backend()
    state = backend.new_game(_setup(), seed=3)
    observation = backend.observe(state, 0).data
    assert observation["own_team"][0]["skills"]
    assert "skills" not in observation["opponent_team"][0]
    assert "ability" not in observation["opponent_team"][0]


def test_real_backend_search_runs_through_replacement_nodes():
    backend = create_backend()
    state = backend.new_game(_setup(), seed=3)
    result = BeliefTreeSearch(backend, UniformOpponentPolicy(), seed=3).plan(
        ParticleBelief([Particle(state)]), simulations=8, horizon=5
    )
    assert result.action_key in {action.key for action in backend.legal_actions(state, 0)}
    assert abs(sum(result.policy.values()) - 1.0) < 1e-9


def test_population_prior_candidates_are_accepted_by_real_backend():
    backend = create_backend()
    prior = PopulationPrior.from_database("data/nrc_wiki.db")
    candidates = prior.candidate_setups(_setup(team_size=1), count=4, seed=21, aptitude_iv=54)
    for index, candidate in enumerate(candidates):
        state = backend.new_game(candidate["setup"], seed=index)
        assert backend.decision(state).players == (0, 1)
