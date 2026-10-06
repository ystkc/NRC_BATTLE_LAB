"""Versioned wiki catalog storage, isolated from the legacy battle database."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SCHEMA_VERSION = 3
LOGGER = logging.getLogger("nrc.wiki.database")
KINDS = {"skills", "spirits", "evolutions", "spirit_skills", "game_descriptions", "skill", "nature", "blood", "talent"}
SCHEMA = (
    """CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY,
        path TEXT NOT NULL UNIQUE,
        source_url TEXT NOT NULL DEFAULT '',
        sha256 TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'unknown'
    )""",
    """CREATE TABLE IF NOT EXISTS elements (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )""",
    """CREATE TABLE IF NOT EXISTS skill_catalog (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        wiki_id TEXT NOT NULL DEFAULT '',
        element_id INTEGER REFERENCES elements(id),
        category TEXT NOT NULL DEFAULT '',
        energy_cost INTEGER CHECK(energy_cost >= 0),
        power INTEGER CHECK(power >= -1),
        description TEXT NOT NULL DEFAULT '',
        season TEXT NOT NULL DEFAULT '',
        recent_status TEXT NOT NULL DEFAULT '',
        learnable_text TEXT NOT NULL DEFAULT '',
        icon_asset_id INTEGER REFERENCES assets(id),
        source_url TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS skill_tags (
        skill_id INTEGER NOT NULL REFERENCES skill_catalog(id) ON DELETE CASCADE,
        tag TEXT NOT NULL,
        position INTEGER NOT NULL,
        PRIMARY KEY(skill_id, tag)
    )""",
    """CREATE TABLE IF NOT EXISTS ability_catalog (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        description_conflict INTEGER NOT NULL DEFAULT 0 CHECK(description_conflict IN (0, 1)),
        icon_asset_id INTEGER REFERENCES assets(id),
        source_url TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS spirit_forms (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        wiki_id TEXT NOT NULL DEFAULT '',
        catalog_number TEXT NOT NULL DEFAULT '',
        evolution_stage INTEGER CHECK(evolution_stage IN (1, 2, 3)),
        stage_label TEXT NOT NULL DEFAULT '',
        is_lord INTEGER NOT NULL DEFAULT 0 CHECK(is_lord IN (0, 1)),
        has_shiny INTEGER CHECK(has_shiny IN (0, 1)),
        season TEXT NOT NULL DEFAULT '',
        ability_id INTEGER REFERENCES ability_catalog(id),
        ability_description TEXT NOT NULL DEFAULT '',
        base_hp INTEGER CHECK(base_hp >= 0),
        base_speed INTEGER CHECK(base_speed >= 0),
        base_attack INTEGER CHECK(base_attack >= 0),
        base_magic_attack INTEGER CHECK(base_magic_attack >= 0),
        base_defense INTEGER CHECK(base_defense >= 0),
        base_magic_defense INTEGER CHECK(base_magic_defense >= 0),
        base_total INTEGER CHECK(base_total >= 0),
        egg_groups TEXT NOT NULL DEFAULT '',
        height_text TEXT NOT NULL DEFAULT '',
        height_sort_value REAL,
        weight_text TEXT NOT NULL DEFAULT '',
        weight_sort_value REAL,
        rideable INTEGER CHECK(rideable IN (0, 1)),
        double_rideable INTEGER CHECK(double_rideable IN (0, 1)),
        description TEXT NOT NULL DEFAULT '',
        avatar_asset_id INTEGER REFERENCES assets(id),
        evolution_chain_text TEXT NOT NULL DEFAULT '',
        previous_stage_text TEXT NOT NULL DEFAULT '',
        next_stage_text TEXT NOT NULL DEFAULT '',
        evolution_levels_text TEXT NOT NULL DEFAULT '',
        evolution_condition TEXT NOT NULL DEFAULT '',
        source_url TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS spirit_elements (
        spirit_id INTEGER NOT NULL REFERENCES spirit_forms(id) ON DELETE CASCADE,
        element_id INTEGER NOT NULL REFERENCES elements(id),
        position INTEGER NOT NULL,
        PRIMARY KEY(spirit_id, element_id)
    )""",
    """CREATE TABLE IF NOT EXISTS spirit_portraits (
        spirit_id INTEGER NOT NULL REFERENCES spirit_forms(id) ON DELETE CASCADE,
        asset_id INTEGER NOT NULL REFERENCES assets(id),
        position INTEGER NOT NULL,
        PRIMARY KEY(spirit_id, asset_id)
    )""",
    """CREATE TABLE IF NOT EXISTS game_rules (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL DEFAULT '',
        element_id INTEGER REFERENCES elements(id),
        element_icon_asset_id INTEGER REFERENCES assets(id),
        icon_asset_id INTEGER REFERENCES assets(id),
        description TEXT NOT NULL DEFAULT '',
        source_url TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS evolution_links (
        id INTEGER PRIMARY KEY,
        from_name TEXT NOT NULL,
        to_name TEXT NOT NULL,
        from_number TEXT NOT NULL DEFAULT '',
        to_number TEXT NOT NULL DEFAULT '',
        from_stage INTEGER,
        to_stage INTEGER,
        required_level INTEGER,
        condition TEXT NOT NULL DEFAULT '',
        chain_text TEXT NOT NULL DEFAULT '',
        inference_method TEXT NOT NULL DEFAULT '',
        UNIQUE(from_name, to_name)
    )""",
    """CREATE TABLE IF NOT EXISTS spirit_skills (
        id INTEGER PRIMARY KEY,
        record_key TEXT NOT NULL UNIQUE,
        spirit_id INTEGER REFERENCES spirit_forms(id) ON DELETE SET NULL,
        skill_id INTEGER REFERENCES skill_catalog(id) ON DELETE SET NULL,
        spirit_name TEXT NOT NULL,
        skill_name TEXT NOT NULL,
        skill_source TEXT NOT NULL CHECK(skill_source IN ('default-skill', 'blood-skill', 'stone-skill')),
        source_url TEXT NOT NULL DEFAULT ''
    )""",
    "CREATE INDEX IF NOT EXISTS idx_spirit_name ON spirit_forms(name)",
    "CREATE INDEX IF NOT EXISTS idx_spirit_number ON spirit_forms(catalog_number)",
    "CREATE INDEX IF NOT EXISTS idx_spirit_wiki_id ON spirit_forms(wiki_id)",
    "CREATE INDEX IF NOT EXISTS idx_evolution_from ON evolution_links(from_name)",
    "CREATE INDEX IF NOT EXISTS idx_evolution_to ON evolution_links(to_name)",
    "CREATE INDEX IF NOT EXISTS idx_spirit_skill_spirit ON spirit_skills(spirit_id)",
    """CREATE TABLE IF NOT EXISTS distribution_records (
        id INTEGER PRIMARY KEY,
        distribution_kind TEXT NOT NULL,
        spirit_name TEXT NOT NULL,
        item_name TEXT NOT NULL,
        percentage TEXT NOT NULL DEFAULT '',
        position INTEGER NOT NULL,
        UNIQUE(distribution_kind, spirit_name, item_name)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_spirit_skill_skill ON spirit_skills(skill_id)",
    """CREATE VIEW IF NOT EXISTS spirit_evolution_neighbors AS
        SELECT from_name AS spirit_name, 'next' AS direction, to_name AS neighbor_name
        FROM evolution_links
        UNION ALL
        SELECT to_name, 'previous', from_name
        FROM evolution_links""",
)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def spirit_key(row: dict) -> str:
    return _text(row.get("名称"))


def spirit_base_name(name: object) -> str:
    return _text(name).split("（", 1)[0].split("(", 1)[0].strip()


def evolution_key(row: dict) -> str:
    return json.dumps([spirit_base_name(row.get("from_name")), spirit_base_name(row.get("to_name"))], ensure_ascii=False, separators=(",", ":"))


def _base_chain_text(value: object) -> str:
    return " → ".join("|".join(dict.fromkeys(spirit_base_name(name) for name in stage.split("|") if spirit_base_name(name))) for stage in _text(value).split(" → "))


def normalize_record(kind: str, row: dict) -> dict:
    result = dict(row)
    if kind == "spirits":
        result.setdefault("是否首领", "no")
        for field in ("进化链", "上一阶", "下一阶"):
            if field in result:
                result[field] = _base_chain_text(result[field])
    elif kind == "evolutions":
        result["from_name"] = spirit_base_name(result.get("from_name"))
        result["to_name"] = spirit_base_name(result.get("to_name"))
        if "chain_text" in result:
            result["chain_text"] = _base_chain_text(result["chain_text"])
    return result


def _optional_int(value: object) -> int | None:
    try:
        return int(_text(value))
    except ValueError:
        return None


def _optional_float(value: object) -> float | None:
    try:
        return float(_text(value))
    except ValueError:
        return None


def _optional_bool(value: object) -> int | None:
    return {"yes": 1, "no": 0, "1": 1, "0": 0, "true": 1, "false": 0}.get(_text(value).casefold())


def _stage(value: object) -> int | None:
    return {"1": 1, "2": 2, "3": 3, "一阶": 1, "二阶": 2, "三阶": 3}.get(_text(value))


def _parts(value: object) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in _text(value).replace(" / ", "|").split("|") if part.strip()))


def _upsert(connection: sqlite3.Connection, table: str, key: str | tuple[str, ...], values: dict) -> int:
    columns = list(values)
    key_columns = (key,) if isinstance(key, str) else key
    assignments = ", ".join(f"{column}=excluded.{column}" for column in columns if column not in key_columns)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for column in columns)}) "
        f"ON CONFLICT({', '.join(key_columns)}) DO UPDATE SET {assignments}",
        tuple(values.values()),
    )
    conditions = " AND ".join(f"{column}=?" for column in key_columns)
    return connection.execute(f"SELECT id FROM {table} WHERE {conditions}", tuple(values[column] for column in key_columns)).fetchone()[0]


