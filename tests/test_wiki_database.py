import json
import sqlite3
import subprocess
import sys
import unittest
from contextlib import closing
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import scripts.wiki_crawler.sync as sync

from scripts.wiki_crawler.database import read_committed_rows, read_evolution_neighbors, spirit_key, sync_log_directory, write_database
from scripts.wiki_crawler.sync import _rebuild_spirit_evolution


class WikiDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / "wiki.db"

    def fetch(self, query, parameters=()):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, parameters)]

    def skill(self, name="抓挠", **overrides):
        return {
            "名称": name, "技能目录ID": "skill_000246", "属性": "普通系", "分类": "物攻",
            "耗能": "0", "威力": "35", "描述": "造成物伤，回复能量。", "归属赛季": "S1",
            "标签": "回能|连击", "近期状态": "无", "图标路径": "skill_icons/抓挠.png",
            "来源URL": "https://wiki.biligame.com/nrc/抓挠", **overrides,
        }

    def spirit(self, name="幼体", form="main", number="005", stage="1", **overrides):
        if form == "regional":
            name += "（区域）"
        return {
            "名称": name, "编号": number, "精灵ID": "shared_id", "是否首领": "yes" if "lord" in form.split("|") else "no", "阶段": stage,
            "是否有异色": "yes", "属性": "冰|萌", "归属赛季": "S1",
            "生命": "78", "速度": "54", "物攻": "62", "魔攻": "59", "物防": "39", "魔防": "78", "总种族值": "370",
            "特性": "捉迷藏", "特性效果": "冻结时增加敌方技能能耗。", "特性图标路径": "ability_icons/捉迷藏.png",
            "特性来源URL": "https://wiki.biligame.com/nrc/捉迷藏", "蛋组": "妖精组 / 拟人组",
            "身高范围": "0.39~0.42M", "体重范围": "8.39~10.7KG", "身高排序值": "0.39", "体重排序值": "8.39",
            "可骑乘": "1", "可同乘": "0", "精灵介绍": "白色绒毛，喜欢抱抱。",
            "头像路径": "spirit_icons/avatar.png", "立绘路径": "spirit_icons/portrait.png|spirit_icons/portrait2.png",
            "来源URL": "https://wiki.biligame.com/nrc/" + name, **overrides,
        }

    def test_complete_fields_assets_and_lossless_snapshot(self):
        spirit = self.spirit()
        skill = self.skill()
        spirit["未来新增字段"] = {"nested": [1, 2]}
        manifest = {"assets": {"icon": {"path": "skill_icons/抓挠.png", "url": "https://example.com/icon.png", "sha256": "hash", "status": "downloaded"}}}
        write_database(self.database, {"skills": [skill], "spirits": [spirit]}, manifest)
        row = self.fetch("SELECT * FROM spirit_forms")[0]
        self.assertEqual(row["base_hp"], 78)
        self.assertEqual(row["base_total"], 370)
        self.assertEqual(row["wiki_id"], "shared_id")
        self.assertEqual(row["catalog_number"], "005")
        self.assertEqual(row["height_text"], "0.39~0.42M")
        self.assertEqual(row["height_sort_value"], 0.39)
        self.assertEqual(row["weight_text"], "8.39~10.7KG")
        self.assertEqual(row["description"], "白色绒毛，喜欢抱抱。")
        self.assertEqual(row["rideable"], 1)
        self.assertEqual(row["double_rideable"], 0)
        self.assertEqual(row["has_shiny"], 1)
        self.assertEqual(self.fetch("SELECT COUNT(*) AS count FROM spirit_portraits")[0]["count"], 2)
        self.assertEqual([row["name"] for row in self.fetch("SELECT e.name FROM spirit_elements se JOIN elements e ON e.id=se.element_id ORDER BY se.position")], ["冰", "萌"])
        skill_row = self.fetch("SELECT * FROM skill_catalog")[0]
        self.assertEqual(skill_row["energy_cost"], 0)
        self.assertEqual(skill_row["wiki_id"], "skill_000246")
        self.assertEqual(skill_row["season"], "S1")
        self.assertEqual([row["tag"] for row in self.fetch("SELECT tag FROM skill_tags ORDER BY position")], ["回能", "连击"])
        self.assertEqual(self.fetch("SELECT source_url FROM assets WHERE path=?", ("skill_icons/抓挠.png",))[0]["source_url"], "https://example.com/icon.png")
        self.assertEqual(read_committed_rows(self.database, "spirits"), [spirit])
        self.assertEqual(read_committed_rows(self.database, "skills"), [skill])
        self.assertEqual(self.fetch("PRAGMA foreign_key_check"), [])

    def test_shared_number_and_wiki_id_keep_independent_named_spirits(self):
        rows = [self.spirit(form="main"), self.spirit(form="regional")]
        write_database(self.database, {"spirits": rows})
        self.assertEqual(len(self.fetch("SELECT * FROM spirit_forms")), 2)
        self.assertNotEqual(spirit_key(rows[0]), spirit_key(rows[1]))
        before = self.fetch("SELECT id, name FROM spirit_forms ORDER BY id")
        rows[0]["是否有异色"] = "no"
        rows[0]["精灵ID"] = "corrected_id"
        write_database(self.database, {"spirits": rows})
        self.assertEqual(self.fetch("SELECT id, name FROM spirit_forms ORDER BY id"), before)

    def test_unknown_values_are_null_not_zero(self):
        write_database(self.database, {"skills": [self.skill(耗能="", 威力="—")], "spirits": [self.spirit(生命="", 是否首领="yes", 阶段="首领", 可骑乘="", 是否有异色="")]})
        skill = self.fetch("SELECT energy_cost, power FROM skill_catalog")[0]
        self.assertIsNone(skill["energy_cost"])
        self.assertIsNone(skill["power"])
        spirit = self.fetch("SELECT base_hp, evolution_stage, rideable, has_shiny FROM spirit_forms")[0]
        self.assertTrue(all(value is None for value in spirit.values()))

    def test_basic_evolution_links_ignore_independent_appearance(self):
        rows = [self.spirit(), self.spirit(form="regional", 生命="91"), self.spirit(name="成体", number="006", stage="2")]
        edges = _rebuild_spirit_evolution(rows)
        write_database(self.database, {"spirits": rows, "evolutions": edges})
        relations = self.fetch("SELECT * FROM evolution_links")
        self.assertEqual(len(relations), 1)
        self.assertEqual((relations[0]["from_name"], relations[0]["to_name"]), ("幼体", "成体"))
        self.assertEqual(relations[0]["inference_method"], "adjacent_number_stage")
        self.assertFalse({"record_key", "from_key", "to_key", "from_spirit_id", "to_spirit_id"} & relations[0].keys())
        self.assertEqual(self.fetch("SELECT name, base_hp FROM spirit_forms ORDER BY id"), [{"name": "幼体", "base_hp": 78}, {"name": "幼体（区域）", "base_hp": 91}, {"name": "成体", "base_hp": 78}])
        self.assertEqual(read_evolution_neighbors(self.database, "幼体（区域）"), {"previous": [], "next": ["成体"]})
        self.assertEqual(read_evolution_neighbors(self.database, "幼体(区域)"), {"previous": [], "next": ["成体"]})
        self.assertEqual(read_evolution_neighbors(self.database, "成体（区域）"), {"previous": ["幼体"], "next": []})
        self.assertEqual(self.fetch("PRAGMA foreign_key_check"), [])

    def test_exact_independent_names_and_missing_relations_are_preserved(self):
        relations = [
            {"精灵": "幼体", "技能": "抓挠", "技能类别": "default-skill", "来源URL": "detail"},
            {"精灵": "未采集", "技能": "未采集技能", "技能类别": "stone-skill"},
        ]
        write_database(self.database, {"skills": [self.skill()], "spirits": [self.spirit(), self.spirit(form="regional")], "spirit_skills": relations})
        stored = self.fetch("SELECT * FROM spirit_skills ORDER BY id")
        self.assertEqual(len(stored), 2)
        self.assertIsNotNone(stored[0]["spirit_id"])
        self.assertIsNotNone(stored[0]["skill_id"])
        self.assertIsNone(stored[1]["spirit_id"])
        self.assertIsNone(stored[1]["skill_id"])
        self.assertEqual(stored[1]["spirit_name"], "未采集")
        self.assertEqual(read_committed_rows(self.database, "spirit_skills"), relations)

    def test_skill_relation_keeps_regional_name_without_form_keys(self):
        spirits = [self.spirit(), self.spirit(form="regional")]
        relation = {"精灵": "幼体（区域）", "技能": "抓挠", "技能类别": "blood-skill"}
        write_database(self.database, {"skills": [self.skill()], "spirits": spirits, "spirit_skills": [relation]})
        row = self.fetch("SELECT spirit.name FROM spirit_skills ss JOIN spirit_forms spirit ON spirit.id=ss.spirit_id")[0]
        self.assertEqual(row, {"name": "幼体（区域）"})

    def test_partial_catalog_updates_resolve_pending_relations(self):
        relation = {"精灵": "幼体", "技能": "抓挠", "技能类别": "default-skill"}
        write_database(self.database, {"spirit_skills": [relation]})
        self.assertEqual(self.fetch("SELECT spirit_id, skill_id FROM spirit_skills")[0], {"spirit_id": None, "skill_id": None})
        write_database(self.database, {"skills": [self.skill()]})
        write_database(self.database, {"spirits": [self.spirit()]})
        relation_row = self.fetch("SELECT spirit_id, skill_id FROM spirit_skills")[0]
        self.assertIsNotNone(relation_row["spirit_id"])
        self.assertIsNotNone(relation_row["skill_id"])
        self.assertEqual(read_committed_rows(self.database, "spirit_skills"), [relation])
        self.assertEqual(len(self.fetch("SELECT * FROM skill_catalog")), 1)

    def test_removal_and_unselected_kinds(self):
        spirits = [self.spirit(), self.spirit(name="成体", number="006", stage="2")]
        edges = _rebuild_spirit_evolution(spirits)
        write_database(self.database, {"skills": [self.skill()], "spirits": spirits, "evolutions": edges})
        write_database(self.database, {"spirits": spirits[:1]})
        self.assertEqual(len(self.fetch("SELECT * FROM spirit_forms")), 1)
        self.assertEqual(len(self.fetch("SELECT * FROM skill_catalog")), 1)
        edge = self.fetch("SELECT * FROM evolution_links")[0]
        self.assertEqual(edge["to_name"], "成体")
        self.assertEqual(read_evolution_neighbors(self.database, "幼体"), {"previous": [], "next": ["成体"]})
        write_database(self.database, {"evolutions": []})
        self.assertEqual(self.fetch("SELECT * FROM evolution_links"), [])
        self.assertEqual(read_committed_rows(self.database, "evolutions"), [])
        self.assertEqual(self.fetch("PRAGMA foreign_key_check"), [])

    def test_failure_rolls_back_all_kinds_without_committed_json_log(self):
        original = self.skill()
        write_database(self.database, {"skills": [original]})
        log_count = len(list(sync_log_directory(self.database).glob("*.json")))
        with self.assertRaises(sqlite3.IntegrityError):
            write_database(self.database, {"skills": [self.skill(描述="不应提交")], "spirit_skills": [{"精灵": "幼体", "技能": "抓挠", "技能类别": "invalid"}]})
        self.assertEqual(self.fetch("SELECT description FROM skill_catalog")[0]["description"], original["描述"])
        self.assertEqual(len(list(sync_log_directory(self.database).glob("*.json"))), log_count)
        self.assertEqual(read_committed_rows(self.database, "skills"), [original])

    def test_old_database_is_refused_without_any_changes(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE skill(id INTEGER PRIMARY KEY, name TEXT)")
            connection.execute("INSERT INTO skill(name) VALUES ('旧错误数据')")
            connection.commit()
        before = self.database.read_bytes()
        with self.assertRaisesRegex(ValueError, "旧战斗数据库"):
            write_database(self.database, {"skills": [self.skill()]})
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(read_committed_rows(self.database, "skills"), [])

    def test_rules_allow_missing_icons_and_schema_version(self):
        rule = {"名称": "规则", "类别": "status", "系别": "火", "描述": "完整描述"}
        write_database(self.database, {"game_descriptions": [rule]})
        row = self.fetch("SELECT * FROM game_rules")[0]
        self.assertEqual(row["description"], "完整描述")
        self.assertIsNone(row["icon_asset_id"])
        self.assertIsNone(row["element_icon_asset_id"])
        self.assertEqual(self.fetch("PRAGMA user_version")[0]["user_version"], 2)
        tables = {row["name"] for row in self.fetch("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse({"skill", "pokemon", "pokemon_skill", "sync_runs", "sync_records"} & tables)

    def test_unsupported_kinds_do_not_create_database(self):
        with self.assertRaises(ValueError):
            write_database(self.database, {"typo": []})
        self.assertFalse(self.database.exists())

    def test_conflicting_ability_text_is_not_silently_overwritten(self):
        forms = [self.spirit(), self.spirit(form="regional", 特性效果="不同的特性效果")]
        write_database(self.database, {"spirits": forms})
        ability = self.fetch("SELECT description, description_conflict FROM ability_catalog")[0]
        self.assertEqual(ability, {"description": "", "description_conflict": 1})
        self.assertEqual([row["ability_description"] for row in self.fetch("SELECT ability_description FROM spirit_forms ORDER BY id")], [forms[0]["特性效果"], forms[1]["特性效果"]])

    def test_csv_and_json_preserve_full_spirit_fields(self):
        record = self.spirit()
        record["未来字段"] = {"value": 7}
        with patch.object(sync, "STAGING_DIR", Path(self.temporary.name) / "staging"):
            path = sync.write_snapshot("spirits", [record])
        csv_record = sync.read_csv(path, "spirits")[0]
        for field in ("生命", "速度", "物攻", "魔攻", "物防", "魔防", "总种族值", "归属赛季", "蛋组", "身高范围", "体重范围", "身高排序值", "体重排序值", "精灵介绍", "特性来源URL", "可骑乘", "可同乘"):
            self.assertEqual(csv_record[field], record[field])
        self.assertEqual(json.loads(path.with_suffix(".json").read_text(encoding="utf-8")), [record])

    def run_fake_collection(self, flags):
        directory = Path(self.temporary.name)
        parser = sync.build_parser()
        args = parser.parse_args(["--kind", "all", "--database", str(self.database), *flags])
        with patch.multiple(sync, DATA=directory, STAGING_DIR=directory / "staging", CANONICAL_DIR=directory / "canonical", MANIFEST_PATH=directory / "manifest.json", DB_PATH=self.database):
            with patch.object(sync, "_skill_snapshot", return_value=[self.skill()]), patch.object(sync, "_spirit_snapshot", return_value=([self.spirit()], [])), patch.object(sync, "_game_description_snapshot", return_value=[{"名称": "规则", "描述": "内容"}]):
                with patch("sys.stdout", new=StringIO()), patch.object(sync, "configure_logging"):
                    return sync.run(args)

    def test_stage_only_does_not_create_database_or_canonical(self):
        self.assertEqual(self.run_fake_collection(["--stage-only"]), 0)
        self.assertFalse(self.database.exists())
        self.assertFalse((Path(self.temporary.name) / "canonical").exists())
        self.assertTrue((Path(self.temporary.name) / "staging" / "spirits.json").exists())

    def test_confirmed_collection_writes_new_database_and_complete_csv(self):
        self.assertEqual(self.run_fake_collection(["--yes", "--keep-missing"]), 0)
        self.assertEqual(len(self.fetch("SELECT * FROM spirit_forms")), 1)
        self.assertEqual(len(self.fetch("SELECT * FROM skill_catalog")), 1)
        self.assertEqual(len(self.fetch("SELECT * FROM game_rules")), 1)
        canonical = Path(self.temporary.name) / "canonical" / "spirits.csv"
        self.assertEqual(sync.read_csv(canonical, "spirits")[0]["生命"], "78")
        self.assertTrue(canonical.with_suffix(".json").exists())

    def test_empty_required_list_blocks_confirmed_write(self):
        with patch.object(self, "skill", return_value={}):
            directory = Path(self.temporary.name)
            args = sync.build_parser().parse_args(["--kind", "skills", "--yes", "--database", str(self.database)])
            with patch.multiple(sync, DATA=directory, STAGING_DIR=directory / "staging", CANONICAL_DIR=directory / "canonical", MANIFEST_PATH=directory / "manifest.json", DB_PATH=self.database):
                with patch.object(sync, "_skill_snapshot", return_value=[]), patch("sys.stdout", new=StringIO()), patch.object(sync, "configure_logging"):
                    self.assertEqual(sync.run(args), 1)
        self.assertFalse(self.database.exists())

    def test_new_json_log_contains_full_data_without_removed_markers(self):
        record = self.spirit()
        record.update({"未来字段": {"value": 7}})
        write_database(self.database, {"spirits": [record]})
        logs = list(sync_log_directory(self.database).glob("*.json"))
        self.assertEqual(len(logs), 1)
        payload = json.loads(logs[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["counts"], {"spirits": 1})
        self.assertEqual(payload["records"]["spirits"][0]["未来字段"], {"value": 7})
        self.assertNotIn("形态", payload["records"]["spirits"][0])
        self.assertNotIn("形态分类", payload["records"]["spirits"][0])
        self.assertIn("committed_at", payload)

    def test_json_log_failure_reports_already_committed_database(self):
        with patch("scripts.wiki_crawler.database._write_json_log", side_effect=OSError("read only")):
            with self.assertRaisesRegex(RuntimeError, "数据库已提交"):
                write_database(self.database, {"skills": [self.skill()]})
        self.assertEqual(len(self.fetch("SELECT * FROM skill_catalog")), 1)

    def test_duplicate_full_names_are_rejected_not_last_row_wins(self):
        with self.assertRaisesRegex(ValueError, "完整名称重复"):
            write_database(self.database, {"spirits": [self.spirit(), self.spirit(生命="99")]})

    def test_unsupported_schema_versions_are_refused_without_migration(self):
        for version in (1, 3):
            with self.subTest(version=version):
                with closing(sqlite3.connect(self.database)) as connection:
                    connection.execute(f"PRAGMA user_version={version}")
                before = self.database.read_bytes()
                with self.assertRaisesRegex(ValueError, "不支持的 wiki 数据库版本"):
                    write_database(self.database, {"skills": [self.skill()]})
                self.assertEqual(self.database.read_bytes(), before)
                self.assertFalse(sync_log_directory(self.database).exists())

    def test_unversioned_populated_database_is_not_implicitly_upgraded(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE custom_data(value TEXT)")
        before = self.database.read_bytes()
        with self.assertRaisesRegex(ValueError, "无版本表结构"):
            write_database(self.database, {"skills": [self.skill()]})
        self.assertEqual(self.database.read_bytes(), before)

    def test_package_and_direct_entry_points_keep_project_data_paths(self):
        project = Path(__file__).resolve().parents[1]
        self.assertEqual(sync.ROOT, project)
        self.assertEqual(sync.DATA, project / "data")
        self.assertEqual(sync.DB_PATH, project / "data" / "nrc_wiki.db")
        commands = [
            ([sys.executable, "-X", "utf8", "-m", "scripts.wiki_crawler", "--help"], project),
            ([sys.executable, "-X", "utf8", str(project / "scripts" / "wiki_crawler" / "sync.py"), "--help"], Path(self.temporary.name)),
        ]
        for command, directory in commands:
            with self.subTest(command=command):
                result = subprocess.run(command, cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--crawl-skill-relations", result.stdout)


if __name__ == "__main__":
    unittest.main()
