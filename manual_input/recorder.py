from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validation import validate_request


class BattleRecorder:
    def __init__(self, root: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[1]
        self.root = Path(root) if root else project_root / "data" / "manual_battles"
        self.root.mkdir(parents=True, exist_ok=True)

    def create_battle(self) -> dict[str, Any]:
        battle_id = f"battle-{uuid.uuid4().hex[:10]}"
        document = {
            "schema_version": 2,
            "battle_id": battle_id,
            "source": "manual_browser",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rounds": [],
        }
        self._path(battle_id).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return document

    def save_round(
        self,
        battle_id: str,
        request: dict[str, Any],
        observed_after: dict[str, Any] | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        errors = validate_request(request)
        if errors:
            raise ValueError("; ".join(errors))
        path = self._path(battle_id)
        if path.exists():
            document = json.loads(path.read_text(encoding="utf-8"))
        else:
            document = {
                "schema_version": 2,
                "battle_id": battle_id,
                "source": "manual_browser",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "rounds": [],
            }
        document["rounds"].append(
            {
                "round": len(document["rounds"]) + 1,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "request": request,
                "observed_after": observed_after,
                "note": note,
            }
        )
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return document

    def save_initial(self, battle_id: str, request: dict[str, Any]) -> dict[str, Any]:
        errors = validate_request(request, require_round=False)
        if errors:
            raise ValueError("; ".join(errors))
        document = self.load(battle_id)
        if document.get("initial_state") or document.get("rounds"):
            raise ValueError("battle already started")
        document["initial_state"] = {
            "round": 1,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "request": request,
        }
        self._path(battle_id).write_text(
            json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return document

    def _path(self, battle_id: str) -> Path:
        safe_id = "".join(character for character in battle_id if character.isalnum() or character in "-_")
        if not safe_id:
            raise ValueError("invalid battle id")
        return self.root / f"{safe_id}.json"

    def load(self, battle_id: str) -> dict[str, Any]:
        path = self._path(battle_id)
        if not path.exists():
            raise FileNotFoundError(battle_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def list_battles(self) -> list[dict[str, Any]]:
        result = []
        for index, path in enumerate(sorted(self.root.glob("*.json")), start=1):
            document = json.loads(path.read_text(encoding="utf-8"))
            raw_rounds = document.get("rounds", [])
            if isinstance(raw_rounds, int):
                raw_rounds = [{"round": round_index + 1, "saved_at": ""} for round_index in range(raw_rounds)]
            result.append(
                {
                    "battle_id": document.get("battle_id", path.stem),
                    "label": f"战斗 {index}",
                    "rounds": [
                        {"round": item.get("round", index + 1), "saved_at": item.get("saved_at", "")}
                        for index, item in enumerate(raw_rounds)
                    ],
                    "created_at": document.get("created_at", ""),
                    "has_initial_state": bool(document.get("initial_state")),
                }
            )
        return result