def _retain_keys(connection: sqlite3.Connection, table: str, column: str, keys: list[str | int]) -> None:
    connection.execute("CREATE TEMP TABLE IF NOT EXISTS retained_keys (value TEXT PRIMARY KEY)")
    connection.execute("DELETE FROM retained_keys")
    connection.executemany("INSERT OR IGNORE INTO retained_keys(value) VALUES (?)", ((key,) for key in keys))
    connection.execute(f"DELETE FROM {table} WHERE NOT EXISTS (SELECT 1 FROM retained_keys WHERE value={table}.{column})")


def _element(connection: sqlite3.Connection, name: object) -> int | None:
    value = _text(name).removesuffix("系")
    if not value:
        return None
    connection.execute("INSERT OR IGNORE INTO elements(name) VALUES (?)", (value,))
    return connection.execute("SELECT id FROM elements WHERE name=?", (value,)).fetchone()[0]


def _asset(connection: sqlite3.Connection, path: object, asset_metadata: dict) -> int | None:
    value = _text(path).replace("\\", "/")
    if not value:
        return None
    metadata = asset_metadata.get(value, {})
    connection.execute(
        """INSERT INTO assets(path, source_url, sha256, status) VALUES (?, ?, ?, ?)
           ON CONFLICT(path) DO UPDATE SET
           source_url=CASE WHEN excluded.source_url != '' THEN excluded.source_url ELSE assets.source_url END,
           sha256=CASE WHEN excluded.sha256 != '' THEN excluded.sha256 ELSE assets.sha256 END,
           status=CASE WHEN excluded.status != 'unknown' THEN excluded.status ELSE assets.status END""",
        (value, metadata.get("url", ""), metadata.get("sha256", ""), metadata.get("status", "unknown")),
    )
    return connection.execute("SELECT id FROM assets WHERE path=?", (value,)).fetchone()[0]


