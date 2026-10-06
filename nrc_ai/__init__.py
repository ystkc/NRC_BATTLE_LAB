"""Training-side interfaces and baseline components for NRC battles.

This package does not import the in-progress nrc_core. A versioned backend
adapter can be connected after the core contract is agreed.
"""

from .contracts import CoreBackend, CoreManifest, Decision, LegalAction, Observation, Transition
from .belief import Particle, ParticleBelief, ParticleFilter
from .opponent import EmpiricalOpponentPolicy, UniformOpponentPolicy
from .replay import Episode, ReplayBuffer, StepRecord
from .search import BeliefTreeSearch, SearchEstimate, SearchResult
from .belief_setup import belief_from_setups
from .selfplay import generate_episode, generate_population_search_episode, generate_search_episode
from .online import BeliefUpdateResult, OnlineBeliefAgent, OnlineBeliefUpdater, observation_likelihood
from .population_prior import PopulationBuild, PopulationPrior
from .battle_log import ActionOption, BattleLogReport, BattleRound, format_review, parse_battle_log
from .battle_prediction import build_round_setups, format_prediction_review, predict_round_setups

__all__ = [
    "CoreBackend", "CoreManifest", "Decision", "LegalAction", "Observation", "Transition",
    "Particle", "ParticleBelief", "ParticleFilter", "EmpiricalOpponentPolicy",
    "UniformOpponentPolicy", "Episode", "ReplayBuffer", "StepRecord",
    "BeliefTreeSearch", "SearchEstimate", "SearchResult",
    "belief_from_setups",
    "generate_episode", "generate_search_episode", "generate_population_search_episode", "BeliefUpdateResult", "OnlineBeliefAgent", "OnlineBeliefUpdater", "observation_likelihood",
    "PopulationBuild", "PopulationPrior",
    "ActionOption", "BattleLogReport", "BattleRound", "format_review", "parse_battle_log",
    "build_round_setups", "format_prediction_review", "predict_round_setups",
]
