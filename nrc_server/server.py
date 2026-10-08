from __future__ import annotations

import argparse
import copy
import re
import secrets
import sys
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pypinyin import Style, lazy_pinyin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nrc_platform import BattlePlatform
from nrc_platform.input import merge_creature_spec
from nrc_platform.platform import PlatformError
from nrc_core.pokemon_nature_table import NATURE_BONUSES

TYPE_NAMES = {
    "normal": "普通", "fire": "火", "water": "水", "electric": "电", "grass": "草",
    "ice": "冰", "fighting": "武", "poison": "毒", "ground": "地", "flying": "翼",
    "psychic": "幻", "bug": "虫", "ghost": "幽", "dragon": "龙", "dark": "恶",
    "steel": "机械", "fairy": "萌", "light": "光",
}

HIDDEN_EVENT_TYPES = {"display_power", "ability_candidate", "weather_candidate", "counter_candidate"}

MANUAL_LOADOUTS = {
    "画间沉铁兽": ["连续爪击", "反击拳", "幻象", "鼓劲"],
    "蹦蹦花": ["毒誓", "见招拆招", "反击拳", "蜡质膜"],
    "尖嘴狐仙": ["火焰箭", "暴风雪", "晒太阳", "防御"],
    "深渊蛙": ["沉溺", "叠浪", "网缚", "三连破"],
    "晶石蜗": ["震击", "跺地", "锐利眼神", "蓄势待发"],
    "巨灵石": ["跺地", "穿膛", "晒太阳", "吓退"],
    "恶魔狼": ["力量增效", "贪婪", "一拳", "斩断"],
    "海豹船长": ["一拳", "水幕冲击", "反击拳", "斩断"],
    "银月狼王": ["月蚀", "叠加态", "反击拳", "斩断"],
    "魔力猫": ["孢子", "斩断", "光合作用", "月蚀"],
}


def _error_response(error: Exception) -> JSONResponse:
    if isinstance(error, PlatformError):
        return JSONResponse(error.to_dict(), status_code=422)
    if isinstance(error, (ValueError, TypeError)):
        return JSONResponse({"error": str(error)}, status_code=422)
    return JSONResponse({"error": f"{type(error).__name__}: {error}"}, status_code=500)


def _new_player_token() -> str:
    return secrets.token_urlsafe(18)


def _view_side(session: Mapping[str, Any], request: Request, *, allow_legacy: bool = False) -> tuple[str, str] | None:
    """Return (token, platform side) for this browser session."""
    players = session.get("players") or {}
    token = request.headers.get("X-Player-Token", "")
    if token and token in players:
        return token, str(players[token])
    if allow_legacy and len(players) == 1:
        token, side = next(iter(players.items()))
        return str(token), str(side)
    return None


def _swap_team_code(event: dict[str, Any], side: str) -> dict[str, Any]:
    if side != "opponent":
        return event
    if event.get("team") in {"a", "b"}:
        event["team"] = "b" if event["team"] == "a" else "a"
    for key in ("active", "hp", "mp"):
        value = event.get(key)
        if isinstance(value, dict) and "a" in value and "b" in value:
            event[key] = {"a": value["b"], "b": value["a"]}
    return event


