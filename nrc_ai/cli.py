"""Command line smoke checks for the training package."""

from __future__ import annotations

import argparse
import compileall
from datetime import datetime
import importlib
import json
from pathlib import Path
import subprocess
import sys

from .belief import Particle, ParticleBelief
from .belief_setup import belief_from_setups
from .encoding import JsonObservationEncoder
from .model import RecurrentPolicyValue
from .opponent import UniformOpponentPolicy
from .rollout import RootActionEvaluator
from .search import BeliefTreeSearch
from .selfplay import generate_episode, generate_population_search_episode, generate_search_episode
from .toy_backend import ToyBackend
from .training import train_policy_value
from .population_prior import PopulationPrior
from .battle_log import format_review, parse_battle_log
from .battle_prediction import build_round_setups, format_prediction_review, predict_round_setups


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


def population_search_selfplay(setup_path: str, database: str, episodes: int, max_decisions: int, simulations: int, horizon: int, output: str, aptitude_iv: int) -> int:
    backend = _build_core_backend()
    prior = PopulationPrior.from_database(database)
    setup = json.loads(Path(setup_path).read_text(encoding="utf-8"))
    records = [generate_population_search_episode(backend, setup, prior, seed=index, max_decisions=max_decisions, simulations=simulations, horizon=horizon, aptitude_iv=aptitude_iv) for index in range(episodes)]
    from .replay import ReplayBuffer
    ReplayBuffer(records).save_jsonl(output)
    print(json.dumps({"episodes": len(records), "steps": sum(len(item.steps) for item in records), "output": output, "teacher": "population-top-k-oracle", "population_prior_digest": prior.source_digest, "aptitude_grade": 10, "aptitude_iv": aptitude_iv, "manifest": backend.manifest.__dict__}, ensure_ascii=False, indent=2))
    return 0


def population_validate(database: str, csv_directory: str) -> int:
    database_prior = PopulationPrior.from_database(database, nature_tail_floor=0.0)
    csv_prior = PopulationPrior.from_csv_directory(csv_directory, nature_tail_floor=0.0)
    mismatches = []
    overlapping_spirits = set(database_prior.records) & set(csv_prior.records)
    for spirit in overlapping_spirits:
        for kind in set(database_prior.records[spirit]) | set(csv_prior.records[spirit]):
            db_rows = database_prior.records[spirit].get(kind, {})
            csv_rows = csv_prior.records[spirit].get(kind, {})
            for item in set(db_rows) & set(csv_rows):
                if abs(db_rows[item] - csv_rows[item]) > 1e-9:
                    mismatches.append({"spirit": spirit, "kind": kind, "item": item, "database": db_rows[item], "csv": csv_rows[item]})
    payload = {"overlap_matches": not mismatches, "database_digest": database_prior.source_digest, "csv_digest": csv_prior.source_digest, "database_spirits": len(database_prior.spirits()), "csv_spirits": len(csv_prior.spirits()), "overlapping_spirits": len(overlapping_spirits), "mismatch_count": len(mismatches), "mismatch_examples": mismatches[:5], "scope_note": "CSV may be an incremental staging subset; non-overlapping DB rows are not treated as mismatches."}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if mismatches:
        raise SystemExit(1)
    return 0


def train_replay(replay_path: str, action_keys_path: str, input_dim: int, hidden_dim: int, epochs: int, model_output: str | None = None) -> int:
    from .replay import ReplayBuffer
    buffer = ReplayBuffer.load_jsonl(replay_path)
    action_keys = json.loads(Path(action_keys_path).read_text(encoding="utf-8"))
    model = RecurrentPolicyValue(input_dim, len(action_keys), hidden_dim=hidden_dim)
    metrics = train_policy_value(model, buffer.episodes, action_keys, encoder=JsonObservationEncoder(input_dim), epochs=epochs)
    payload: dict[str, object] = {"metrics": metrics.__dict__, "replay": replay_path, "action_keys": len(action_keys)}
    if model_output:
        import torch
        target = Path(model_output)
        target.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"input_dim": input_dim, "hidden_dim": hidden_dim, "action_keys": action_keys, "state_dict": model.state_dict(), "metrics": metrics.__dict__}, target)
        payload["model_output"] = str(target)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _wizard_prompt(prompt: str, default: str, input_fn=input) -> str:
    answer = input_fn(f"{prompt} [{default}]: ").strip()
    return answer or default


