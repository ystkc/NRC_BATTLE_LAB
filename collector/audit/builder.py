"""把 skills_all.csv 转成机器可读、可人工回填的审计表。"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from collector.parsing.skill_description import SkillDescriptionParser


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_skill_audit(
    csv_path: str | Path,
    output_dir: str | Path,
    strict: bool = False,
) -> dict:
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    parser = SkillDescriptionParser()
    rows = _read_rows(csv_path)
    records: list[dict] = []
    unresolved: list[dict] = []
    strategy_groups: dict[str, list[str]] = {}

    for row in rows:
        name = (row.get("技能名") or "").strip()
        description = (row.get("效果描述") or "").strip()
        parsed = parser.parse(name, description)
        record = {
            "name": name,
            "element": (row.get("属性") or "").strip(),
            "category": (row.get("类型") or "").strip(),
            "power": (row.get("威力") or "").strip(),
            "energy_cost": (row.get("耗能") or "").strip(),
            "description": description,
            "source": (row.get("数据来源") or "").strip(),
            "parser": parsed.to_json(),
            "audit": {
                "status": parsed.status.value,
                "branch_status": {
                    "__".join(option.key.code for option in branch) or "condition:base": "pending"
                    for branch in parsed.branches
                },
                "manual_note": "",
            },
        }
        records.append(record)
        strategy_groups.setdefault(parsed.strategy_key, []).append(name)
        if parsed.status.value == "manual_required":
            unresolved.append({
                "name": name,
                "description": description,
                "strategy_key": parsed.strategy_key,
                "reason": parsed.manual_reason,
            })

    payload = {
        "schema_version": 1,
        "source": str(csv_path),
        "parser": "fixed-text-v1",
        "record_count": len(records),
        "unresolved_count": len(unresolved),
        "strategy_groups": strategy_groups,
        "records": records,
    }
    (output_dir / "skills_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output_dir / "skills_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "name", "strategy_key", "status", "branch_count", "description", "manual_reason",
        ])
        writer.writeheader()
        for record in records:
            parsed = record["parser"]
            writer.writerow({
                "name": record["name"],
                "strategy_key": parsed["strategy_key"],
                "status": parsed["status"],
                "branch_count": len(parsed["options"]),
                "description": record["description"],
                "manual_reason": parsed["manual_reason"],
            })
    with (output_dir / "skills_unresolved.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "strategy_key", "reason", "description"])
        writer.writeheader()
        writer.writerows(unresolved)

    if strict and unresolved:
        raise RuntimeError(f"有 {len(unresolved)} 条技能未能安全解析，详见 skills_unresolved.csv")
    return payload