def _visible_events(session: Mapping[str, Any], side: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in session.get("history", []):
        turn = entry.get("turn", "")
        for raw in entry.get("events", []):
            if raw.get("type") in HIDDEN_EVENT_TYPES:
                continue
            event = _swap_team_code(copy.deepcopy(dict(raw)), side)
            event.setdefault("turn", turn)
            if event.get("type") == "skill":
                if event.get("team") == "b":
                    event["skill"] = "未知技能"
                    event.pop("switched_to", None)
                elif event.get("team") == "a":
                    event.pop("target_switched_to", None)
            if event.get("type") == "selection":
                if event.get("team") == "b":
                    event["status"] = "locked"
                    event.pop("skill", None)
                    event.pop("action_key", None)
                else:
                    event["status"] = "locked"
            if event.get("type") == "state_change" and event.get("team") == "b":
                event["pokemon"] = "未知精灵"
                event["changes"] = [
                    change for change in event.get("changes", [])
                    if change.get("kind") not in {"hp", "energy", "ability"}
                    and not str(change.get("name", "")).startswith("skill_cost:")
                ]
            if event.get("type") == "turn":
                for phase in ("before", "after"):
                    state = event.get(phase)
                    if isinstance(state, dict):
                        active = state.get("active")
                        if isinstance(active, dict) and "b" in active:
                            active["b"] = "未知"
                        hp = state.get("hp")
                        if isinstance(hp, dict) and "b" in hp:
                            hp.pop("b", None)
                        actions = state.get("actions")
                        if isinstance(actions, dict) and "b" in actions:
                            actions["b"] = {"kind": actions["b"].get("kind", "unknown")}
            event["event_index"] = len(result)
            result.append(event)
    return result


def _visible_event_count(session: Mapping[str, Any]) -> int:
    return sum(
        1
        for entry in session.get("history", [])
        for event in entry.get("events", [])
        if event.get("type") not in HIDDEN_EVENT_TYPES
    )


def _selection_event(platform: BattlePlatform, battle_id: str, side: str, action_key: str, turn: int) -> dict[str, Any]:
    event: dict[str, Any] = {"type": "selection", "team": "a" if side == "own" else "b", "action_key": action_key, "turn": turn}
    try:
        actions = platform.get_legal_actions(battle_id, side).get("actions", [])
        selected = next((item for item in actions if item.get("key") == action_key), None)
        primary = (selected or {}).get("payload", {}).get("primary", {})
        event["kind"] = primary.get("kind", "unknown")
        if primary.get("skill_name"):
            event["skill"] = primary["skill_name"]
        if primary.get("switch_index") is not None:
            event["switch_index"] = primary["switch_index"]
        if "|resonance=" in action_key:
            event["resonance"] = action_key.rsplit("|resonance=", 1)[1]
    except Exception:
        event["kind"] = "unknown"
    return event


def _redact_observation(data: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only information a player is allowed to learn about the opponent."""
    result = copy.deepcopy(dict(data))
    opponent = []
    for item in result.get("opponent_team", []):
        visible = {
            "index": item.get("index"),
            "name": item.get("name"),
            "types": item.get("types", []),
            "active": bool(item.get("active")),
            "fainted": bool(item.get("fainted")),
            "status": item.get("status"),
            "poison_stacks": item.get("poison_stacks", 0),
            "burn_stacks": item.get("burn_stacks", 0),
            "freeze_stacks": item.get("freeze_stacks", 0),
            "frostbite_damage": item.get("frostbite_damage", 0),
            "electric_stacks": item.get("electric_stacks", 0),
            "cute_stacks": item.get("cute_stacks", 0),
        }
        if visible["active"]:
            max_hp = item.get("max_hp")
            hp = item.get("hp")
            visible["hp_percent"] = None if not max_hp or hp is None else max(0, min(100, round(float(hp) / float(max_hp) * 100)))
            visible["energy"] = item.get("energy")
        opponent.append(visible)
    result["opponent_team"] = opponent
    return result


def _public_summary(session: Mapping[str, Any], side: str | None = None) -> dict[str, Any]:
    players = session.get("players") or {}
    teams = session.get("teams") or {}
    confirmed = session.get("confirmed") or {"own": False, "opponent": False}
    submitted = session.get("roster_submitted") or {"own": False, "opponent": False}
    ready = [name for name, roster in teams.items() if roster]
    pending = set(session.get("pending") or [])
    own_side = side if side in {"own", "opponent"} else None
    winner = session.get("winner")
    if own_side and winner is not None:
        winner = int(winner) if (winner == 0 and own_side == "own") or (winner == 1 and own_side == "opponent") else 1 - int(winner)
    if session.get("initialized"):
        waiting_for = "battle"
    elif len(players) < 2:
        waiting_for = "opponent"
    elif own_side and not submitted.get(own_side):
        waiting_for = "roster"
    elif own_side and not confirmed.get(own_side):
        waiting_for = "first_choice"
    else:
        waiting_for = "opponent_first_choice" if not all(confirmed.values()) else "battle"
    return {
        "battle_id": session["battle_id"],
        "mode": session.get("mode", "full"),
        "turn": session.get("turn", 1),
        "phase": session.get("phase", "waiting_for_players"),
        "decision_index": session.get("decision_index", 0),
        "status": "finished" if session.get("terminal") else "active" if session.get("initialized") else "waiting",
        "players": len(players),
        "joined": len(players) >= 2,
        "ready": ready,
        "initialized": bool(session.get("initialized")),
        "roster_submitted": bool(own_side and submitted.get(own_side)),
        "confirmed": bool(own_side and confirmed.get(own_side)),
        "confirmed_sides": [name for name, value in confirmed.items() if value],
        "waiting_for": waiting_for,
        "pending": bool(own_side and own_side in pending),
        "terminal": bool(session.get("terminal")),
        "winner": winner,
        "event_count": _visible_event_count(session),
        "roster": copy.deepcopy(teams.get(own_side) or []) if own_side else [],
    }

def _base_name(name: str) -> str:
    return re.split(r'[（(]', str(name), maxsplit=1)[0].strip()


def _base_name(name: str) -> str:
    return re.split(r"[\(\uff08]", str(name), maxsplit=1)[0].strip()


def _pinyin(value: str) -> tuple[str, str]:
    syllables = lazy_pinyin(value)
    return "".join(syllables), "".join(lazy_pinyin(value, style=Style.FIRST_LETTER))


@lru_cache(maxsize=8)
def _asset_files(root: Path, directory: str) -> tuple[Path, ...]:
    folder = root / directory
    if not folder.exists():
        return ()
    return tuple(path for path in folder.iterdir() if path.is_file())


def _asset(root: Path, directory: str, name: str, *, portrait: bool = False) -> str | None:
    tokens = [part for part in re.split(r'[（）()]', name) if part]
    candidates = [path for path in _asset_files(root, directory) if all(token in path.stem for token in tokens)]
    if not candidates:
        candidates = [path for path in _asset_files(root, directory) if _base_name(name) in path.stem]
    if portrait:
        candidates = [path for path in candidates if "portrait" in path.stem] or candidates
    else:
        candidates = [path for path in candidates if "portrait" not in path.stem] or candidates
    if not candidates:
        return None
    candidates.sort(key=lambda path: ("_main_" not in path.stem, len(path.name)))
    return "/assets/" + directory + "/" + candidates[0].name


def _asset_exact(root: Path, directory: str, filename: str) -> str | None:
    path = root / directory / filename
    return f"/assets/{directory}/{filename}" if path.is_file() else None


def _distribution_options(catalog: Any, name: str, kind: str) -> list[dict[str, Any]]:
    rows = catalog.get_distribution(name, kind)
    return [{"name": str(row.get("item", "")), "percentage": float(row.get("percentage", 0))} for row in rows if row.get("item")]


def _customization_options(catalog: Any, name: str) -> dict[str, Any]:
    nature_rows = _distribution_options(catalog, name, "nature")
    bloodline_rows = _distribution_options(catalog, name, "blood")
    aptitude_rows = _distribution_options(catalog, name, "talent")
    if not nature_rows:
        nature_rows = [{"name": nature, "percentage": 0} for nature in NATURE_BONUSES]
    if not bloodline_rows:
        all_bloodlines = sorted({str(row.get("item")) for (spirit, kind), rows in catalog.distributions.items() if kind == "blood" for row in rows if row.get("item")})
        bloodline_rows = [{"name": bloodline, "percentage": 0} for bloodline in all_bloodlines]
    bonus = {
        nature: {key: float(value) for key, value in values.items() if float(value)}
        for nature, values in NATURE_BONUSES.items()
    }
    def enrich(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            item = dict(row)
            pinyin, initials = _pinyin(str(item.get("name", "")))
            item.update({"pinyin": pinyin, "initials": initials})
            result.append(item)
        return result

    return {
        "natures": enrich(nature_rows),
        "nature_bonus": bonus,
        "bloodlines": enrich(bloodline_rows),
        "aptitudes": enrich(aptitude_rows),
    }


def _catalog_index(platform: BattlePlatform, data_root: Path) -> dict[str, Any]:
    catalog = platform._catalog.catalog
    forms: dict[str, list[dict[str, Any]]] = {}
    for name, record in catalog.pokemon.items():
        pinyin, initials = _pinyin(_base_name(name))
        forms.setdefault(_base_name(name), []).append({
            "name": name,
            "base_name": _base_name(name),
            "types": list(record.get("types", ())),
            "ability": record.get("ability", ""),
            "skills": list(record.get("skills", ())),
            "default_skills": list(MANUAL_LOADOUTS.get(_base_name(name), record.get("skills", ()))[:4]),
            "portrait": _asset(data_root, "spirit_icons", name, portrait=True),
            "art": _asset(data_root, "spirit_icons", name),
            "pinyin": pinyin,
            "initials": initials,
            "customization": _customization_options(catalog, name),
            "aliases": ["bbh"] if _pinyin(_base_name(name))[1].casefold() == "bbh" else [],
        })
    pokemon = [{"name": base, "pinyin": _pinyin(base)[0], "initials": _pinyin(base)[1], "aliases": sorted({alias for form in values for alias in form.get("aliases", [])}), "forms": values} for base, values in sorted(forms.items())]
    skills = []
    for name, skill in catalog.skills.items():
        element = getattr(getattr(skill, "skill_type", None), "value", "normal")
        skills.append({
            "name": name,
            "pinyin": _pinyin(name)[0],
            "initials": _pinyin(name)[1],
            "element": TYPE_NAMES.get(element, element),
            "element_key": element,
            "category": getattr(getattr(skill, "category", None), "value", "状态"),
            "energy_cost": int(skill.energy_cost),
            "power": int(skill.power),
            "icon": _asset(data_root, "skill_icons", name),
            "description": str(getattr(skill, "description", "") or catalog.skill_descriptions.get(name, "")),
        })
    return {"pokemon": pokemon, "skills": sorted(skills, key=lambda row: row["name"])}

def create_app() -> FastAPI:
    app = FastAPI(title="NRC Battle Server")
    app.state.platform = BattlePlatform()
    app.state.sessions: dict[str, dict[str, Any]] = {}
    data_root = ROOT / "data"
    static_root = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_root), name="static")
    app.mount("/assets", StaticFiles(directory=data_root), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static_root / "index.html")

    @app.get("/api/catalog/index")
    def catalog_index() -> Any:
        try:
            if not hasattr(app.state, "catalog_index"):
                app.state.catalog_index = _catalog_index(app.state.platform, data_root)
            return app.state.catalog_index
        except Exception as error:
            return _error_response(error)

    @app.get("/api/catalog")
    def catalog(kind: str = Query(default="pokemon"), q: str = Query(default="")) -> Any:
        try:
            index = catalog_index()
            rows = index.get("pokemon" if kind == "pokemon" else "skills", [])
            text = q.strip().casefold()
            if not text:
                return rows
            return [row for row in rows if text in row["name"].casefold() or text in row["pinyin"] or text in row["initials"]][:30]
        except Exception as error:
            return _error_response(error)

    @app.get("/api/pokemon/{name}")
    def pokemon_detail(name: str) -> Any:
        try:
            record = _resolve_record(app.state.platform, name)
            if record is None:
                return JSONResponse({"error": "pokemon not found"}, status_code=404)
            return _creature_preview(app.state.platform, data_root, record["name"])
        except Exception as error:
            return _error_response(error)

    @app.post("/api/pokemon/preview")
    async def pokemon_preview(request: Request) -> Any:
        try:
            payload = await request.json()
            name = str(payload.get("name") or "").strip()
            record = _resolve_record(app.state.platform, name)
            if record is None:
                return JSONResponse({"error": "pokemon not found"}, status_code=404)
            creature = merge_creature_spec({
                "name": name,
                "base": copy.deepcopy(payload.get("base") or {}),
                "skills": copy.deepcopy(payload.get("skills") or []),
            })
            creature["name"] = record["name"]
            result = app.state.platform.preview_creature(creature)
            form_name = result.get("name", record["name"])
            bloodline = next(iter(result.get("bloodline_attributes") or []), "")
            stat_files = {
                "hp": "\u751f\u547d.png",
                "atk": "\u653b\u51fb.png",
                "def": "\u7269\u9632.png",
                "spatk": "\u9b54\u653b.png",
                "spdef": "\u9b54\u9632.png",
                "speed": "\u901f\u5ea6.png",
            }
            result.update({
                "portrait": _asset(data_root, "spirit_icons", form_name, portrait=True),
                "art": _asset(data_root, "spirit_icons", form_name),
                "bloodline_icon": _asset(data_root, "icon_blood", bloodline) if bloodline else None,
                "stat_icons": {key: _asset_exact(data_root, "icon_aptitudes", filename) for key, filename in stat_files.items()},
            })
            return result
        except Exception as error:
            return _error_response(error)

    @app.post("/api/battles")
    async def create_battle(request: Request) -> Any:
        try:
            payload = await request.json()
            mode = str(payload.get("mode", "full"))
            result = app.state.platform.create_battle(mode=mode, seed=payload.get("seed"))
            player_token = _new_player_token()
            app.state.sessions[result.battle_id] = {
                "battle_id": result.battle_id, "mode": mode, "turn": 1, "phase": "setup",
                "decision_index": 0, "teams": {"own": None, "opponent": None}, "pending": [],
                "history": [], "terminal": False, "winner": None, "manifest": dict(result.manifest),
                "players": {player_token: "own"}, "initialized": False, "confirmed": {"own": False, "opponent": False},
                "roster_submitted": {"own": False, "opponent": False}, "active_index": {"own": None, "opponent": None},
            }
            response = result.to_dict()
            response.update({"player_token": player_token, "side": "own", "status": "waiting"})
            return response
        except Exception as error:
            return _error_response(error)

    @app.post("/api/battles/{battle_id}/join")
    async def join_battle(battle_id: str, request: Request) -> Any:
        try:
            session = _session(app, battle_id)
            current = _view_side(session, request)
            if current:
                token, side = current
                return {"player_token": token, "side": side, **_public_summary(session, side)}
            players = session.setdefault("players", {})
            if len(players) >= 2:
                raise ValueError("battle already has two players")
            player_token = _new_player_token()
            players[player_token] = "opponent"
            return {"player_token": player_token, "side": "opponent", **_public_summary(session, "opponent")}
        except Exception as error:
            return _error_response(error)

    @app.get("/api/battles/{battle_id}")
    def battle_summary(battle_id: str, request: Request) -> Any:
        session = app.state.sessions.get(battle_id)
        if session is None:
            return JSONResponse({"error": "battle not found"}, status_code=404)
        current = _view_side(session, request, allow_legacy=True)
        return _public_summary(session, current[1] if current else None)

    @app.get("/api/battles/{battle_id}/opponent-roster")
    def opponent_roster(battle_id: str, request: Request) -> Any:
        try:
            session = _session(app, battle_id)
            current = _view_side(session, request, allow_legacy=True)
            if not current:
                raise ValueError("player token is required")
            side = current[1]
            other_side = "opponent" if side == "own" else "own"
            teams = session.get("teams") or {}
            return {
                "battle_id": battle_id,
                "side": side,
                "opponent_side": other_side,
                "submitted": bool((session.get("roster_submitted") or {}).get(other_side)),
                "confirmed": bool((session.get("confirmed") or {}).get(other_side)),
                "active_index": (session.get("active_index") or {}).get(other_side),
                "roster": copy.deepcopy(teams.get(other_side) or []),
            }
        except Exception as error:
            return _error_response(error)

    @app.post("/api/battles/{battle_id}/rosters")
    async def set_rosters(battle_id: str, request: Request) -> Any:
        try:
            session = _session(app, battle_id)
            payload = await request.json()
            current = _view_side(session, request, allow_legacy=True)
            teams = payload.get("teams") or {}
            if current and ("roster" in payload or not teams.get("opponent")):
                if session.get("initialized"):
                    raise ValueError("battle has already started")
                side = current[1]
                raw = payload.get("roster", teams.get("own"))
                roster = _normalize_roster(app.state.platform, raw, allow_empty=False)
                active_index = int(payload.get("active_index", 0))
                if active_index < 0 or active_index >= len(roster):
                    raise ValueError("active_index must point to a creature in the roster")
                session["teams"][side] = roster
                session["active_index"][side] = active_index
                session["roster_submitted"][side] = True
                session["confirmed"][side] = bool(payload.get("confirm", False))
                session["phase"] = "waiting_for_first_choice"
                initialized = False
                if all(session["confirmed"].values()) and all(session["teams"].values()):
                    own_result = app.state.platform.set_roster(
                        battle_id, "own", {"creatures": session["teams"]["own"], "active_index": session["active_index"]["own"]},
                        request_id=f"{uuid.uuid4().hex}-own-team",
                    )
                    result = app.state.platform.set_roster(
                        battle_id, "opponent", {"creatures": session["teams"]["opponent"], "active_index": session["active_index"]["opponent"]},
                        request_id=f"{uuid.uuid4().hex}-opponent-team",
                    )
                    initialized = bool(result.initialized or own_result.initialized)
                    if initialized:
                        session["initialized"] = True
                        session["phase"] = result.phase
                        session.setdefault("history", []).append({"turn": 1, "events": [{"type": "round_start", "turn": 1}]})
                        session["history"].append({"turn": 1, "events": [{"type": "battle_start", "message": "对战开始，双方选择行动"}]})
                return {
                    "accepted": True,
                    "initialized": initialized,
                    "phase": session["phase"],
                    "side": side,
                    "active_index": active_index,
                    **_public_summary(session, side),
                }

            # Compatibility path for the original single-browser console.
            own = _normalize_roster(app.state.platform, teams.get("own"), allow_empty=False)
            opponent = _normalize_roster(app.state.platform, teams.get("opponent"), allow_empty=False)
            app.state.platform.set_roster(battle_id, "own", {"creatures": own}, request_id=f"{uuid.uuid4().hex}-own-team")
            result = app.state.platform.set_roster(battle_id, "opponent", {"creatures": opponent}, request_id=f"{uuid.uuid4().hex}-opponent-team")
            session["teams"] = {"own": own, "opponent": opponent}
            session["phase"] = result.phase
            session["initialized"] = bool(result.initialized)
            session["players"] = session.get("players") or {_new_player_token(): "own"}
            return {"accepted": result.accepted, "initialized": result.initialized, "phase": result.phase, "teams": session["teams"]}
        except Exception as error:
            return _error_response(error)

    @app.get("/api/battles/{battle_id}/display")
    def display(battle_id: str, request: Request, side: str = Query(default="own")) -> Any:
        try:
            session = _session(app, battle_id)
            current = _view_side(session, request)
            actual_side = current[1] if current else side
            result = app.state.platform.get_display_info(battle_id, actual_side)
            for skill in result.get("skills", []):
                name = str(skill.get("name") or "")
                meta = app.state.platform._catalog.catalog.skills.get(name)
                element = getattr(getattr(meta, "skill_type", None), "value", "normal")
                multiplier = skill.get("type_effectiveness")
                relation = "无" if multiplier is None else "双重克制" if float(multiplier) > 2 else "克制" if float(multiplier) > 1 else "双重抵抗" if 0 < float(multiplier) < 0.5 else "抵抗" if 0 < float(multiplier) < 1 else "平衡"
                skill.update({
                    "icon": _asset(data_root, "skill_icons", name),
                    "description": str(getattr(meta, "description", "") or ""),
                    "element": TYPE_NAMES.get(element, element),
                    "type_icon": _asset(data_root, "dept_icons", TYPE_NAMES.get(element, element)),
                    "effect_icon": _asset(data_root, "icon_dept_relation", relation),
                })
            return result
        except Exception as error:
            return _error_response(error)

    @app.get("/api/battles/{battle_id}/actions")
    def actions(battle_id: str, request: Request, side: str = Query(default="own")) -> Any:
        try:
            session = _session(app, battle_id)
            current = _view_side(session, request)
            actual_side = current[1] if current else side
            return app.state.platform.get_legal_actions(battle_id, actual_side)
        except Exception as error:
            return _error_response(error)

    @app.get("/api/battles/{battle_id}/state")
    def public_state(battle_id: str, request: Request, side: str = Query(default="own")) -> Any:
        try:
            session = _session(app, battle_id)
            current = _view_side(session, request)
            actual_side = current[1] if current else side
            result = app.state.platform.get_public_observation(battle_id, actual_side)
            if result.get("data"):
                result["data"] = _redact_observation(result["data"])
                for item in result["data"].get("opponent_team", []):
                    item["portrait"] = _asset(data_root, "spirit_icons", str(item.get("name") or ""), portrait=True)
                    item["art"] = _asset(data_root, "spirit_icons", str(item.get("name") or ""))
            return result
        except Exception as error:
            return _error_response(error)

    @app.get("/api/battles/{battle_id}/operation")
    def operation(battle_id: str, request: Request, since: int = Query(default=-1)) -> Any:
        try:
            session = _session(app, battle_id)
            current = _view_side(session, request, allow_legacy=True)
            if not current:
                raise ValueError("player token is required")
            side = current[1]
            opponent = "opponent" if side == "own" else "own"
            pending = set(session.get("pending") or [])
            decision_index = int(session.get("decision_index", 0))
            return {
                "battle_id": battle_id,
                "side": side,
                "own_pending": side in pending,
                "opponent_pending": opponent in pending,
                "resolved": since >= 0 and decision_index != since,
                "decision_index": decision_index,
                "turn": session.get("turn", 1),
                "phase": session.get("phase", "waiting_for_players"),
                "terminal": bool(session.get("terminal")),
            }
        except Exception as error:
            return _error_response(error)

    @app.get("/api/battles/{battle_id}/events")
    def battle_events(battle_id: str, request: Request, since: int = Query(default=0)) -> Any:
        try:
            session = _session(app, battle_id)
            current = _view_side(session, request, allow_legacy=True)
            if not current:
                raise ValueError("player token is required")
            events = _visible_events(session, current[1])
            cursor = max(0, min(int(since), len(events)))
            return {
                "battle_id": battle_id,
                "side": current[1],
                "events": events[cursor:],
                "cursor": len(events),
                "total": len(events),
            }
        except Exception as error:
            return _error_response(error)

    @app.post("/api/battles/{battle_id}/selection")
    async def select_action(battle_id: str, request: Request) -> Any:
        try:
            session = _session(app, battle_id)
            payload = await request.json()
            side = str(payload.get("side", ""))
            key = str(payload.get("action_key", ""))
            if session["terminal"]:
                raise ValueError("battle has ended")
            current = _view_side(session, request)
            actual_side = current[1] if current else side
            if actual_side not in {"own", "opponent"} or not key:
                raise ValueError("side and action_key are required")
            if actual_side in session["pending"]:
                raise ValueError("that side already locked an action")
            selection_event = _selection_event(app.state.platform, battle_id, actual_side, key, session["turn"])
            result = app.state.platform.submit_selection(battle_id, actual_side, key, request_id=str(uuid.uuid4()))
            session["history"].append({
                "turn": session["turn"],
                "events": [selection_event],
            })
            session["pending"].append(actual_side)
            session["next_required"] = list(result.next_required)
            if result.resolved:
                events = list((result.result or {}).get("events", []))
                session["history"].append({"turn": session["turn"], "events": events})
                snapshot = app.state.platform.get_public_observation(battle_id, "own")
                session["turn"] = snapshot.turn
                session["phase"] = result.phase
                session["decision_index"] = result.decision_index
                session["pending"] = []
                session["terminal"] = bool(result.terminated)
                session["winner"] = result.winner
                if not session["terminal"]:
                    session["history"].append({"turn": session["turn"], "events": [{"type": "round_start", "turn": session["turn"]}]})
            response = result.to_dict()
            response["side"] = actual_side
            response["event_count"] = _visible_event_count(session)
            return response
        except Exception as error:
            return _error_response(error)

    return app


def _resolve_record(platform: BattlePlatform, name: str) -> Mapping[str, Any] | None:
    parsed = merge_creature_spec({"name": name})
    direct = platform.resolve_pokemon(parsed.get("name", ""))
    if direct:
        return direct
    catalog = platform._catalog.catalog
    direct = catalog.get_pokemon(name)
    if direct:
        return direct
    normalized = name.replace("(", "（").replace(")", "）").replace("（短毛球）", "（短毛球形态）").replace("（火山琉璃）", "（火山琉璃的样子）")
    direct = catalog.get_pokemon(normalized)
    if direct:
        return direct
    base = _base_name(name)
    return next((record for key, record in catalog.pokemon.items() if _base_name(key) == base), None)


def _creature_preview(platform: BattlePlatform, data_root: Path, name: str) -> dict[str, Any]:
    record = _resolve_record(platform, name) or {}
    base = _base_name(name)
    pinyin, initials = _pinyin(base)
    return {
        "name": record.get("name", name), "base_name": base, "types": list(record.get("types", ())),
        "ability": record.get("ability", ""), "skills": list(record.get("skills", ())),
        "portrait": _asset(data_root, "spirit_icons", record.get("name", name), portrait=True),
        "art": _asset(data_root, "spirit_icons", record.get("name", name)), "pinyin": pinyin, "initials": initials,
    }


def _normalize_roster(platform: BattlePlatform, raw: Any, *, allow_empty: bool) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("invalid roster")
    result = []
    for item in raw:
        if isinstance(item, str): item = {"name": item}
        if not isinstance(item, dict): continue
        item = merge_creature_spec(item)
        record = _resolve_record(platform, str(item.get("name", "")).strip())
        if record is None: raise ValueError(f"unknown creature: {item.get('name')}")
        name = str(record["name"]); base = _base_name(name)
        skill_names = [skill.get("name") if isinstance(skill, dict) else skill for skill in (item.get("skills") or MANUAL_LOADOUTS.get(base) or list(record.get("skills", ()))[:4])]
        if len(skill_names) < 4: raise ValueError(f"{name} must provide all skill slots")
        creature = copy.deepcopy(item)
        creature.update({"name": name, "skills": [{"name": skill} for skill in skill_names[:4]]})
        result.append(creature)
    if not result and not allow_empty: raise ValueError("each team needs at least one creature")
    return result


def _session(app: FastAPI, battle_id: str) -> dict[str, Any]:
    session = app.state.sessions.get(battle_id)
    if session is None: raise ValueError("battle not found")
    return session


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the NRC battle UI")
    parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("nrc_server.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__": main()
