"""History-aware recommendations from partially observed markdown battle logs."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .population_prior import PopulationPrior


_ROUND_DIGITS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
    "八": 8, "九": 9, "十": 10,
}


def _round_number(text: str) -> int:
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if text.startswith("十"):
        return 10 + _ROUND_DIGITS.get(text[1:], 0)
    if text.endswith("十"):
        return _ROUND_DIGITS.get(text[0], 0) * 10
    if "十" in text:
        left, right = text.split("十", 1)
        return _ROUND_DIGITS.get(left, 0) * 10 + _ROUND_DIGITS.get(right, 0)
    return _ROUND_DIGITS.get(text, 0)


@dataclass
class ActionOption:
    name: str
    cost: int | None = None
    power: int | None = None
    trend: str = ""
    kind: str = "skill"

    def to_json(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class BattleRound:
    number: int
    start: dict[str, Any]
    options: list[ActionOption] = field(default_factory=list)
    actual_action: str | None = None
    selection: str | None = None
    evidence: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "round": self.number,
            "start": self.start,
            "options": [item.to_json() for item in self.options],
            "actual_action": self.actual_action,
            "selection": self.selection,
            "evidence": self.evidence,
        }


@dataclass
class BattleLogReport:
    path: str
    rounds: list[BattleRound]
    recommendation_mode: str = "history-aware-partial-observation"

    def to_json(self, prior: PopulationPrior | None = None) -> dict[str, Any]:
        recommendations = []
        seen_options: dict[str, list[ActionOption]] = {}
        for index, battle_round in enumerate(self.rounds):
            options = battle_round.options
            active = str(battle_round.start.get("own_active") or "")
            if not options and active in seen_options:
                options = seen_options[active]
                battle_round.options = options
            if not options and prior is not None and active in prior.records:
                build = prior.top_build(active, skill_count=4, aptitude_count=3, aptitude_iv=60)
                options = [ActionOption(name=item) for item in build.skills]
                battle_round.options = options
            if options and active:
                seen_options[active] = options
            recommendations.append(_recommend(battle_round, self.rounds[:index], options))
        return {
            "path": self.path,
            "recommendation_mode": self.recommendation_mode,
            "round_count": len(self.rounds),
            "latest_round": self.rounds[-1].number if self.rounds else None,
            "rounds": [item.to_json() for item in self.rounds],
            "recommendations": recommendations,
        }


def _parse_options(text: str) -> list[ActionOption]:
    pattern = re.compile(r"(?P<name>[^\s\[]+)\[(?P<cost>\d+)(?:，冷却\d+)?\]\((?P<power>\d+|--)\)(?P<trend>[↑↓]*)")
    return [
        ActionOption(
            name=match.group("name"),
            cost=int(match.group("cost")),
            power=None if match.group("power") == "--" else int(match.group("power")),
            trend=match.group("trend"),
        )
        for match in pattern.finditer(text)
    ]


def _hp_value(text: str) -> int | float | str | None:
    match = re.search(r"(?:HP=|血量)(\d+(?:\.\d+)?%?)", text)
    if not match:
        return None
    value = match.group(1)
    if value.endswith("%"):
        return value
    number = float(value)
    return int(number) if number.is_integer() else number


def _energy_value(text: str) -> int | None:
    match = re.search(r"(?:能量|剩余能量)(\d+)", text)
    return int(match.group(1)) if match else None


def _name_after_label(text: str, label: str) -> str | None:
    match = re.search(re.escape(label) + r"\s*([^，\s]+)", text)
    return match.group(1) if match else None


def parse_battle_log(path: str | Path) -> BattleLogReport:
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    own_label = "\u6211\u65b9"
    enemy_label = "\u654c\u65b9"
    current: dict[str, Any] = {
        "own_active": None,
        "opponent_active": None,
        "own_hp": None,
        "opponent_hp": None,
        "own_energy": None,
        "opponent_energy": None,
        "opponent_statuses": [],
    }
    rounds: list[BattleRound] = []
    known_options: dict[str, list[ActionOption]] = {}
    own_switch = re.compile(r"\]\s*([^\s，]+)→([^\s，]+).*?(?:HP=|血量)(\d+%?)")
    entry = re.compile(r"\]\s*([^\s，]+).*?(?:HP=|血量)(\d+%?)")
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        heading = re.match(r"##\s*第(.+?)回合", line)
        if heading:
            number = _round_number(heading.group(1))
            rounds.append(BattleRound(number=number, start=dict(current)))
            continue
        if not rounds:
            continue
        battle_round = rounds[-1]
        if line.startswith("["):
            battle_round.evidence.append(line)
        if f"[{enemy_label}出场]" in line or f"[{enemy_label}选择上场精灵]" in line:
            name = _name_after_label(line, "]")
            if name:
                current["opponent_active"] = name
            current["opponent_hp"] = _hp_value(line)
            current["opponent_energy"] = _energy_value(line)
        if f"[{own_label}出场]" in line or f"[{own_label}选择上场精灵]" in line:
            name = _name_after_label(line, "]")
            if name:
                current["own_active"] = name
            current["own_hp"] = _hp_value(line)
            current["own_energy"] = _energy_value(line)
        if f"[{enemy_label}切换精灵]" in line:
            match = own_switch.search(line)
            if match:
                current["opponent_active"] = match.group(2)
                current["opponent_hp"] = _hp_value(line)
                current["opponent_energy"] = _energy_value(line)
        if f"[{own_label}切换精灵]" in line:
            match = own_switch.search(line)
            if match:
                current["own_active"] = match.group(2)
                current["own_hp"] = _hp_value(line)
                current["own_energy"] = _energy_value(line)
        if f"[{own_label}选择技能]" in line:
            if not battle_round.options:
                battle_round.start = dict(current)
            content = line.split("]", 1)[1].strip()
            options = _parse_options(content)
            if options:
                battle_round.options = options
                active = str(current.get("own_active") or "")
                if active:
                    known_options[active] = options
            switch = re.search(r"选择了?换人[-—]([^\s，]+)", content)
            if switch:
                battle_round.selection = f"换人-{switch.group(1)}"
            else:
                selected = re.search(r"选择了(\d+)", content)
                if selected:
                    battle_round.selection = selected.group(1)
        if f"[{own_label}使用技能]" in line:
            name = _name_after_label(line, f"[{own_label}使用技能]")
            if name:
                battle_round.actual_action = name
            current["own_energy"] = _energy_value(line) if _energy_value(line) is not None else current["own_energy"]
        if f"[{own_label}应对成功]" in line:
            match = re.search(r"应对！([^，\s]+)", line)
            battle_round.actual_action = match.group(1) if match else battle_round.actual_action
            current["own_energy"] = _energy_value(line) if _energy_value(line) is not None else current["own_energy"]
        if f"[{enemy_label}使用技能]" in line:
            current["opponent_energy"] = _energy_value(line) if _energy_value(line) is not None else current["opponent_energy"]
        if "中毒+" in line:
            current["opponent_statuses"] = sorted(set(current["opponent_statuses"]) | {"中毒"})
        hp = _hp_value(line)
        if hp is not None:
            if current.get("opponent_active") and current["opponent_active"] in line and ("敌方" in line or "状态结算" in line or "铭记" in line):
                current["opponent_hp"] = hp
            if current.get("own_active") and current["own_active"] in line and "我方" in line:
                current["own_hp"] = hp
    for battle_round in rounds:
        if not battle_round.options:
            active = str(battle_round.start.get("own_active") or "")
            if active in known_options:
                battle_round.options = list(known_options[active])
    return BattleLogReport(str(path), rounds)


def _recommend(battle_round: BattleRound, history: list[BattleRound], options: list[ActionOption]) -> dict[str, Any]:
    start = battle_round.start
    opponent_hp = start.get("opponent_hp")
    own_hp = start.get("own_hp")
    opponent_low = isinstance(opponent_hp, str) and opponent_hp.endswith("%") and float(opponent_hp[:-1]) <= 50.0
    own_low = isinstance(own_hp, str) and own_hp.endswith("%") and float(own_hp[:-1]) <= 35.0
    scored: list[dict[str, Any]] = []
    historical_actions = {item.actual_action for item in history if item.actual_action}
    historical_evidence = [line for item in history for line in item.evidence]
    eclipse_count = sum("月蚀" in line for line in historical_evidence)
    for index, option in enumerate(options):
        score = float(option.power or 0) / max(1, option.cost or 1)
        reasons: list[str] = []
        if option.power is not None:
            reasons.append(f"显示威力={option.power}")
        if option.cost is not None:
            reasons.append(f"能耗={option.cost}")
        if "↑" in option.trend:
            score += 2.0
            reasons.append("面板上升箭头")
        if "↓" in option.trend:
            score -= 1.0
            reasons.append("面板下降箭头")
        if opponent_low and option.power is not None:
            score += 2.0
            reasons.append("对手已进入低血量区间")
        if start.get("opponent_statuses") and option.power is not None:
            score += 0.5
            reasons.append("对手已有持续伤害，优先压血/收尾")
        if eclipse_count >= 2 and option.name in {"见招拆招", "蜡质膜", "蜂质膜"}:
            score += 0.5
            reasons.append("历史中对手多次使用月蚀，保留应对手段")
        if own_low and option.kind == "switch":
            score += 5.0
            reasons.append("己方低血量，换人优先")
        if option.name in {"防御", "蜡质膜", "蜂质膜"} and not opponent_low:
            score += 0.5
            reasons.append("保留防守/应对价值")
        if option.name in historical_actions:
            score += 0.25
            reasons.append("此前回合已有实战记录")
        scored.append({"action": option.name, "kind": option.kind, "score": round(score, 4), "reasons": reasons, "option_index": index + 1})
    scored.sort(key=lambda item: (-item["score"], item["option_index"]))
    selected = scored[0] if scored else None
    confidence = "low" if not options or (selected and selected["action"] in {"防御", "蜡质膜", "蜂质膜"}) else "medium"
    return {
        "round": battle_round.number,
        "own_active": start.get("own_active"),
        "opponent_active": start.get("opponent_active"),
        "recommendation": selected,
        "alternatives": scored[1:4],
        "actual_action": battle_round.actual_action,
        "selection": battle_round.selection,
        "confidence": confidence,
        "history_rounds_used": len(history),
        "note": "只使用本回合开始时可见字段和此前回合；未知队伍成员没有被补成确定事实。",
    }


def format_review(payload: Mapping[str, Any]) -> str:
    lines = [f"战报: {payload.get('path')}", f"推荐模式: {payload.get('recommendation_mode')}", ""]
    for item in payload.get("recommendations", []):
        recommendation = item.get("recommendation") or {}
        lines.append(
            f"第{item.get('round')}回合 | {item.get('own_active')} vs {item.get('opponent_active')} | "
            f"推荐: {recommendation.get('action', '信息不足')} | 实际: {item.get('actual_action') or item.get('selection') or '尚未记录'} | "
            f"置信度: {item.get('confidence')}"
        )
        if recommendation:
            lines.append(f"  理由: {'；'.join(recommendation.get('reasons', [])) or '无可量化面板信息'}")
    return "\n".join(lines)


__all__ = ["ActionOption", "BattleLogReport", "BattleRound", "format_review", "parse_battle_log"]
