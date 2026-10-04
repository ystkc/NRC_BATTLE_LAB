"""Command line smoke checks for the training package."""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from .belief import Particle, ParticleBelief
from .belief_setup import belief_from_setups
from .encoding import JsonObservationEncoder
from .model import RecurrentPolicyValue
from .opponent import UniformOpponentPolicy
from .rollout import RootActionEvaluator
from .search import BeliefTreeSearch
from .selfplay import generate_episode, generate_search_episode
from .toy_backend import ToyBackend
from .training import train_policy_value


def _build_core_backend():
    factory = _load_factory("nrc_core.training:create_backend")
    return factory()


def real_selfplay(setup_path: str, episodes: int, max_decisions: int, output: str) -> int:
    backend = _build_core_backend()
    setup = json.loads(Path(setup_path).read_text(encoding="utf-8"))
    from .replay import ReplayBuffer
    records = [generate_episode(backend, setup, seed=index, max_decisions=max_decisions) for index in range(episodes)]
    buffer = ReplayBuffer(records)
    buffer.save_jsonl(output)
    print(json.dumps({"episodes": len(buffer), "steps": sum(len(item.steps) for item in records), "output": output, "manifest": backend.manifest.__dict__}, ensure_ascii=False, indent=2))
    return 0


def real_search_selfplay(setup_path: str, episodes: int, max_decisions: int, simulations: int, horizon: int, output: str) -> int:
    backend = _build_core_backend()
    setup = json.loads(Path(setup_path).read_text(encoding="utf-8"))
    records = [generate_search_episode(backend, setup, seed=index, max_decisions=max_decisions, simulations=simulations, horizon=horizon) for index in range(episodes)]
    from .replay import ReplayBuffer
    ReplayBuffer(records).save_jsonl(output)
    print(json.dumps({"episodes": len(records), "steps": sum(len(item.steps) for item in records), "output": output, "teacher": "belief-tree-search", "manifest": backend.manifest.__dict__}, ensure_ascii=False, indent=2))
    return 0


def train_replay(replay_path: str, action_keys_path: str, input_dim: int, hidden_dim: int, epochs: int) -> int:
    from .replay import ReplayBuffer
    buffer = ReplayBuffer.load_jsonl(replay_path)
    action_keys = json.loads(Path(action_keys_path).read_text(encoding="utf-8"))
    model = RecurrentPolicyValue(input_dim, len(action_keys), hidden_dim=hidden_dim)
    metrics = train_policy_value(model, buffer.episodes, action_keys, encoder=JsonObservationEncoder(input_dim), epochs=epochs)
    print(json.dumps(metrics.__dict__, ensure_ascii=False, indent=2))
    return 0