def _named_row(connection: sqlite3.Connection, table: str, name: str) -> tuple[int | None, str]:
    row = connection.execute(f"SELECT id FROM {table} WHERE name=?", (name,)).fetchone()
    return (row[0], "resolved") if row else (None, "missing")


def _resolve_relations(connection: sqlite3.Connection) -> None:
    pending = 0
    for row in connection.execute("SELECT id, spirit_name, skill_name FROM spirit_skills").fetchall():
        spirit_id, spirit_status = _named_row(connection, "spirit_forms", row[1])
        skill_id, skill_status = _named_row(connection, "skill_catalog", row[2])
        status = "resolved" if spirit_status == skill_status == "resolved" else f"spirit_{spirit_status};skill_{skill_status}"
        connection.execute("UPDATE spirit_skills SET spirit_id=?, skill_id=? WHERE id=?", (spirit_id, skill_id, row[0]))
        pending += status != "resolved"
    if pending:
        LOGGER.warning("[DB] unresolved skill relations=%d; source names retained, no fuzzy matching", pending)


def _write_skills(connection: sqlite3.Connection, rows: list[dict], metadata: dict) -> None:
    for row in rows:
        name = _text(row.get("名称"))
        if not name:
            raise ValueError("技能记录缺少名称")
        skill_id = _upsert(connection, "skill_catalog", "name", {
            "name": name, "wiki_id": _text(row.get("技能目录ID")),
            "element_id": _element(connection, row.get("属性")), "category": _text(row.get("分类")),
            "energy_cost": _optional_int(row.get("耗能")), "power": _optional_int(row.get("威力")),
            "description": _text(row.get("描述")), "season": _text(row.get("归属赛季")),
            "recent_status": _text(row.get("近期状态")), "learnable_text": _text(row.get("可学习精灵")),
            "icon_asset_id": _asset(connection, row.get("图标路径"), metadata),
            "source_url": _text(row.get("来源URL")),
        })
        connection.execute("DELETE FROM skill_tags WHERE skill_id=?", (skill_id,))
        connection.executemany("INSERT INTO skill_tags(skill_id, tag, position) VALUES (?, ?, ?)", ((skill_id, tag, index) for index, tag in enumerate(_parts(row.get("标签")))))
    _retain_keys(connection, "skill_catalog", "name", [_text(row.get("名称")) for row in rows])


