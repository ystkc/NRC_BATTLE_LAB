"""Small self-play trajectory generator for backend integration tests."""

from __future__ import annotations

import random
import uuid

from nrc_core.contracts import CoreBackend
from .belief import Particle, ParticleBelief
from .opponent import OpponentPolicy, UniformOpponentPolicy
from .replay import Episode, StepRecord
from .search import BeliefTreeSearch
from .population_prior import PopulationPrior


def generate_episode(backend: CoreBackend, setup: dict, *, seed: int = 0, max_decisions: int = 64, player_policy: OpponentPolicy | None = None, opponent_policy: OpponentPolicy | None = None) -> Episode:
    player_policy = player_policy or UniformOpponentPolicy()
    opponent_policy = opponent_policy or UniformOpponentPolicy()
    rng = random.Random(seed)
    state = backend.new_game(setup, seed)
    episode = Episode(f"episode-{uuid.uuid4().hex[:12]}", backend.manifest.__dict__, metadata={"seed": seed})
    for _ in range(max_decisions):
        decision = backend.decision(state)
        if decision.terminated:
            episode.terminal_winner = decision.winner
            return episode
        actions = {}
        own_observation = None
        own_legal = ()
        own_action = None
        if 0 in decision.players:
            own_observation = backend.observe(state, 0)
            own_legal = backend.legal_actions(state, 0)
            if not own_legal:
                raise RuntimeError(
                    f"backend contract violation: player 0 has no legal action at "
                    f"decision {decision.index} without a terminal state"
                )
            own_action = player_policy.choose(own_observation, own_legal, rng)
            actions[0] = own_action
        for player in decision.players:
            if player == 0:
                continue
            observation = backend.observe(state, player)
            legal = backend.legal_actions(state, player)
            if not legal:
                raise RuntimeError(
                    f"backend contract violation: player {player} has no legal action at "
                    f"decision {decision.index} without a terminal state"
                )
            actions[player] = opponent_policy.choose(observation, legal, rng)
        transition = backend.advance(state, actions, rng.randrange(2**32))
        if own_observation is not None and own_action is not None:
            episode.append(StepRecord(decision.index, decision.turn, decision.phase, own_observation.data, tuple(action.key for action in own_legal), own_action, float(transition.rewards.get(0, 0.0)), transition.terminated, transition.winner, source="self_play"))
        state = transition.state
        if transition.terminated:
            episode.terminal_winner = transition.winner
            return episode
    episode.truncated = True
    return episode


def generate_search_episode(backend: CoreBackend, setup: dict, *, seed: int = 0, max_decisions: int = 64, simulations: int = 64, horizon: int = 8, opponent_policy: OpponentPolicy | None = None) -> Episode:
    """Generate an episode with root-tree search as player 0's teacher.

    The default particle is explicitly a full-state teacher particle. This is
    suitable for exact-model self-play data generation, not for claiming that
    an online actor can see hidden opponent state.
    """
    opponent_policy = opponent_policy or UniformOpponentPolicy()
    rng = random.Random(seed)
    state = backend.new_game(setup, seed)
    episode = Episode(f"search-episode-{uuid.uuid4().hex[:12]}", backend.manifest.__dict__, metadata={"seed": seed, "teacher": "belief-tree-search", "information_mode": "oracle-full-state"})
    for _ in range(max_decisions):
        decision = backend.decision(state)
        if decision.terminated:
            episode.terminal_winner = decision.winner
            return episode
        actions = {}
        own_observation = None
        own_legal = ()
        search_policy = None
        if 0 in decision.players:
            own_observation = backend.observe(state, 0)
            own_legal = backend.legal_actions(state, 0)
            if not own_legal:
                raise RuntimeError(f"backend returned no legal action for player 0 at decision {decision.index}")
            result = BeliefTreeSearch(backend, opponent_policy, seed=rng.randrange(2**32)).plan(
                ParticleBelief([Particle(backend.clone(state))]), player=0, simulations=simulations, horizon=horizon
            )
            actions[0] = result.action_key
            search_policy = result.policy
        for player in decision.players:
            if player == 0:
                continue
            observation = backend.observe(state, player)
            legal = backend.legal_actions(state, player)
            if not legal:
                raise RuntimeError(f"backend returned no legal action for player {player} at decision {decision.index}")
            actions[player] = opponent_policy.choose(observation, legal, rng)
        transition = backend.advance(state, actions, rng.randrange(2**32))
        if own_observation is not None:
            episode.append(StepRecord(decision.index, decision.turn, decision.phase, own_observation.data, tuple(action.key for action in own_legal), actions[0], float(transition.rewards.get(0, 0.0)), transition.terminated, transition.winner, search_policy=search_policy, source="search_self_play"))
        state = transition.state
        if transition.terminated:
            episode.terminal_winner = transition.winner
            return episode
    episode.truncated = True
    return episode


def generate_population_search_episode(backend: CoreBackend, setup: dict, prior: PopulationPrior, *, seed: int = 0, max_decisions: int = 64, simulations: int = 64, horizon: int = 8, opponent_policy: OpponentPolicy | None = None, aptitude_iv: int = 60) -> Episode:
    """Generate a search-teacher episode from the deterministic population-top-K setup.

    Search still uses the completed state as its teacher state. The actor
    observation remains private/public separated by the backend, so this is not
    a claim that the actor sees hidden data. Phase one deliberately avoids
    random population sampling until actual battle replay is available.
    """
    candidates = prior.candidate_setups(setup, count=1, seed=seed, aptitude_iv=aptitude_iv)
    episode = generate_search_episode(backend, candidates[0]["setup"], seed=seed, max_decisions=max_decisions, simulations=simulations, horizon=horizon, opponent_policy=opponent_policy)
    episode.metadata = {
        **dict(episode.metadata),
        "information_mode": "population-top-k-oracle-teacher",
        "population_prior_source": prior.source,
        "population_prior_digest": prior.source_digest,
        "aptitude_iv_assumption": aptitude_iv,
    }
    return episode
