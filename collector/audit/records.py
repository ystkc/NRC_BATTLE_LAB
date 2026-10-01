"""人工审计记录的读写与分支回填。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AuditTable:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.payload = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def records(self) -> list[dict]:
        return self.payload.setdefault("records", [])

    def mark_branch(
        self,
        name: str,
        branch_id: str,
        *,
        status: str = "recorded",
        battle_id: str = "",
        note: str = "",
    ) -> bool:
        for record in self.records:
            if record.get("name") != name:
                continue
            audit = record.setdefault("audit", {})
            branch_status = audit.setdefault("branch_status", {})
            if branch_id not in branch_status:
                return False
            branch_status[branch_id] = status
            audit.setdefault("records", []).append({
                "battle_id": battle_id,
                "branch_id": branch_id,
                "status": status,
                "note": note,
            })
            audit["status"] = "audited" if all(value == "recorded" for value in branch_status.values()) else "partial"
            return True
        return False

    def save(self) -> None:
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")

