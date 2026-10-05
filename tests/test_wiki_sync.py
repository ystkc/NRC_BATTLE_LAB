import pytest

from scripts.wiki_crawler import sync
from scripts.wiki_crawler.sync import (
    _rebuild_spirit_evolution,
    _row_key,
    normalize_url,
    parse_game_description_list,
    parse_skill_pet_cards,
    parse_skill_list,
    parse_spirit_list,
)


def test_skill_list_uses_fixed_row_classes_and_catalog_attributes():
    html = """
    <table><thead><tr><th>技能</th><th>技能名称</th><th>技能属性</th><th>技能分类</th><th>技能能耗</th><th>技能威力</th><th>技能效果</th></tr></thead>
    <tr class="nrc-skill-table-row" data-skill-catalog-id="skill_000246" data-skill-catalog-season="S1" data-skill-catalog-tags="回能" data-skill-catalog-recent="无">
      <td class="nrc-skill-table-icon"><img alt="抓挠" src="https://patchwiki.biligame.com/images/nrc/thumb/a/ad/hash.png/42px-Skill.png"></td>
      <td class="nrc-skill-table-name"><a href="/nrc/抓挠" title="抓挠">抓挠</a></td>
      <td class="nrc-skill-table-type">普通系</td><td class="nrc-skill-table-category">物攻</td>
      <td class="nrc-skill-table-number" data-sort-value="0">0</td><td class="nrc-skill-table-number" data-sort-value="35">35</td>
      <td class="nrc-skill-table-description">造成物伤，自己回复1能量。</td>
    </tr></table>
    """
    rows = parse_skill_list(html)
    assert rows[0]["名称"] == "抓挠"
    assert rows[0]["耗能"] == "0"
    assert rows[0]["威力"] == "35"
    assert rows[0]["技能目录ID"] == "skill_000246"
    assert rows[0]["_icon_urls"][0].endswith("/a/ad/hash.png")


def test_spirit_list_uses_data_column_and_row_attributes():
    html = """
    <table><thead><tr>
      <th data-column="number">编号</th><th data-column="avatar">头像</th><th data-column="name">精灵名称</th>
      <th data-column="types">属性</th><th data-column="feature">特性</th><th data-column="hp">生命</th>
      <th data-column="featureDesc">特性效果</th><th data-column="height">身高</th>
      <th data-column="weight">体重</th><th data-column="description">精灵介绍</th>
    </tr></thead>
    <tr class="npc-table-row" data-number="142" data-stage="1" data-form="main" data-position="initial|" data-shiny="yes" data-season="S1" data-type="冰|萌">
      <td>142</td><td><img src="https://patchwiki.biligame.com/images/nrc/avatar.png"></td>
      <td><a href="/nrc/大耳帽兜" title="大耳帽兜">大耳帽兜</a></td><td data-sort-value="冰 / 萌">冰 萌</td>
      <td><div class="npc-table-feature"><img src="https://patchwiki.biligame.com/images/nrc/feature.png"><a href="/nrc/捉迷藏" title="捉迷藏">捉迷藏</a></div></td>
      <td>78</td><td>使敌方获得冻结时，也会使其获得全技能能耗+1。</td><td data-sort-value="0.39">0.39~0.42M</td>
      <td data-sort-value="8.39">8.39~10.7KG</td><td>全身覆满白色绒毛。</td>
    </tr></table>
    """
    rows = parse_spirit_list(html)
    assert rows[0]["编号"] == "142"
    assert rows[0]["名称"] == "大耳帽兜"
    assert rows[0]["属性"] == "冰|萌"
    assert rows[0]["特性"] == "捉迷藏"
    assert rows[0]["特性效果"].startswith("使敌方获得冻结")
    assert rows[0]["生命"] == "78"
    assert rows[0]["身高范围"] == "0.39~0.42M"
    assert rows[0]["身高排序值"] == "0.39"
    assert rows[0]["体重范围"] == "8.39~10.7KG"
    assert rows[0]["体重排序值"] == "8.39"
    assert rows[0]["精灵介绍"] == "全身覆满白色绒毛。"
    assert rows[0]["特性来源URL"].endswith("/%E6%8D%89%E8%BF%B7%E8%97%8F")
    assert rows[0]["_ability_icon_urls"]


