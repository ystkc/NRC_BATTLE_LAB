"""管理精灵培养统计的 SQLite 和内存缓存，按单个精灵回填。"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Lock

from .database import DISTRIBUTION_RECORDS_TABLE
from .usage import CATEGORIES, read_usage


DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "data" / "nrc_wiki.db"
KINDS = frozenset(CATEGORIES.values())
COMPLETED_TABLE = """CREATE TABLE IF NOT EXISTS distribution_cache_completed (
    spirit_name TEXT PRIMARY KEY
)"""


class DistributionCache:
    """初始化时加载 SQLite 中的分布，并在单次查询缺失时回填该精灵。"""

    def __init__(self, database: Path):
        """加载已有记录和已验证为空的类别。"""
        self.database = Path(database).resolve()
        self._rows: dict[tuple[str, str], tuple[dict, ...]] = {}
        self._lock = Lock()
        if self.database.exists():
            with closing(sqlite3.connect(f"{self.database.as_uri()}?mode=ro", uri=True)) as connection:
                self._rows = self._load(connection)

    @staticmethod
    def _load(connection: sqlite3.Connection, spirit_name: str | None = None) -> dict[tuple[str, str], tuple[dict, ...]]:
        """读取全库或一只精灵的缓存，兼容没有完成标记的旧数据库。"""
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        where, args = (" WHERE spirit_name = ?", (spirit_name,)) if spirit_name is not None else ("", ())
        grouped: dict[tuple[str, str], list[dict]] = {}
        if "distribution_records" in tables:
            for name, kind, item, percentage, position in connection.execute(
                "SELECT spirit_name, distribution_kind, item_name, percentage, position FROM distribution_records" + where, args,
            ):
                grouped.setdefault((name, kind), []).append({
                    "item": item, "percentage": float((percentage or "0").rstrip("%")), "position": position,
                })
        if "distribution_cache_completed" in tables:
            for (name,) in connection.execute("SELECT spirit_name FROM distribution_cache_completed" + where, args):
                for kind in KINDS:
                    grouped.setdefault((name, kind), [])
        return {key: tuple(sorted(rows, key=lambda row: (-row["percentage"], row["position"]))) for key, rows in grouped.items()}

    def has_distributions(self, spirit_name: str, kinds: tuple[str, ...]) -> bool:
        """检查请求的类别是否均已缓存。"""
        return all((spirit_name, kind) in self._rows for kind in kinds)

    def get_distributions(self, spirit_name: str, kinds: tuple[str, ...], *, source_url: str = "", allow_fetch: bool = True) -> dict[str, tuple[dict, ...]]:
        """查询一个精灵的指定类别，缺失时至多发起一次统计查询。"""
        wanted = tuple(kind for kind in kinds if kind in KINDS)
        if spirit_name and allow_fetch and not self.has_distributions(spirit_name, wanted):
            # 进程内合并同一只精灵的并发缺失请求，命中读取不占用锁。
            with self._lock:
                if not self.has_distributions(spirit_name, wanted):
                    self._fill(spirit_name, wanted, source_url)
        return {kind: tuple(row.copy() for row in self._rows.get((spirit_name, kind), ())) for kind in kinds}

    def bloodline_names(self) -> list[str]:
        """返回已缓存的血脉名称，用于没有分布时的编辑器选项。"""
        return sorted({row["item"] for (_, kind), rows in self._rows.copy().items() if kind == "blood" for row in rows})

    def _fill(self, spirit_name: str, wanted: tuple[str, ...], source_url: str) -> None:
        """只补齐缺失类别，提交成功后更新内存。"""
        if self.database.exists():
            with closing(sqlite3.connect(f"{self.database.as_uri()}?mode=ro", uri=True)) as connection:
                self._rows.update(self._load(connection, spirit_name))
            if self.has_distributions(spirit_name, wanted):
                return
        incoming = read_usage(spirit_name, source_url)
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(DISTRIBUTION_RECORDS_TABLE)
            connection.execute(COMPLETED_TABLE)
            existing = self._load(connection, spirit_name)
            for kind, rows in incoming.items():
                if (spirit_name, kind) in existing:
                    continue
                connection.executemany(
                    """INSERT INTO distribution_records
                    (distribution_kind, spirit_name, item_name, percentage, position) VALUES (?, ?, ?, ?, ?)""",
                    [(kind, spirit_name, row["item"], f'{row["percentage"]}%', row["position"]) for row in rows],
                )
            connection.execute("INSERT OR IGNORE INTO distribution_cache_completed VALUES (?)", (spirit_name,))
            saved = self._load(connection, spirit_name)
        self._rows.update(saved)


DEFAULT_CACHE = DistributionCache(DEFAULT_DATABASE)
