"""采集精灵详情页的赛季历史，仅导出独立 CSV。"""

import csv
from pathlib import Path

from bs4 import BeautifulSoup


def parse_balance_adjustments(html: str, spirit_name: str) -> list[dict]:
    """每张历史卡片保留一条记录，内容按页面顺序逐行展示。"""
    soup = BeautifulSoup(html or "", "html.parser")
    records = []
    for card in soup.select("#sd-p-history .sd-p-history-card"):
        head = card.select_one(".sd-p-history-head")
        if head is None:
            continue
        season = head.select_one(".sd-p-history-season")
        date = head.select_one(".sd-p-muted")
        lines = []
        for row in card.select(".sd-p-history-row"):
            tag = row.select_one(".sd-p-history-tag")
            copy = row.select_one(".sd-p-history-copy")
            if copy is None:
                continue
            content = copy.get_text(" ", strip=True)
            if content:
                prefix = f"【{tag.get_text(' ', strip=True)}】" if tag else ""
                lines.append(prefix + content)
        if lines:
            records.append({
                "赛季": season.get_text(" ", strip=True) if season else "",
                "日期": date.get_text(" ", strip=True) if date else "",
                "精灵名": spirit_name,
                "调整内容": "\n".join(lines),
            })
    return records


def export_balance_adjustments(records: list[dict], path: Path) -> int:
    """将已解析的历史记录写入独立 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".csv.tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["赛季", "日期", "精灵名", "调整内容"])
        writer.writeheader()
        print(records)
        writer.writerows(records)
    temp.replace(path)
    return len(records)
