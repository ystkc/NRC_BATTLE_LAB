"""验证审计产物结构、证据入口和业务文件未变，不自证游戏规则。"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
ALLOWED = {"通过", "确认缺陷", "未实现", "规则存疑", "检查受阻", "未上线"}


def read_csv(path):
    """读取审计CSV。"""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def missing_links(path):
    """检查文档中的本地文件入口，不推断证据是否足以证明规则。"""
    problems = []
    text = path.read_text(encoding="utf-8-sig")
    for target in re.findall(r"\]\(([^\n)]+)\)", text):
        value = unquote(target.strip().strip("<>"))
        if value.startswith(("https://", "http://", "#", "mailto:")):
            continue
        filename = value.split("#", 1)[0]
        filename = re.sub(r":\d+$", "", filename)
        destination = path.parent / filename
        if destination == AUDIT / "deliverable_validation.json":
            continue
        if not destination.exists():
            problems.append({"document": path.relative_to(AUDIT).as_posix(), "target": target})
    return problems


def main():
    """只读产品，最终产物缺口使验证返回非零。"""
    inventory = read_csv(AUDIT / "inventory.csv")
    coverage = read_csv(AUDIT / "coverage.csv")
    objects = read_csv(AUDIT / "tasks/T06/final_object_review.csv")
    issues = read_csv(AUDIT / "issue_index.csv")
    questions = read_csv(AUDIT / "question_index.csv")
    files = read_csv(AUDIT / "baseline_files_final.csv")
    stats = json.loads((AUDIT / "statistics.json").read_text(encoding="utf-8"))
    inventory_ids = [row["item_id"] for row in inventory]
    coverage_ids = [row["item_id"] for row in coverage]
    errors = []

    def check(condition, message):
        """积累所有交付错误便于一次纠正。"""
        if not condition:
            errors.append(message)

    check(len(inventory_ids) == len(set(inventory_ids)), "inventory有重复ID")
    check(len(coverage_ids) == len(set(coverage_ids)), "coverage有重复ID")
    check(set(inventory_ids) == set(coverage_ids), "inventory/coverage不一一对应")
    by_id = {row["item_id"]: row for row in inventory}
    for row in coverage:
        check(row["conclusion"] in ALLOWED, f"非法结论{row['item_id']}")
        for key in ("rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability", "owner", "task_report"):
            check(bool(row.get(key)), f"coverage字段{key}为空：{row['item_id']}")
        check(row["owner"] == by_id[row["item_id"]]["owner"], f"主责不一致：{row['item_id']}")
        check((AUDIT / row["task_report"]).is_file(), f"任务证据入口不存在：{row['item_id']}")

    owners = defaultdict(set)
    for row in inventory:
        if row["kind"] == "file":
            owners[row["source"]].add(row["owner"])
    changed = []
    for row in files:
        path = ROOT / row["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
        if digest != row["sha256"]:
            changed.append(row["path"])
        check(owners[row["path"]] == {row["owner"]}, f"文件非唯一主责：{row['path']}")
    check(not changed, "业务/规则/来源指纹变化：" + repr(changed))
    spec = importlib.util.spec_from_file_location("audit_inventory", AUDIT / "build_inventory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    current_paths = {path.relative_to(ROOT).as_posix() for path in module.source_paths()}
    check(current_paths <= set(owners), "原枚举范围出现未归属文件：" + repr(sorted(current_paths - set(owners))))
    check(len(files) == len(owners) == 149, "文件数与最终基线不一致")
    counts = Counter(row["kind"] for row in inventory)
    for kind, expected in {"skill": 580, "ability": 242, "form": 625, "element": 18, "game_rule": 57}.items():
        check(counts[kind] == expected, f"实体{kind}数量错误")
    object_ids = {row["item_id"] for row in objects}
    check(len(objects) == len(object_ids) == 822, "最终对象表不等于822唯一对象")
    check(object_ids == {row["item_id"] for row in inventory if row["kind"] in {"skill", "ability"}}, "对象终表ID不匹配")
    check(not any(row["overall_conclusion"] == "通过" for row in objects), "对象完整通过与最终证据边界不符")
    check(sum(row["overall_conclusion"] == "未实现" for row in objects) == 70, "空特性未实现数量错误")
    object_lookup = {row["item_id"]: row for row in objects}
    for row in coverage:
        if row["item_id"] in object_lookup:
            check(row["conclusion"] == object_lookup[row["item_id"]]["overall_conclusion"], f"对象总体结论未同步：{row['item_id']}")

    required = ["README.md", "assignments.md", "inventory.csv", "coverage.csv", "issues.md", "questions.md", "baseline.json", "baseline_files_final.csv", "validation.json", "statistics.json", "scenario_matrix.csv", "issue_aliases.csv", "question_aliases.csv"]
    required += [f"tasks/T{task:02}/{filename}" for task in range(13) for filename in ("report.md", "coverage.csv", "issues.md", "questions.md")]
    for relative in required:
        check((AUDIT / relative).is_file(), "缺交付：" + relative)
    link_documents = [AUDIT / filename for filename in ("README.md", "assignments.md", "issues.md", "questions.md")]
    link_documents += [AUDIT / f"tasks/T{task:02}/report.md" for task in range(13)]
    link_documents += [AUDIT / "tasks/T06/final_addendum_report.md"]
    dead_links = [problem for path in link_documents for problem in missing_links(path)]
    check(not dead_links, f"文档死链接{len(dead_links)}处")
    for row in issues + questions:
        check((AUDIT / row["evidence"]).exists(), "问题索引来源不存在：" + row["evidence"])
    check(len(issues) == stats["confirmed_issue_groups"] == 108, "问题根因统计不同步")
    check(len(questions) == stats["question_groups"] == 64, "存疑统计不同步")
    check(dict(Counter(row["conclusion"] for row in coverage)) == stats["conclusions"], "分类统计不同步")
    check(len(inventory) == stats["recorded_units"] == 22487, "最终记录数不同步")
    scenarios = read_csv(AUDIT / "scenario_matrix.csv")
    check(len(scenarios) == 48, "必查场景索引数不同步")
    for row in scenarios:
        for evidence in row["evidence"].split(";"):
            check((AUDIT / evidence).is_file(), f"场景{row['scenario_id']}证据不存在：{evidence}")
    with (AUDIT / "tasks/T01/data_record_checks.csv").open(encoding="utf-8-sig", newline="") as handle:
        data_record_count = sum(1 for _ in csv.DictReader(handle))
    check(data_record_count == 78224, "单列数据记录数错误")
    pytest_tree = ET.parse(AUDIT / "tasks/T00/pytest.xml")
    cases = pytest_tree.findall(".//testcase")
    check(len(cases) == 19 and all(not case.findall("failure") and not case.findall("error") for case in cases), "19现有pytest证据不符")
    cleanup = json.loads((AUDIT / "tasks/T12/cleanup.json").read_text(encoding="utf-8"))
    check(cleanup["portAvailable"] and all(not process["alive"] for process in cleanup["serverProcesses"]), "T12关闭证据不符")

    syntax_errors = []
    for path in AUDIT.rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except SyntaxError as exception:
            syntax_errors.append({"path": path.relative_to(AUDIT).as_posix(), "error": str(exception)})
    check(not syntax_errors, "审计脚本语法错误")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, encoding="utf-8").strip()
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, encoding="utf-8")
    diff = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, encoding="utf-8")
    check(not diff.strip(), "存在未提交业务差异，须与用户已有修改区分后复核：" + diff)
    check(head == stats["head"], "HEAD与最终报告不同步")
    result = {
        "created": datetime.now().isoformat(), "valid": not errors, "errors": errors,
        "scope": "交付结构/统计/入口/哈希核验，不证明尚未验证游戏行为正确",
        "inventory_rows": len(inventory), "coverage_rows": len(coverage), "unique_ids": len(set(inventory_ids)),
        "source_files": len(files), "source_fingerprints_unchanged": not changed, "changed_source_files": changed,
        "required_artifacts": len(required), "local_link_documents": len(link_documents), "dead_links": dead_links,
        "issues": len(issues), "questions": len(questions), "object_reviews": len(objects),
        "required_scenarios": len(scenarios), "separate_data_records": data_record_count,
        "pytest_cases": len(cases), "audit_python_scripts_parsed": sum(1 for _ in AUDIT.rglob("*.py")),
        "syntax_errors": syntax_errors, "head": head, "working_tree_status": status,
        "tracked_diff_from_head": diff, "browser_cleanup_evidence": cleanup,
    }
    (AUDIT / "deliverable_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("valid", "errors", "inventory_rows", "source_files", "issues", "questions", "dead_links", "head")}, ensure_ascii=False))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
