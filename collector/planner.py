"""人工参与的下一步操作规划器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from collector.audit.matcher import BranchMatch, match_observed_branch
from collector.audit.records import AuditTable
from nrc_core.schema import BattleRequest, BattleResult


@dataclass
class NextActionPlan:
    action: dict[str, Any]
    reason: str
    skill_name: str | None = None
    pending_branch_count: int = 0
    notes: list[str] = field(default_factory=list)


class CollectionSession:
    def __init__(self, skill_audit_path: str | Path):
        self.skill_audit = AuditTable(skill_audit_path)

    def plan_next_action(self, request: BattleRequest, side: str = "own") -> NextActionPlan:
        team = request.own_team if side == "own" else request.opponent_team
        active_index = team.active_index.or_default(0)
        if not (0 <= active_index < len(team.creatures)):
            return NextActionPlan({"kind": "pass"}, "当前出场位置未知，先等待 mitmproxy 补齐")
        creature = team.creatures[active_index]
        pending = []
        for slot in creature.skills:
            if not slot.name.known or not slot.name.exists or not slot.name.value:
                continue
            record = next((item for item in self.skill_audit.records if item.get("name") == slot.name.value), None)
            if not record:
                pending.append((slot.name.value, 0))
                continue
            branch_status = record.get("audit", {}).get("branch_status", {})
            count = sum(value != "recorded" for value in branch_status.values())
            if count:
                pending.append((slot.name.value, count))
        if pending:
            pending.sort(key=lambda item: (-item[1], item[0]))
            skill_name, count = pending[0]
            return NextActionPlan(
                action={"kind": "skill", "skill_name": skill_name},
                reason="优先使用当前精灵仍有未记录分支的技能",
                skill_name=skill_name,
                pending_branch_count=count,
            )
        return NextActionPlan(
            action={"kind": "charge"},
            reason="当前已知技能没有待审分支，使用聚能等待新的观察机会",
        )

    def record_observation(
        self,
        skill_name: str,
        result: BattleResult,
        observed_codes: set[str],
        *,
        battle_id: str = "",
        note: str = "",
    ) -> BranchMatch:
        match = match_observed_branch(result.possible_branches, observed_codes)
        if match.status == "matched" and match.branch_id:
            self.skill_audit.mark_branch(
                skill_name,
                match.branch_id,
                status="recorded",
                battle_id=battle_id,
                note=note,
            )
            self.skill_audit.save()
        return match