def test_game_description_card_extracts_category_type_icons_and_description():
    html = """
    <div data-nrc-tag="article" class="nrc-game-description-card" data-game-description-category="status" data-description-element="火">
      <div class="nrc-game-description-mechanic-icon"><img src="https://patchwiki.biligame.com/images/nrc/rule.png"></div>
      <div class="nrc-game-description-card-top"><span class="nrc-game-description-category-chip">状态</span><span class="nrc-game-description-type-chip"><span class="nrc-game-description-type-icon"><img src="https://patchwiki.biligame.com/images/nrc/type.png"></span><span>火</span></span></div>
      <div data-nrc-tag="h2"><a href="/nrc/灼烧" title="灼烧">灼烧</a></div>
      <div class="nrc-game-description-card-desc">回合结束时，造成2%生命的火系伤害。</div>
    </div>
    """
    rows = parse_game_description_list(html)
    assert rows == [{
        "名称": "灼烧", "类别": "status", "系别": "火",
        "描述": "回合结束时，造成2%生命的火系伤害。",
        "来源URL": "https://wiki.biligame.com/nrc/%E7%81%BC%E7%83%A7",
        "_type_icon_urls": ["https://patchwiki.biligame.com/images/nrc/type.png"],
        "_rule_icon_urls": ["https://patchwiki.biligame.com/images/nrc/rule.png"],
    }]


def test_parsers_do_not_guess_from_unclassified_links():
    html = '<table><tr><td><a href="/nrc/脏数据">脏数据</a></td></tr></table>'
    assert parse_skill_list(html) == []
    assert parse_spirit_list(html) == []


def test_skill_relation_cards_are_grouped_by_source():
    html = """
    <div class="nrc-skill-pet-card" data-skill-source="default"><span class="nrc-skill-pet-name">小火</span></div>
    <div class="nrc-skill-pet-card" data-skill-source="blood"><span class="nrc-skill-pet-name">小火</span></div>
    <div class="nrc-skill-pet-card" data-skill-source="stone"><span class="nrc-skill-pet-name">大火</span></div>
    """
    rows = parse_skill_pet_cards(html, "火球", "https://wiki.biligame.com/nrc/fire")
    assert {(row["精灵"], row["技能类别"]) for row in rows} == {
        ("小火", "default-skill"), ("小火", "blood-skill"), ("大火", "stone-skill"),
    }


def test_chinese_page_url_is_percent_encoded_before_network_request():
    assert normalize_url("https://wiki.biligame.com/nrc/火球").endswith("/nrc/%E7%81%AB%E7%90%83")


def test_spirit_atlas_npc_card_extracts_portrait_and_avatar_separately():
    html = """
    <div class="npc-card is-mounted" data-id="pet_000559" data-number="001" data-stage="" data-position="" data-form="lord" data-shiny="no" data-season="none" data-type="光|草">
      <span class="npc-card-target"><a href="/nrc/dimo" title="dimo">001 dimo</a></span>
      <div class="npc-card-face"><div class="npc-card-top"><div class="npc-number">001</div><div class="npc-stage">首领</div></div>
      <div class="npc-art"><div class="npc-art-normal"><img src="https://example.com/portrait.png"></div><div class="npc-art-head"><img src="https://example.com/avatar.png"></div></div>
      <div class="npc-card-copy"><div class="npc-name">dimo</div><div class="npc-form">首领形态</div><div class="npc-card-types"><div class="npc-type" title="光系"><img src="https://example.com/type-light.png"></div><div class="npc-type" title="草系"><img src="https://example.com/type-grass.png"></div></div></div></div>
    </div>
    """
    rows = parse_spirit_list(html, "https://wiki.biligame.com/nrc/精灵图鉴", image_role="portrait")
    assert len(rows) == 1
    assert rows[0]["编号"] == "001"
    assert rows[0]["精灵ID"] == "pet_000559"
    assert rows[0]["是否首领"] == "yes"
    assert "形态" not in rows[0]
    assert "形态分类" not in rows[0]
    assert rows[0]["_portrait_urls"] == ["https://example.com/portrait.png"]
    assert rows[0]["_avatar_urls"] == ["https://example.com/avatar.png"]


