"""Replay manually recorded 1002 rounds as independent one-turn cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nrc_core import BattleSimulator
from scripts.manual_verify_core import bind_catalog_fields
from nrc_core.pokemon_db import get_pokemon
from nrc_core.skill_db import get_all_skills


def u(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


PAINTER = u(r"\u753b\u95f4\u6c89\u94c1\u517d")
FLOWER = u(r"\u8e66\u8e66\u82b1")
FOX = u(r"\u5c16\u5634\u72d0\u4ed9")
FROG = u(r"\u6df1\u6e0a\u86d9")
CRYSTAL = u(r"\u6676\u77f3\u8717")
GIANT = u(r"\u5de8\u7075\u77f3")
EVIL = u(r"\u6076\u9b54\u72fc")
SEA = u(r"\u6d77\u8c79\u8239\u957f")
SILVER = u(r"\u94f6\u6708\u72fc\u738b")

SKILLS = {
    "claw": u(r"\u8fde\u7eed\u722a\u51fb"), "counter": u(r"\u53cd\u51fb\u62f3"),
    "phantom": u(r"\u5e7b\u8c61"), "drum": u(r"\u9f13\u52b2"),
    "power": u(r"\u529b\u91cf\u589e\u6548"), "greed": u(r"\u8d2a\u5a6a"),
    "sink": u(r"\u6c89\u6eba"), "waves": u(r"\u53e0\u6d6a"),
    "net": u(r"\u7f51\u7f1a"), "triple": u(r"\u4e09\u8fde\u7834"),
    "arrow": u(r"\u706b\u7130\u7bad"), "snow": u(r"\u66b4\u98ce\u96ea"),
    "sun": u(r"\u6652\u592a\u9633"), "guard": u(r"\u9632\u5fa1"),
    "stomp": u(r"\u8dfa\u5730"), "pierce": u(r"\u7a7f\u819b"),
    "sound": u(r"\u9e23\u97f3"), "retreat": u(r"\u5413\u9000"),
    "dart": u(r"\u6bd2\u8a93"), "answer": u(r"\u89c1\u62db\u62c6\u62db"),
    "membrane": u(r"\u8721\u8d28\u819c"), "punch": u(r"\u4e00\u62f3"),
   "slash": u(r"\u65a9\u65ad"), "charge": u(r"\u805a\u80fd"),
    "eclipse": u(r"\u6708\u8680"), "water": "水幕冲击",
}


def creature(name, skills, hp, energy=10, buffs=None, statuses=None):
    return {
        "name": name,
        "base": {"nature": None, "individual_values": None, "stats": None, "bloodline_attributes": None},
        "abilities": [], "skills": [{"name": skill} for skill in skills],
        "state": {"hp": hp, "max_hp": hp, "energy": energy, "buffs": buffs or [], "debuffs": [], "marks": {}, "statuses": statuses or [], "fatigue_turns": 0},
        "entry_count": 1, "metadata": {},
    }


def team(name, creatures, active_index):
    return {"team_name": name, "active_index": active_index, "resonance_magic": None, "creatures": creatures}


def skill(slot):
    return {"kind": "skill", "skill_slot": slot}


def switch(index):
    return {"kind": "switch", "switch_index": index}


def charge():
    return {"kind": "charge"}


OWN_NAMES = [PAINTER, FLOWER, FOX, FROG, CRYSTAL, GIANT]


def _available_roster_name(name):
    if get_pokemon(name):
        return name
    return FROG


def make_case(round_no, own_index, own_action, opponent_index, opponent_action):
    own = [
        creature(_available_roster_name(PAINTER), [SKILLS["claw"], SKILLS["counter"], SKILLS["phantom"], SKILLS["drum"]], 490, buffs=[{"name": "spdef_up", "unit": "+10%", "stacks": 17}] if own_index == 0 and round_no >= 7 else []),
        creature(_available_roster_name(FLOWER), [SKILLS["dart"], SKILLS["answer"], SKILLS["counter"], SKILLS["membrane"]], 426),
        creature(_available_roster_name(FOX), [SKILLS["arrow"], SKILLS["snow"], SKILLS["sun"], SKILLS["guard"]], 406),
        creature(_available_roster_name(FROG), [SKILLS["sink"], SKILLS["waves"], SKILLS["net"], SKILLS["triple"]], 403),
        creature(_available_roster_name(CRYSTAL), [SKILLS["claw"], SKILLS["counter"], SKILLS["phantom"], SKILLS["guard"]], 376),
        creature(_available_roster_name(GIANT), [SKILLS["stomp"], SKILLS["pierce"], SKILLS["sun"], SKILLS["retreat"]], 426),
    ]
    opponents = [
        creature(EVIL, [SKILLS["power"], SKILLS["greed"], SKILLS["punch"], SKILLS["slash"]], 100),
        creature(SEA, [SKILLS["punch"], SKILLS["slash"], SKILLS["water"], SKILLS["eclipse"]], 100),
        creature(SILVER, [SKILLS["eclipse"], SKILLS["charge"], SKILLS["slash"], SKILLS["punch"]], 100, statuses=[{"name": "poison", "unit": "poison", "stacks": 2}] if round_no >= 13 else []),
    ]
    return {
        "own_team": team("1002-own", own, own_index), "opponent_team": team("1002-opponent", opponents, opponent_index),
        "shared": {"turn": round_no, "weather": None, "weather_turns": None, "mp": {"own": 4, "opponent": 4}, "metadata": {}},
        "own_turn": {"primary": own_action, "items": []}, "opponent_turn": {"primary": opponent_action, "items": []},
        "seed": round_no, "battle_id": "1002", "source": "manual-round-replay",
    }


CASES = [
    (3, 0, skill(1), 0, switch(1)), (4, 0, switch(3), 1, skill(0)),
    (5, 3, switch(2), 1, skill(1)), (6, 2, switch(0), 1, charge()),
    (7, 0, skill(3), 1, skill(0)), (8, 0, switch(5), 1, skill(1)),
    (9, 5, skill(1), 1, charge()), (10, 5, skill(1), 1, skill(2)),
    (11, 5, switch(1), 1, charge()), (12, 1, skill(2), 1, skill(1)),
    (13, 1, skill(3), 2, skill(0)), (14, 1, switch(0), 2, skill(0)),
    (15, 3, skill(0), 2, charge()), (16, 3, skill(3), 2, skill(0)),
]


def _unresolved_skill_names(payload):
    catalog = get_all_skills()
    unresolved = []
    for team_key, action_key in (("own_team", "own_turn"), ("opponent_team", "opponent_turn")):
        action = payload[action_key]["primary"]
        if action.get("kind") != "skill":
            continue
        team = payload[team_key]
        active = team["creatures"][team["active_index"]]
        slot = int(action["skill_slot"])
        name = active["skills"][slot]["name"]
        if name not in catalog:
            unresolved.append({"team": team_key, "slot": slot, "name": name})
    return unresolved


def main():
    simulator = BattleSimulator(Path("data"))
    results = []
    for round_no, own_index, own_action, opponent_index, opponent_action in CASES:
        required = [OWN_NAMES[own_index]]
        if own_action.get("kind") == "switch":
            required.append(OWN_NAMES[own_action["switch_index"]])
        missing = [name for name in required if not get_pokemon(name)]
        if missing:
            results.append({
                "round": round_no,
                "status": "skipped_missing_exact_database_name",
                "missing_names": missing,
            })
            continue
        payload = bind_catalog_fields(make_case(round_no, own_index, own_action, opponent_index, opponent_action), Path("data"))
        unresolved = _unresolved_skill_names(payload)
        if unresolved:
            results.append({
                "round": round_no,
                "status": "skipped_missing_exact_skill_name",
                "unresolved_skills": unresolved,
            })
            continue
        try:
            result = simulator.resolve_turn(payload).to_json()
            results.append({"round": round_no, "status": "ok", "events": [
                {"team": event.get("team"), "skill": event.get("skill"), "damage": event.get("final_damage"), "debug": event.get("debug", {}).get("damage_calculation", {})}
                for event in result.get("events", []) if event.get("type") == "skill"
            ], "warnings": result.get("warnings", []), "unresolved_skills": []})
        except Exception as exc:
            results.append({"round": round_no, "status": "error", "error": repr(exc)})
    output = Path("data/1002_round_replay_2026-10-05.json")
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
