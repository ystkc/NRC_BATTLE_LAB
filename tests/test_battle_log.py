import json
from pathlib import Path

from nrc_ai.battle_log import parse_battle_log
from nrc_ai.battle_prediction import build_round_setups, predict_round_setups
from nrc_ai.cli import _build_core_backend
from nrc_ai.population_prior import PopulationPrior


def test_battle_log_recommends_each_round_without_completing_hidden_team():
    report = parse_battle_log(Path("#1002.md"))
    prior = PopulationPrior.from_database("data/nrc_wiki.db")
    payload = report.to_json(prior)

    assert payload["round_count"] == 17
    latest = payload["recommendations"][-1]
    assert latest["round"] == 17
    assert latest["own_active"]
    assert latest["opponent_active"]
    assert latest["recommendation"]["action"]
    assert latest["history_rounds_used"] == 16
    json.dumps(payload, ensure_ascii=False)


def test_population_top_build_uses_four_skills_three_grade_ten_aptitudes():
    prior = PopulationPrior.from_database("data/nrc_wiki.db")
    spirit = prior.spirits()[0]
    build = prior.top_build(spirit)

    assert len(build.skills) == 4
    assert len(build.aptitudes) == 3
    assert build.aptitude_values == {item: 60 for item in build.aptitudes}
    assert build.personality
    assert build.bloodline


def test_battle_log_generates_and_predicts_every_round():
    report = parse_battle_log(Path("#1002.md"))
    prior = PopulationPrior.from_database("data/nrc_wiki.db")
    setups = build_round_setups(report, prior)
    predictions = predict_round_setups(report, setups, _build_core_backend(), simulations=1, horizon=1, seed=7)

    assert len(setups) == len(report.rounds) == 17
    assert len(predictions) == 17
    assert all(item["status"] == "ok" for item in predictions)
    assert all(item["recommendation"]["action_key"] for item in predictions)
