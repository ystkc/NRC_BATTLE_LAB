import json

from nrc_ai.belief import Particle, ParticleBelief, ParticleFilter
from nrc_ai.encoding import JsonObservationEncoder
from nrc_ai.model import RecurrentPolicyValue
from nrc_ai.opponent import EmpiricalOpponentPolicy
from nrc_ai.replay import Episode, ReplayBuffer, StepRecord
from nrc_ai.rollout import RootActionEvaluator
from nrc_ai.selfplay import generate_episode
from nrc_ai.toy_backend import ToyBackend
from nrc_ai.training import train_policy_value
from nrc_ai.search import BeliefTreeSearch
from nrc_ai.online import OnlineBeliefAgent, OnlineBeliefUpdater, observation_likelihood


def test_toy_backend_is_simultaneous_and_observation_hides_style():
    backend = ToyBackend()
    state = backend.new_game({"styles": ("aggressive", "defensive")}, 0)
    assert backend.decision(state).players == (0, 1)
    assert "style" not in backend.observe(state, 0).data["opponent"]
    transition = backend.advance(state, {0: "attack", 1: "guard"}, 1)
    assert transition.rewards == {0: 0.0, 1: 0.0}
    assert state.turn == 1


def test_root_rollout_returns_all_legal_actions():
    backend = ToyBackend()
    state = backend.new_game({}, 0)
    belief = ParticleBelief([Particle(state)])
    estimates = RootActionEvaluator(backend, EmpiricalOpponentPolicy(), seed=3).evaluate(belief, simulations_per_action=4, horizon=3)
    assert {estimate.action_key for estimate in estimates} == {"attack", "guard", "charge"}


def test_particle_filter_updates_and_normalizes():
    belief = ParticleBelief([Particle("a"), Particle("b")])
    updated = ParticleFilter(resample_threshold=0.01).update(belief, "seen-a", lambda state, observation: 1.0 if state == "a" else 0.0)
    assert updated.particles[0].weight == 1.0
    assert updated.particles[1].weight == 0.0


def test_replay_jsonl_round_trip(tmp_path):
    episode = Episode("episode-1", {"rules_version": "toy"})
    episode.append(StepRecord(0, 1, "turn_choice", {"own": {"hp": 5}}, ("attack",), "attack", 1.0, True, 0))
    path = tmp_path / "replay.jsonl"
    ReplayBuffer([episode]).save_jsonl(path)
    loaded = ReplayBuffer.load_jsonl(path)
    assert loaded.episodes[0].steps[0].action_key == "attack"
    json.loads(path.read_text(encoding="utf-8"))


def test_toy_selfplay_and_warm_start_training():
    backend = ToyBackend()
    episodes = [generate_episode(backend, {}, seed=index, max_decisions=8) for index in range(3)]
    model = RecurrentPolicyValue(32, 3, hidden_dim=16)
    metrics = train_policy_value(model, episodes, ["attack", "guard", "charge"], encoder=JsonObservationEncoder(32))
    assert metrics.steps > 0


def test_belief_tree_search_returns_normalized_policy():
    backend = ToyBackend()
    state = backend.new_game({}, 0)
    result = BeliefTreeSearch(backend, EmpiricalOpponentPolicy(), seed=5).plan(
        ParticleBelief([Particle(state)]), simulations=12, horizon=3
    )
    assert result.action_key in {"attack", "guard", "charge"}
    assert sum(result.policy.values()) == 1.0
    assert sum(item.visits for item in result.estimates) == 12


def test_truncated_episode_does_not_force_terminal_value():
    backend = ToyBackend()
    episodes = [generate_episode(backend, {}, seed=1, max_decisions=1)]
    assert episodes[0].truncated
    model = RecurrentPolicyValue(16, 3, hidden_dim=8)
    metrics = train_policy_value(model, episodes, ["attack", "guard", "charge"], encoder=JsonObservationEncoder(16))
    assert metrics.value_loss >= 0.0


def test_online_belief_update_consumes_public_observation():
    backend = ToyBackend()
    state = backend.new_game({}, 0)
    belief = ParticleBelief([Particle(backend.clone(state)), Particle(backend.clone(state))])
    agent = OnlineBeliefAgent(backend, EmpiricalOpponentPolicy(), belief, seed=9, samples_per_particle=3, simulations=4, horizon=2)
    result = agent.plan()
    actual = backend.advance(state, {0: result.action_key, 1: "guard"}, 17)
    update = agent.observe(actual.observations[0])
    assert update.attempted == 6
    assert update.accepted > 0
    assert agent.belief.particles
    assert observation_likelihood(actual.observations[0], actual.observations[0], exact=True) == 1.0