def _wizard_int(prompt: str, default: int, input_fn=input) -> int:
    while True:
        answer = _wizard_prompt(prompt, str(default), input_fn)
        try:
            value = int(answer)
        except ValueError:
            print("请输入整数。", file=sys.stderr)
            continue
        if value > 0:
            return value
        print("请输入大于 0 的整数。", file=sys.stderr)


def _wizard_yes_no(prompt: str, default: bool, input_fn=input) -> bool:
    suffix = "Y/n" if default else "y/N"
    answer = input_fn(f"{prompt} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "是", "1"}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _wizard_plan(backend, setup: dict, candidates_path: Path, *, simulations: int, horizon: int, seed: int) -> dict:
    candidates_payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    particles = []
    reference_own = reference_shared = None
    for item in candidates_payload:
        candidate_setup = item["setup"] if isinstance(item, dict) and "setup" in item else item
        own = json.dumps(candidate_setup.get("own_team", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        shared = json.dumps(candidate_setup.get("shared", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if reference_own is None:
            reference_own, reference_shared = own, shared
        elif own != reference_own or shared != reference_shared:
            raise ValueError("wizard candidates must keep own_team and shared state identical")
        particles.append(Particle(backend.new_game(candidate_setup, seed), float(item.get("weight", 1.0))))
    belief = ParticleBelief(particles)
    result = BeliefTreeSearch(backend, UniformOpponentPolicy(), seed=seed).plan(belief, simulations=simulations, horizon=horizon)
    return {"action": result.action_key, "information_mode": "candidate-setups", "particle_count": len(particles), "simulations": result.simulations, "estimates": [estimate.__dict__ for estimate in result.estimates], "manifest": backend.manifest.__dict__}


def phase1_wizard(database: str, csv_directory: str, setup_path: str | None, output_dir: str | None, episodes: int | None, max_decisions: int | None, simulations: int | None, horizon: int | None, epochs: int | None, input_fn=input) -> int:
    """Run the former phase-one A-G handoff as one guided command."""
    print("=== NRC AI 第一阶段训练向导 ===")
    print("数据校验已按要求跳过；程序只读取 DB/CSV，并记录路径。")
    setup_path = setup_path or _wizard_prompt("setup JSON 路径", "setup.json", input_fn)
    output_dir = output_dir or _wizard_prompt("本次产物目录", f"data/ai_runs/phase1_{datetime.now():%Y%m%d_%H%M%S}", input_fn)
    episodes = episodes or _wizard_int("搜索教师轨迹 episode 数", 16, input_fn)
    max_decisions = max_decisions or _wizard_int("每个 episode 最大决策数", 128, input_fn)
    simulations = simulations or _wizard_int("每个决策搜索次数", 64, input_fn)
    horizon = horizon or _wizard_int("搜索 horizon", 8, input_fn)
    epochs = epochs or _wizard_int("GRU 训练 epoch 数", 5, input_fn)
    setup_file = Path(setup_path)
    if not setup_file.exists():
        raise FileNotFoundError(f"setup 不存在: {setup_file}")
    setup = json.loads(setup_file.read_text(encoding="utf-8"))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    seed = 20261005
    manifest: dict[str, object] = {"started_at": datetime.now().isoformat(timespec="seconds"), "database": database, "csv_directory": csv_directory, "setup": str(setup_file), "output_dir": str(output), "population_mode": "deterministic-top-k", "aptitude_grade": 10, "aptitude_iv": 60}

    print("[A] 跳过 DB/CSV 数值校验，保留输入路径")
    manifest["data"] = {"database": database, "csv_directory": csv_directory, "validation": "skipped-by-user"}

    print("[B] 编译 AI/core，并检查训练后端")
    if not compileall.compile_dir("nrc_ai", quiet=1) or not compileall.compile_dir("nrc_core", quiet=1):
        raise RuntimeError("nrc_ai/nrc_core 编译失败")
    check_backend("nrc_core.training:create_backend", str(setup_file))
    backend = _build_core_backend()

    print("[C] 生成确定性 Top-K 候选阵容")
    prior = PopulationPrior.from_database(database)
    candidates_path = output / "population-candidates.json"
    candidates = prior.candidate_setups(setup, count=1, seed=seed, aptitude_count=3, aptitude_iv=60)
    _write_json(candidates_path, candidates)

    print("[D] 对候选隐藏状态执行一次 belief 规划")
    plan_path = output / "belief-plan.json"
    _write_json(plan_path, _wizard_plan(backend, setup, candidates_path, simulations=simulations, horizon=horizon, seed=seed))

    print("[E] 生成确定性人口先验搜索教师轨迹")
    population_replay = output / "population-search.jsonl"
    population_search_selfplay(str(setup_file), database, episodes, max_decisions, simulations, horizon, str(population_replay), 60)

    print("[F] 生成动作字典并训练 GRU policy/value")
    action_keys_path = output / "action_keys.json"
    build_action_keys(str(population_replay), str(action_keys_path))
    model_path = output / "policy_value.pt"
    train_replay(str(population_replay), str(action_keys_path), 256, 128, epochs, str(model_path))

    print("[G] 运行 pytest，并按需生成三类对照轨迹")
    comparison = _wizard_yes_no("是否生成 uniform/oracle-search/population-search 三类对照轨迹", False, input_fn)
    if comparison:
        real_selfplay(str(setup_file), episodes, max_decisions, str(output / "uniform.jsonl"))
        real_search_selfplay(str(setup_file), episodes, max_decisions, simulations, horizon, str(output / "oracle-search.jsonl"))
        manifest["comparison_replays"] = ["uniform.jsonl", "oracle-search.jsonl", "population-search.jsonl"]
    else:
        manifest["comparison_replays"] = ["population-search.jsonl"]
    pytest_result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_nrc_ai_framework.py", "tests/test_nrc_ai_real_integration.py", "tests/test_nrc_core_training_backend.py", "tests/test_battle_log.py", "-q"], check=False)
    manifest["pytest_returncode"] = pytest_result.returncode
    manifest["artifacts"] = {"candidates": str(candidates_path), "belief_plan": str(plan_path), "replay": str(population_replay), "action_keys": str(action_keys_path), "model": str(model_path)}
    manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
    manifest_path = output / "phase1_manifest.json"
    _write_json(manifest_path, manifest)
    print(f"训练向导完成，产物清单: {manifest_path}")
    return 0 if pytest_result.returncode == 0 else pytest_result.returncode


def update_and_recommend(database: str, csv_directory: str, battle_log: str, output: str, replay_path: str | None, action_keys_path: str | None, model_output: str | None, epochs: int) -> int:
    """Validate refreshed priors, optionally retrain, then review every log turn."""
    print("[1/4] loading database and CSV distributions", file=sys.stderr)
    database_prior = PopulationPrior.from_database(database, nature_tail_floor=0.0)
    csv_prior = PopulationPrior.from_csv_directory(csv_directory, nature_tail_floor=0.0)
    overlapping = set(database_prior.records) & set(csv_prior.records)
    mismatches = []
    for spirit in overlapping:
        for kind in set(database_prior.records[spirit]) | set(csv_prior.records[spirit]):
            left = database_prior.records[spirit].get(kind, {})
            right = csv_prior.records[spirit].get(kind, {})
            for item in set(left) & set(right):
                if abs(left[item] - right[item]) > 1e-9:
                    mismatches.append({"spirit": spirit, "kind": kind, "item": item, "database": left[item], "csv": right[item]})
    if mismatches:
        raise ValueError(f"database/CSV overlap mismatch: {mismatches[:3]}")
    print(f"[2/4] distributions ready: db_spirits={len(database_prior.spirits())}, csv_spirits={len(csv_prior.spirits())}, overlap={len(overlapping)}", file=sys.stderr)
    training_payload: dict[str, object]
    if replay_path and action_keys_path:
        print(f"[3/4] retraining from replay: {replay_path}", file=sys.stderr)
        from .replay import ReplayBuffer
        import torch
        buffer = ReplayBuffer.load_jsonl(replay_path)
        action_keys = json.loads(Path(action_keys_path).read_text(encoding="utf-8"))
        model = RecurrentPolicyValue(256, len(action_keys), hidden_dim=128)
        metrics = train_policy_value(model, buffer.episodes, action_keys, encoder=JsonObservationEncoder(256), epochs=epochs)
        training_payload = {"status": "trained", "replay": replay_path, "action_keys": len(action_keys), "metrics": metrics.__dict__}
        if model_output:
            target = Path(model_output)
            target.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"input_dim": 256, "hidden_dim": 128, "action_keys": action_keys, "state_dict": model.state_dict(), "metrics": metrics.__dict__}, target)
            training_payload["model_output"] = str(target)
    else:
        print("[3/4] no replay supplied; skip neural retraining and keep deterministic warm-start policy", file=sys.stderr)
        training_payload = {"status": "skipped-no-replay", "reason": "当前没有实际对局回放，不能凭空拟合策略网络"}
    print(f"[4/4] parsing battle log and recommending one action per turn: {battle_log}", file=sys.stderr)
    report = parse_battle_log(battle_log)
    payload = report.to_json(database_prior)
    payload["population_prior"] = {
        "source": database_prior.source,
        "source_digest": database_prior.source_digest,
        "selection_mode": "deterministic-top-k",
        "skills": "top-4",
        "aptitudes": "top-3, grade-10 (core IV=60)",
        "personality": "top-1",
        "bloodline": "top-1",
    }
    payload["distribution_validation"] = {"database_spirits": len(database_prior.spirits()), "csv_spirits": len(csv_prior.spirits()), "overlapping_spirits": len(overlapping), "mismatch_count": len(mismatches), "csv_digest": csv_prior.source_digest}
    payload["training"] = training_payload
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(format_review(payload))
    print(f"\n审阅 JSON 已写入: {target}")
    return 0


def predict_battle_log(battle_log: str, database: str, output: str, text_output: str, simulations: int, horizon: int, seed: int) -> int:
    print(f"[1/3] parsing battle log: {battle_log}", file=sys.stderr)
    report = parse_battle_log(battle_log)
    print(f"[2/3] generating {len(report.rounds)} round setups with visible-history cutoff", file=sys.stderr)
    prior = PopulationPrior.from_database(database)
    setups = build_round_setups(report, prior)
    print(f"[3/3] predicting each setup with nrc_core search: simulations={simulations}, horizon={horizon}", file=sys.stderr)
    backend = _build_core_backend()
    predictions = predict_round_setups(report, setups, backend, simulations=simulations, horizon=horizon, seed=seed)
    payload = report.to_json(prior)
    payload.update({
        "prediction_mode": "per-round-generated-setup-exact-core-search",
        "prediction_config": {"simulations": simulations, "horizon": horizon, "seed": seed, "information_cutoff": "round-start-visible-history-only"},
        "round_setups": setups,
        "round_predictions": predictions,
    })
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readable = format_prediction_review(payload)
    text_target = Path(text_output)
    text_target.parent.mkdir(parents=True, exist_ok=True)
    text_target.write_text(readable + "\n", encoding="utf-8")
    print(readable)
    print(f"\nJSON: {target}\n人类可读报告: {text_target}")
    return 0


def build_action_keys(replay_path: str, output: str) -> int:
    from .replay import ReplayBuffer
    buffer = ReplayBuffer.load_jsonl(replay_path)
    action_keys = sorted({key for step in buffer.steps() for key in step.legal_action_keys})
    if not action_keys:
        raise ValueError("replay contains no legal action keys")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(action_keys, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"actions": len(action_keys), "output": output}, ensure_ascii=False, indent=2))
    return 0


def population_summary(database: str, spirit: str | None) -> int:
    prior = PopulationPrior.from_database(database)
    print(json.dumps(prior.summary(spirit), ensure_ascii=False, indent=2))
    return 0


def population_candidates(setup_path: str, database: str, output: str, count: int, seed: int, aptitude_count: int, aptitude_iv: int, categorical_temperature: float) -> int:
    prior = PopulationPrior.from_database(database)
    setup = json.loads(Path(setup_path).read_text(encoding="utf-8"))
    candidates = prior.candidate_setups(setup, count=count, seed=seed, aptitude_count=None if aptitude_count < 0 else aptitude_count, aptitude_iv=aptitude_iv, categorical_temperature=categorical_temperature)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "output": output, "source": prior.source, "source_digest": prior.source_digest}, ensure_ascii=False, indent=2))
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
    replay.add_argument("--model-output")
    wizard = subparsers.add_parser("phase1-wizard", help="交互式执行第一阶段 A-G：编译、候选、belief、训练、对照和测试")
    wizard.add_argument("--database", default="data/nrc_wiki.db")
    wizard.add_argument("--csv-directory", default="data/wiki_staging")
    wizard.add_argument("--setup")
    wizard.add_argument("--output-dir")
    wizard.add_argument("--episodes", type=int)
    wizard.add_argument("--max-decisions", type=int)
    wizard.add_argument("--simulations", type=int)
    wizard.add_argument("--horizon", type=int)
    wizard.add_argument("--epochs", type=int)
    update = subparsers.add_parser("update-and-recommend", help="validate refreshed distributions, retrain if replay exists, and review each battle-log turn")
    update.add_argument("--database", default="data/nrc_wiki.db")
    update.add_argument("--csv-directory", default="data/wiki_staging")
    update.add_argument("--battle-log", required=True)
    update.add_argument("--output", default="data/ai_runs/battle_review.json")
    update.add_argument("--replay")
    update.add_argument("--action-keys")
    update.add_argument("--model-output")
    update.add_argument("--epochs", type=int, default=1)
    predict = subparsers.add_parser("predict-battle-log", help="为战报每回合生成可复现 setup，并用 nrc_core 逐回合预测")
    predict.add_argument("--battle-log", required=True)
    predict.add_argument("--database", default="data/nrc_wiki.db")
    predict.add_argument("--output", default="data/ai_runs/battle_predictions.json")
    predict.add_argument("--text-output", default="data/ai_runs/battle_predictions.txt")
    predict.add_argument("--simulations", type=int, default=32)
    predict.add_argument("--horizon", type=int, default=8)
    predict.add_argument("--seed", type=int, default=20261005)
    action_keys = subparsers.add_parser("build-action-keys")
    action_keys.add_argument("--replay", required=True)
    action_keys.add_argument("--output", required=True)
    population = subparsers.add_parser("population-summary")
    population.add_argument("--database", default="data/nrc_wiki.db")
    population.add_argument("--spirit")
    candidates = subparsers.add_parser("population-candidates")
    candidates.add_argument("--setup", required=True)
    candidates.add_argument("--database", default="data/nrc_wiki.db")
    candidates.add_argument("--output", required=True)
    candidates.add_argument("--count", type=int, default=1)
    candidates.add_argument("--seed", type=int, default=0)
    candidates.add_argument("--aptitude-count", type=int, default=3, help="deterministic number of selected aptitude dimensions; phase one uses 3")
    candidates.add_argument("--aptitude-iv", type=int, default=60, help="core IV equivalent of aptitude grade 10")
    candidates.add_argument("--categorical-temperature", type=float, default=1.0, help="retained for CLI compatibility; deterministic mode ignores it")
    population_selfplay = subparsers.add_parser("population-selfplay")
    population_selfplay.add_argument("--setup", required=True)
    population_selfplay.add_argument("--database", default="data/nrc_wiki.db")
    population_selfplay.add_argument("--episodes", type=int, default=16)
    population_selfplay.add_argument("--max-decisions", type=int, default=128)
    population_selfplay.add_argument("--simulations", type=int, default=64)
    population_selfplay.add_argument("--horizon", type=int, default=8)
    population_selfplay.add_argument("--aptitude-iv", type=int, default=60)
    population_selfplay.add_argument("--output", required=True)
    population_validate_parser = subparsers.add_parser("population-validate")
    population_validate_parser.add_argument("--database", default="data/nrc_wiki.db")
    population_validate_parser.add_argument("--csv-directory", default="data/wiki_staging")
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
        return train_replay(args.replay, args.action_keys, args.input_dim, args.hidden_dim, args.epochs, args.model_output)
    if args.command == "phase1-wizard":
        return phase1_wizard(args.database, args.csv_directory, args.setup, args.output_dir, args.episodes, args.max_decisions, args.simulations, args.horizon, args.epochs)
    if args.command == "update-and-recommend":
        if bool(args.replay) != bool(args.action_keys):
            raise ValueError("--replay and --action-keys must be provided together")
        return update_and_recommend(args.database, args.csv_directory, args.battle_log, args.output, args.replay, args.action_keys, args.model_output, args.epochs)
    if args.command == "predict-battle-log":
        return predict_battle_log(args.battle_log, args.database, args.output, args.text_output, args.simulations, args.horizon, args.seed)
    if args.command == "build-action-keys":
        return build_action_keys(args.replay, args.output)
    if args.command == "population-summary":
        return population_summary(args.database, args.spirit)
    if args.command == "population-candidates":
        return population_candidates(args.setup, args.database, args.output, args.count, args.seed, args.aptitude_count, args.aptitude_iv, args.categorical_temperature)
    if args.command == "population-selfplay":
        return population_search_selfplay(args.setup, args.database, args.episodes, args.max_decisions, args.simulations, args.horizon, args.output, args.aptitude_iv)
    if args.command == "population-validate":
        return population_validate(args.database, args.csv_directory)
    if args.command == "plan":
        return real_plan(args.setup, args.simulations, args.horizon, args.seed)
    return real_plan_belief(args.setup, args.candidates, args.simulations, args.horizon, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
