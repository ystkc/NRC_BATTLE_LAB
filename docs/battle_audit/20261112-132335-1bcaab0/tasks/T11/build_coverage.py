"""合并平台完整静态阅读与明确边界证据，保留待证分支。"""

import ast
import csv
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3].parents[1]
FIELDS = ["item_id", "conclusion", "rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability"]


def main():
    """逐ID记录实际已审内容，不将所有静态定位计为通过。"""
    audit = OUT.parents[1]
    root = audit.parents[2]
    with (OUT / "assigned_inventory.csv").open(encoding="utf-8-sig", newline="") as file:
        inventory = list(csv.DictReader(file))
    issues = {"_normalize_creature": "T11-I01", "_visible_events": "T11-I02", "normalize_observation": "T11-I03", "predict_damage": "T11-I04"}
    verified = {"_serialized": "outer_transaction_rollback", "_room_operation": "outer_transaction_rollback", "export_battle": "snapshot_pending_roundtrip", "import_battle": "snapshot_pending_roundtrip", "submit_selection": "simultaneous_submissions", "select_action": "room_idempotence", "battle_events": "cursor_audit-a", "_ensure_mutable": "terminal_lock", "_member": "身份成员表读取与非成员显式异常（源码静态）", "_swap_team_code": "1007双视角事件原始team及私有字段翻转（源码+replay）"}
    spans = {}
    for path in {row["source"] for row in inventory if row["source"].endswith(".py")}:
        tree = ast.parse((root / path).read_text(encoding="utf-8-sig"))
        spans[path] = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    coverage = []
    for row in inventory:
        path, line = row["source"], int(row["line"])
        containers = [node for node in spans.get(path, []) if node.lineno <= line <= node.end_lineno]
        function = min(containers, key=lambda node: node.end_lineno - node.lineno).name if containers else Path(path).stem
        conclusion = "规则存疑"
        note = f"已静态核对{function}调用、输入和输出；本项{row['name']}：{row['description']}。"
        evidence = "report.md;questions.md"
        if function in issues:
            conclusion = "确认缺陷" if row["kind"] != "code_branch" else "规则存疑"
            evidence = "issues.md#" + issues[function] + ";probe_output.json"
            note += "函数含已复现缺陷；分支级另保留条件待证，不把函数全部分支等同缺陷。"
        elif function in verified:
            conclusion = "通过" if row["kind"] in {"code_object", "file"} else "规则存疑"
            evidence = "probe_output.json:" + verified[function]
            note += "通过仅限该函数已记录的契约样本/直接等价的静态适配；该语法方向未独立构造时不冒充动态覆盖。"
        else:
            note += "具体待证：此条件真假方向或转换字段在全部技能/特性组合下的独立预期；应沿对应机制补输入与观测/事件对照，详questions.md。"
        coverage.append(dict(item_id=row["item_id"], conclusion=conclusion, rule_basis="data/对战过程中的信息遮蔽规则.md;data/状态分类.md;data/部分规则详解/战报.md;AGENTS.md;平台协议（只作接口约定）", implementation=f"{path}:{line} {function}", objects=function, method="完整静态阅读；重点边界实际复现；1007双顺序回放", evidence=evidence, notes=note, reachability="生产RoomService/BattlePlatform调用；本地快照/预测入口单列于报告"))
    for name, conclusion, basis in (("outer_transaction_rollback", "通过", "异常回滚接口契约"), ("room_idempotence", "通过", "双人请求幂等接口契约"), ("snapshot_pending_roundtrip", "通过", "快照恢复语义契约；不要求pickle字节相同"), ("simultaneous_submissions", "通过", "双方提交一次推进契约"), ("terminal_lock", "通过", "data/README.md:33")):
        identifier = "T11:CONTRACT:" + name
        inventory.append(dict(item_id=identifier, kind="contract_branch", name=name, owner="T11", source="nrc_platform/platform.py", line=1, parent_id="", description=basis, reachability="当前生产路径/本地快照入口"))
        coverage.append(dict(item_id=identifier, conclusion=conclusion, rule_basis=basis, implementation="nrc_platform/platform.py;nrc_platform/rooms.py", objects=name, method="独立两身份实际复现", evidence=f"probe_output.json:{name}", notes="快照pickle可重排不作字节等价要求；恢复后提交结果及双视角观测相等。", reachability="当前生产路径/本地快照入口"))
    with (OUT / "coverage.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, FIELDS)
        writer.writeheader()
        writer.writerows(coverage)
    with (OUT / "inventory_extra.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, list(inventory[0]))
        writer.writeheader()
        writer.writerows(inventory[-5:])
    print(json.dumps({"assigned": len(inventory) - 5, "extra": 5, "coverage": dict(Counter(row["conclusion"] for row in coverage))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
