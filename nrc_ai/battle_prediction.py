"""Turn partial battle-log history into core setups and readable predictions."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .battle_log import BattleLogReport, _recommend
from .population_prior import PopulationPrior
from nrc_core.skill_db import load_ability_effects
from nrc_core.pokemon_db import get_pokemon, get_pokemon_skills, search_pokemon


def _extract_roster(report: BattleLogReport) -> tuple[list[dict[str, Any]], bool]:
    lines = Path(report.path).read_text(encoding="utf-8").splitlines()
    own_label = "\u6211\u65b9"
    enemy_label = "\u654c\u65b9"
    roster: list[dict[str, Any]] = []
    reading = False
    opponent_known = False
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith(f"{own_label}\u961f\u4f0d"):
            reading = True
            continue
        if line.startswith(f"{enemy_label}\u961f\u4f0d"):
            reading = False
            opponent_known = "\u672a\u77e5" not in line
            continue
        if reading and not line.startswith("#") and not line.startswith("##"):
            match = re.match(r"^(.+?)\s+(\d+(?:\.\d+)?)$", line)
            if match:
                hp = float(match.group(2))
                roster.append({"name": match.group(1), "max_hp": int(hp) if hp.is_integer() else hp})
    return roster, opponent_known


def _visible_opponent_names(report: BattleLogReport, round_index: int) -> list[str]:
    names: list[str] = []
    enemy_label = "\u654c\u65b9"
    for battle_round in report.rounds[:round_index + 1]:
        for line in battle_round.evidence:
            if f"[{enemy_label}\u51fa\u573a]" in line or f"[{enemy_label}\u9009\u62e9\u4e0a\u573a\u7cbe\u7075]" in line:
                match = re.search(r"\]\s*([^\s，]+)", line)
                if match and match.group(1) not in names:
                    names.append(match.group(1))
            if f"[{enemy_label}\u5207\u6362\u7cbe\u7075]" in line:
                match = re.search(r"\]\s*[^\s，]+→([^\s，]+)", line)
                if match and match.group(1) not in names:
                    names.append(match.group(1))
            if f"[{enemy_label}\u4f7f\u7528\u5171\u9e23\u9b54\u6cd5]" in line:
                content = line.split("]", 1)[1].strip()
                parts = [item.strip() for item in re.split(r"[-—]", content) if item.strip()]
                if len(parts) >= 2:
                    old_name, new_name = parts[0], parts[-1]
                    if old_name in names:
                        names[names.index(old_name)] = new_name
                    elif new_name not in names:
                        names.append(new_name)
    active = report.rounds[round_index].start.get("opponent_active")
    if active and active not in names:
        names.append(str(active))
    return names


def _resolve_name(prior: PopulationPrior, name: str) -> str | None:
    """Resolve a battle-log shorthand to a canonical core spirit name."""
    if get_pokemon(name) is not None:
        return name
    candidates = search_pokemon(name)
    if candidates:
        return str(candidates[0]["name"])
    prior_candidates = [item for item in prior.spirits() if item.startswith(name) or name.startswith(item)]
    for candidate in prior_candidates:
        if get_pokemon(candidate) is not None:
            return candidate
    return None


def _prior_creature(prior: PopulationPrior, name: str) -> dict[str, Any]:
    partial = {
        "name": name,
        "base": {"bloodline_attributes": None, "nature": None, "stats": None},
        "abilities": [],
        "skills": [],
        "state": {"hp": None, "max_hp": None, "energy": 10, "buffs": {}, "debuffs": {}, "marks": {}, "fatigue_turns": 0},
        "entry_count": 0,
        "metadata": {"source": "battle-log-top-k-completion", "observed": False},
    }
    if name not in prior.records:
        skills = get_pokemon_skills(name)
        if skills:
            ranked = sorted(skills, key=lambda item: (-float(item.get("power", -1)), int(item.get("id", 0))))[:4]
            partial["skills"] = [{"name": item["name"], "source": "core-skill-catalog-fallback"} for item in ranked]
        partial["base"]["nature"] = "\u5766\u7387"
        creature = partial
    else:
        creature = prior.candidate_setups({"opponent_team": {"creatures": [partial]}}, count=1, aptitude_count=3, aptitude_iv=60)[0]["setup"]["opponent_team"]["creatures"][0]
    db_record = get_pokemon(name)
    ability = str(db_record.get("ability") or "") if db_record else ""
    if ability and not load_ability_effects(ability):
        creature["ability"] = {"name": "\u5f20\u5f1b\u6709\u5ea6"}
        creature.setdefault("metadata", {})["ability_assumption"] = {"original": ability, "replacement": "\u5f20\u5f1b\u6709\u5ea6", "reason": "battle-log partial setup requires a supported core ability"}
    return creature


def _numeric_max_hp(creature: Mapping[str, Any]) -> float:
    stats = creature.get("base", {}).get("stats") if isinstance(creature.get("base"), Mapping) else None
    if isinstance(stats, Mapping) and "value" in stats:
        stats = stats["value"]
    if isinstance(stats, Mapping) and stats.get("hp") is not None:
        return float(stats["hp"])
    return 1.0


def _set_round_state(creature: dict[str, Any], hp: Any, energy: Any, max_hp_override: Any, active: bool) -> None:
    state = creature.setdefault("state", {})
    max_hp = float(max_hp_override) if max_hp_override is not None else _numeric_max_hp(creature)
    if isinstance(hp, str) and hp.endswith("%"):
        current_hp = max_hp * float(hp[:-1]) / 100.0
    elif hp is None:
        current_hp = max_hp
    else:
        current_hp = float(hp)
    state.update({
        "hp": int(current_hp) if current_hp.is_integer() else current_hp,
        "max_hp": int(max_hp) if max_hp.is_integer() else max_hp,
        "energy": int(energy) if energy is not None else (10 if active else 0),
        "buffs": {}, "debuffs": {}, "marks": {}, "fatigue_turns": 0,
    })


def build_round_setups(report: BattleLogReport, prior: PopulationPrior) -> list[dict[str, Any]]:
    """Generate a setup snapshot for every round without exposing future enemies."""
    roster, opponent_known = _extract_roster(report)
    own_names = [item["name"] for item in roster]
    if not own_names and report.rounds:
        own_names = [str(report.rounds[0].start.get("own_active"))]
    own_max_hp = {item["name"]: item.get("max_hp") for item in roster}
    aliases: dict[str, str] = {}
    resolved_own: list[tuple[str, str]] = []
    for original in own_names:
        canonical = _resolve_name(prior, original)
        if canonical:
            aliases[original] = canonical
            resolved_own.append((original, canonical))
    setups: list[dict[str, Any]] = []
    for round_index, battle_round in enumerate(report.rounds):
        visible_opponent_names = _visible_opponent_names(report, round_index)
        if not visible_opponent_names and battle_round.start.get("opponent_active"):
            visible_opponent_names = [str(battle_round.start["opponent_active"])]
        resolved_opponent: list[tuple[str, str]] = []
        for original in visible_opponent_names:
            canonical = _resolve_name(prior, original)
            if canonical:
                aliases[original] = canonical
                resolved_opponent.append((original, canonical))
        active_own_original = str(battle_round.start.get("own_active") or (own_names[0] if own_names else ""))
        active_opponent_original = str(battle_round.start.get("opponent_active") or (visible_opponent_names[0] if visible_opponent_names else ""))
        active_own = aliases.get(active_own_original)
        active_opponent = aliases.get(active_opponent_original)
        if not active_own or not active_opponent:
            raise ValueError(f"无法解析第{battle_round.number}回合当前精灵: own={active_own_original!r}, opponent={active_opponent_original!r}")
        own_creatures = [_prior_creature(prior, canonical) for _, canonical in resolved_own if canonical == active_own or _resolve_name(prior, canonical)]
        opponent_creatures = [_prior_creature(prior, canonical) for _, canonical in resolved_opponent]
        for creature in own_creatures:
            name = str(creature["name"])
            if name == active_own and battle_round.options:
                creature["skills"] = [{"name": option.name, "source": "battle-log-visible"} for option in battle_round.options]
            original_name = next((original for original, canonical in resolved_own if canonical == name), name)
            _set_round_state(creature, battle_round.start.get("own_hp") if name == active_own else None, battle_round.start.get("own_energy") if name == active_own else None, own_max_hp.get(original_name), name == active_own)
        for creature in opponent_creatures:
            name = str(creature["name"])
            _set_round_state(creature, battle_round.start.get("opponent_hp") if name == active_opponent else None, battle_round.start.get("opponent_energy") if name == active_opponent else None, None, name == active_opponent)
        own_index = next((index for index, item in enumerate(own_creatures) if item["name"] == active_own), 0)
        opponent_index = next((index for index, item in enumerate(opponent_creatures) if item["name"] == active_opponent), 0)
        setups.append({
            "own_team": {"team_name": "battle-log-own", "active_index": own_index, "resonance_magic": None, "creatures": own_creatures},
            "opponent_team": {"team_name": "battle-log-opponent-visible", "active_index": opponent_index, "resonance_magic": None, "creatures": opponent_creatures},
            "shared": {"turn": battle_round.number, "weather": None, "weather_turns": None, "system_time": None, "weekend": None, "bypass": None, "mp": {"own": 4, "opponent": 4}, "metadata": {"source": report.path, "partial_observation": True, "opponent_roster_known": opponent_known, "visible_opponent_names": visible_opponent_names, "name_aliases": aliases, "history_rounds_before": [item.to_json() for item in report.rounds[:round_index]]}},
            "own_turn": None, "opponent_turn": None, "seed": round_index, "battle_id": f"battle-log-{battle_round.number}", "source": "battle-log-round-snapshot",
        })
    return setups


def predict_round_setups(report: BattleLogReport, setups: list[Mapping[str, Any]], backend: Any, *, simulations: int = 32, horizon: int = 8, seed: int = 0) -> list[dict[str, Any]]:
    """Run exact-core search once per setup, with explicit history fallback."""
    from .belief import Particle, ParticleBelief
    from .opponent import UniformOpponentPolicy
    from .search import BeliefTreeSearch

    results: list[dict[str, Any]] = []
    for index, (battle_round, setup) in enumerate(zip(report.rounds, setups)):
        record: dict[str, Any] = {"round": battle_round.number, "setup": copy.deepcopy(setup), "status": "error", "model": "nrc-core-belief-tree-search", "actual_action": battle_round.actual_action, "selection": battle_round.selection}
        try:
            state = backend.new_game(setup, seed + index)
            legal = backend.legal_actions(state, 0)
            own_names = [str(item.get("name")) for item in setup.get("own_team", {}).get("creatures", [])]
            action_labels = {}
            for item in legal:
                primary = item.payload.get("primary", {})
                switch_index = primary.get("switch_index")
                switch_name = own_names[int(switch_index)] if switch_index is not None and int(switch_index) < len(own_names) else None
                action_labels[item.key] = primary.get("skill_name") or (f"换人->{switch_name}" if switch_name else item.key)
            result = BeliefTreeSearch(backend, UniformOpponentPolicy(), seed=seed + index).plan(ParticleBelief([Particle(state)]), simulations=simulations, horizon=horizon)
            estimates = [{"action_key": estimate.action_key, "action_name": action_labels.get(estimate.action_key, estimate.action_key), "visits": estimate.visits, "mean_value": estimate.mean_value, "probability": estimate.probability} for estimate in result.estimates]
            top_probability = estimates[0]["probability"] if estimates else 0.0
            second_probability = estimates[1]["probability"] if len(estimates) > 1 else 0.0
            margin = top_probability - second_probability
            confidence = "high" if top_probability >= 0.65 or margin >= 0.35 else "medium" if top_probability >= 0.4 or margin >= 0.15 else "low"
            record.update({"status": "ok", "decision": backend.decision(state).__dict__, "legal_actions": [{"key": item.key, "name": action_labels[item.key], "payload": dict(item.payload)} for item in legal], "recommendation": {"action_key": result.action_key, "action_name": action_labels.get(result.action_key, result.action_key), "probability": top_probability, "confidence": confidence, "margin": margin}, "estimates": estimates, "simulations": simulations, "horizon": horizon})
        except Exception as error:
            fallback = _recommend(battle_round, report.rounds[:index], battle_round.options)
            fallback_choice = fallback.get("recommendation") or {}
            record.update({
                "status": "fallback",
                "model": "history-visible-heuristic-fallback",
                "error": f"{type(error).__name__}: {error}",
                "fallback_reason": "nrc_core search failed for this partial setup; recommendation remains reviewable but is not an exact-core result",
                "recommendation": {
                    "action_key": f"log-option:{fallback_choice.get('option_index', 0)}" if fallback_choice else None,
                    "action_name": fallback_choice.get("action"),
                    "probability": None,
                    "confidence": fallback.get("confidence", "low"),
                    "margin": None,
                    "reasons": fallback_choice.get("reasons", []),
                },
            })
        results.append(record)
    return results


def format_prediction_review(payload: Mapping[str, Any]) -> str:
    lines = [f"\u6218\u62a5: {payload.get('path')}", "\u4ee5\u4e0b\u4e3a\u6bcf\u56de\u5408\u72ec\u7acb\u751f\u6210 setup \u540e\u7684\u9884\u6d4b", ""]
    for item in payload.get("round_predictions", []):
        recommendation = item.get("recommendation") or {}
        actual = item.get("actual_action") or item.get("selection") or "尚未记录"
        if item.get("status") == "ok":
            lines.append(f"\u7b2c{item.get('round')}\u56de\u5408 | \u63a8\u8350: {recommendation.get('action_name')} ({recommendation.get('action_key')}) | \u7f6e\u4fe1\u5ea6: {recommendation.get('confidence')} | \u641c\u7d22\u6982\u7387: {recommendation.get('probability', 0.0):.1%} | \u5b9e\u9645: {actual}")
        elif item.get("status") == "fallback":
            reasons = "；".join(recommendation.get("reasons", [])) or "当前可见技能面板不足"
            fallback_action = recommendation.get("action_name") or "信息不足"
            fallback_confidence = recommendation.get("confidence") or "低"
            lines.append(f"\u7b2c{item.get('round')}\u56de\u5408 | \u56de\u9000\u63a8\u8350: {fallback_action} | \u7f6e\u4fe1\u5ea6: {fallback_confidence} | \u5b9e\u9645: {actual} | \u7406\u7531: {reasons}")
        else:
            lines.append(f"\u7b2c{item.get('round')}\u56de\u5408 | \u9884\u6d4b\u5931\u8d25 | \u539f\u56e0: {item.get('error')}")
    return "\n".join(lines)


__all__ = ["build_round_setups", "format_prediction_review", "predict_round_setups"]
