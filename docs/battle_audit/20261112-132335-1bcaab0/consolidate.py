"""合并只读审计台账，消歧稳定编号并核验交付完整性。"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
INVFIELDS = ["item_id", "kind", "name", "owner", "source", "line", "parent_id", "description", "reachability"]
COVFIELDS = ["item_id", "conclusion", "rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability", "owner", "original_id", "task_report", "config_conclusion", "execution_conclusion", "overall_conclusion", "required_inputs"]
CONCLUSIONS = {"通过", "确认缺陷", "未实现", "规则存疑", "检查受阻", "未上线"}


def read_csv(path):
    """读取UTF-8生成台账。"""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    """生成主表，不改各任务原始记录。"""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def branch_nodes(path):
    """用AST列位置区分同行嵌套三元条件。"""
    result = defaultdict(list)
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
        if isinstance(node, (ast.If, ast.IfExp)):
            for direction in ("true", "false"):
                result[(node.lineno, direction)].append(node.col_offset)
    return result


def prefixed_evidence(task, raw):
    """主表以任务报告为入口，原始证据保留任务内相对语境。"""
    return f"tasks/{task}/report.md；任务内证据：{raw}"


def issue_sections():
    """按原编号收集确认问题，保留所有最小输入与限制。"""
    sections = {}
    for path in sorted((AUDIT / "tasks").glob("T*/issues.md")):
        source = path.read_text(encoding="utf-8")
        headers = list(re.finditer(r"^## (.+)$", source, flags=re.M))
        for index, header in enumerate(headers):
            identity = re.search(r"T\d\d-I\d\d", header.group(1))
            if identity is None:
                continue
            key = identity.group()
            if key == "T04-I12":
                continue
            end = headers[index + 1].start() if index + 1 < len(headers) else len(source)
            body = source[header.end():end].strip()
            title = header.group(1).replace(key, "", 1).strip(" ：:｜·　")
            title = re.sub(r"^(确认缺陷[｜ ]*)?P[0-3][｜· ]*", "", title)
            severity = re.search(r"严重度[：: ]*(P[0-3])", body)
            if severity:
                level = severity.group(1)
            elif "P1" in header.group(1) or re.search(r"严重度[：: ]*(High|高)", body):
                level = "P1"
            elif "P3" in header.group(1):
                level = "P3"
            elif "P2" in header.group(1) or "Medium" in body:
                level = "P2"
            else:
                level = "P1"
            sections[key] = {"original_id": key, "task": path.parent.name, "title": title, "body": body, "severity": level, "source": path.relative_to(AUDIT).as_posix(), "related": []}
    return sections


def build_issues():
    """按根因合并重复，子因不同的沙暴重设另列。"""
    sections = issue_sections()
    merge_map = {"T07-I08": "T06-I01", "T03-I06": "T04-I06", "T10-I12": "T07-I05"}
    aliases = []
    for duplicate, primary in merge_map.items():
        if duplicate in sections:
            sections[primary]["related"].append(sections.pop(duplicate))
            aliases.append({"source_id": duplicate, "primary_id": primary, "reason": "同根接口两端证据合并，不重复计数"})
    if "T08-I02" in sections:
        sand = sections.pop("T08-I02")
        sections["T04-I14"]["related"].append(sand)
        aliases.append({"source_id": "T08-I02:额外伤害", "primary_id": "T04-I14", "reason": "同一天气扣血消费者"})
        sections["T08-I02B"] = dict(sand, original_id="T08-I02B", title="重复设置沙暴把已经折半的地系技能再次折半", related=[], body="主责T08，协同T04。规则依据：data/wiki/game_descriptions.csv沙暴只使双方地系技能能耗减半；持续天气不授权重复累乘。代码：handlers_skill.py:851-869。最小输入：一地系技能原耗4，连续执行两次沙暴设置。预期同一天气仍耗2，实际4→2→1。影响重复天气来源的成本、合法动作和支付。证据：tasks/T08/probe_output.json 的 sand_reapply；源问题T08-I02同时含额外天气伤害，后者已合T04-I14。")
        aliases.append({"source_id": "T08-I02:重设折半", "primary_id": "T08-I02B", "reason": "不同代码根因另列，避免把两种故障混成一个"})
    if "T09-I11" in sections:
        sections["T09-I11"]["title"] = "虫群入场时点和攻防速目标未落实（毒牙/毒腺合T06-I11）"
        aliases.append({"source_id": "T09-I11:毒牙/毒腺", "primary_id": "T06-I11", "reason": "原文参数/阈值与已有复现相同；虫群另保留自身handler问题"})
    aliases += [
        {"source_id": "T02:X01_charge", "primary_id": "T06-I15", "reason": "解析→输出→装载同一charge遗漏链"},
        {"source_id": "T02:X02_devotion", "primary_id": "T10-I01", "reason": "初始化与场地授予上限/满池排除协同"},
        {"source_id": "T12:invalid_base", "primary_id": "T02-I07", "reason": "HTTP500为input形状错误的端到端后果"},
        {"source_id": "T12:privacy/devotion/preview", "primary_id": "T11-I01/I02/I03/I04", "reason": "投影/规范化主根因，网页保留表现证据"},
    ]
    priority = {"T11-I01": 0, "T06-I01": 1, "T02-I08": 2, "T05-I04": 3, "T04-I03": 4, "T03-I01": 5, "T10-I11": 6, "T09-I02": 7, "T05-I05": 8}
    issues = sorted(sections.values(), key=lambda row: (row["severity"], priority.get(row["original_id"], 100), row["original_id"]))
    index, markdown = [], ["# 确认缺陷与已知未实现机制", "", "业务代码未修复。下列按影响/严重度排序并合并跨任务同根反例。原编号保留以便追溯；完整参数、实际状态和事件见各任务输入/输出。P1为可改变结果、机制缺失或正常执行失败，P2为输入/协议/显示偏差，P3为局部界面问题。接口可达不等于当前阵容必现，原记录分别说明。", "", "70种空特性属于未实现：direct builder正确抛UnsupportedMechanicError，但实际平台抹名后放行，主根因T11-I01；17血脉、传动、禁足和选择等静默缺口分别列于所属问题。完整对象清单见T06最终表，不能把未实现等同未上线。", ""]
    summary = ["| 汇总编号 | 严重度 | 主责任务 | 原编号/根因 |", "|---|---|---|---|"]
    for number, row in enumerate(issues, 1):
        row["issue_id"] = f"AUD-{number:03}"
        primary = row["task"]
        if row["original_id"] in {"T08-I03"}:
            primary = "T08（接口）+T04（调用）"
        category = "规则/运行" if primary not in {"T00", "T01", "T12"} else {"T00": "依赖协议", "T01": "数据/采集", "T12": "网页/接口"}[primary]
        index.append({"issue_id": row["issue_id"], "severity": row["severity"], "primary_task": primary, "source_ids": ";".join([row["original_id"]] + [item["original_id"] for item in row["related"]]), "title": row["title"], "category": category, "evidence": row["source"], "collaboration": ";".join(item["task"] for item in row["related"])})
        summary.append(f"| {row['issue_id']} | {row['severity']} | {primary} | [{row['original_id']} {row['title']}](#{row['issue_id'].lower()}) |")
    markdown += summary + [""]
    for row in issues:
        markdown += [f"<a id=\"{row['issue_id'].lower()}\"></a>", f"## {row['issue_id']} · {row['severity']} · {row['title']}", "", f"主责：{row['task']}；原编号：{row['original_id']}。[完整原记录]({row['source']})。", ""]
        body = re.sub(r"\]\((?!https?://|#|[A-Za-z]:)([^)]+)\)", lambda match: f"](tasks/{row['task']}/{match.group(1)})", row["body"])
        markdown += [body, ""]
        for related in row["related"]:
            markdown += [f"协同证据：[{related['original_id']}（{related['task']}）]({related['source']})；与上项同根不计新增问题。", ""]
        if row["original_id"] in {"T04-I01", "T04-I03"}:
            markdown += ["T00独立补核：[cross_module_output.json](tasks/T00/cross_module_output.json)，包含多重减伤/最低伤害或四项50回合指标；不重复计数。", ""]
        if row["original_id"] == "T06-I11":
            markdown += ["T09毒牙/毒腺协同：[source_correction_probe_output.json](tasks/T09/source_correction_probe_output.json)。虫群处理器另列T09-I11。", ""]
    markdown += ["## 未实现拒绝方式", "", "| 机制 | 拒绝/放行事实 | 证据 |", "|---|---|---|", "| 70种空特性、152形态 | direct builder正确抛出；平台抹特性名后错误放行 | T11-I01；tasks/T10/unsupported_ability_forms.json |", "| 空技能效果 | 构建接受，正式执行扣能量后零效果 | T06-I13 |", "| 未知E/ABILITY_COMPUTE action | 静默返回，没有UnsupportedMechanicError | T07-I01；T09-I01 |", "| 17血脉/传动/禁足/选择 | 无效果或未执行完整规则，未明确拒绝 | T10-I07；T07-I05；T05-I07/I08 |", "| 闪焰爆发/节流术 | 权威文档明确未上线，非上述实现缺口 | questions.md；T05报告 |", "", "根因拆并明细见 [issue_aliases.csv](issue_aliases.csv)。存疑或证据不足项不在此表冒充确认缺陷，见 [questions.md](questions.md)。", ""]
    (AUDIT / "issues.md").write_text("\n".join(markdown), encoding="utf-8")
    write_csv(AUDIT / "issue_index.csv", ["issue_id", "severity", "primary_task", "source_ids", "title", "category", "evidence", "collaboration"], index)
    write_csv(AUDIT / "issue_aliases.csv", ["source_id", "primary_id", "reason"], aliases)
    return index


def main():
    """只合并已交付清单，缺项会使最终校验失败。"""
    frozen = AUDIT / "inventory_baseline.csv"
    if not frozen.exists():
        frozen.write_bytes((AUDIT / "inventory.csv").read_bytes())
    original = read_csv(frozen)
    duplicates = Counter(row["item_id"] for row in original)
    offsets = {}
    positions = Counter()
    inventory, aliases = [], []
    for source_row in original:
        row = dict(source_row)
        old = row["item_id"]
        if duplicates[old] > 1:
            if row["source"] not in offsets:
                offsets[row["source"]] = branch_nodes(ROOT / row["source"])
            occurrence = positions[old]
            positions[old] += 1
            candidates = offsets[row["source"]][(int(row["line"]), row["name"])]
            column = candidates[occurrence]
            row["item_id"] = f"{old}:c{column}:n{occurrence+1}"
            row["name"] += f"（列{column}）"
            aliases.append({"original_id": old, "item_id": row["item_id"], "owner": row["owner"], "source": row["source"], "line": row["line"], "column": column, "condition": row["description"]})
        if row["source"].startswith("data/manual_battles/") and row["kind"] == "rule_clause":
            row["kind"] = "evidence_clause"
            row["description"] = "人工观察，非规则权威：" + row["description"]
        row["_original_id"] = old
        inventory.append(row)
    seen = {row["item_id"] for row in inventory}
    for task in sorted((AUDIT / "tasks").glob("T[0-9][0-9]")):
        extra_rows = read_csv(task / "inventory_extra.csv") + read_csv(task / "inventory_addendum.csv")
        for source_row in extra_rows:
            row = dict(source_row)
            assert row["owner"] == task.name, (task.name, row)
            if row["item_id"] in seen:
                raise ValueError(f"重复extra ID：{row['item_id']}")
            seen.add(row["item_id"])
            row["_original_id"] = row["item_id"]
            inventory.append(row)
    for source_row in read_csv(AUDIT / "branch_inventory_addendum.csv"):
        row = dict(source_row)
        assert row["item_id"] not in seen, row["item_id"]
        seen.add(row["item_id"])
        row["_original_id"] = row["item_id"]
        inventory.append(row)
    task_coverage = {}
    task_stats = {}
    for task in sorted((AUDIT / "tasks").glob("T[0-9][0-9]")):
        coverage_path = task / "coverage_addendum.csv"
        values = read_csv(coverage_path if coverage_path.exists() else task / "coverage.csv")
        assert values, f"缺少{task.name}覆盖表"
        records = defaultdict(list)
        for row in values:
            records[row["item_id"]].append(row)
        task_coverage[task.name] = records
        task_stats[task.name] = {"raw_rows": len(values), "unique_original_ids": len(records), "conclusions": dict(Counter(row["conclusion"] for row in values))}
    for row in read_csv(AUDIT / "branch_coverage_addendum.csv"):
        task_coverage[row["owner"]][row["item_id"]].append(row)
    final_objects = {row["item_id"]: row for row in read_csv(AUDIT / "tasks/T06/final_object_review.csv")}
    missing = []
    coverage = []
    for item in inventory:
        task, old = item["owner"], item["_original_id"]
        options = task_coverage[task].get(old, [])
        if not options:
            missing.append((item["item_id"], task))
            continue
        row = dict(options[0])
        row.update(item_id=item["item_id"], owner=task, original_id=old, task_report=f"tasks/{task}/report.md")
        row["evidence"] = prefixed_evidence(task, row["evidence"])
        if duplicates[old] > 1:
            row["notes"] += f"；原始同行ID碰撞已按AST列拆分，本项条件为【{item['description']}】；原任务聚合证据不足以单独证明此方向，需针对该条件方向构造输入。"
            if row["conclusion"] in {"通过", "确认缺陷"}:
                row["conclusion"] = "规则存疑"
        base_id = ":".join(old.split(":")[:2])
        if task == "T06" and item["kind"] in {"skill", "ability"} and base_id in final_objects:
            updated = final_objects[base_id]
            final_conclusion = updated.get("overall_conclusion", updated.get("conclusion"))
            if final_conclusion:
                row["conclusion"] = final_conclusion
                row["evidence"] += "；tasks/T06/final_object_review.csv"
                row["notes"] += "；T00收口：对象总体结论与局部配置通过分列，参见最终对象表；子句按各自记录另列。" + updated.get("limitations", updated.get("notes", ""))
                for key in ("config_conclusion", "execution_conclusion", "overall_conclusion", "required_inputs"):
                    row[key] = updated.get(key, row.get(key, ""))
        if task == "T06" and row["conclusion"] == "检查受阻":
            row["conclusion"] = "规则存疑"
            row["notes"] += f"；协同审阅已交付，此项属于实现待证实而非权限受阻。下一步依据本行条件【{item['description']}】在关联handler配置下补真假/上下界独立预期与前后状态，不以非空配置判断正确。见T00-Q06。"
        if task == "T10" and old.startswith("FILE:") and row["conclusion"] == "检查受阻":
            row["conclusion"] = "确认缺陷"
            row["notes"] += "；文件整体已有13组具体问题，不能因不是每方向都动态运行而称文件读取受阻；未证分支仍按各行存疑。"
        assert row["conclusion"] in CONCLUSIONS, row
        for key in ("rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability"):
            assert row.get(key), (item["item_id"], key)
        coverage.append(row)
    write_csv(AUDIT / "inventory.csv", INVFIELDS, inventory)
    write_csv(AUDIT / "coverage.csv", COVFIELDS, coverage)
    write_csv(AUDIT / "id_aliases.csv", ["original_id", "item_id", "owner", "source", "line", "column", "condition"], aliases)
    issues = build_issues()
    file_rows = read_csv(AUDIT / "baseline_files.csv") + read_csv(AUDIT / "tasks/T01/additional_baseline_files.csv")
    file_rows = list({row["path"]: row for row in file_rows}.values())
    verification = []
    for row in file_rows:
        path = ROOT / row["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
        verification.append(dict(row, final_sha256=actual, matches=actual == row["sha256"]))
    write_csv(AUDIT / "baseline_files_final.csv", ["path", "owner", "sha256", "bytes", "mtime_ns", "final_sha256", "matches"], verification)
    owners = {row["source"]: row["owner"] for row in inventory if row["kind"] == "file"}
    unmatched_files = [row["path"] for row in file_rows if owners.get(row["path"]) != row["owner"]]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8").strip()
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True, encoding="utf-8")
    by_kind = defaultdict(Counter)
    for item, result in zip(inventory, coverage):
        by_kind[item["kind"]][result["conclusion"]] += 1
    summary = {"created": datetime.now().isoformat(), "head": head, "working_tree_status": status, "inventory_rows": len(inventory), "coverage_rows": len(coverage), "unique_inventory_ids": len(seen), "alias_rows": len(aliases), "missing": missing, "file_ownership_errors": unmatched_files, "source_files": len(verification), "changed_files": [row["path"] for row in verification if not row["matches"]], "conclusions": dict(Counter(row["conclusion"] for row in coverage)), "by_kind": {key: dict(value) for key, value in by_kind.items()}, "by_owner": dict(Counter(row["owner"] for row in inventory)), "task_raw_counts": task_stats, "issue_groups": len(issues), "issue_severity": dict(Counter(row["severity"] for row in issues)), "final_objects_loaded": len(final_objects), "limitations": "记录覆盖不等于所有行为路径实测；通过均为行内限定范围，复杂分支与规则不明单列。"}
    (AUDIT / "validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    assert not missing, missing[:10]
    assert not unmatched_files, unmatched_files
    assert not summary["changed_files"], summary["changed_files"]
    assert len(coverage) == len(inventory) == len(seen)
    print(json.dumps({key: value for key, value in summary.items() if key in {"head", "inventory_rows", "coverage_rows", "source_files", "changed_files", "missing", "issue_groups", "issue_severity", "final_objects_loaded", "conclusions"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