def test_spirit_identity_does_not_collapse_same_number_different_forms():
    first = {"编号": "001", "精灵ID": "pet_chain", "名称": "dimo（首领）", "是否首领": "yes", "是否有异色": "no"}
    second = {"编号": "001", "精灵ID": "pet_chain", "名称": "dimo", "是否首领": "no", "是否有异色": "no"}
    assert _row_key("spirits", first) != _row_key("spirits", second)


def test_spirit_evolution_fields_connect_adjacent_numbers_not_ids():
    rows = [
        {"编号": "007", "精灵ID": "third", "名称": "三阶形态", "阶段": "3"},
        {"编号": "005", "精灵ID": "first", "名称": "一阶形态", "阶段": "1"},
        {"编号": "006", "精灵ID": "second", "名称": "二阶形态", "阶段": "2"},
        {"编号": "008", "精灵ID": "single", "名称": "单阶", "阶段": "1"},
    ]
    evolutions = _rebuild_spirit_evolution(rows)
    assert rows[0]["进化链"] == "一阶形态 → 二阶形态 → 三阶形态"
    assert rows[1]["上一阶"] == ""
    assert rows[1]["下一阶"] == "二阶形态"
    assert rows[2]["上一阶"] == "一阶形态"
    assert rows[2]["下一阶"] == "三阶形态"
    assert rows[0]["上一阶"] == "二阶形态"
    assert rows[0]["下一阶"] == ""
    assert all(rows[3][field] == "" for field in ("进化链", "上一阶", "下一阶"))
    assert {(row["from_name"], row["to_name"]) for row in evolutions} == {
        ("一阶形态", "二阶形态"), ("二阶形态", "三阶形态"),
    }


def test_evolution_deduplicates_appearances_to_basic_types_and_excludes_lord():
    rows = [
        {"编号": "001", "名称": "幼体", "阶段": "一阶", "是否首领": "no"},
        {"编号": "001", "名称": "幼体（区域）", "阶段": "1", "是否首领": "no"},
        {"编号": "001", "名称": "首领", "阶段": "1", "是否首领": "yes"},
        {"编号": "002", "名称": "成体", "阶段": "二阶", "是否首领": "no"},
        {"编号": "002", "名称": "成体(区域)", "阶段": "2", "是否首领": "no"},
    ]
    evolutions = _rebuild_spirit_evolution(rows)
    assert rows[0]["进化链"] == "幼体 → 成体"
    assert rows[1]["下一阶"] == "成体"
    assert rows[3]["上一阶"] == "幼体"
    assert rows[4]["下一阶"] == ""
    assert all(rows[2][field] == "" for field in ("进化链", "上一阶", "下一阶"))
    assert [(row["from_name"], row["to_name"]) for row in evolutions] == [("幼体", "成体")]
    assert all("from_key" not in row and "to_key" not in row for row in evolutions)
    assert all("形态" not in row and "形态分类" not in row for row in rows)
    assert rows[1]["名称"] == "幼体（区域）"


def test_evolution_skips_ambiguous_basic_types_instead_of_cross_linking():
    rows = [
        {"编号": "001", "名称": "幼体甲", "阶段": "1"},
        {"编号": "001", "名称": "幼体乙", "阶段": "1"},
        {"编号": "002", "名称": "成体", "阶段": "2"},
    ]
    assert _rebuild_spirit_evolution(rows) == []
    assert all(row["进化链"] == "" for row in rows)


