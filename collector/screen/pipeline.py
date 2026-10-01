"""End-to-end screen collection and simulator comparison."""

from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

from nrc_core import BattleSimulator

from .recognizer import ScreenRecognizer, VideoFrameSource, load_manifest

ACTION_SCREENS = {"perform", "perform_counter"}


def _nearest_manual_event(observation: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any] | None:
    timestamp = float(observation["timestamp"])
    candidates = [event for event in events if abs(float(event.get("time", -999)) - timestamp) <= 2.0]
    return min(candidates, key=lambda event: abs(float(event.get("time", -999)) - timestamp)) if candidates else None


class TurnSegmenter:
    def __init__(self, pair_window: float = 12.0):
        self.pair_window = pair_window

    def build(self, observations: list[dict[str, Any]], manual_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        actions = []
        for observation in observations:
            if observation["screen"] not in ACTION_SCREENS:
                continue
            event = copy.deepcopy(observation)
            manual = _nearest_manual_event(observation, manual_events)
            if manual:
                event.update({key: value for key, value in manual.items() if key != "time"})
                event["manual_override"] = True
            else:
                event["manual_override"] = False
            event.setdefault("side", "own" if observation["screen"] == "perform" else "opponent")
            event.setdefault("kind", "skill" if event.get("skill_name") else "unknown_action")
            actions.append(event)

        turns: list[dict[str, Any]] = []
        for action in actions:
            if not turns:
                turns.append(self._new_turn(action, "first_action"))
                continue
            current = turns[-1]
            previous = current["actions"][-1]
            opposite = action.get("side") and previous.get("side") and action["side"] != previous["side"]
            close = float(action["timestamp"]) - float(previous["timestamp"]) <= self.pair_window
            already_side = any(item.get("side") == action.get("side") for item in current["actions"])
            if opposite and close and not already_side:
                current["actions"].append(action)
                current["end"] = action["timestamp"]
                current["boundary_reason"] = "paired_opposite_sides"
            else:
                reason = "same_side_or_gap" if already_side or not close else "ambiguous_side"
                turns.append(self._new_turn(action, reason))
        for index, turn in enumerate(turns, start=1):
            turn["turn"] = index
        return turns

    @staticmethod
    def _new_turn(action: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "turn": 0, "start": action["timestamp"], "end": action["timestamp"],
            "boundary_reason": reason, "actions": [action],
        }


class ScreenCollectionPipeline:
    def __init__(
        self,
        video_path: str | Path,
        output_path: str | Path,
        reference_dir: str | Path,
        data_dir: str | Path,
        sample_fps: float = 5.0,
        manifest: dict[str, Any] | None = None,
    ):
        self.video_path = Path(video_path)
        self.output_path = Path(output_path)
        self.reference_dir = Path(reference_dir)
        self.data_dir = Path(data_dir)
        self.manifest = manifest or {}
        self.source = VideoFrameSource(video_path, sample_fps=sample_fps)
        self.recognizer = ScreenRecognizer(self.reference_dir, self.data_dir / "nrc.db", self.data_dir.parent)
        self.simulator = BattleSimulator(self.data_dir)

    def run(self, simulate: bool = True) -> dict[str, Any]:
        observations = self.recognizer.recognize(self.source)
        turns = TurnSegmenter().build(observations, list(self.manifest.get("events") or []))
        base_request = copy.deepcopy(self.manifest.get("request")) or self._default_request(observations)
        records = []
        state_request = base_request
        for turn in turns:
            record = {
                "turn": turn["turn"], "time": {"start": turn["start"], "end": turn["end"]},
                "boundary_reason": turn["boundary_reason"],
                "observations": [item for item in observations if turn["start"] <= item["timestamp"] <= turn["end"]],
                "actions": turn["actions"], "database_snapshot": self._database_snapshot(turn["actions"]),
                "simulation": None, "comparison": {"status": "not_run", "mismatches": []},
            }
            if simulate:
                request = self._request_for_turn(state_request, turn)
                record["input_request"] = request
                try:
                    result = self.simulator.resolve_turn(request).to_json()
                    record["simulation"] = result
                    record["calculation_trace"] = self._calculation_trace(request, result)
                    record["comparison"] = self._compare_observation(turn, result)
                    state_request = self._advance_request(request, result)
                except Exception as error:
                    record["comparison"] = {"status": "simulation_error", "mismatches": [str(error)]}
            records.append(record)
        payload = {
            "schema_version": 1, "source": "screen_video", "video": self.source.metadata(),
            "ocr_available": self.recognizer.ocr.available, "reference_dir": str(self.reference_dir),
            "observations": observations, "turn_count": len(records), "records": records,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _default_request(self, observations: list[dict[str, Any]]) -> dict[str, Any]:
        own_skills = list(dict.fromkeys(item.get("skill_name") for item in observations if item.get("side") == "own" and item.get("skill_name")))
        opponent_skills = list(dict.fromkeys(item.get("skill_name") for item in observations if item.get("side") == "opponent" and item.get("skill_name")))
        own_skills = own_skills or ["__screen_own_skill"]
        opponent_skills = opponent_skills or ["__screen_opponent_skill"]
        return {
            "own_team": {"team_name": "screen-own", "active_index": 0, "creatures": [self._creature("screen_own", own_skills)]},
            "opponent_team": {"team_name": "screen-opponent", "active_index": 0, "creatures": [self._creature("screen_opponent", opponent_skills)]},
            "shared": {"turn": 1, "mp": {"own": 10, "opponent": 10}},
            "own_turn": {"primary": {"kind": "charge"}, "items": []},
            "opponent_turn": {"primary": {"kind": "charge"}, "items": []},
            "seed": 7, "battle_id": self.video_path.stem, "source": "screen_video",
        }

    @staticmethod
    def _creature(name: str, skills: list[str]) -> dict[str, Any]:
        slots = skills[:4] + [f"{name}_skill_{index}" for index in range(len(skills), 4)]
        return {
            "name": name,
            "base": {"attributes": ["普通"], "stats": {"hp": 100, "atk": 100, "def": 100, "spatk": 100, "spdef": 100, "speed": 100}},
            "ability": {"name": {"known": False}}, "state": {"hp": 100, "max_hp": 100, "energy": 10},
            "skills": [{"name": skill, "current_energy_cost": 2, "current_power": 40, "use_count": 0} for skill in slots],
        }

    @staticmethod
    def _request_for_turn(base: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
        request = copy.deepcopy(base)
        own = next((item for item in turn["actions"] if item.get("side") == "own"), None)
        opponent = next((item for item in turn["actions"] if item.get("side") == "opponent"), None)
        request["own_turn"] = {"primary": {"kind": "skill", "skill_name": own["skill_name"]} if own and own.get("skill_name") else {"kind": "charge"}, "items": []}
        request["opponent_turn"] = {"primary": {"kind": "skill", "skill_name": opponent["skill_name"]} if opponent and opponent.get("skill_name") else {"kind": "charge"}, "items": []}
        request.setdefault("shared", {})["turn"] = turn["turn"]
        return request
