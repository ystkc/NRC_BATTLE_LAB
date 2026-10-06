from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from manual_input.catalog import Catalog
from manual_input.recorder import BattleRecorder


def known(value):
    return {"known": True, "exists": True, "value": value}


def opening_request():
    creature = {
        "name": known("测试精灵"),
        "state": {"hp": known(100), "max_hp": known(100), "energy": known(10)},
        "skills": [{} for _ in range(4)],
    }
    return {
        "own_team": {"active_index": known(0), "creatures": [creature for _ in range(6)]},
        "opponent_team": {"active_index": known(0), "creatures": [creature for _ in range(6)]},
        "shared": {"turn": known(1), "mp": {"own": known(4), "opponent": known(4)}},
        "own_turn": {"primary": {"kind": "pass"}},
        "opponent_turn": {"primary": {"kind": "pass"}},
    }


def test_initial_checkpoint_does_not_consume_a_round(tmp_path):
    recorder = BattleRecorder(tmp_path)
    battle = recorder.create_battle()
    request = opening_request()
    saved = recorder.save_initial(battle["battle_id"], request)
    assert saved["initial_state"]["request"] == request
    assert saved["rounds"] == []
    assert recorder.load(battle["battle_id"]) == saved
    assert recorder.list_battles()[0]["has_initial_state"] is True
    with pytest.raises(ValueError, match="already started"):
        recorder.save_initial(battle["battle_id"], request)
    saved = recorder.save_round(battle["battle_id"], request)
    assert saved["rounds"][0]["round"] == 1
    assert saved["initial_state"]["request"] == request


def test_invalid_checkpoint_does_not_write(tmp_path):
    recorder = BattleRecorder(tmp_path)
    battle = recorder.create_battle()
    with pytest.raises(ValueError):
        recorder.save_initial(battle["battle_id"], {})
    assert "initial_state" not in recorder.load(battle["battle_id"])


def test_initial_checkpoint_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from manual_input.server import create_app

    recorder = BattleRecorder(tmp_path)
    client = TestClient(create_app(recorder=recorder))
    battle = client.post("/api/new-battle").json()
    payload = {"battle_id": battle["battle_id"], "request": opening_request()}
    response = client.post("/api/save-initial", json=payload)
    assert response.status_code == 201
    assert response.json()["rounds"] == []
    assert client.get("/api/battle", params={"id": battle["battle_id"]}).json()["initial_state"]
    assert client.post("/api/save-initial", json=payload).status_code == 422


def test_catalog_reads_new_wiki_database():
    catalog = Catalog()
    assert len(catalog.pokemon) == 625
    assert len(catalog.skills) == 579
    candidate = catalog.pokemon[0].to_json()
    assert candidate["forms"]
    assert candidate["icon_url"] or candidate["forms"][0]["icon_url"]
    assert catalog.search("skill", "")[0]["icon_url"]
    assert catalog.search("weather", "yt")[0]["id"] == "rain"
    assert catalog.search("weather", "无天气")[0]["id"] == ""


@pytest.fixture
def isolated_core(monkeypatch, tmp_path):
    import nrc_core.simulator as core
    from nrc_core.models import Skill, SkillCategory, Type

    monkeypatch.setattr(core, "get_pokemon", lambda name: None)
    monkeypatch.setattr(core, "get_skill", lambda name: Skill(name, Type.NORMAL, SkillCategory.PHYSICAL, 0, 0))
    return core.BattleSimulator(data_dir=tmp_path)


