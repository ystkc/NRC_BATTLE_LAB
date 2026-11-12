"""只读建立审计基线、文件归属和双向检查台账。"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
FIELDS = ["item_id", "kind", "name", "owner", "source", "line", "parent_id", "description", "reachability"]
COVERAGE_FIELDS = ["item_id", "conclusion", "rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability"]


def owner(path: str) -> str:
    """为每个范围内文件分配唯一主责。"""
    if path.startswith("wiki_crawler/") or path.startswith("data/") and not path.endswith(".md"):
        return "T01"
    if path.startswith("nrc_platform/"):
        return "T02" if Path(path).stem in {"catalog", "builder", "input"} else "T11"
    if path.startswith("nrc_server/"):
        return "T12"
    if path.startswith("nrc_core/engine/"):
        return {"handlers_skill": "T08", "handlers_ability": "T09", "handlers_field": "T10"}.get(Path(path).stem, "T07")
    if path.startswith("nrc_core/"):
        stem = Path(path).stem
        if stem in {"models", "compound_status", "catalog", "constant", "pokemon_nature_table"}:
            return "T03"
        if stem in {"battle", "core", "rng"}:
            return "T04"
        if stem in {"effect_data", "skill_effects_generated"}:
            return "T06"
        if stem in {"effect_models", "effect_engine"}:
            return "T07"
        return "T05"
    return "T06" if path == "scripts/generate_skill_effects.py" else "T00"


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    """以 UTF-8 保存便于人读和机器合并的台账。"""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def source_paths() -> list[Path]:
    """排除训练、废弃 OCR、旧审计和运行产物。"""
    paths = []
    for folder in ("nrc_core", "nrc_platform", "nrc_server", "wiki_crawler", "data", "tests", "scripts"):
        for path in (ROOT / folder).rglob("*"):
            relative = path.relative_to(ROOT).as_posix()
            if not path.is_file() or any(part in {"__pycache__", "node_modules", ".pytest_cache"} for part in path.parts):
                continue
            if relative.startswith(("data/audit/", "data/icon_dept_relation/")):
                continue
            if path.suffix in {".py", ".js", ".html", ".css", ".md", ".csv", ".db", ".xlsx", ".yaml"}:
                paths.append(path)
    for pattern in ("AGENTS.md", "pyproject.toml", "package.json", "package-lock.json", "1007.md", "1007-issues.md", "1007A.json", "1007B.json", "playwright_1007.js"):
        path = ROOT / pattern
        if path.exists():
            paths.append(path)
    return sorted(set(paths))


def main() -> None:
    """冻结当前工作区指纹并列出所有原始检查单位。"""
    for task in range(13):
        (AUDIT / "tasks" / f"T{task:02}").mkdir(parents=True, exist_ok=True)
    rows = []
    hashes = []
    for path in source_paths():
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        hashes.append({"path": relative, "owner": owner(relative), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "mtime_ns": path.stat().st_mtime_ns})
        rows.append(dict(item_id=f"FILE:{relative}", kind="file", name=relative, owner=owner(relative), source=relative, line=1, parent_id="", description="文件完整检查；测试和旧对局仅为线索", reachability="待核对"))
        if path.suffix == ".py":
            tree = ast.parse(data.decode("utf-8-sig"), filename=relative)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    rows.append(dict(item_id=f"CODE:{relative}:{node.lineno}:{node.name}", kind="code_object", name=node.name, owner=owner(relative), source=relative, line=node.lineno, parent_id=f"FILE:{relative}", description=ast.get_docstring(node) or "无描述字符串", reachability="待核对"))
                branches = []
                if isinstance(node, (ast.If, ast.IfExp)):
                    branches = ["true", "false"]
                elif isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                    branches = ["body", "zero_or_exit"]
                elif isinstance(node, ast.ExceptHandler):
                    branches = ["exception"]
                elif isinstance(node, ast.Match):
                    branches = [f"case{index}" for index, _ in enumerate(node.cases)]
                for branch in branches:
                    rows.append(dict(item_id=f"BRANCH:{relative}:{node.lineno}:{branch}", kind="code_branch", name=branch, owner=owner(relative), source=relative, line=node.lineno, parent_id=f"FILE:{relative}", description=ast.get_source_segment(data.decode("utf-8-sig"), node.test) if hasattr(node, "test") else type(node).__name__, reachability="待核对"))
        if relative.startswith("data/") and path.suffix == ".md":
            for index, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
                if line.strip() and not line.startswith("#"):
                    rows.append(dict(item_id=f"RULE:{relative}:{index}", kind="rule_clause", name=line.strip()[:100], owner="T00", source=relative, line=index, parent_id=f"FILE:{relative}", description=line.strip(), reachability="待核对"))
    connection = sqlite3.connect(f"file:{(ROOT / 'data/nrc_wiki.db').as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    counts = {}
    for table, prefix, task in (("skill_catalog", "SKILL", "T06"), ("ability_catalog", "ABILITY", "T06"), ("spirit_forms", "FORM", "T01"), ("elements", "ELEMENT", "T03"), ("game_rules", "GAME_RULE", "T00")):
        records = [dict(record) for record in connection.execute(f"SELECT * FROM {table} ORDER BY id")]
        counts[table] = len(records)
        (AUDIT / "tasks" / "T00" / f"{table}.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        for record in records:
            item_id = f"{prefix}:{record['id']:04}"
            description = record.get("description", record.get("ability_description", ""))
            rows.append(dict(item_id=item_id, kind=prefix.lower(), name=record["name"], owner=task, source=f"data/nrc_wiki.db:{table}", line=record["id"], parent_id="", description=description, reachability="待核对"))
            if prefix in {"SKILL", "ABILITY", "GAME_RULE"}:
                clauses = [clause.strip() for clause in re.split(r"[。；;\n]+", description) if clause.strip()]
                for index, clause in enumerate(clauses, 1):
                    rows.append(dict(item_id=f"{item_id}:C{index:02}", kind=f"{prefix.lower()}_clause", name=record["name"], owner=task, source=f"data/nrc_wiki.db:{table}", line=record["id"], parent_id=item_id, description=clause, reachability="待核对"))
    connection.close()
    write_csv(AUDIT / "inventory.csv", FIELDS, rows)
    write_csv(AUDIT / "baseline_files.csv", ["path", "owner", "sha256", "bytes", "mtime_ns"], hashes)
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, encoding="utf-8", check=True).stdout
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, encoding="utf-8", check=True).stdout.strip()
    baseline = {"created": datetime.now().isoformat(), "head": head, "working_tree_status": status, "counts": counts, "inventory_counts": dict(Counter(row["kind"] for row in rows)), "database_access": "sqlite mode=ro", "encoding_incident": "首次控制台输出 CSV 中文乱码；显式 PYTHONIOENCODING=utf-8 后重读正常，原文件未改写"}
    (AUDIT / "baseline.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    for task in range(13):
        task_id = f"T{task:02}"
        write_csv(AUDIT / "tasks" / task_id / "assigned_inventory.csv", FIELDS, [row for row in rows if row["owner"] == task_id])
    print(json.dumps({"audit": str(AUDIT), **baseline["counts"], "inventory": baseline["inventory_counts"], "files": len(hashes)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