def real_plan(setup_path: str, simulations: int, horizon: int, seed: int) -> int:
    backend = _build_core_backend()
    setup = json.loads(Path(setup_path).read_text(encoding="utf-8"))
    state = backend.new_game(setup, seed)
    belief = ParticleBelief([Particle(state)])
    result = BeliefTreeSearch(backend, UniformOpponentPolicy(), seed=seed).plan(
        belief, simulations=simulations, horizon=horizon
    )
    payload = {
        "action": result.action_key,
        "information_mode": "oracle-full-state",
        "simulations": result.simulations,
        "estimates": [estimate.__dict__ for estimate in result.estimates],
        "manifest": backend.manifest.__dict__,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def real_plan_belief(setup_path: str, candidates: str | None, simulations: int, horizon: int, seed: int) -> int:
    backend = _build_core_backend()
    setup = json.loads(Path(setup_path).read_text(encoding="utf-8"))
    belief, information_mode = belief_from_setups(backend, setup, candidates, seed=seed)
    result = BeliefTreeSearch(backend, UniformOpponentPolicy(), seed=seed).plan(belief, simulations=simulations, horizon=horizon)
    payload = {
        "action": result.action_key,
        "information_mode": information_mode,
        "particle_count": len(belief.particles),
        "simulations": result.simulations,
        "estimates": [estimate.__dict__ for estimate in result.estimates],
        "manifest": backend.manifest.__dict__,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _load_factory(spec: str):
    module_name, separator, attribute = spec.partition(":")
    if not separator:
        raise ValueError("backend must use module:factory syntax")
    return getattr(importlib.import_module(module_name), attribute)


def check_backend(spec: str, setup_path: str | None) -> int:
    factory = _load_factory(spec)
    backend = factory()
    manifest = backend.manifest
    if not manifest.protocol_version or not manifest.rules_version:
        raise ValueError("backend manifest is incomplete")
    setup = json.loads(Path(setup_path).read_text(encoding="utf-8")) if setup_path else {}
    state = backend.new_game(setup, 0)
    decision = backend.decision(state)
    actions = {}
    for player in decision.players:
        keys = [action.key for action in backend.legal_actions(state, player)]
        if len(keys) != len(set(keys)):
            raise ValueError(f"duplicate action keys for player {player}")
        actions[str(player)] = keys
    print(json.dumps({"environment": manifest.environment, "decision": decision.__dict__, "actions": actions}, ensure_ascii=False, indent=2))
    return 0


def toy_rollout(simulations: int) -> int:
    backend = ToyBackend()
    state = backend.new_game({}, 0)
    belief = ParticleBelief([Particle(backend.clone(state)), Particle(backend.clone(state))])
    result = RootActionEvaluator(backend, UniformOpponentPolicy(), seed=7).evaluate(belief, simulations_per_action=simulations)
    print(json.dumps([estimate.__dict__ for estimate in result], ensure_ascii=False, indent=2))
    return 0


def toy_train(episodes: int, epochs: int) -> int:
    backend = ToyBackend()
    records = [generate_episode(backend, {}, seed=index, max_decisions=16) for index in range(episodes)]
    model = RecurrentPolicyValue(64, 3, hidden_dim=32)
    metrics = train_policy_value(model, records, ["attack", "guard", "charge"], encoder=JsonObservationEncoder(64), epochs=epochs)
    print(json.dumps(metrics.__dict__, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--backend", required=True)
    check.add_argument("--setup")
    rollout = subparsers.add_parser("toy-rollout")
    rollout.add_argument("--simulations", type=int, default=16)
    train = subparsers.add_parser("toy-train")
    train.add_argument("--episodes", type=int, default=8)
    train.add_argument("--epochs", type=int, default=1)
    real = subparsers.add_parser("selfplay")
    real.add_argument("--setup", required=True)
    real.add_argument("--episodes", type=int, default=1)
    real.add_argument("--max-decisions", type=int, default=128)
    real.add_argument("--output", required=True)
    search_selfplay = subparsers.add_parser("search-selfplay")
    search_selfplay.add_argument("--setup", required=True)
    search_selfplay.add_argument("--episodes", type=int, default=1)
    search_selfplay.add_argument("--max-decisions", type=int, default=128)
    search_selfplay.add_argument("--simulations", type=int, default=64)
    search_selfplay.add_argument("--horizon", type=int, default=8)
    search_selfplay.add_argument("--output", required=True)
    replay = subparsers.add_parser("train-replay")
    replay.add_argument("--replay", required=True)
    replay.add_argument("--action-keys", required=True, help="JSON array of stable action keys")
    replay.add_argument("--input-dim", type=int, default=256)
    replay.add_argument("--hidden-dim", type=int, default=128)
    replay.add_argument("--epochs", type=int, default=1)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--setup", required=True)
    plan.add_argument("--simulations", type=int, default=128)
    plan.add_argument("--horizon", type=int, default=8)
    plan.add_argument("--seed", type=int, default=0)
    belief_plan = subparsers.add_parser("plan-belief")
    belief_plan.add_argument("--setup", required=True)
    belief_plan.add_argument("--candidates")
    belief_plan.add_argument("--simulations", type=int, default=128)
    belief_plan.add_argument("--horizon", type=int, default=8)
    belief_plan.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.command == "check":
        return check_backend(args.backend, args.setup)
    if args.command == "toy-rollout":
        return toy_rollout(args.simulations)
    if args.command == "toy-train":
        return toy_train(args.episodes, args.epochs)
    if args.command == "selfplay":
        return real_selfplay(args.setup, args.episodes, args.max_decisions, args.output)
    if args.command == "search-selfplay":
        return real_search_selfplay(args.setup, args.episodes, args.max_decisions, args.simulations, args.horizon, args.output)
    if args.command == "train-replay":
        return train_replay(args.replay, args.action_keys, args.input_dim, args.hidden_dim, args.epochs)
    if args.command == "plan":
        return real_plan(args.setup, args.simulations, args.horizon, args.seed)
    return real_plan_belief(args.setup, args.candidates, args.simulations, args.horizon, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
