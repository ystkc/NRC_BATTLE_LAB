"""只读核对采集源、关系和辅助表格，并在内存复现转换边界。"""

from __future__ import annotations

import collections
import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
import types
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from wiki_crawler import database as db


def read_rows(kind):
    """读取人工核对用的 UTF-8 CSV。"""
    with (ROOT / "data/wiki" / f"{kind}.csv").open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def spreadsheet(path):
    """在无 artifact_tool 运行时只读提取 OpenXML 单元格。"""
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    sheets = []
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(node.itertext()) for node in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", ns)]
        for name in sorted(archive.namelist()):
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            document = ET.fromstring(archive.read(name))
            rows = []
            for row in document.findall("s:sheetData/s:row", ns):
                values = {}
                for cell in row.findall("s:c", ns):
                    raw = cell.findtext("s:v", default="", namespaces=ns)
                    if cell.get("t") == "s":
                        raw = shared[int(raw)]
                    elif cell.get("t") == "inlineStr":
                        inline = cell.find("s:is", ns)
                        raw = "".join(inline.itertext()) if inline is not None else ""
                    values[cell.get("r")] = raw
                rows.append(values)
            sheets.append({"part": name, "rows": len(rows), "formulas": len(document.findall(".//s:f", ns)), "values": rows})
    return sheets


