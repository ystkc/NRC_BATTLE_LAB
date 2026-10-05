import json
import sqlite3
from contextlib import closing

import pytest

from scripts.wiki_crawler import sync
from scripts.wiki_crawler.database import read_committed_rows, write_database


def test_default_template_is_empty_and_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = sync.build_parser().parse_args([])
    assert args.manual_data == sync.ROOT / "scripts/wiki_crawler/manual_data.yaml"
    assert sync.load_manual_data(args.manual_data) == {kind: [] for kind in sync.CSV_FIELDS}


def test_yaml_normalizes_scalars_lists_and_explicit_empty_values(tmp_path):
    path = tmp_path / "manual.yaml"
    path.write_text('''version: 1
skills:
  - 名称: 新技能
    耗能: 0
    威力: null
    标签: [回能, 连击]
spirits:
  - 名称: 新精灵（区域）
    编号: "005"
    是否首领: false
    是否有异色: true
    属性: [冰, 萌]
evolutions:
  - from_name: 幼体（区域）
    to_name: 成体(区域)
''', encoding="utf-8-sig")
    rows = sync.load_manual_data(path)
    assert rows["skills"][0] == {"名称": "新技能", "耗能": "0", "威力": "", "标签": "回能|连击"}
    assert rows["spirits"][0]["编号"] == "005"
    assert rows["spirits"][0]["名称"] == "新精灵（区域）"
    assert rows["spirits"][0]["是否首领"] == "no"
    assert rows["spirits"][0]["是否有异色"] == "yes"
    assert rows["spirits"][0]["属性"] == "冰|萌"
    assert rows["evolutions"][0] == {"from_name": "幼体", "to_name": "成体", "method": "manual"}


@pytest.mark.parametrize("content", [
    "- not-a-mapping",
    "version: 2",
    "version: true",
    "skill: []",
    "skills: null",
    "skills: [bad-record]",
    "skills: [{描述: 缺少名称}]",
    "skills: [{名称: 技能, 错误字段: 1}]",
    "skills: [{名称: 技能, 描述: {嵌套: 错误}}]",
    "skills: [{名称: 技能, 标签: [1]}]",
    "skills: [{名称: 技能, 名称: 另一个技能}]",
    "skills: []\nskills: []",
    "skills: [{名称: 技能}, {名称: ' 技能 '}]",
    "evolutions: [{from_name: 幼体}]",
    "evolutions: [{from_name: '幼体（区域）', to_name: 成体}, {from_name: 幼体, to_name: 成体}]",
    "spirit_skills: [{精灵: 幼体, 技能: 技能, 技能类别: unknown}]",
    "skills: [{名称: !!python/object:builtins.object {}}]",
])
def test_invalid_yaml_is_rejected(tmp_path, content):
    path = tmp_path / "manual.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        sync.load_manual_data(path)


def test_missing_manual_file_is_reported(tmp_path):
    with pytest.raises(ValueError, match="无法读取人工 YAML"):
        sync.load_manual_data(tmp_path / "missing.yaml")


def test_manual_fields_override_without_erasing_wiki_and_input(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "current_rows", lambda kind: [])
    incoming = [{"名称": "技能", "耗能": "3", "威力": "35", "描述": "Wiki", "来源URL": "wiki"}]
    patches = [{"名称": "技能", "耗能": "0", "描述": "人工"}, {"名称": "新技能", "威力": ""}]
    result = sync.merge_manual_rows("skills", incoming, patches, "manual:example.yaml")
    assert result[0] == {**incoming[0], "耗能": "0", "描述": "人工"}
    assert result[1] == {"名称": "新技能", "威力": "", "来源URL": "manual:example.yaml"}
    assert incoming[0]["耗能"] == "3"
    assert "来源URL" not in patches[1]


def test_partial_patch_uses_committed_baseline_and_preserves_exact_names(monkeypatch):
    baseline = [{"名称": "精灵（区域）", "生命": "78", "是否首领": "yes"}]
    monkeypatch.setattr(sync, "current_rows", lambda kind: baseline)
    rows = sync.merge_manual_rows("spirits", [{"名称": "精灵"}], [{"名称": "精灵（区域）", "特性效果": "人工效果"}], "manual:test.yaml")
    assert len(rows) == 2
    assert rows[1]["生命"] == "78"
    assert rows[1]["是否首领"] == "yes"
    assert rows[1]["特性效果"] == "人工效果"


def test_manual_spirits_rebuild_evolutions_before_manual_conditions(monkeypatch):
    monkeypatch.setattr(sync, "current_rows", lambda kind: [])
    incoming = {"spirits": [{"名称": "幼体", "编号": "005", "阶段": "1"}], "evolutions": []}
    manual = {
        "spirits": [{"名称": "成体", "编号": "006", "阶段": "2"}],
        "evolutions": [{"from_name": "幼体", "to_name": "成体", "level": "30", "method": "manual"}],
    }
    sync.apply_manual_data(incoming, manual, "manual:test.yaml")
    assert incoming["spirits"][0]["下一阶"] == "成体"
    assert incoming["spirits"][1]["上一阶"] == "幼体"
    assert len(incoming["evolutions"]) == 1
    assert incoming["evolutions"][0]["level"] == "30"
    assert incoming["evolutions"][0]["from_number"] == "005"