def _write_spirits(connection: sqlite3.Connection, rows: list[dict], metadata: dict) -> None:
    names = [_text(row.get("名称")) for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("精灵完整名称重复；请保留括号后缀来区分独立精灵")
    ability_groups: dict[str, list[dict]] = {}
    for row in rows:
        ability_name = _text(row.get("特性"))
        if ability_name:
            ability_groups.setdefault(ability_name, []).append(row)
    ability_ids: dict[str, int] = {}
    for ability_name, evidence_rows in ability_groups.items():
        descriptions = list(dict.fromkeys(_text(row.get("特性效果")) for row in evidence_rows if _text(row.get("特性效果"))))
        icon_paths = [_text(row.get("特性图标路径")) for row in evidence_rows if _text(row.get("特性图标路径"))]
        source_urls = [_text(row.get("特性来源URL")) for row in evidence_rows if _text(row.get("特性来源URL"))]
        conflict = len(descriptions) > 1
        ability_ids[ability_name] = _upsert(connection, "ability_catalog", "name", {
            "name": ability_name, "description": descriptions[0] if len(descriptions) == 1 else "",
            "description_conflict": int(conflict),
            "icon_asset_id": _asset(connection, icon_paths[0] if icon_paths else None, metadata),
            "source_url": source_urls[0] if source_urls else "",
        })
        if conflict:
            LOGGER.warning("[DB] conflicting ability descriptions name=%s; per-spirit text and raw snapshots retained", ability_name)
    for row in rows:
        name = _text(row.get("名称"))
        if not name:
            raise ValueError("精灵记录缺少名称")
        ability_name = _text(row.get("特性"))
        ability_id = ability_ids.get(ability_name)
        spirit_id = _upsert(connection, "spirit_forms", "name", {
            "name": name, "wiki_id": _text(row.get("精灵ID")),
            "catalog_number": _text(row.get("编号")), "evolution_stage": _stage(row.get("阶段")),
            "stage_label": _text(row.get("阶段")), "is_lord": int(_optional_bool(row.get("是否首领")) == 1),
            "has_shiny": _optional_bool(row.get("是否有异色")),
            "season": _text(row.get("归属赛季")), "ability_id": ability_id,
            "ability_description": _text(row.get("特性效果")),
            "base_hp": _optional_int(row.get("生命")), "base_speed": _optional_int(row.get("速度")),
            "base_attack": _optional_int(row.get("物攻")), "base_magic_attack": _optional_int(row.get("魔攻")),
            "base_defense": _optional_int(row.get("物防")), "base_magic_defense": _optional_int(row.get("魔防")),
            "base_total": _optional_int(row.get("总种族值")), "egg_groups": _text(row.get("蛋组")),
            "height_text": _text(row.get("身高范围")), "height_sort_value": _optional_float(row.get("身高排序值")),
            "weight_text": _text(row.get("体重范围")), "weight_sort_value": _optional_float(row.get("体重排序值")),
            "rideable": _optional_bool(row.get("可骑乘")), "double_rideable": _optional_bool(row.get("可同乘")),
            "description": _text(row.get("精灵介绍")), "avatar_asset_id": _asset(connection, row.get("头像路径"), metadata),
            "evolution_chain_text": _text(row.get("进化链")), "previous_stage_text": _text(row.get("上一阶")),
            "next_stage_text": _text(row.get("下一阶")), "evolution_levels_text": _text(row.get("进化等级")),
            "evolution_condition": _text(row.get("进化条件")), "source_url": _text(row.get("来源URL")),
        })
        connection.execute("DELETE FROM spirit_elements WHERE spirit_id=?", (spirit_id,))
        for index, element in enumerate(_parts(row.get("属性"))):
            connection.execute("INSERT INTO spirit_elements(spirit_id, element_id, position) VALUES (?, ?, ?)", (spirit_id, _element(connection, element), index))
        connection.execute("DELETE FROM spirit_portraits WHERE spirit_id=?", (spirit_id,))
        for index, portrait in enumerate(_parts(row.get("立绘路径"))):
            connection.execute("INSERT INTO spirit_portraits(spirit_id, asset_id, position) VALUES (?, ?, ?)", (spirit_id, _asset(connection, portrait, metadata), index))
    _retain_keys(connection, "spirit_forms", "name", [spirit_key(row) for row in rows])


def _write_rules(connection: sqlite3.Connection, rows: list[dict], metadata: dict) -> None:
    for row in rows:
        name = _text(row.get("名称"))
        if not name:
            raise ValueError("游戏描述记录缺少名称")
        _upsert(connection, "game_rules", "name", {
            "name": name, "category": _text(row.get("类别")), "element_id": _element(connection, row.get("系别")),
            "element_icon_asset_id": _asset(connection, row.get("系别图标路径"), metadata),
            "icon_asset_id": _asset(connection, row.get("规则图标路径"), metadata),
            "description": _text(row.get("描述")), "source_url": _text(row.get("来源URL")),
        })
    _retain_keys(connection, "game_rules", "name", [_text(row.get("名称")) for row in rows])


def _evolution_values(row: dict) -> dict:
    source = spirit_base_name(row.get("from_name"))
    target = spirit_base_name(row.get("to_name"))
    if not source or not target or source == target:
        raise ValueError("进化关系需要两个不同的基本类型名称")
    return {
        "from_name": source, "to_name": target,
        "from_number": _text(row.get("from_number")), "to_number": _text(row.get("to_number")),
        "from_stage": _optional_int(row.get("from_stage")), "to_stage": _optional_int(row.get("to_stage")),
        "required_level": _optional_int(row.get("level")), "condition": _text(row.get("condition")),
        "chain_text": _base_chain_text(row.get("chain_text")), "inference_method": _text(row.get("method")),
    }


def _write_evolutions(connection: sqlite3.Connection, rows: list[dict]) -> None:
    retained_ids = []
    for row in rows:
        retained_ids.append(_upsert(connection, "evolution_links", ("from_name", "to_name"), _evolution_values(row)))
    _retain_keys(connection, "evolution_links", "id", retained_ids)


def _relation_key(row: dict) -> str:
    return json.dumps([_text(row.get("精灵")), _text(row.get("技能")), _text(row.get("技能类别"))], ensure_ascii=False, separators=(",", ":"))


def _write_distributions(connection: sqlite3.Connection, kind: str, rows: list[dict]) -> None:
    for row in rows:
        _upsert(connection, "distribution_records", ("distribution_kind", "spirit_name", "item_name"), {
            "distribution_kind": kind, "spirit_name": _text(row.get("精灵")),
            "item_name": _text(row.get("名称")), "percentage": _text(row.get("百分比")),
            "position": _optional_int(row.get("排序")) or 0,
        })

def _write_spirit_skills(connection: sqlite3.Connection, rows: list[dict]) -> None:
    for row in rows:
        if not _text(row.get("精灵")) or not _text(row.get("技能")):
            raise ValueError("技能关系缺少精灵名或技能名")
        _upsert(connection, "spirit_skills", "record_key", {
            "record_key": _relation_key(row),
            "spirit_name": _text(row.get("精灵")), "skill_name": _text(row.get("技能")),
            "skill_source": _text(row.get("技能类别")), "source_url": _text(row.get("来源URL")),
        })
    _retain_keys(connection, "spirit_skills", "record_key", [_relation_key(row) for row in rows])


def sync_log_directory(database: Path) -> Path:
    return database.parent / f"{database.stem}_sync_logs"


def _write_json_log(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def write_database(database: Path, rows_by_kind: dict[str, list[dict]], manifest: dict | None = None) -> None:
    unknown = set(rows_by_kind) - KINDS
    if unknown:
        raise ValueError(f"未知采集类别：{sorted(unknown)}")
    rows_by_kind = {kind: [normalize_record(kind, row) for row in rows] for kind, rows in rows_by_kind.items()}
    asset_metadata = {asset["path"]: asset for asset in (manifest or {}).get("assets", {}).values() if asset.get("path")}
    now = datetime.now(timezone.utc)
    updated_at = now.isoformat()
    log_path = sync_log_directory(database) / f"{now.strftime('%Y%m%dT%H%M%S%fZ')}_{uuid4().hex}.json"
    payload = {"schema_version": SCHEMA_VERSION, "committed_at": updated_at, "counts": {kind: len(rows) for kind, rows in rows_by_kind.items()}, "records": rows_by_kind}
    json.dumps(payload, ensure_ascii=False)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if {"skill", "pokemon", "pokemon_skill"} & existing:
            raise ValueError("拒绝向旧战斗数据库写入新结构；请选择新的数据库文件，例如 data/nrc_wiki.db")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 2, SCHEMA_VERSION):
            raise ValueError(f"不支持的 wiki 数据库版本：{version}")
        if version == 0 and existing:
            raise ValueError("目标数据库已有无版本表结构；请使用当前 v2 数据库或新的空文件")
        with connection:
            connection.execute("BEGIN")
            for statement in SCHEMA:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            if "skills" in rows_by_kind:
                _write_skills(connection, rows_by_kind["skills"], asset_metadata)
            if "spirits" in rows_by_kind:
                _write_spirits(connection, rows_by_kind["spirits"], asset_metadata)
            if "game_descriptions" in rows_by_kind:
                _write_rules(connection, rows_by_kind["game_descriptions"], asset_metadata)
            if "evolutions" in rows_by_kind:
                _write_evolutions(connection, rows_by_kind["evolutions"])
            if "spirit_skills" in rows_by_kind:
                _write_spirit_skills(connection, rows_by_kind["spirit_skills"])
            for distribution_kind in ("skill", "nature", "blood", "talent"):
                if distribution_kind in rows_by_kind:
                    _write_distributions(connection, distribution_kind, rows_by_kind[distribution_kind])
            _resolve_relations(connection)
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise ValueError(f"外键检查失败：{violations}")
    LOGGER.info("[DB] COMMIT path=%s kinds=%s", database, sorted(rows_by_kind))
    try:
        _write_json_log(log_path, payload)
    except OSError as error:
        raise RuntimeError(f"数据库已提交，但 JSON 同步日志保存失败：{log_path}") from error
    LOGGER.info("[JSON] committed sync log path=%s", log_path)


def read_committed_rows(database: Path, kind: str) -> list[dict]:
    directory = sync_log_directory(database)
    if not database.exists() or not directory.exists():
        return []
    logs = []
    for path in directory.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if kind in payload.get("counts", {}):
                logs.append((payload["committed_at"], path.name, payload))
        except (OSError, ValueError, KeyError, TypeError) as error:
            LOGGER.warning("[JSON] skipping unreadable sync log path=%s error=%s", path, error)
    if not logs:
        return []
    latest = max(logs, key=lambda item: (item[0], item[1]))[2]
    return [normalize_record(kind, row) for row in latest["records"].get(kind, [])]


def read_evolution_neighbors(database: Path, name: str) -> dict[str, list[str]]:
    result = {"previous": [], "next": []}
    if not database.exists():
        return result
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        for direction, neighbor_name in connection.execute("SELECT direction, neighbor_name FROM spirit_evolution_neighbors WHERE spirit_name=? ORDER BY direction, neighbor_name", (spirit_base_name(name),)):
            result[direction].append(neighbor_name)
    return result