def test_simulator_receives_modifiers_and_status_layers(isolated_core):

    request = opening_request()
    request["own_team"]["creatures"] = [json.loads(json.dumps(creature)) for creature in request["own_team"]["creatures"]]
    active = request["own_team"]["creatures"][0]
    active["state"]["buffs"] = known([
        {"name": "atk_up", "unit": "+100%", "stacks": 2},
        {"name": "speed_up", "unit": "+100%", "stacks": 1},
    ])
    active["state"]["debuffs"] = known([
        {"name": "def_down", "unit": "+100%", "stacks": 3},
    ])
    active["state"]["statuses"] = known([
        {"name": "poison", "unit": "poison", "stacks": 2},
        {"name": "combo", "unit": "hit", "stacks": 3},
        {"name": "cute", "unit": "cute", "stacks": 1},
    ])
    request["shared"]["weather"] = known("rain")
    request["shared"]["weather_turns"] = known(3)
    request["seed"] = 7
    result = isolated_core.resolve_turn(request).to_json()
    before = result["own"]["before"]["creatures"][0]
    assert {item["name"]: item["stacks"] for item in before["buffs"]} == {"atk_up": 2, "speed_up": 1}
    assert {item["name"]: item["stacks"] for item in before["debuffs"]} == {"def_down": 3}
    assert {item["name"]: item["stacks"] for item in before["statuses"]} == {"poison": 2, "combo": 3, "cute": 1}
    assert result["shared_before"]["weather"] == "rain"
    assert result["shared_after"]["weather_turns"] == 2
    assert result["own"]["after"]["creatures"][0]["hp"] < 100
    repeated = isolated_core.resolve_turn(request).to_json()
    assert repeated == result


def test_simulate_endpoint_returns_ui_snapshots(tmp_path, isolated_core):
    from fastapi.testclient import TestClient
    from manual_input.server import create_app

    client = TestClient(create_app(recorder=BattleRecorder(tmp_path), simulator=isolated_core))
    response = client.post("/api/simulate", json=opening_request())
    assert response.status_code == 200
    result = response.json()
    assert len(result["own"]["after"]["creatures"]) == 6
    assert "statuses" in result["opponent"]["after"]["creatures"][0]
    assert "mp" in result["shared_after"]
    assert result["warnings"]
    assert client.post("/api/simulate", json={}).status_code == 422


def test_catalog_failure_is_reported_without_breaking_startup(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from manual_input.server import create_app

    def unavailable_catalog(self):
        raise ValueError("test database unavailable")

    monkeypatch.setattr(Catalog, "_load", unavailable_catalog)
    client = TestClient(create_app(recorder=BattleRecorder(tmp_path)))
    response = client.get("/api/catalog")
    assert response.status_code == 503
    assert "test database unavailable" in response.json()["error"]
    assert client.post("/api/new-battle").status_code == 201


@pytest.mark.parametrize("window_size", ["1440,900", "800,900"])
def test_browser_keyboard_and_checkpoint_flow(tmp_path, window_size):
    chrome = shutil.which("chrome") or "C:/Program Files/Google/Chrome/Application/chrome.exe"
    if not Path(chrome).exists():
        pytest.skip("Chrome is required for the headless interaction regression")
    project = Path(__file__).resolve().parents[1]
    static = project / "manual_input" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    styles = (static / "app.css").read_text(encoding="utf-8")
    app = (static / "app.js").read_text(encoding="utf-8")
    comparison = (static / "comparison.js").read_text(encoding="utf-8")
    icons = (static / "status-icons.js").read_text(encoding="utf-8")
    fixture = (project / "tests" / "manual_input_browser.js").read_text(encoding="utf-8")
    mocks, checks = fixture.split("void 'BROWSER_CHECKS';", 1)
    html = html.replace('<link rel="stylesheet" href="/app.css">', '<style>' + styles + '</style>')
    html = html.replace('<script src="/status-icons.js"></script>', '<script>' + icons + '</script>')
    html = html.replace('<script src="/comparison.js"></script>', '<script>' + comparison + '</script>')
    html = html.replace('<script src="/app.js"></script>', '<script>' + mocks + '</script><script>' + app + '</script><script>' + checks + '</script>')
    fixture_path = tmp_path / "manual-input.html"
    fixture_path.write_text(html, encoding="utf-8")
    result = subprocess.run(
        [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--allow-file-access-from-files", "--window-size=" + window_size,
         "--user-data-dir=" + str(tmp_path / "profile"), "--virtual-time-budget=10000",
         "--screenshot=" + str(tmp_path / "browser.png"), "--dump-dom", fixture_path.as_uri()],
        capture_output=True, encoding="utf-8", timeout=40,
    )
    marker = re.search(r'<pre id="test-result"[^>]*>([^<]*)</pre>', result.stdout)
    assert marker, result.stderr + result.stdout[-2000:]
    report = json.loads(marker.group(1).replace("&quot;", '"').replace("&amp;", "&"))
    assert report["passed"], report