def test_evolution_does_not_connect_gaps_restarted_stages_or_shared_ids():
    groups = [
        [("010", "1"), ("012", "2")],
        [("010", "1"), ("011", "3")],
        [("010", "2"), ("011", "3")],
        [("010", "1"), ("011", "1")],
    ]
    for group in groups:
        rows = [
            {"编号": number, "阶段": stage, "精灵ID": "shared", "名称": number,
             "进化链": "old", "上一阶": "old", "下一阶": "old"}
            for number, stage in group
        ]
        assert _rebuild_spirit_evolution(rows) == []
        assert all(row[field] == "" for row in rows for field in ("进化链", "上一阶", "下一阶"))


def test_evolution_separates_consecutive_independent_chains():
    rows = [
        {"编号": str(number), "名称": str(number), "阶段": str(stage)}
        for number, stage in ((1, 1), (2, 2), (3, 1), (4, 2), (5, 3))
    ]
    _rebuild_spirit_evolution(rows)
    assert rows[0]["进化链"] == "1 → 2"
    assert rows[1]["下一阶"] == ""
    assert rows[2]["进化链"] == "3 → 4 → 5"
    assert rows[2]["上一阶"] == ""


def test_deprecated_divsort_cards_are_not_parsed():
    html = '<div class="divsort" data-number="001" data-param1="1"><span class="font-mainfeiziti">旧卡片</span></div>'
    assert parse_spirit_list(html) == []


@pytest.mark.parametrize("kind,row", [
    ("skills", {"名称": "技能", "耗能": 0, "威力": 35, "描述": None}),
    ("spirits", {"名称": "幼体", "编号": "005", "阶段": 1, "生命": 78}),
    ("game_descriptions", {"名称": "规则", "描述": None}),
    ("evolutions", {"from_name": "幼体", "to_name": "成体", "from_stage": 1, "to_stage": 2, "level": None}),
    ("spirit_skills", {"精灵": "幼体", "技能": "技能", "技能类别": "default-skill"}),
])
def test_diff_ignores_csv_round_trip_and_timestamp_metadata(tmp_path, monkeypatch, kind, row):
    monkeypatch.setattr(sync, "CANONICAL_DIR", tmp_path)
    sync.write_canonical(kind, [{**row, "created_at": "2026-10-04T00:00:00Z"}])
    incoming = [{**row, "created_at": "2026-10-05T00:00:00Z"}]
    summary = sync.diff_rows(kind, incoming)
    assert summary == {"current": 1, "incoming": 1, "new": [], "missing": [], "changed": []}
    assert incoming == [{**row, "created_at": "2026-10-05T00:00:00Z"}]


@pytest.mark.parametrize("kind,row,patch", [
    ("spirits", {"名称": "幼体", "生命": "78"}, {"生命": 79}),
    ("spirits", {"名称": "幼体", "进化条件": "道具"}, {"进化条件": None}),
    ("evolutions", {"from_name": "幼体", "to_name": "成体", "level": "30"}, {"level": 31}),
    ("skills", {"名称": "技能", "耗能": "0"}, {"耗能": ""}),
])
def test_diff_still_reports_business_field_changes(tmp_path, monkeypatch, kind, row, patch):
    monkeypatch.setattr(sync, "CANONICAL_DIR", tmp_path)
    sync.write_canonical(kind, [row])
    summary = sync.diff_rows(kind, [{**row, **patch}])
    assert summary["changed"] == [sync._row_key(kind, row)]
    assert summary["new"] == summary["missing"] == []


def test_diff_preserves_added_and_missing_keys(monkeypatch):
    monkeypatch.setattr(sync, "current_rows", lambda kind: [{"名称": "旧精灵"}])
    summary = sync.diff_rows("spirits", [{"名称": "新精灵"}])
    assert summary == {"current": 1, "incoming": 1, "new": ["新精灵"], "missing": ["旧精灵"], "changed": []}
