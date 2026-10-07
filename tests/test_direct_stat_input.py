from __future__ import annotations

from fastapi.testclient import TestClient

from nrc_platform import create_platform
from nrc_platform.input import split_creature_spec
from nrc_server.server import create_app


def test_split_creature_spec_supports_hp_only_and_six_stats():
    assert split_creature_spec("bbh 420") == ("bbh", {"hp": 420})
    assert split_creature_spec("hjcts 440 380 250 280 390 100") == (
        "hjcts",
        {"hp": 440, "atk": 380, "def": 250, "spatk": 280, "spdef": 390, "speed": 100},
    )


def test_platform_preview_keeps_unknown_nature_and_aptitudes_for_direct_stats():
    result = create_platform().preview_creature({"name": "hjcts 440 380 250 280 390 100"})

    assert result["stats"] == {"hp": 440, "atk": 380, "def": 250, "spatk": 280, "spdef": 390, "speed": 100}
    assert result["nature"] is None
    assert result["nature_known"] is False
    assert result["individual_values_known"] is False


def test_hp_only_input_uses_neutral_zero_aptitude_defaults_for_other_stats():
    result = create_platform().preview_creature({"name": "bbh 420"})

    assert result["stats"]["hp"] == 420
    assert set(result["stats_known"]) == {"hp", "atk", "def", "spatk", "spdef", "speed"}
    assert all(result["stats_known"].values())
    assert result["nature"] is None
    assert result["individual_values_known"] is False


def test_server_accepts_compact_name_and_hp_roster_input():
    client = TestClient(create_app())
    created = client.post("/api/battles", json={"mode": "full", "seed": 1002}).json()
    response = client.post(
        f"/api/battles/{created['battle_id']}/rosters",
        headers={"X-Player-Token": created["player_token"]},
        json={"roster": [{"name": "bbh 420"}]},
    )

    assert response.status_code == 200
    assert response.json()["roster"][0]["base"]["stats"] == {"hp": 420}