def main():
    """保存字段级对照、每个形态检查和可重复探针。"""
    source_db = ROOT / "data/nrc_wiki.db"
    connection = sqlite3.connect(source_db.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    all_tables = {row[0]: [dict(item) for item in connection.execute(f'SELECT * FROM "{row[0]}"')] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    csvs = {kind: read_rows(kind) for kind in ("skills", "spirits", "game_descriptions", "evolutions", "spirit_skills", "skill", "nature", "blood", "talent")}
    output = {"access": "source database sqlite mode=ro; schema probes sqlite :memory: only", "table_counts": {name: len(rows) for name, rows in all_tables.items()}, "csv_counts": {name: len(rows) for name, rows in csvs.items()}, "quick_check": connection.execute("PRAGMA quick_check").fetchall()[0][0], "foreign_key_check": [list(row) for row in connection.execute("PRAGMA foreign_key_check")]}
    elements = {row["id"]: row["name"] for row in all_tables["elements"]}
    abilities = {row["id"]: row for row in all_tables["ability_catalog"]}
    assets = {row["id"]: row["path"] for row in all_tables["assets"]}
    differences = []
    missing_rows = []
    skill_map = {"名称": "name", "技能目录ID": "wiki_id", "分类": "category", "耗能": "energy_cost", "威力": "power", "描述": "description", "归属赛季": "season", "近期状态": "recent_status", "可学习精灵": "learnable_text", "来源URL": "source_url"}
    spirit_map = {"名称": "name", "编号": "catalog_number", "精灵ID": "wiki_id", "阶段": "stage_label", "特性效果": "ability_description", "生命": "base_hp", "速度": "base_speed", "物攻": "base_attack", "魔攻": "base_magic_attack", "物防": "base_defense", "魔防": "base_magic_defense", "总种族值": "base_total", "归属赛季": "season", "蛋组": "egg_groups", "身高范围": "height_text", "体重范围": "weight_text", "身高排序值": "height_sort_value", "体重排序值": "weight_sort_value", "精灵介绍": "description", "进化链": "evolution_chain_text", "上一阶": "previous_stage_text", "下一阶": "next_stage_text", "进化等级": "evolution_levels_text", "进化条件": "evolution_condition", "来源URL": "source_url"}
    rule_map = {"名称": "name", "类别": "category", "描述": "description", "来源URL": "source_url"}

    def compare(kind, table, mapping):
        """独立比较原始字段，不借用被审计转换函数生成预期。"""
        by_name = {row["name"]: row for row in all_tables[table]}
        for raw in csvs[kind]:
            current = by_name.get(raw["名称"])
            if current is None:
                missing_rows.append({"kind": kind, "name": raw["名称"]})
                continue
            for chinese, column in mapping.items():
                expected = raw.get(chinese, "").strip()
                actual = current[column]
                equal = expected == ("" if actual is None else str(actual))
                if isinstance(actual, (int, float)) and expected:
                    try:
                        equal = float(expected) == actual
                    except ValueError:
                        pass
                if not equal:
                    differences.append({"kind": kind, "name": raw["名称"], "field": chinese, "csv": expected, "db": actual})
        for name in set(by_name) - {row["名称"] for row in csvs[kind]}:
            missing_rows.append({"kind": kind, "database_only": name})

    compare("skills", "skill_catalog", skill_map)
    compare("spirits", "spirit_forms", spirit_map)
    compare("game_descriptions", "game_rules", rule_map)
    # 联表字段与多值顺序另核对，避免只比较标量就称数据一致。
    form_checks = []
    spirit_csv = {row["名称"]: row for row in csvs["spirits"]}
    for form in all_tables["spirit_forms"]:
        raw = spirit_csv[form["name"]]
        types_actual = [elements[row[0]] for row in connection.execute("SELECT element_id FROM spirit_elements WHERE spirit_id=? ORDER BY position", (form["id"],))]
        portraits = [assets[row[0]] for row in connection.execute("SELECT asset_id FROM spirit_portraits WHERE spirit_id=? ORDER BY position", (form["id"],))]
        ability = abilities.get(form["ability_id"], {})
        flags = {"types": types_actual == raw["属性"].split("|"), "ability": ability.get("name", "") == raw["特性"], "ability_text": ability.get("description", "") == raw["特性效果"] or bool(ability.get("description_conflict")), "lord": form["is_lord"] == int(raw["是否首领"] == "yes"), "shiny": form["has_shiny"] == {"yes": 1, "no": 0}.get(raw["是否有异色"]), "portraits": portraits == [p for p in raw["立绘路径"].split("|") if p], "avatar": assets.get(form["avatar_asset_id"], "") == raw["头像路径"], "total": form["base_total"] == sum(form[key] for key in ("base_hp", "base_speed", "base_attack", "base_magic_attack", "base_defense", "base_magic_defense")), "six_present": all(form[key] is not None for key in ("base_hp", "base_speed", "base_attack", "base_magic_attack", "base_defense", "base_magic_defense"))}
        form_checks.append({"id": form["id"], "name": form["name"], "flags": flags, "passed": all(flags.values())})
    for skill in all_tables["skill_catalog"]:
        raw = next(row for row in csvs["skills"] if row["名称"] == skill["name"])
        tag_list = [row[0] for row in connection.execute("SELECT tag FROM skill_tags WHERE skill_id=? ORDER BY position", (skill["id"],))]
        for name, expected, actual in (("属性", raw["属性"].removesuffix("系"), elements.get(skill["element_id"], "")), ("标签", raw["标签"].split("|") if raw["标签"] else [], tag_list), ("图标路径", raw["图标路径"], assets.get(skill["icon_asset_id"], ""))):
            if expected != actual:
                differences.append({"kind": "skills", "name": skill["name"], "field": name, "csv": expected, "db": actual})
    for rule in all_tables["game_rules"]:
        raw = next(row for row in csvs["game_descriptions"] if row["名称"] == rule["name"])
        for name, actual in (("系别", elements.get(rule["element_id"], "")), ("系别图标路径", assets.get(rule["element_icon_asset_id"], "")), ("规则图标路径", assets.get(rule["icon_asset_id"], ""))):
            if raw[name] != actual:
                differences.append({"kind": "game_descriptions", "name": rule["name"], "field": name, "csv": raw[name], "db": actual})
    output["field_differences"] = differences
    output["missing_rows"] = missing_rows
    output["form_checks"] = form_checks
    output["ability_conflicts"] = [row for row in abilities.values() if row["description_conflict"]]
    output["empty_ability_descriptions"] = [row["name"] for row in abilities.values() if not row["description"]]
    csv_relations = {(row["精灵"], row["技能"], row["技能类别"], row["来源URL"]) for row in csvs["spirit_skills"]}
    db_relations = {(row["spirit_name"], row["skill_name"], row["skill_source"], row["source_url"]) for row in all_tables["spirit_skills"]}
    output["relation_set_differences"] = {"csv_only": sorted(csv_relations - db_relations), "db_only": sorted(db_relations - csv_relations)}
    output["unresolved_relations"] = [row for row in all_tables["spirit_skills"] if row["spirit_id"] is None or row["skill_id"] is None]
    output["duplicate_csv_keys"] = {}
    for kind, rows in csvs.items():
        keys = [(row["精灵"], row["名称"]) if kind in {"skill", "blood", "nature", "talent"} else (row["精灵"], row["技能"], row["技能类别"]) if kind == "spirit_skills" else (row["from_name"], row["to_name"]) if kind == "evolutions" else row["名称"] for row in rows]
        output["duplicate_csv_keys"][kind] = [(key, count) for key, count in collections.Counter(keys).items() if count > 1]
    output["distribution_differences"] = {}
    form_names = set(spirit_csv)
    skill_names = {row["name"] for row in all_tables["skill_catalog"]}
    for kind in ("skill", "nature", "blood", "talent"):
        expected = {(row["精灵"], row["名称"], row["百分比"], int(row["排序"])) for row in csvs[kind]}
        actual = {(row["spirit_name"], row["item_name"], row["percentage"], row["position"]) for row in all_tables["distribution_records"] if row["distribution_kind"] == kind}
        output["distribution_differences"][kind] = {"csv_only": sorted(expected - actual), "db_only": sorted(actual - expected), "unknown_forms": sorted({row["精灵"] for row in csvs[kind]} - form_names), "unknown_skills": sorted({row["名称"] for row in csvs[kind]} - skill_names) if kind == "skill" else []}
    evcols = {"from_name": "from_name", "to_name": "to_name", "from_number": "from_number", "to_number": "to_number", "from_stage": "from_stage", "to_stage": "to_stage", "method": "inference_method", "level": "required_level", "condition": "condition", "chain_text": "chain_text"}
    ev_expected = {tuple(str(row.get(col, "")) for col in evcols) for row in csvs["evolutions"]}
    ev_actual = {tuple("" if row[key] is None else str(row[key]) for key in evcols.values()) for row in all_tables["evolution_links"]}
    output["evolution_differences"] = {"csv_only": sorted(ev_expected - ev_actual), "db_only": sorted(ev_actual - ev_expected)}
    output["evolution_methods"] = dict(collections.Counter(row["inference_method"] for row in all_tables["evolution_links"]))
    base_names = {name.split("（", 1)[0].split("(", 1)[0] for name in form_names}
    output["unknown_evolution_endpoints"] = sorted({row[key] for row in all_tables["evolution_links"] for key in ("from_name", "to_name")} - base_names)
    asset_failures = []
    for row in all_tables["assets"]:
        path = ROOT / "data" / row["path"]
        if not path.is_file():
            asset_failures.append({"path": row["path"], "problem": "missing"})
        elif row["sha256"] and hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            asset_failures.append({"path": row["path"], "problem": "sha256 differs"})
    output["asset_failures"] = asset_failures
    output["asset_statuses"] = dict(collections.Counter(row["status"] for row in all_tables["assets"]))
    connection.close()
    cli = subprocess.run([sys.executable, "-m", "wiki_crawler", "--help"], cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    output["original_cli"] = {"returncode": cli.returncode, "stdout": cli.stdout, "stderr": cli.stderr}
    # 只在内存替换失效导入以继续审计下游；原始入口仍明确记为失败。
    module = types.ModuleType("audit_crawler_sync")
    module.__file__ = str(ROOT / "wiki_crawler/sync.py")
    sys.modules[module.__name__] = module
    code = (ROOT / "wiki_crawler/sync.py").read_text(encoding="utf-8").replace("from scripts.wiki_crawler.database import", "from wiki_crawler.database import")
    exec(compile(code, module.__file__, "exec"), module.__dict__)
    output["memory_probe_adapter"] = "Only import path replaced in memory; no network, staging, canonical or source database writes."
    output["configured_root"] = {"actual": str(module.ROOT), "expected_project": str(ROOT), "match": module.ROOT == ROOT}
    manual = module.load_manual_data(ROOT / "wiki_crawler/manual_data.yaml")
    output["manual_counts"] = {kind: len(rows) for kind, rows in manual.items()}
    module.current_rows = lambda kind: [{"名称": "甲", "描述": "旧", "耗能": "3"}]
    output["manual_override"] = module.merge_manual_rows("skills", [{"名称": "甲", "描述": "网", "耗能": "4"}], [{"名称": "甲", "描述": "人"}], "manual:probe")
    memory = sqlite3.connect(":memory:")
    for statement in db.SCHEMA:
        memory.execute(statement)
    db._write_distributions(memory, "skill", [{"精灵": "甲", "名称": "旧技能", "百分比": "100%", "排序": "1"}])
    db._write_distributions(memory, "skill", [{"精灵": "甲", "名称": "新技能", "百分比": "100%", "排序": "1"}])
    output["distribution_replace_probe"] = {"expected_items": ["新技能"], "actual_items": [row[0] for row in memory.execute("SELECT item_name FROM distribution_records ORDER BY item_name")]}
    memory.close()
    sample = '<table><tr class="nrc-skill-table-row" data-skill-catalog-type="火" data-skill-catalog-category="魔法"><td class="nrc-skill-table-name"><a href="/nrc/甲">甲</a></td><td class="nrc-skill-table-number" data-sort-value="2"></td><td class="nrc-skill-table-number" data-sort-value="40"></td><td class="nrc-skill-table-description">回复10%生命。</td></tr></table>'
    output["parser_probe"] = module.parse_skill_list(sample)
    output["duplicate_merge_probe"] = module._unique_records([{"名称": "甲", "耗能": "2"}, {"名称": "甲", "耗能": "8"}], "名称")
    output["xlsx"] = {name: spreadsheet(ROOT / "data" / name) for name in ("skills.xlsx", "pokemon_stats.xlsx")}
    xlsx_skills = output["xlsx"]["skills.xlsx"][0]["values"][1:]
    xlsx_forms = output["xlsx"]["pokemon_stats.xlsx"][0]["values"][1:]
    output["xlsx_comparison"] = {}
    for kind, rows, target, cols in (("skills", xlsx_skills, {row["名称"]: row for row in csvs["skills"]}, {"C": "属性", "E": "耗能", "F": "威力", "G": "描述"}), ("spirits", xlsx_forms, spirit_csv, {"F": "生命", "G": "物攻", "H": "魔攻", "I": "物防", "J": "魔防", "K": "速度", "L": "总种族值"})):
        previous_names = set()
        changed = []
        unknown = []
        for raw in rows:
            fields = {''.join(filter(str.isalpha, key)): value for key, value in raw.items()}
            name = fields.get("B", "")
            if not name:
                continue
            previous_names.add(name)
            if name not in target:
                unknown.append(name)
                continue
            for col, chinese in cols.items():
                if fields.get(col, "") != target[name].get(chinese, ""):
                    changed.append({"name": name, "field": chinese, "xlsx": fields.get(col, ""), "csv": target[name].get(chinese, "")})
        output["xlsx_comparison"][kind] = {"unique_names": len(previous_names), "xlsx_only": unknown, "csv_only": sorted(set(target) - previous_names), "changed_fields": changed}
    output["json_sources"] = []
    additional_hashes = []
    for path in sorted((ROOT / "data").rglob("*.json")):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(("data/ai_runs/", "data/audit/")):
            continue
        data = path.read_bytes()
        record = {"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "mtime_ns": path.stat().st_mtime_ns, "owner": "T00" if path.name.startswith("1002") else "T01"}
        additional_hashes.append(record)
        try:
            payload = json.loads(data.decode("utf-8-sig"))
            info = {"path": relative, "type": type(payload).__name__, "records": len(payload), "version": payload.get("version", payload.get("schema_version")) if isinstance(payload, dict) else None}
            if path.parent.name in {"wiki", "wiki_staging"} and path.stem in csvs:
                csv_path = path.with_suffix(".csv")
                with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                    reference = list(csv.DictReader(handle))
                # 分布序号 JSON 保留数值、CSV 为文本，只比较每个字段规范文本。
                def textual(row):
                    return {key: "" if row.get(key) is None else str(row[key]) for key in module.CSV_FIELDS[path.stem]}
                info["equals_adjacent_csv"] = [textual(row) for row in payload] == [textual(row) for row in reference]
            output["json_sources"].append(info)
        except (ValueError, TypeError) as error:
            output["json_sources"].append({"path": relative, "error": str(error)})
    output["latest_committed_log_comparison"] = {}
    for kind, rows in csvs.items():
        committed = db.read_committed_rows(source_db, kind)
        def normalized_text(row):
            return tuple("" if row.get(key) is None else str(row[key]) for key in module.CSV_FIELDS[kind])
        output["latest_committed_log_comparison"][kind] = {"rows": len(committed), "equal_canonical": sorted(normalized_text(row) for row in committed) == sorted(normalized_text(row) for row in rows)}
    (HERE / "additional_baseline_files.csv").write_text("", encoding="utf-8")
    with (HERE / "additional_baseline_files.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "owner", "sha256", "bytes", "mtime_ns"])
        writer.writeheader()
        writer.writerows(additional_hashes)
    (HERE / "probe_output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"forms": len(form_checks), "form_failures": sum(not row["passed"] for row in form_checks), "field_differences": len(differences), "unresolved_relations": len(output["unresolved_relations"]), "assets_failed": len(asset_failures), "cli_returncode": cli.returncode, "distribution_probe": output["distribution_replace_probe"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
