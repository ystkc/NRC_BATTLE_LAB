"""Generate and execute one-turn manual verification cases.

Usage:
    python scripts/manual_verify_core.py init --output manual_case.json
    python scripts/manual_verify_core.py run --input manual_case.json

The run command writes the core result and a separate state-diff report.  The
diff report is intentionally descriptive rather than asserting whether a
result is correct; a human compares it with the expected game behavior.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nrc_core import BattleSimulator


MISSING = object()


def _catalog_examples(data_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    database = data_dir / "nrc_wiki.db"
    with sqlite3.connect(database) as connection:
        spirit_records: list[dict[str, Any]] = []
        rows = connection.execute(
            """
            SELECT s.id, s.name, COALESCE(a.name, '') AS ability
            FROM spirit_forms s
            LEFT JOIN ability_catalog a ON a.id = s.ability_id
            ORDER BY s.id
            LIMIT 2
            """
        ).fetchall()
        for spirit_id, name, ability in rows:
            attributes = [item[0] for item in connection.execute(
                """
                SELECT e.name
                FROM spirit_elements se
                JOIN elements e ON e.id = se.element_id
                WHERE se.spirit_id = ?
                ORDER BY se.position
                """,
                (spirit_id,),
            )]
            spirit_records.append({
                "name": name,
                "attributes": attributes or ["普通"],
                "ability": ability or None,
            })
        skill_names = [row[0] for row in connection.execute(
            "SELECT name FROM skill_catalog ORDER BY id LIMIT 4"
        )]
    if len(spirit_records) < 2 or len(skill_names) < 4:
        raise RuntimeError("nrc_wiki.db 中没有足够的精灵或技能示例")
    return spirit_records, skill_names


def _input_value(value: Any) -> Any:
    if isinstance(value, dict) and "known" in value:
        return value.get("value") if value.get("known") and value.get("exists", True) else None
    return value


def bind_catalog_fields(payload: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    """Bind combat attributes and the default ability to each creature name."""
    result = json.loads(json.dumps(payload, ensure_ascii=False))
    database = data_dir / "nrc_wiki.db"
    with sqlite3.connect(database) as connection:
        for team_key in ("own_team", "opponent_team"):
            for creature in result.get(team_key, {}).get("creatures", []):
                creature.pop("display_name", None)
                name = _input_value(creature.get("name"))
                if not name:
                    continue
                row = connection.execute(
                    """
                    SELECT s.id, COALESCE(a.name, '') AS ability
                    FROM spirit_forms s
                    LEFT JOIN ability_catalog a ON a.id = s.ability_id
                    WHERE s.name = ?
                    LIMIT 1
                    """,
                    (name,),
                ).fetchone()
                if row is None:
                    raise ValueError(f"数据库中不存在精灵：{name}")
                base = creature.setdefault("base", {})
                base.pop("attributes", None)
                creature.pop("ability", None)
    return result


def build_template(data_dir: Path) -> dict[str, Any]:
    """Build a valid, minimal, single-turn request using catalog examples."""
    spirit_records, skill_names = _catalog_examples(data_dir)

    def creature(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": record["name"],
            "base": {
                "bloodline_attributes": None,
                "nature": None,
                "individual_values": None,
                "stats": None,
            },
            "skills": [{"name": skill} for skill in skill_names],
            "state": {
                "hp": None,
                "max_hp": None,
                "energy": 10,
                "buffs": [],
                "debuffs": [],
                "marks": [],
                "fatigue_turns": 0,
            },
            "entry_count": 1,
            "metadata": {"attribute_assumption": "database"},
        }

    return {
        "__manual_verification": {
            "说明": "请修改本文件后运行 run；顶层以下划线开头的字段不会传入核心。",
            "规则来源": ["data/wiki/game_descriptions.csv", "data/nrc_wiki.db", "data/*.md"],
            "填写重点": [
                "双方精灵名称、血脉和四个技能；属性与特性已经从数据库绑定",
                "不要手动添加 display_name；不要在出招动作中重复填写技能名称",
                "当前生命、能量、增益减益、状态层数和印记",
                "双方本回合主动作，以及需要使用的共鸣魔法",
                "weather、weather_turns、mp 和 seed",
            ],
            "共鸣魔法可填": ["willpower", "boss", "solar_heal", None],
        },
        "own_team": {
            "team_name": "人工验证-我方",
            "active_index": 0,
            "resonance_magic": None,
            "creatures": [creature(spirit_records[0])],
        },
        "opponent_team": {
            "team_name": "人工验证-对方",
            "active_index": 0,
            "resonance_magic": None,
            "creatures": [creature(spirit_records[1])],
        },
        "shared": {
            "turn": 1,
            "weather": None,
            "weather_turns": None,
            "system_time": None,
            "weekend": None,
            "bypass": None,
            "mp": {"own": 4, "opponent": 4},
            "metadata": {},
        },
        "own_turn": {
            "primary": {
                "kind": "skill",
                "skill_slot": 0,
                "choice": None,
            },
            "items": [],
        },
        "opponent_turn": {
            "primary": {"kind": "charge"},
            "items": [],
        },
        "seed": 1,
        "battle_id": "manual-verification-001",
        "source": "manual-verification",
    }


def _strip_private_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_private_fields(item)
            for key, item in value.items()
            if not key.startswith("__") and key != "display_name"
        }
    if isinstance(value, list):
        return [_strip_private_fields(item) for item in value]
    return value


def _display_value(value: Any) -> Any:
    return "<missing>" if value is MISSING else value


def _diff_values(before: Any, after: Any, path: str, changes: list[dict[str, Any]]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            _diff_values(
                before.get(key, MISSING),
                after.get(key, MISSING),
                f"{path}.{key}" if path else str(key),
                changes,
            )
        return
    if isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            old = before[index] if index < len(before) else MISSING
            new = after[index] if index < len(after) else MISSING
            _diff_values(old, new, f"{path}[{index}]", changes)
        return
    if before != after:
        changes.append({
            "path": path,
            "before": _display_value(before),
            "after": _display_value(after),
        })


def build_change_report(input_payload: dict[str, Any], result_payload: dict[str, Any], input_path: Path, output_path: Path) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    sections = (
        ("own", result_payload.get("own", {}).get("before"), result_payload.get("own", {}).get("after")),
        ("opponent", result_payload.get("opponent", {}).get("before"), result_payload.get("opponent", {}).get("after")),
        ("shared", result_payload.get("shared_before"), result_payload.get("shared_after")),
    )
    for name, before, after in sections:
        _diff_values(before, after, name, changes)

    return {
        "format": "nrc_manual_verification_changes.v1",
        "input_file": str(input_path),
        "output_file": str(output_path),
        "change_count": len(changes),
        "changes": changes,
        "input_actions": {
            "own": input_payload.get("own_turn"),
            "opponent": input_payload.get("opponent_turn"),
        },
        "events": result_payload.get("events", []),
        "warnings": result_payload.get("warnings", []),
        "input_unknowns": result_payload.get("input_unknowns", []),
        "latent_uncertainties": result_payload.get("latent_uncertainties", []),
        "人工核对提示": [
            "changes 只记录核心归一化状态的变化，不判断规则是否正确。",
            "events 记录本回合战报、显示威力和其他核心事件，请与实际游戏逐项比对。",
            "若输入含 unknown 字段，先确认 input_unknowns 和 latent_uncertainties 是否符合预期。",
        ],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def init_case(output: Path, data_dir: Path, overwrite: bool) -> None:
    if output.exists() and not overwrite:
        raise FileExistsError(f"文件已存在：{output}；如需覆盖请添加 --overwrite")
    _write_json(output, build_template(data_dir))
    print(f"已生成输入模板：{output}")
    print("请手动填写后运行：")
    print(f"  python scripts/manual_verify_core.py run --input \"{output}\"")


def run_case(input_path: Path, output_path: Path | None, changes_path: Path | None, data_dir: Path) -> None:
    input_payload = json.loads(input_path.read_text(encoding="utf-8"))
    input_payload = bind_catalog_fields(_strip_private_fields(input_payload), data_dir)
    simulator = BattleSimulator(data_dir)
    result_payload = simulator.resolve_turn(input_payload).to_json()

    output_path = output_path or input_path.with_name(f"{input_path.stem}.output.json")
    changes_path = changes_path or input_path.with_name(f"{input_path.stem}.changes.json")
    _write_json(output_path, result_payload)
    _write_json(changes_path, build_change_report(input_payload, result_payload, input_path, output_path))
    print(f"已生成输出：{output_path}")
    print(f"已生成变化记录：{changes_path}")
    print(f"记录变化数：{len(json.loads(changes_path.read_text(encoding='utf-8'))['changes'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成并执行 NRC 核心人工特例验证 JSON")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="数据目录，默认 data")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="生成可编辑的输入 JSON 模板")
    init_parser.add_argument("--output", type=Path, default=Path("manual_verify_input.json"))
    init_parser.add_argument("--overwrite", action="store_true")

    run_parser = subparsers.add_parser("run", help="执行输入 JSON 并生成输出和变化 JSON")
    run_parser.add_argument("--input", type=Path, required=True)
    run_parser.add_argument("--output", type=Path)
    run_parser.add_argument("--changes", type=Path)

    args = parser.parse_args()
    if args.command == "init":
        init_case(args.output, args.data_dir, args.overwrite)
    else:
        run_case(args.input, args.output, args.changes, args.data_dir)


if __name__ == "__main__":
    main()
