"""Incrementally synchronize NRC wiki data without mutating the live database.

The crawler deliberately has two phases:

1. Fetch HTML, download assets, and write a reviewable snapshot under
   ``data/wiki_staging``.
2. After the user confirms the diff, merge the snapshot into canonical CSV
   files and a separate wiki catalog SQLite database.

The wiki pages contain their records in server-rendered HTML, so no browser or
JavaScript runtime is required.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.wiki_crawler.database import evolution_key, normalize_record, read_committed_rows, spirit_base_name, spirit_key, write_database

try:
    from bs4 import BeautifulSoup, Tag
except ImportError as error:  # pragma: no cover - depends on environment
    raise SystemExit("wiki_crawler requires beautifulsoup4; install with: pip install -e '.[collector]'") from error


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DB_PATH = DATA / "nrc_wiki.db"
STAGING_DIR = DATA / "wiki_staging"
CANONICAL_DIR = DATA / "wiki"
MANIFEST_PATH = DATA / "wiki_assets_manifest.json"

BASE_URL = "https://wiki.biligame.com"
NAMESPACE = "/nrc/"
SKILL_LIST_URL = BASE_URL + "/nrc/%E6%8A%80%E8%83%BD%E5%88%97%E8%A1%A8"
SPIRIT_LIST_URL = BASE_URL + "/nrc/%E7%B2%BE%E7%81%B5%E5%88%97%E8%A1%A8"
SPIRIT_ATLAS_URL = BASE_URL + "/nrc/%E7%B2%BE%E7%81%B5%E5%9B%BE%E9%89%B4"
GAME_DESCRIPTION_ATLAS_URL = BASE_URL + "/nrc/%E6%B8%B8%E6%88%8F%E6%8F%8F%E8%BF%B0%E5%9B%BE%E9%89%B4"

HEADERS = {
    "User-Agent": "Mozilla/5.0 NRC-Battle-Lab/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
}

CSV_FIELDS = {
    "skills": [
        "名称", "属性", "分类", "耗能", "威力", "描述", "可学习精灵",
        "技能目录ID", "归属赛季", "标签", "近期状态",
        "图标路径", "来源URL",
    ],
    "spirits": [
        "编号", "精灵ID", "名称", "阶段", "属性", "是否首领", "是否有异色",
        "特性", "特性效果", "特性图标路径", "头像路径", "立绘路径", "身高范围", "体重范围", "进化链", "上一阶", "下一阶",
        "进化等级", "进化条件", "生命", "速度", "物攻", "魔攻", "物防", "魔防", "总种族值",
        "归属赛季", "蛋组", "身高排序值", "体重排序值", "可骑乘", "可同乘", "精灵介绍", "特性来源URL", "来源URL",
    ],
    "game_descriptions": ["名称", "类别", "系别", "系别图标路径", "规则图标路径", "描述", "来源URL"],
    "evolutions": ["from_name", "to_name", "from_number", "to_number", "from_stage", "to_stage", "method", "level", "condition", "chain_text"],
    "spirit_skills": ["精灵", "技能", "技能类别", "来源URL"],
}

CSV_KEYS = {
    "skills": "名称",
    "spirits": "名称",
    "game_descriptions": "名称",
    "evolutions": "_evolution_key",
    "spirit_skills": "_spirit_skill_key",
}

LOGGER = logging.getLogger("nrc.wiki")


@dataclass
class FetchError:
    url: str
    error: str


class WikiFetcher:
    def __init__(self, delay: float = 0.0, retries: int = 3):
        self.delay = max(0.0, delay)
        self.retries = max(1, retries)
        self.errors: list[FetchError] = []

    def get_bytes(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            started = time.perf_counter()
            LOGGER.debug("[HTTP] GET %s attempt=%d/%d", url, attempt + 1, self.retries)
            try:
                request = Request(url, headers=HEADERS)
                with urlopen(request, timeout=30) as response:
                    content = response.read()
                    status = getattr(response, "status", "?")
                    content_type = response.headers.get("Content-Type", "")
                elapsed = time.perf_counter() - started
                LOGGER.debug(
                    "[HTTP] OK status=%s bytes=%d content_type=%s elapsed=%.3fs url=%s",
                    status,
                    len(content),
                    content_type or "-",
                    elapsed,
                    url,
                )
                if self.delay:
                    LOGGER.debug("[HTTP] sleep delay=%.3fs after %s", self.delay, url)
                    time.sleep(self.delay)
                return content
            except Exception as error:  # pragma: no cover - network-specific
                last_error = error
                elapsed = time.perf_counter() - started
                LOGGER.warning(
                    "[HTTP] ERROR attempt=%d/%d elapsed=%.3fs url=%s error=%r",
                    attempt + 1,
                    self.retries,
                    elapsed,
                    url,
                    error,
                )
                if attempt + 1 < self.retries:
                    LOGGER.info("[HTTP] retry sleep=%.3fs url=%s", 1 + attempt, url)
                    time.sleep(1 + attempt)
        message = str(last_error or "unknown fetch error")
        self.errors.append(FetchError(url, message))
        LOGGER.error("[HTTP] FAILED retries_exhausted=%d url=%s error=%s", self.retries, url, message)
        return b""

    def get_text(self, url: str) -> str:
        return self.get_bytes(url).decode("utf-8", errors="replace")






# The list pages are tables, so every parser below operates on
# BeautifulSoup nodes.
def safe_name(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]", "_", value).strip("._") or "asset"


def full_image_url(image_url: str) -> str:
    if "/thumb/" in image_url:
        prefix, suffix = image_url.split("/thumb/", 1)
        parts = suffix.rsplit("/", 1)
        if len(parts) == 2:
            return prefix + "/" + parts[0]
    return image_url


def extension(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"} else ".png"


def _unique_records(records: Iterable[dict], key: str) -> list[dict]:
    result: list[dict] = []
    positions: dict[str, int] = {}
    for record in records:
        value = str(record.get(key, "")).strip()
        if not value:
            continue
        if value in positions:
            index = positions[value]
            result[index] = {**result[index], **{k: v for k, v in record.items() if v not in ("", [], None)}}
        else:
            positions[value] = len(result)
            result.append(record)
    return result


def normalize_url(url: str, base_url: str = BASE_URL) -> str:
    joined = urljoin(base_url, url)
    parsed = urlparse(joined)
    path = quote(unquote(parsed.path), safe="/%:@-._~!$&'()*+,;=")
    query = quote(unquote(parsed.query), safe="=&/%:@-._~!$'()*+,;?")
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, query, parsed.fragment))


def clean_text(fragment: str | Tag) -> str:
    soup = fragment if isinstance(fragment, Tag) else BeautifulSoup(fragment or "", "html.parser")
    return " ".join(html_lib.unescape(soup.get_text(" ", strip=True)).split())


def _soup(fragment: str | Tag) -> BeautifulSoup | Tag:
    return fragment if isinstance(fragment, Tag) else BeautifulSoup(fragment or "", "html.parser")


def _strict_img_urls(fragment: str | Tag, base_url: str) -> list[str]:
    soup = _soup(fragment)
    result: list[str] = []
    for image in soup.select("img[src], img[data-src], img[data-original]"):
        source = image.get("data-src") or image.get("src") or image.get("data-original")
        if not source or str(source).startswith("data:"):
            continue
        absolute = normalize_url(full_image_url(urljoin(base_url, str(source))), base_url)
        if absolute not in result:
            result.append(absolute)
    return result


def _strict_link(cell: Tag | None, source_url: str) -> tuple[str, str]:
    if not cell:
        return "", ""
    link = cell.select_one("a[href]")
    if not link:
        return clean_text(cell), ""
    return str(link.get("title") or clean_text(link)).strip(), normalize_url(str(link.get("href")), source_url)


def _strict_columns(table: Tag) -> list[str]:
    header = table.select_one("thead tr")
    if not header:
        header = table.select_one("tr") # 部分页面直接把第一行作为header，解析前没有thead标签
    return [str(cell.get("data-column", "")).strip() for cell in header.select(":scope > th[data-column]")] if header else []


def _strict_cell(row: Tag, columns: list[str], column: str) -> Tag | None:
    if column not in columns:
        return None
    cells = row.select(":scope > td")
    index = columns.index(column)
    return cells[index] if index < len(cells) else None


def _strict_text(row: Tag, columns: list[str], column: str) -> str:
    cell = _strict_cell(row, columns, column)
    return clean_text(cell) if cell else ""


def _strict_attr(row: Tag, columns: list[str], column: str, attribute: str) -> str:
    cell = _strict_cell(row, columns, column)
    return str(cell.get(attribute, "")).strip() if cell else ""


def parse_skill_list(html: str, source_url: str = SKILL_LIST_URL) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    records: list[dict] = []
    for row in soup.select("tr.nrc-skill-table-row"):
        name, source = _strict_link(row.select_one("td.nrc-skill-table-name"), source_url)
        if not name:
            LOGGER.warning("[PARSE] skill row has no .nrc-skill-table-name url=%s", source_url)
            continue
        number_cells = row.select("td.nrc-skill-table-number")
        energy = number_cells[0] if len(number_cells) > 0 else None
        power = number_cells[1] if len(number_cells) > 1 else None
        records.append({
            "名称": name,
            "属性": str(row.get("data-skill-catalog-type", "")).strip() or clean_text(row.select_one("td.nrc-skill-table-type") or ""),
            "分类": str(row.get("data-skill-catalog-category", "")).strip() or clean_text(row.select_one("td.nrc-skill-table-category") or ""),
            "耗能": str(energy.get("data-sort-value", "")).strip() if energy else "",
            "威力": str(power.get("data-sort-value", "")).strip() if power else "",
            "描述": clean_text(row.select_one("td.nrc-skill-table-description") or ""),
            "可学习精灵": "",
            "技能目录ID": str(row.get("data-skill-catalog-id", "")).strip(),
            "归属赛季": str(row.get("data-skill-catalog-season", "")).strip(),
            "标签": str(row.get("data-skill-catalog-tags", "")).strip(),
            "近期状态": str(row.get("data-skill-catalog-recent", "")).strip(),
            "来源URL": source or normalize_url(f"{NAMESPACE}{quote(name, safe='')}", source_url),
            "_icon_urls": _strict_img_urls(row.select_one("td.nrc-skill-table-icon") or row, source_url),
        })
    if not records:
        LOGGER.warning("[PARSE] no .nrc-skill-table-row found url=%s", source_url)
    return _unique_records(records, "名称")


def _strict_spirit_tables(html: str, source_url: str, image_role: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    records: list[dict] = []
    for table in soup.select("table"):
        columns = _strict_columns(table)
        if not columns:
            continue
        for row in table.select("tr.npc-table-row"):
            name, source = _strict_link(_strict_cell(row, columns, "name"), source_url)
            if not name:
                continue
            feature_cell = _strict_cell(row, columns, "feature")
            feature, feature_source = _strict_link(feature_cell, source_url)
            records.append({
                "编号": str(row.get("data-number", "")).strip() or _strict_text(row, columns, "number"),
                "精灵ID": str(row.get("data-id", "")).strip(),
                "名称": name,
                "阶段": str(row.get("data-stage", "")).strip(),
                "属性": str(row.get("data-type", "")).strip() or _strict_attr(row, columns, "types", "data-sort-value"),
                "是否首领": "yes" if "lord" in str(row.get("data-form", "")).casefold().split("|") else "no",
                "是否有异色": str(row.get("data-shiny", "")).strip(),
                "特性": feature,
                "特性来源URL": feature_source,
                "特性效果": _strict_text(row, columns, "featureDesc"),
                "生命": _strict_text(row, columns, "hp"),
                "速度": _strict_text(row, columns, "spe"),
                "物攻": _strict_text(row, columns, "atk"),
                "魔攻": _strict_text(row, columns, "spa"),
                "物防": _strict_text(row, columns, "def"),
                "魔防": _strict_text(row, columns, "spd"),
                "总种族值": _strict_text(row, columns, "total"),
                "归属赛季": str(row.get("data-season", "")).strip() or _strict_text(row, columns, "season"),
                "蛋组": _strict_text(row, columns, "eggs"),
                "身高范围": _strict_text(row, columns, "height"),
                "体重范围": _strict_text(row, columns, "weight"),
                "身高排序值": _strict_attr(row, columns, "height", "data-sort-value"),
                "体重排序值": _strict_attr(row, columns, "weight", "data-sort-value"),
                "精灵介绍": _strict_text(row, columns, "description"),
                "可骑乘": _strict_attr(row, columns, "ride", "data-sort-value") or _strict_text(row, columns, "ride"),
                "可同乘": _strict_attr(row, columns, "doubleRide", "data-sort-value") or _strict_text(row, columns, "doubleRide"),
                "来源URL": source or source_url,
                "_avatar_urls": _strict_img_urls(_strict_cell(row, columns, "avatar") or row, source_url)[:1],
                "_portrait_urls": _strict_img_urls(row, source_url) if image_role == "portrait" else [],
                "_ability_icon_urls": _strict_img_urls(feature_cell or "", source_url)[:1],
            })
    return records


def _strict_spirit_cards(html: str, source_url: str, image_role: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    records: list[dict] = []
    for card in soup.select("div.npc-card"):
        link = card.select_one(".npc-card-target a[href]") or card.select_one("a[href]")
        name = str(link.get("title") or clean_text(card.select_one(".npc-name") or link or "")).strip()
        number = str(card.get("data-number", "")).strip() or clean_text(card.select_one(".npc-number") or "")
        if not name or not number:
            continue
        type_names = [str(item.get("title", "")).removesuffix("系") for item in card.select(".npc-card-types .npc-type[title]")]
        portrait_urls = _strict_img_urls(card.select_one(".npc-art-normal") or "", source_url)
        avatar_urls = _strict_img_urls(card.select_one(".npc-art-head") or "", source_url)
        records.append({
            "编号": number.upper(), "名称": name, "精灵ID": str(card.get("data-id", "")).strip(),
            "阶段": str(card.get("data-stage", "")).strip() or clean_text(card.select_one(".npc-stage") or ""),
            "属性": str(card.get("data-type", "")).strip() or "|".join(type_names),
            "是否首领": "yes" if "lord" in str(card.get("data-form", "")).casefold().split("|") else "no",
            "是否有异色": str(card.get("data-shiny", "")).strip(),
            "归属赛季": str(card.get("data-season", "")).strip(),
            "特性": "", "特性效果": "",
            "来源URL": normalize_url(str(link.get("href")), source_url) if link else source_url,
            "_avatar_urls": avatar_urls,
            "_portrait_urls": portrait_urls if image_role == "portrait" else [],
            "_ability_icon_urls": [],
        })
    return records


def parse_spirit_list(html: str, source_url: str = SPIRIT_LIST_URL, image_role: str = "avatar") -> list[dict]:
    records = _strict_spirit_tables(html, source_url, image_role)
    if not records:
        records = _strict_spirit_cards(html, source_url, image_role)
    if not records:
        LOGGER.warning("[PARSE] no .npc-table-row or .npc-card found url=%s", source_url)
    records = [normalize_record("spirits", record) for record in records]
    for record in records:
        record["_identity"] = spirit_key(record)
    return _unique_records(records, "_identity")


def parse_game_description_list(html: str, source_url: str = GAME_DESCRIPTION_ATLAS_URL) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    records: list[dict] = []
    for card in soup.select("div.nrc-game-description-card[data-nrc-tag='article']"):
        title_link = card.select_one("div[data-nrc-tag='h2'] a[href]")
        name = str(title_link.get("title") or clean_text(title_link or "")).strip()
        if not name:
            continue
        type_chip = card.select_one(".nrc-game-description-type-chip")
        records.append({
            "名称": name,
            "类别": str(card.get("data-game-description-category", "")).strip() or clean_text(card.select_one(".nrc-game-description-category-chip") or ""),
            "系别": str(card.get("data-description-element", "")).strip() or clean_text(type_chip.select_one(".nrc-game-description-type-icon") if type_chip else ""),
            "描述": clean_text(card.select_one(".nrc-game-description-card-desc") or ""),
            "来源URL": normalize_url(str(title_link.get("href")), source_url) if title_link else source_url,
            "_type_icon_urls": _strict_img_urls(card.select_one(".nrc-game-description-type-icon") or "", source_url),
            "_rule_icon_urls": _strict_img_urls(card.select_one(".nrc-game-description-mechanic-icon") or "", source_url),
        })
    if not records:
        LOGGER.warning("[PARSE] no .nrc-game-description-card found url=%s", source_url)
    return _unique_records(records, "名称")


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"version": 2, "assets": {}}
    try:
        value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        value.setdefault("version", 2)
        value.setdefault("assets", {})
        return value
    except (OSError, json.JSONDecodeError):
        return {"version": 2, "assets": {}}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def store_asset(manifest: dict, fetcher: WikiFetcher, kind: str, key: str, url: str, directory: Path, filename: str | None = None, note: str | None = None) -> str:
    if not url:
        return ""
    record_key = f"{kind}:{key}:{filename}"
    old = manifest["assets"].get(record_key, {})
    destination = directory / (filename or f"{safe_name(key)}{extension(url)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    relative = str(destination.relative_to(DATA)).replace("\\", "/")
    if destination.exists() and old.get("url") == url:
        old.update({"path": relative, "url": url, "status": "cached"})
        manifest["assets"][record_key] = old
        LOGGER.debug("[ASSET] CACHE-HIT %s key=%s path=%s url=%s", kind, key, relative, url)
        return relative
    LOGGER.debug("[ASSET] DOWNLOAD (%s) %s key=%s destination=%s url=%s", note, kind, key, relative, url)
    content = fetcher.get_bytes(url)
    if not content:
        manifest["assets"][record_key] = {"url": url, "path": relative, "status": "error"}
        LOGGER.error("[ASSET] FAILED %s key=%s url=%s", kind, key, url)
        return ""
    destination.write_bytes(content)
    manifest["assets"][record_key] = {
        "path": relative,
        "url": url,
        "sha256": hashlib.sha256(content).hexdigest(),
        "status": "downloaded",
    }
    LOGGER.info("[ASSET] SAVED %s (%s) %s", kind, note, relative)
    return relative


def _public_record(record: dict) -> dict:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def _log_first_record(kind: str, rows: list[dict]) -> None:
    if not rows:
        LOGGER.info("[SAMPLE] %s no records", kind)
        return
    LOGGER.info(
        "[SAMPLE] %s first_record=%s",
        kind,
        json.dumps(rows[0], ensure_ascii=False, sort_keys=True, default=str),
    )


def _row_key(kind: str, row: dict) -> str:
    if kind == "evolutions":
        return evolution_key(row)
    if kind == "spirit_skills":
        return "\x00".join((str(row.get("精灵", "")).strip(), str(row.get("技能", "")).strip(), str(row.get("技能类别", "")).strip()))
    if kind == "spirits":
        return spirit_key(row)
    return str(row.get(CSV_KEYS[kind], "")).strip()


def _stage_number(value: str) -> int | None:
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    return {"一阶": 1, "二阶": 2, "三阶": 3}.get(text)


def _rebuild_spirit_evolution(records: list[dict]) -> list[dict]:
    numbered_stages: dict[tuple[int, int], dict[str, list[dict]]] = {}
    for record in records:
        cleaned = normalize_record("spirits", record)
        record.clear()
        record.update(cleaned)
        record["进化链"] = ""
        record["上一阶"] = ""
        record["下一阶"] = ""
        number_text = str(record.get("编号", "")).strip()
        stage = _stage_number(record.get("阶段", ""))
        is_lord = str(record.get("是否首领", "")).casefold() in {"yes", "1", "true"}
        name = spirit_base_name(record.get("名称"))
        if is_lord or not number_text.isdigit() or stage not in {1, 2, 3} or not name:
            continue
        numbered_stages.setdefault((int(number_text), stage), {}).setdefault(name, []).append(record)

    evolutions: dict[str, dict] = {}
    chain_count = 0
    for (number, stage), initial_group in sorted(numbered_stages.items()):
        if stage != 1:
            continue
        stage_groups = {1: initial_group}
        for next_stage in (2, 3):
            next_group = numbered_stages.get((number + next_stage - 1, next_stage))
            if not next_group:
                break
            stage_groups[next_stage] = next_group
        if len(stage_groups) < 2:
            continue
        if any(len(group) != 1 for group in stage_groups.values()):
            LOGGER.warning("[EVOLUTION] ambiguous basic types start_number=%03d; chain skipped names=%s", number, [list(group) for group in stage_groups.values()])
            continue
        names = {chain_stage: next(iter(group)) for chain_stage, group in stage_groups.items()}
        chain = " → ".join(names.values())
        for chain_stage, group in stage_groups.items():
            for record in group[names[chain_stage]]:
                record["进化链"] = chain
                record["上一阶"] = names.get(chain_stage - 1, "")
                record["下一阶"] = names.get(chain_stage + 1, "")
        LOGGER.debug("[EVOLUTION] start_number=%03d chain=%s", number, chain)
        chain_count += 1
        for left_stage in range(1, len(stage_groups)):
            source = stage_groups[left_stage][names[left_stage]][0]
            target = stage_groups[left_stage + 1][names[left_stage + 1]][0]
            edge = {
                "from_name": names[left_stage], "to_name": names[left_stage + 1],
                "from_number": source.get("编号", ""), "to_number": target.get("编号", ""),
                "from_stage": left_stage, "to_stage": left_stage + 1,
                "method": "adjacent_number_stage", "level": "", "condition": "", "chain_text": chain,
            }
            evolutions[evolution_key(edge)] = edge
    result = list(evolutions.values())
    LOGGER.info("[EVOLUTION] chains=%d edges=%d; basic types only, regional suffixes stripped, lord excluded", chain_count, len(result))
    return result


def _skill_snapshot(fetcher: WikiFetcher, limit: int) -> list[dict]:
    LOGGER.info("[PAGE] FETCH skills list url=%s", SKILL_LIST_URL)
    list_html = fetcher.get_text(SKILL_LIST_URL)
    if not list_html:
        _log_first_record("skills", [])
        return []
    records = parse_skill_list(list_html)
    LOGGER.debug("[PARSE] skills rows=%d url=%s", len(records), SKILL_LIST_URL)
    if limit:
        records = records[:limit]
    manifest = load_manifest()
    result = []
    for index, record in enumerate(records, 1):
        name = record["名称"]
        icon_urls = record.get("_icon_urls", [])
        record["图标路径"] = store_asset(
            manifest, fetcher, "skill", name, icon_urls[0] if icon_urls else "",
            DATA / "skill_icons", f"{safe_name(name)}{extension(icon_urls[0])}" if icon_urls else None,
            f"{index}/{len(records)}"
        )
        result.append(_public_record(record))
        if index % 100 == 0:
            LOGGER.info("[PARSE] skills progress=%d/%d", index, len(records))
    save_manifest(manifest)
    _log_first_record("skills", result)
    return result


SKILL_RELATION_SOURCES = {
    "default": "default-skill",
    "blood": "blood-skill",
    "stone": "stone-skill",
}


def parse_skill_pet_cards(html: str, skill_name: str, source_url: str) -> list[dict]:
    """Read skill-to-spirit cards from one skill detail page."""
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict] = []
    for card in soup.select(".nrc-skill-pet-card"):
        raw_source = str(card.get("data-skill-source", "")).strip().casefold()
        if raw_source.endswith("-skill"):
            raw_source = raw_source[:-6]
        skill_source = SKILL_RELATION_SOURCES.get(raw_source)
        if not skill_source:
            LOGGER.warning("[RELATION] unknown data-skill-source=%r skill=%s url=%s", raw_source, skill_name, source_url)
            continue
        name_element = card.select_one(".nrc-skill-pet-name")
        spirit_name = clean_text(name_element or "")
        if not spirit_name:
            LOGGER.warning("[RELATION] card has no spirit name skill=%s source=%s url=%s", skill_name, raw_source, source_url)
            continue
        rows.append({
            "精灵": spirit_name,
            "技能": skill_name,
            "技能类别": skill_source,
            "来源URL": source_url,
        })
    return list({
        (row["精灵"], row["技能"], row["技能类别"]): row for row in rows
    }.values())


def _skill_relation_snapshot(fetcher: WikiFetcher, skills: list[dict]) -> list[dict]:
    result: list[dict] = []
    total = len(skills)
    for index, skill in enumerate(skills, 1):
        name = str(skill.get("名称", "")).strip()
        if not name:
            continue
        url = normalize_url(f"{BASE_URL}{NAMESPACE}{quote(name, safe='')}")
        LOGGER.info("[RELATION] FETCH skill=%d/%d name=%s url=%s", index, total, name, url)
        html = fetcher.get_text(url)
        rows = parse_skill_pet_cards(html, name, url)
        result.extend(rows)
        LOGGER.info("[RELATION] PARSE skill=%d/%d name=%s cards=%d", index, total, name, len(rows))
    unique = {(row["精灵"], row["技能"], row["技能类别"]): row for row in result}
    LOGGER.info("[RELATION] COMPLETE skills=%d relations=%d", total, len(unique))
    rows = list(unique.values())
    _log_first_record("spirit_skills", rows)
    return rows


def _spirit_snapshot(fetcher: WikiFetcher, limit: int) -> tuple[list[dict], list[dict]]:
    LOGGER.info("[PAGE] FETCH spirits list url=%s", SPIRIT_LIST_URL)
    list_html = fetcher.get_text(SPIRIT_LIST_URL)
    LOGGER.info("[PAGE] FETCH spirits atlas url=%s", SPIRIT_ATLAS_URL)
    atlas_html = fetcher.get_text(SPIRIT_ATLAS_URL)
    if not list_html and not atlas_html:
        _log_first_record("spirits", [])
        _log_first_record("evolutions", [])
        return [], []
    records = parse_spirit_list(list_html) if list_html else []
    atlas_records = parse_spirit_list(atlas_html, SPIRIT_ATLAS_URL, image_role="portrait") if atlas_html else []
    by_key = {
        (record.get("名称", ""), record.get("形态", "")): record
        for record in records
    }
    for atlas_record in atlas_records:
        key = (atlas_record.get("名称", ""), atlas_record.get("形态", ""))
        if key in by_key:
            by_key[key]["_portrait_urls"] = list(dict.fromkeys(by_key[key].get("_portrait_urls", []) + atlas_record.get("_portrait_urls", [])))
            for field, value in atlas_record.items():
                if field.startswith("_") or value in ("", [], None):
                    continue
                if by_key[key].get(field) in ("", [], None):
                    by_key[key][field] = value
        else:
            by_key[key] = atlas_record
    records = list(by_key.values())
    evolutions = _rebuild_spirit_evolution(records)
    if limit:
        records = records[:limit]
    manifest = load_manifest()
    result: list[dict] = []
    for index, record in enumerate(records, 1):
        identity_parts = (
            str(record.get("精灵ID", "")).strip(),
            str(record.get("名称", "")).strip(),
            str(record.get("形态", "")).strip(),
            str(record.get("是否有异色", "")).strip(),
        )
        key = "_".join(safe_name(part) for part in identity_parts if part) or record["编号"] or record["名称"]
        merged = dict(record)
        avatar_urls = record.get("_avatar_urls", [])
        portrait_urls = list(dict.fromkeys(record.get("_portrait_urls", [])))
        avatar_path = store_asset(
            manifest, fetcher, "spirit_avatar", key, avatar_urls[0] if avatar_urls else "",
            DATA / "spirit_icons", f"{safe_name(key)}_{safe_name(record['名称'])}{extension(avatar_urls[0])}" if avatar_urls else None,
            f"{index}/{len(records)}",
        )
        portrait_paths = []
        for portrait_index, url in enumerate(portrait_urls, 1):
            path = store_asset(
                manifest, fetcher, "spirit_portrait", f"{key}:{portrait_index}", url,
                DATA / "spirit_icons", f"{safe_name(key)}_{safe_name(record['名称'])}_portrait_{portrait_index}{extension(url)}",
                f"{index}/{len(records)}",
            )
            if path:
                portrait_paths.append(path)
        ability_urls = record.get("_ability_icon_urls", [])
        ability_path = store_asset(
            manifest, fetcher, "ability", record.get("特性", "") or key, ability_urls[0] if ability_urls else "",
            DATA / "ability_icons", f"{safe_name(record.get('特性', '') or key)}{extension(ability_urls[0])}" if ability_urls else None,
            f"{index}/{len(records)}",
        )
        if ability_path and not merged.get("特性"):
            merged["特性"] = record.get("特性", "")
        merged["头像路径"] = avatar_path
        merged["立绘路径"] = "|".join(portrait_paths)
        merged["特性图标路径"] = ability_path
        public = _public_record(merged)
        result.append(public)
        if index % 100 == 0:
            LOGGER.info("[PARSE] spirits progress=%d/%d", index, len(records))
    save_manifest(manifest)
    evolution_map = {}
    for evolution in evolutions:
        evolution_map[evolution_key(evolution)] = evolution
    unique_evolutions = list(evolution_map.values())
    _log_first_record("spirits", result)
    _log_first_record("evolutions", unique_evolutions)
    return result, unique_evolutions


def _game_description_snapshot(fetcher: WikiFetcher, limit: int) -> list[dict]:
    LOGGER.info("[PAGE] FETCH game descriptions url=%s", GAME_DESCRIPTION_ATLAS_URL)
    list_html = fetcher.get_text(GAME_DESCRIPTION_ATLAS_URL)
    if not list_html:
        _log_first_record("game_descriptions", [])
        return []
    records = parse_game_description_list(list_html)
    LOGGER.info("[PARSE] game descriptions rows=%d url=%s", len(records), GAME_DESCRIPTION_ATLAS_URL)
    if limit:
        records = records[:limit]
    manifest = load_manifest()
    result = []
    for index, record in enumerate(records, 1):
        name = record["名称"]
        type_urls = record.get("_type_icon_urls", [])
        rule_urls = record.get("_rule_icon_urls", [])
        record["系别图标路径"] = "dept_icons/" + record["系别"] + ".png" if record.get("系别") else ""
        record["规则图标路径"] = store_asset(
            manifest, fetcher, "game_description_rule", name, rule_urls[0] if rule_urls else "",
            DATA / "icon_rules", f"{safe_name(name)}{extension(rule_urls[0])}" if rule_urls else None,
        )
        result.append(_public_record(record))
        if index % 100 == 0:
            LOGGER.info("[PARSE] game_description %d/%d",index,len(records))
    save_manifest(manifest)
    _log_first_record("game_descriptions", result)
    return result


def write_snapshot(kind: str, rows: list[dict]) -> Path:
    rows = [normalize_record(kind, row) for row in rows]
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    path = STAGING_DIR / f"{kind}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS[kind], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    path.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_csv(path: Path, kind: str) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [normalize_record(kind, dict(row)) for row in csv.DictReader(handle)]


def current_rows(kind: str) -> list[dict]:
    canonical = CANONICAL_DIR / f"{kind}.csv"
    if canonical.exists():
        return read_csv(canonical, kind)
    return read_committed_rows(DB_PATH, kind)


def diff_rows(kind: str, incoming: list[dict]) -> dict:
    old_rows = current_rows(kind)
    old = {_row_key(kind, row): row for row in old_rows if _row_key(kind, row)}
    new = {_row_key(kind, row): row for row in incoming if _row_key(kind, row)}
    return {
        "current": len(old),
        "incoming": len(new),
        "new": sorted(set(new) - set(old)),
        "missing": sorted(set(old) - set(new)),
        "changed": sorted(name for name in set(old) & set(new) if old[name] != new[name]),
    }


def merge_rows(kind: str, incoming: list[dict], remove_missing: bool) -> list[dict]:
    old_rows = current_rows(kind)
    old = {_row_key(kind, row): row for row in old_rows if _row_key(kind, row)}
    new = {_row_key(kind, row): row for row in incoming if _row_key(kind, row)}
    if not remove_missing:
        for old_key, row in old.items():
            new.setdefault(old_key, row)
    return [new[name] for name in sorted(new)]


def write_canonical(kind: str, rows: list[dict]) -> Path:
    rows = [normalize_record(kind, row) for row in rows]
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    path = CANONICAL_DIR / f"{kind}.csv"
    temp = path.with_suffix(".csv.tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS[kind], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)
    path.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def apply_database(rows_by_kind: dict[str, list[dict]]) -> None:
    write_database(DB_PATH, rows_by_kind, load_manifest())


def print_diff(kind: str, summary: dict) -> None:
    def display(value: str) -> str:
        return value.replace("\x00", " / ")

    print(f"{kind}: 当前 {summary['current']}，wiki {summary['incoming']}，新增 {len(summary['new'])}，变化 {len(summary['changed'])}，wiki 未找到 {len(summary['missing'])}")
    if summary["new"]:
        print("  新增：" + "、".join(display(item) for item in summary["new"][:20]) + (" …" if len(summary["new"]) > 20 else ""))
    if summary["missing"]:
        print("  wiki 未找到：" + "、".join(display(item) for item in summary["missing"][:20]) + (" …" if len(summary["missing"]) > 20 else ""))


def configure_logging(level: str = "INFO", quiet: bool = False) -> None:
    if quiet:
        level = "WARNING"
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix} ").strip().lower()
    return default if not answer else answer in {"y", "yes", "是", "确认"}


def run(args: argparse.Namespace) -> int:
    global DB_PATH
    DB_PATH = Path(getattr(args, "database", DB_PATH)).resolve()
    configure_logging(
        "DEBUG" if getattr(args, "verbose", False) else getattr(args, "log_level", "INFO"),
        getattr(args, "quiet", False),
    )
    selected = {"skills", "spirits", "game_descriptions"} if args.kind == "all" else {
        "game_descriptions" if args.kind == "game-descriptions" else args.kind
    }
    if getattr(args, "crawl_skill_relations", False) and "skills" not in selected:
        LOGGER.error("[RELATION] --crawl-skill-relations requires --kind skills or --kind all")
        return 2
    fetcher = WikiFetcher(delay=args.delay)
    rows_by_kind: dict[str, list[dict]] = {}
    if "skills" in selected:
        LOGGER.info("[JOB] skills list + icons; detail pages disabled")
        rows_by_kind["skills"] = _skill_snapshot(fetcher, args.limit)
        write_snapshot("skills", rows_by_kind["skills"])
        if getattr(args, "crawl_skill_relations", False):
            rows_by_kind["spirit_skills"] = _skill_relation_snapshot(fetcher, rows_by_kind["skills"])
            write_snapshot("spirit_skills", rows_by_kind["spirit_skills"])
    if "spirits" in selected:
        LOGGER.info("[JOB] spirit list + atlas; detail pages disabled")
        spirits, evolutions = _spirit_snapshot(fetcher, args.limit)
        rows_by_kind["spirits"] = spirits
        rows_by_kind["evolutions"] = evolutions
        write_snapshot("spirits", spirits)
        write_snapshot("evolutions", evolutions)
    if "game_descriptions" in selected:
        LOGGER.info("[JOB] game description atlas + icons; detail pages disabled")
        rows_by_kind["game_descriptions"] = _game_description_snapshot(fetcher, args.limit)
        write_snapshot("game_descriptions", rows_by_kind["game_descriptions"])
    if not rows_by_kind:
        print("[ERROR] 没有抓到任何数据；未触碰数据库。", file=sys.stderr)
        return 1

    snapshot = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": {"skills": SKILL_LIST_URL, "spirits": SPIRIT_LIST_URL, "atlas": SPIRIT_ATLAS_URL, "game_descriptions": GAME_DESCRIPTION_ATLAS_URL},
        "skill_relation_pages": bool(getattr(args, "crawl_skill_relations", False)),
        "counts": {kind: len(rows) for kind, rows in rows_by_kind.items()},
        "errors": [error.__dict__ for error in fetcher.errors],
    }
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    (STAGING_DIR / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    save_manifest(load_manifest())
    print("\n增量报告：")
    for kind, rows in rows_by_kind.items():
        if kind == "evolutions" and "spirits" not in selected:
            continue
        print_diff(kind, diff_rows(kind, rows))
    print(f"资源 manifest：{MANIFEST_PATH}")
    print(f"staging 快照：{STAGING_DIR}")
    if fetcher.errors:
        print(f"[WARN] 抓取失败 {len(fetcher.errors)} 项；请先检查 staging/snapshot.json。")
    if args.stage_only:
        print("[DONE] 仅生成 staging，未写入 canonical CSV/数据库。")
        return 0

    empty_kinds = [kind for kind in selected if not rows_by_kind.get(kind)]
    if empty_kinds:
        LOGGER.error("[DB] 列表采集为空，禁止写库，以免清空已有数据：%s", empty_kinds)
        return 1

    missing_exists = any(diff_rows(kind, rows)["missing"] for kind, rows in rows_by_kind.items())
    if args.remove_missing:
        remove_missing = True
    elif args.keep_missing:
        remove_missing = False
    elif missing_exists:
        remove_missing = ask_yes_no("是否移除 wiki 中未找到的旧记录？", default=False)
    else:
        remove_missing = False
    if args.yes:
        confirm_write = True
    elif not sys.stdin.isatty():
        print("[INFO] 非交互终端，默认保留 staging；使用 --yes 才会写入。")
        confirm_write = False
    else:
        confirm_write = ask_yes_no(f"资源已下载完成，是否将信息写入 canonical CSV 和新 Wiki 数据库 {DB_PATH}？", default=False)
    if not confirm_write:
        print("[DONE] 用户未确认写入；数据库未修改。")
        return 0

    merged_rows: dict[str, list[dict]] = {}
    for kind, rows in rows_by_kind.items():
        merged_rows[kind] = merge_rows(kind, rows, remove_missing)
    apply_database(merged_rows)
    for kind, rows in merged_rows.items():
        write_canonical(kind, rows)
    print(f"[DONE] 已写入 canonical CSV/JSON 和新 Wiki 数据库：{DB_PATH}；旧数据库未修改。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NRC wiki 增量同步：先下载并生成 staging，确认后才写入数据库")
    parser.add_argument("--kind", choices=("all", "skills", "spirits", "game-descriptions"), default="all")
    parser.add_argument("--database", type=Path, default=DB_PATH, help="新 Wiki 数据库路径，默认 data/nrc_wiki.db；不向旧战斗数据库写入")
    parser.add_argument("--limit", type=int, default=0, help="限制每类记录数量，0 为全部")
    parser.add_argument("--delay", type=float, default=0.0, help="请求间隔秒数；缓存命中不等待，默认 0")
    parser.add_argument("--stage-only", action="store_true", help="只抓取、下载和生成差异快照，不询问写入")
    parser.add_argument("--yes", action="store_true", help="自动确认写入 canonical CSV 和 SQLite")
    parser.add_argument("--remove-missing", action="store_true", help="自动移除 wiki 未找到的旧记录")
    parser.add_argument("--keep-missing", action="store_true", help="保留 wiki 未找到的旧记录")
    parser.add_argument("--crawl-skill-relations", action="store_true", help="额外逐个请求技能详情页，抓取 nrc-skill-pet-card 关系")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO", help="日志级别，默认 INFO")
    parser.add_argument("--verbose", action="store_true", help="等同于 --log-level DEBUG")
    parser.add_argument("--quiet", action="store_true", help="仅输出 WARNING/ERROR")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
