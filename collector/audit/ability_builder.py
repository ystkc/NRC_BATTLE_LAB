"""特性审计表生成器。

特性暂不自动推断触发条件，只把数据库中的候选特性拆成可人工填写的审计记录。
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


TRIGGER_KEYWORDS = {
    "super_effective": ("克制", "效果拔群", "弱点"),
    "resisted": ("抵抗", "抗性", "被抵抗"),
    "fire_skill": ("火系", "火属性", "火技能"),
    "water_skill": ("水系", "水属性", "水技能"),
    "grass_skill": ("草系", "草属性", "草技能"),
    "electric_skill": ("电系", "电属性", "电技能"),
    "ice_skill": ("冰系", "冰属性", "冰技能"),
    "poison_skill": ("毒系", "毒属性", "毒技能"),
    "fighting_skill": ("武系", "武属性", "武技能"),
    "ground_skill": ("地系", "地属性", "地技能"),
    "flying_skill": ("翼系", "翼属性", "翼技能"),
    "psychic_skill": ("幻系", "幻属性", "幻技能"),
    "bug_skill": ("虫系", "虫属性", "虫技能"),
    "ghost_skill": ("幽系", "幽属性", "幽技能"),
    "dragon_skill": ("龙系", "龙属性", "龙技能"),
    "dark_skill": ("恶系", "恶属性", "恶技能"),
    "steel_skill": ("机械系", "机械属性", "机械技能"),
    "fairy_skill": ("萌系", "萌属性", "萌技能"),
    "light_skill": ("光系", "光属性", "光技能"),
    "defense_skill": ("防御技能", "防御类技能", "防御技"),
    "before_enemy": ("先于敌方", "先于对手", "优先于敌方", "优先出手"),
    "turn_end": ("回合结束", "每回合结束", "回合末"),
    "take_attack": ("受到攻击", "受到1次攻击", "受到一次攻击", "被攻击"),
    "take_hit": ("受到伤害", "受到打击", "被命中"),
    "on_enter": ("入场", "上场", "登场"),
    "on_leave": ("离场", "下场", "退场"),
    "on_kill": ("击败", "击杀", "击倒"),
    "on_faint": ("力竭", "濒死", "死亡"),
    "on_skill_use": ("使用技能", "释放技能", "施放技能"),
    "on_switch": ("换人", "更换精灵", "敌方换人"),
    "weather": ("天气", "晴天", "雨天", "雪天", "沙暴"),
    "energy": ("能量", "能耗", "魔力", "MP"),
    "hp_threshold": ("生命值低于", "生命低于", "生命值高于", "生命高于", "血量低于"),
    "counter": ("应对", "反制", "抵挡"),
    "probability": ("概率", "几率"),
}


def _candidate_trigger_keywords(raw_value: str) -> dict[str, list[str]]:
    return {
        code: [keyword for keyword in keywords if keyword in raw_value]
        for code, keywords in TRIGGER_KEYWORDS.items()
        if any(keyword in raw_value for keyword in keywords)
    }


def build_ability_audit(db_path: str | Path, output_dir: str | Path) -> dict:
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT DISTINCT ability FROM pokemon WHERE ability IS NOT NULL AND ability != ''").fetchall()

    records = []
    for (raw_ability,) in rows:
        candidates = _candidate_trigger_keywords(str(raw_ability))
        name = str(raw_ability).split(":", 1)[0].split("：", 1)[0].strip()
        records.append({
            "name": name,
            "raw_value": raw_ability,
            "status": "manual_required",
            "trigger_mode": "manual_active_trigger",
            "conditions": [],
            "branches": [],
            "audit_records": [],
            "candidate_trigger_keywords": candidates,
            "keyword_review_status": "pending",
            "note": "特性条件复杂，等待人工主动触发并绑定分支",
        })

    payload = {
        "schema_version": 1,
        "parser": "manual-only-v1",
        "record_count": len(records),
        "records": records,
    }
    (output_dir / "abilities_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output_dir / "abilities_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "name", "raw_value", "status", "trigger_mode",
            "candidate_trigger_codes", "candidate_trigger_keywords", "note",
        ])
        writer.writeheader()
        for record in records:
            writer.writerow({
                "name": record["name"],
                "raw_value": record["raw_value"],
                "status": record["status"],
                "trigger_mode": record["trigger_mode"],
                "candidate_trigger_codes": ",".join(record["candidate_trigger_keywords"]),
                "candidate_trigger_keywords": "；".join(
                    f"{code}={'/'.join(keywords)}"
                    for code, keywords in record["candidate_trigger_keywords"].items()
                ),
                "note": record["note"],
            })
    with (output_dir / "abilities_uncertain.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "name", "raw_value", "candidate_trigger_codes", "candidate_trigger_keywords", "review_note",
        ])
        writer.writeheader()
        for record in records:
            writer.writerow({
                "name": record["name"],
                "raw_value": record["raw_value"],
                "candidate_trigger_codes": ",".join(record["candidate_trigger_keywords"]),
                "candidate_trigger_keywords": "；".join(
                    f"{code}={'/'.join(keywords)}"
                    for code, keywords in record["candidate_trigger_keywords"].items()
                ),
                "review_note": "请确认关键词是否足以表达触发条件，并补充缺失关键词",
            })
    return payload
