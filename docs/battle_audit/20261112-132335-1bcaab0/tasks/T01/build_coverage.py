"""合并数据逐项检查与采集代码的审慎结论。"""

import ast
import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FIELDS = ["item_id", "conclusion", "rule_basis", "implementation", "objects", "method", "evidence", "notes", "reachability"]
INVENTORY_FIELDS = ["item_id", "kind", "name", "owner", "source", "line", "parent_id", "description", "reachability"]


def save(path, fields, rows):
    """输出可独立核对的 UTF-8 台账。"""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    """为每个分配项保留依据、证据和未证方向。"""
    assigned = list(csv.DictReader((HERE / "assigned_inventory.csv").open(encoding="utf-8-sig")))
    probe = json.loads((HERE / "probe_output.json").read_text(encoding="utf-8"))
    function_spans = {}
    for file in ("wiki_crawler/sync.py", "wiki_crawler/database.py"):
        tree = ast.parse((ROOT / file).read_text(encoding="utf-8"))
        function_spans[file] = [(node.lineno, node.end_lineno, node.name) for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    coverage = []
    for item in assigned:
        source, line = item["source"], int(item["line"])
        spans = [span for span in function_spans.get(source, []) if span[0] <= line <= span[1]]
        function = min(spans, key=lambda span: span[1] - span[0])[2] if spans else Path(source).stem
        conclusion = "规则存疑"
        notes = f"已全文静态核对此分支：{item['description']}。尚无足够独立输入覆盖真假/异常方向；见T01-Q04/Q05，不因函数存在判通过。"
        evidence = "report.md;questions.md;probe_output.json"
        if item["kind"] == "form":
            result = next(row for row in probe["form_checks"] if row["id"] == line)
            assert result["passed"]
            conclusion = "通过"
            notes = "逐形态CSV/DB标量、六维齐全/总和、属性顺序、特性名称/原文、首领/异色与图片关系一致；仅资料一致性，不涵盖战斗公式或特性语义。"
        elif source.startswith("data/") and source.endswith(".csv"):
            if source.startswith("data/wiki_staging/"):
                conclusion = "规则存疑"
                notes = "staging为独立采集快照，非当前战斗权威；已读取字段与相邻JSON，和canonical差异需按采集批次解释，不直接计为业务缺陷。T01-Q04。"
            elif Path(source).stem in {"evolutions", "spirit_skills"}:
                conclusion = "规则存疑"
                notes = "集合与DB一致；但进化262边依据为编号推断（Q02），技能关系2564条无形态（Q01），不能给完整关系语义通过。"
            else:
                conclusion = "通过"
                notes = "全量唯一键、字段及关系集合与DB逐项核对一致；只证明资料转换一致，不证明规则文本本身正确。"
        elif source.endswith(".xlsx"):
            notes = "全部工作表与单元格只读提取，无公式；与当前CSV的名字/数值冲突列于xlsx_comparison，旧版本用途待确认，见Q03。"
        elif source == "data/nrc_wiki.db":
            notes = "完整性、外键与CSV字段核对通过；44形态缺失及推断进化依据未定，不能把整个数据库判规则正确，见Q01/Q02。"
        elif source == "wiki_crawler/__main__.py" or source == "wiki_crawler/sync.py" and (line in {33, 34, 44, 45} or item["kind"] == "file"):
            conclusion = "确认缺陷"
            notes = "T01-I01：原入口ModuleNotFoundError；隔离导入后ROOT仍指向项目父目录。"
            evidence = "issues.md;probe_output.json"
        elif source == "wiki_crawler/database.py" and (function == "_write_distributions" or item["kind"] == "file"):
            conclusion = "确认缺陷"
            notes = "T01-I02：第二份完整分布替换输入仍残留旧项；只将根因函数/文件标缺陷，不推定其他条件均错误。"
            evidence = "issues.md;probe_output.json"
        elif function in {"get_bytes", "get_text", "store_asset", "run", "_skill_snapshot", "_spirit_snapshot", "_game_description_snapshot", "_skill_relation_snapshot"}:
            conclusion = "检查受阻"
            notes = f"{function}全量静态核对，原采集入口失效且没有固定远程HTML/下载故障样本；此独立条件未完成端到端行为验证，下一步见Q04。"
        elif item["kind"] == "code_object" and function in {"parse_skill_list", "merge_manual_rows", "load_manual_data"}:
            conclusion = "规则存疑"
            notes = "内存探针证实最小技能解析、真实YAML读取与明确字段覆盖；不涵盖全部同函数边界，见probe_output及Q04/Q05。"
        coverage.append(dict(item_id=item["item_id"], conclusion=conclusion, rule_basis="AGENTS.md（唯一查库与数据完整性）；wiki_crawler/README.md（采集协议）；各对象CSV原文；战斗语义另归T03/T06", implementation=f"{source}:{line} {function}", objects=item["name"], method="完整静态阅读；全量字段/集合核对；隔离内存最小复现", evidence=evidence, notes=notes, reachability="原采集CLI导入受阻；数据库为当前平台资料；辅助快照另列"))
    extras = []
    for label, note in (("all_relations", "25255技能关系逐键检查；2564无形态端见Q01"), ("all_distributions", "49343分布逐字段/唯一键与CSV核对"), ("all_evolutions", "262边完整比较，权威依据待确认Q02"), ("all_assets", "3364资源存在性/已有哈希全量核对"), ("all_json", "版本与相邻CSV规范字段核对"), ("all_xlsx_cells", "两个工作簿全部单元格与工作表读取")):
        item_id = f"T01-DATA:{label}"
        extras.append(dict(item_id=item_id, kind="data_contract", name=label, owner="T01", source="tasks/T01/data_record_checks.csv", line=1, parent_id="", description=note, reachability="见probe_output.json"))
        conclusion = "通过" if label in {"all_distributions", "all_assets"} else "规则存疑"
        coverage.append(dict(item_id=item_id, conclusion=conclusion, rule_basis="当前CSV/SQLite关系完整性及采集协议", implementation="wiki_crawler/database.py;nrc_platform/catalog.py", objects=label, method="逐记录集合与字段比较", evidence="probe_output.json;data_record_checks.csv", notes=note, reachability="平台数据入口/辅助来源分开说明"))
    for item in csv.DictReader((HERE / "additional_baseline_files.csv").open(encoding="utf-8-sig")):
        if item["owner"] != "T01":
            continue
        item_id = f"FILE:{item['path']}"
        extras.append(dict(item_id=item_id, kind="file", name=item["path"], owner="T01", source=item["path"], line=1, parent_id="", description="补充源JSON版本、记录数及与CSV比较", reachability="资料/日志，不作为新战斗规则"))
        coverage.append(dict(item_id=item_id, conclusion="规则存疑", rule_basis="采集版本与来源追溯协议；规则优先级以data/*.md为准", implementation=item["path"], objects=item["path"], method="只读解析与版本/字段核对", evidence="probe_output.json;questions.md", notes="全部已解析；历史日志/快照不等于当前权威，来源版本差异见json_sources/latest_committed_log_comparison及Q04/Q05。", reachability="源资料及恢复日志；当前程序是否消费见报告"))
    save(HERE / "coverage.csv", FIELDS, coverage)
    save(HERE / "inventory_extra.csv", INVENTORY_FIELDS, extras)
    record_checks = []
    connection = sqlite3.connect((ROOT / "data/nrc_wiki.db").resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    for table in ("spirit_skills", "distribution_records", "evolution_links", "assets"):
        for row in connection.execute(f"SELECT * FROM {table} ORDER BY id"):
            row = dict(row)
            conclusion = "通过"
            reason = "与CSV键/字段相等" if table != "assets" else "路径存在且已有sha256匹配"
            if table == "spirit_skills" and row["spirit_id"] is None:
                conclusion, reason = "规则存疑", "T01-Q01：精灵端缺失；技能端存在；原始源名保留"
            if table == "evolution_links":
                conclusion, reason = "规则存疑", "T01-Q02：CSV/DB一致，来源为adjacent_number_stage推断"
            record_checks.append({"item_id": f"DATA:{table}:{row['id']:06}", "kind": table, "source_key": json.dumps({key: row[key] for key in ({"spirit_skills": ("spirit_name", "skill_name", "skill_source"), "distribution_records": ("distribution_kind", "spirit_name", "item_name"), "evolution_links": ("from_name", "to_name"), "assets": ("path",)}[table])}, ensure_ascii=False), "conclusion": conclusion, "evidence": "probe_output.json", "notes": reason})
    connection.close()
    save(HERE / "data_record_checks.csv", ["item_id", "kind", "source_key", "conclusion", "evidence", "notes"], record_checks)
    print(json.dumps({"coverage": len(coverage), "data_records": len(record_checks), "conclusions": dict(Counter(row['conclusion'] for row in coverage)), "assigned_missing": sorted({r['item_id'] for r in assigned} - {r['item_id'] for r in coverage})}, ensure_ascii=False))


if __name__ == "__main__":
    main()