@pytest.fixture
def collection(tmp_path, monkeypatch):
    database = tmp_path / "wiki.db"
    for name, value in {
        "DB_PATH": database, "DATA": tmp_path, "STAGING_DIR": tmp_path / "staging",
        "CANONICAL_DIR": tmp_path / "canonical", "MANIFEST_PATH": tmp_path / "manifest.json",
    }.items():
        monkeypatch.setattr(sync, name, value)
    monkeypatch.setattr(sync, "configure_logging", lambda *args: None)
    monkeypatch.setattr(sync, "_skill_snapshot", lambda *args: [{"名称": "Wiki技能", "耗能": "3", "威力": "35"}])
    monkeypatch.setattr(sync, "_spirit_snapshot", lambda *args: ([{"名称": "Wiki精灵", "生命": "78"}], []))
    monkeypatch.setattr(sync, "_game_description_snapshot", lambda *args: [{"名称": "Wiki规则", "描述": "wiki"}])

    def run(content, *flags):
        manual_path = tmp_path / "manual.yaml"
        manual_path.write_text(content, encoding="utf-8")
        args = sync.build_parser().parse_args(["--database", str(database), "--manual-data", str(manual_path), *flags])
        return sync.run(args)

    return run, database


def test_confirmed_manual_data_reaches_database_canonical_and_log(collection, tmp_path):
    run, database = collection
    assert run('''skills:
  - 名称: Wiki技能
    耗能: 0
  - 名称: 人工技能
    威力: null
spirits:
  - 名称: Wiki精灵
    特性: 人工特性
    特性效果: 人工效果
game_descriptions:
  - 名称: 人工规则
    描述: 人工说明
spirit_skills:
  - 精灵: Wiki精灵
    技能: 人工技能
    技能类别: blood-skill
''', "--yes", "--remove-missing") == 0
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT energy_cost, power FROM skill_catalog WHERE name='Wiki技能'").fetchone() == (0, 35)
        assert connection.execute("SELECT power FROM skill_catalog WHERE name='人工技能'").fetchone() == (None,)
        assert connection.execute("SELECT description FROM ability_catalog WHERE name='人工特性'").fetchone() == ("人工效果",)
        assert connection.execute("SELECT COUNT(*) FROM spirit_skills WHERE spirit_id IS NOT NULL AND skill_id IS NOT NULL").fetchone() == (1,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert len(sync.read_csv(tmp_path / "canonical/skills.csv", "skills")) == 2
    assert len(read_committed_rows(database, "skills")) == 2
    snapshot = json.loads((tmp_path / "staging/snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["wiki_counts"]["skills"] == 1
    assert snapshot["manual_data"]["counts"]["skills"] == 2
    assert snapshot["counts"]["skills"] == 2


def test_manual_stage_only_never_creates_database(collection, tmp_path):
    run, database = collection
    assert run("skills: [{名称: 人工技能}]", "--stage-only") == 0
    assert not database.exists()
    assert not (tmp_path / "canonical").exists()
    assert len(json.loads((tmp_path / "staging/skills.json").read_text(encoding="utf-8"))) == 2


def test_manual_data_does_not_mask_empty_wiki(collection, monkeypatch):
    run, database = collection
    monkeypatch.setattr(sync, "_skill_snapshot", lambda *args: [])
    assert run("skills: [{名称: 人工技能}]", "--kind", "skills", "--yes") == 1
    assert not database.exists()


def test_invalid_file_stops_before_fetching(collection, monkeypatch):
    run, database = collection
    def unexpected_fetch(*args):
        pytest.fail("invalid YAML must be rejected before fetching")
    monkeypatch.setattr(sync, "_skill_snapshot", unexpected_fetch)
    assert run("skills: [{名称: 技能, 错字: 3}]", "--yes") == 2
    assert not database.exists()


def test_kind_selection_does_not_import_other_manual_categories(collection):
    run, database = collection
    assert run("spirits: [{名称: 不应导入的精灵}]", "--kind", "skills", "--yes") == 0
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM spirit_forms").fetchone() == (0,)


def test_manual_relations_preserve_existing_without_detail_crawl(collection):
    run, database = collection
    old_relation = {"精灵": "旧精灵", "技能": "旧技能", "技能类别": "stone-skill"}
    write_database(database, {"spirit_skills": [old_relation]})
    assert run("spirit_skills: [{精灵: Wiki精灵, 技能: Wiki技能, 技能类别: default-skill}]", "--yes", "--remove-missing") == 0
    rows = read_committed_rows(database, "spirit_skills")
    assert len(rows) == 2
    assert old_relation in rows


def test_no_manual_data_does_not_read_default_file(collection, monkeypatch):
    run, database = collection
    def unexpected_load(*args):
        pytest.fail("disabled manual data must not be read")
    monkeypatch.setattr(sync, "load_manual_data", unexpected_load)
    args = sync.build_parser().parse_args(["--database", str(database), "--no-manual-data", "--yes"])
    assert sync.run(args) == 0
    assert len(read_committed_rows(database, "skills")) == 1
