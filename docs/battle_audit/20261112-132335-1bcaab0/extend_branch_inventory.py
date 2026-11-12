"""补列表达式短路和推导式路径，不把语法枚举当行为验证。"""

from __future__ import annotations

import ast
import csv
import json
from collections import Counter
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
INVFIELDS = ["item_id", "kind", "name", "owner", "source", "line", "parent_id", "description", "reachability"]
COVFIELDS = ["item_id", "conclusion", "rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability", "owner", "original_id", "task_report", "required_inputs"]


def read_csv(path):
    """读取已有台账。"""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    """只生成本次主协调补表。"""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    """为原枚举未单列的表达式路径保存明确待证条件。"""
    base = read_csv(AUDIT / "inventory_baseline.csv")
    files = [row for row in base if row["kind"] == "file" and row["source"].endswith(".py")]
    coverage = {row["item_id"]: row for row in read_csv(AUDIT / "coverage.csv")}
    inventory, checks = [], []
    for file_row in files:
        relative, owner = file_row["source"], file_row["owner"]
        text = (ROOT / relative).read_text(encoding="utf-8-sig")
        tree = ast.parse(text, filename=relative)
        functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        for node in ast.walk(tree):
            paths = []
            if isinstance(node, ast.BoolOp):
                operation = "and" if isinstance(node.op, ast.And) else "or"
                for index, value in enumerate(node.values[:-1], 1):
                    expression = ast.get_source_segment(text, value) or ast.unparse(value)
                    for truth in ("truthy", "falsy"):
                        continuing = (truth == "truthy") == (operation == "and")
                        paths.append((value, f"{operation}{index}:{truth}", f"第{index}操作数【{expression}】为{truth}，{'继续求值后续操作数' if continuing else '短路跳过后续操作数'}", f"构造该操作数为{truth}，其前序操作数均允许求值到此；用可观测状态或调用计数区分后续表达式是否执行，核对空值/零/空容器与有效值"))
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for index, generator in enumerate(node.generators, 1):
                    expression = ast.get_source_segment(text, generator.iter) or ast.unparse(generator.iter)
                    for direction in ("iteration", "empty_or_exhausted"):
                        paths.append((generator.iter, f"comp{index}:{direction}", f"推导式第{index}层迭代【{expression}】：{direction}", "构造本层空集合、单项、两项及嵌套层为空，核对输出、迭代副作用、顺序和复制隔离"))
                    for condition_index, condition in enumerate(generator.ifs, 1):
                        condition_text = ast.get_source_segment(text, condition) or ast.unparse(condition)
                        for direction in ("true", "false"):
                            paths.append((condition, f"comp{index}:filter{condition_index}:{direction}", f"推导式过滤【{condition_text}】为{direction}", f"构造迭代项使此过滤为{direction}，前序过滤为真；独立检查该项保留/排除及被跳过表达式是否产生副作用"))
            for position, direction, description, required in paths:
                enclosing = [item for item in functions if item.lineno <= position.lineno <= item.end_lineno]
                parent = min(enclosing, key=lambda item: item.end_lineno - item.lineno) if enclosing else None
                parent_id = f"CODE:{relative}:{parent.lineno}:{parent.name}" if parent else f"FILE:{relative}"
                parent_result = coverage.get(parent_id, coverage.get(f"FILE:{relative}", {}))
                identity = f"EXPR:{relative}:{position.lineno}:{position.col_offset}:{direction}"
                source = f"{relative}:{position.lineno}（列{position.col_offset}）"
                reachability = "语法路径；当前数据能否触发需按本表达式验证，不能据未证可达性标未上线"
                inventory.append(dict(item_id=identity, kind="code_expression_branch", name=direction, owner=owner, source=relative, line=position.lineno, parent_id=parent_id, description=description, reachability=reachability))
                checks.append(dict(item_id=identity, conclusion="规则存疑", rule_basis="父函数关联依据：" + parent_result.get("rule_basis", "见所属任务逐函数审阅；此路径尚未建立精确规则映射"), implementation=source, objects=parent.name if parent else relative, method="补列短路/推导式路径并关联已交付的函数审阅；未为此方向额外执行", evidence=f"{source}；tasks/{owner}/report.md；extend_branch_inventory.py", notes=f"实现待证实：{description}。本行未复用父函数或相邻方向的通过结论。规则到本路径的精确对应及独立预期仍需补充；没有缺陷判断，也不要求用户批准常规验证。", reachability=reachability, owner=owner, original_id=identity, task_report=f"tasks/{owner}/report.md", required_inputs=required))
    assert len({row["item_id"] for row in inventory}) == len(inventory)
    write_csv(AUDIT / "branch_inventory_addendum.csv", INVFIELDS, inventory)
    write_csv(AUDIT / "branch_coverage_addendum.csv", COVFIELDS, checks)
    summary = {"rows": len(inventory), "conclusion": "规则存疑", "by_owner": dict(Counter(row["owner"] for row in inventory)), "scope": "表达式短路操作数、推导式迭代与过滤；仅补台账，不计独立行为验证通过"}
    (AUDIT / "branch_inventory_validation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
