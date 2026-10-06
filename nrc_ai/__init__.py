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
try:
    from .battle_prediction import build_round_setups, format_prediction_review, predict_round_setups
except ImportError as exc:
    _battle_prediction_import_error = exc

    def _battle_prediction_unavailable(*args, **kwargs):
        raise ImportError("battle_prediction requires the legacy pokemon catalog helpers") from _battle_prediction_import_error

    build_round_setups = _battle_prediction_unavailable
    format_prediction_review = _battle_prediction_unavailable
    predict_round_setups = _battle_prediction_unavailable
from .interface import (
    AIInterfaceError,
    AIPrediction,
    ModelActionEstimate,
    NRCAIInterface,
    AIInterface,
    NrcAI,
    ObserverView,
    create_interface,
    normalize_observer_owners,
    observer_mode,
    predict_operations,
)

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
    "AIInterfaceError", "AIPrediction", "ModelActionEstimate", "NRCAIInterface", "AIInterface", "NrcAI", "ObserverView",
    "create_interface", "normalize_observer_owners", "observer_mode", "predict_operations",
]
