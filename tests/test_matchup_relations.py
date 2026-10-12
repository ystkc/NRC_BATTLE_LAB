from __future__ import annotations

from fastapi.testclient import TestClient

from nrc_core.models import SkillCategory, get_type_effectiveness
from nrc_server.server import create_app

ALLOWED = {"super_effective", "effective", "very_resistant", "resistant", "normal"}
RANK = {"super_effective": 5, "effective": 4, "very_resistant": 3, "resistant": 2, "normal": 1}


def _indicator(multiplier: float) -> str:
    if multiplier > 2:
        return "super_effective"
    if multiplier > 1:
        return "effective"
    if multiplier < 0.5:
        return "very_resistant"
    if multiplier < 1:
        return "resistant"
    return "normal"


def _expected(creature, target):
    best = None
    for skill in creature.skills:
        if skill.category not in {SkillCategory.PHYSICAL, SkillCategory.MAGICAL} or skill.power <= 0:
            continue
        indicator = _indicator(get_type_effectiveness(skill.skill_type, target.pokemon_types))
        if best is None or RANK[indicator] > RANK[best]:
            best = indicator
    return best


def _roster(form: dict) -> list[dict]:
    skills = (form.get("default_skills") or form.get("skills") or ())[:4]
    return [{"name": form["name"], "skills": [{"name": name} for name in skills]}]


def _started_battle():
    app = create_app()
    client = TestClient(app)
    created = client.post("/api/battles", json={"mode": "full", "seed": 1002}).json()
    battle_id = created["battle_id"]
    own_token = created["player_token"]
    opponent_token = client.post(f"/api/battles/{battle_id}/join", json={}).json()["player_token"]
    catalog = client.get("/api/catalog/index").json()
    client.post(
        f"/api/battles/{battle_id}/rosters",
        headers={"X-Player-Token": own_token},
        json={"roster": _roster(catalog["pokemon"][0]["forms"][0]), "confirm": True},
    )
    ready = client.post(
        f"/api/battles/{battle_id}/rosters",
        headers={"X-Player-Token": opponent_token},
        json={"roster": _roster(catalog["pokemon"][1]["forms"][0]), "confirm": True},
    ).json()
    assert ready["initialized"] is True
    return app, client, battle_id, own_token, opponent_token


def test_matchups_are_empty_before_the_battle_starts():
    client = TestClient(create_app())
    created = client.post("/api/battles", json={"mode": "full", "seed": 1002}).json()
    response = client.get(
        f"/api/battles/{created['battle_id']}/matchups",
        headers={"X-Player-Token": created["player_token"]},
    ).json()
    assert response["relations"] == []


def test_matchups_rate_each_own_creature_against_the_opposing_active_creature():
    app, client, battle_id, own_token, opponent_token = _started_battle()
    core = app.state.platform._get_battle(battle_id).episode.battle

    own = client.get(f"/api/battles/{battle_id}/matchups", headers={"X-Player-Token": own_token}).json()
    assert own["target"] == core.team_b[core.current_b].name
    assert [item["index"] for item in own["relations"]] == list(range(len(core.team_a)))
    for item, creature in zip(own["relations"], core.team_a):
        expected = _expected(creature, core.team_b[core.current_b])
        assert item["indicator"] == expected
        assert item["indicator"] in ALLOWED | {None}

    opponent = client.get(f"/api/battles/{battle_id}/matchups", headers={"X-Player-Token": opponent_token}).json()
    assert opponent["target"] == core.team_a[core.current_a].name
    for item, creature in zip(opponent["relations"], core.team_b):
        assert item["indicator"] == _expected(creature, core.team_a[core.current_a])
