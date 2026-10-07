from __future__ import annotations

from fastapi.testclient import TestClient

from nrc_server.server import create_app


def _roster(form: dict) -> list[dict]:
    skills = (form.get("default_skills") or form.get("skills") or ())[:4]
    return [{"name": form["name"], "skills": [{"name": name} for name in skills]}]


def test_battle_events_endpoint_returns_only_events_after_cursor():
    client = TestClient(create_app())
    created = client.post("/api/battles", json={"mode": "full", "seed": 1002}).json()
    battle_id = created["battle_id"]
    own_token = created["player_token"]
    opponent_token = client.post(f"/api/battles/{battle_id}/join", json={}).json()["player_token"]

    catalog = client.get("/api/catalog/index").json()
    own_form = catalog["pokemon"][0]["forms"][0]
    opponent_form = catalog["pokemon"][1]["forms"][0]
    client.post(
        f"/api/battles/{battle_id}/rosters",
        headers={"X-Player-Token": own_token},
        json={"roster": _roster(own_form), "confirm": True},
    )
    ready = client.post(
        f"/api/battles/{battle_id}/rosters",
        headers={"X-Player-Token": opponent_token},
        json={"roster": _roster(opponent_form), "confirm": True},
    ).json()
    assert ready["initialized"] is True

    initial = client.get(
        f"/api/battles/{battle_id}/events?since=0",
        headers={"X-Player-Token": own_token},
    ).json()
    assert initial["events"]
    cursor = initial["cursor"]
    assert client.get(
        f"/api/battles/{battle_id}/events?since={cursor}",
        headers={"X-Player-Token": own_token},
    ).json()["events"] == []

    actions = client.get(
        f"/api/battles/{battle_id}/actions",
        headers={"X-Player-Token": own_token},
    ).json()["actions"]
    action_key = actions[0]["key"]
    client.post(
        f"/api/battles/{battle_id}/selection",
        headers={"X-Player-Token": own_token},
        json={"action_key": action_key},
    )
    opponent_actions = client.get(
        f"/api/battles/{battle_id}/actions",
        headers={"X-Player-Token": opponent_token},
    ).json()["actions"]
    client.post(
        f"/api/battles/{battle_id}/selection",
        headers={"X-Player-Token": opponent_token},
        json={"action_key": opponent_actions[0]["key"]},
    )

    latest = client.get(
        f"/api/battles/{battle_id}/events?since={cursor}",
        headers={"X-Player-Token": own_token},
    ).json()
    assert latest["events"]
    assert latest["events"][0]["event_index"] == cursor
    assert all(event["event_index"] >= cursor for event in latest["events"])
