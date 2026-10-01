"""基于固定文本模式的技能/分支解析器。

设计目标不是一次性“猜懂”所有技能，而是：

* 把可确认的分支拆成稳定的枚举键；
* 保留原文和命中的模式，方便人工审计；
* 解析不了时显式标记，不生成看似正确的规则。

同一类文本命中同一个 ``strategy_key``，因此具有相同描述的技能会共享同一套审计拆分方式。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import product
from typing import Iterable

from nrc_core.branching import (
    AuditStatus,
    BranchDimension,
    BranchKey,
    BranchOption,
    expand_branch_dimensions,
)


ATTRIBUTES = [
    ("normal", "普通"), ("fire", "火"), ("water", "水"), ("grass", "草"),
    ("electric", "电"), ("ice", "冰"), ("fighting", "武"), ("poison", "毒"),
    ("ground", "地"), ("flying", "翼"), ("psychic", "幻"), ("bug", "虫"),
    ("ghost", "幽"), ("dragon", "龙"), ("dark", "恶"), ("steel", "机械"),
    ("fairy", "萌"), ("light", "光"),
]


@dataclass
class ParsedDescription:
    source_name: str
    description: str
    strategy_key: str
    options: list[BranchOption] = field(default_factory=list)
    branches: list[list[BranchOption]] = field(default_factory=list)
    effect_atoms: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)
    status: AuditStatus = AuditStatus.PARSED
    manual_reason: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def has_branch(self) -> bool:
        return len(self.options) > 1 or any(
            option.key.dimension != BranchDimension.CONDITION
            or option.key.value != "base"
            for option in self.options
        )

    def to_json(self) -> dict:
        return {
            "source_name": self.source_name,
            "description": self.description,
            "strategy_key": self.strategy_key,
            "options": [option.to_json() for option in self.options],
            "branches": [[option.to_json() for option in branch] for branch in self.branches],
            "effect_atoms": self.effect_atoms,
            "matched_patterns": self.matched_patterns,
            "status": self.status.value,
            "manual_reason": self.manual_reason,
            "warnings": self.warnings,
        }


class SkillDescriptionParser:
    """可扩展的固定模式解析器。"""

    def __init__(self, max_branches: int = 128):
        self.max_branches = max_branches

    def parse(self, name: str, description: str) -> ParsedDescription:
        text = re.sub(r"\s+", "", description or "")
        dimensions: list[list[BranchOption]] = []
        matched: list[str] = []
        warnings: list[str] = []

        dynamic_skill_runtime = name in {"借用", "取念", "复写"}
        if dynamic_skill_runtime:
            matched.append("dynamic_skill_runtime")

        probability = self._probability(text)
        if probability:
            dimensions.append(probability)
            matched.append("probability")

        gulu = self._gulu_ball(text)
        if gulu:
            dimensions.append(gulu)
            matched.append("gulu_ball")

        counter = self._counter(text)
        if counter:
            dimensions.append(counter)
            matched.append("counter")

        # 水星水的属性描述只是说明应对成功时的计算规则，不是额外的
        # 观测分支；审计时只需要区分应对成功/失败。
        if name != "水星水":
            self_attr = self._attribute(text, owner="self")
            if self_attr:
                dimensions.append(self_attr)
                matched.append("self_attribute")

            opponent_attr = self._attribute(text, owner="opponent")
            if opponent_attr:
                dimensions.append(opponent_attr)
                matched.append("opponent_attribute")

        condition = self._condition(text)
        if condition:
            dimensions.append(condition)
            matched.append("condition")

        if name == "折射":
            dimensions.append([
                BranchOption(
                    key=BranchKey(BranchDimension.REFRACTION, "loadout", "按自身携带技能系别计算"),
                    probability=1.0,
                    evidence="折射效果由自身技能组决定",
                )
            ])
            matched.append("refraction_loadout")

        random_devotion = "随机奉献" in text
        if random_devotion:
            dimensions.append([
                BranchOption(
                    key=BranchKey(BranchDimension.DEVOTION_EFFECT, "latent", "随机奉献潜变量"),
                    probability=None,
                    evidence="随机奉献不展开层数分配",
                )
            ])
            matched.append("random_devotion_latent")
        if ("随机" in text or "任意" in text) and not random_devotion and not dynamic_skill_runtime:
            warnings.append("文本包含随机/任意结果，具体结果需要人工绑定")
            matched.append("random_unresolved")

        combinations, overflow = expand_branch_dimensions(dimensions, self.max_branches)
        if overflow:
            return ParsedDescription(
                source_name=name,
                description=description or "",
                strategy_key="overflow:" + "+".join(matched),
                status=AuditStatus.MANUAL_REQUIRED,
                manual_reason=overflow,
                matched_patterns=matched,
                warnings=warnings,
                branches=[],
            )

        if not combinations:
            combinations = [[]]

        branches = combinations
        options = self._flatten_options(branches, description or "")
        if not matched:
            options = [
                BranchOption(
                    key=BranchKey(BranchDimension.CONDITION, "base", "无条件分支"),
                    probability=1.0,
                    evidence=description or "",
                )
            ]
            branches = [[]]

        manual_reason = ""
        status = AuditStatus.PARSED
        if self._looks_like_unhandled_condition(text, matched):
            status = AuditStatus.MANUAL_REQUIRED
            manual_reason = "包含条件描述，但当前固定模式无法安全表达"
        elif "random_unresolved" in matched:
            status = AuditStatus.MANUAL_REQUIRED
            manual_reason = "随机结果需要人工补充结果集合"

        strategy_key = "+".join(matched) if matched else "base"
        return ParsedDescription(
            source_name=name,
            description=description or "",
            strategy_key=strategy_key,
            options=options,
            branches=branches,
            effect_atoms=self._effect_atoms(text),
            matched_patterns=matched,
            status=status,
            manual_reason=manual_reason,
            warnings=warnings,
        )

    def _probability(self, text: str) -> list[BranchOption]:
        match = re.search(r"(\d{1,3})%概率", text)
        if not match:
            return []
        probability = int(match.group(1)) / 100
        return [
            BranchOption(
                key=BranchKey(BranchDimension.PROBABILITY, "triggered", "触发"),
                probability=probability,
                evidence=match.group(0),
            ),
            BranchOption(
                key=BranchKey(BranchDimension.PROBABILITY, "not_triggered", "未触发"),
                probability=1 - probability,
                evidence=match.group(0),
            ),
        ]

    def _gulu_ball(self, text: str) -> list[BranchOption]:
        if "咕噜球" not in text:
            return []
        values = [
            ("normal", "普通"),
            ("advanced", "高级"),
            ("gold", "黄金"),
            ("prism", "棱镜"),
            ("type", "系别"),
        ]
        return [
            BranchOption(
                key=BranchKey(BranchDimension.GULU_BALL, key, label),
                probability=None,
                evidence="咕噜球类型",
            )
            for key, label in values
        ]

    def _counter(self, text: str) -> list[BranchOption]:
        if "应对" not in text:
            return []
        category = "any"
        if "应对攻击" in text:
            category = "attack"
        elif "应对状态" in text:
            category = "status"
        elif "应对防御" in text:
            category = "defense"
        return [
            BranchOption(
                key=BranchKey(BranchDimension.COUNTER, "success", "应对成功"),
                probability=None,
                evidence=f"应对:{category}",
            ),
            BranchOption(
                key=BranchKey(BranchDimension.COUNTER, "failure", "应对失败"),
                probability=None,
                evidence=f"应对:{category}",
            ),
        ]

    def _attribute(self, text: str, owner: str) -> list[BranchOption]:
        is_self = owner == "self"
        patterns = (
            ("自身属性", BranchDimension.SELF_ATTRIBUTE),
            ("自己属性", BranchDimension.SELF_ATTRIBUTE),
        ) if is_self else (
            ("对方属性", BranchDimension.OPPONENT_ATTRIBUTE),
            ("敌方属性", BranchDimension.OPPONENT_ATTRIBUTE),
        )
        if not any(pattern in text for pattern, _ in patterns):
            return []
        dimension = patterns[0][1]
        return [
            BranchOption(
                key=BranchKey(dimension, key, label),
                probability=None,
                evidence="根据" + ("自身" if is_self else "对方") + "属性",
            )
            for key, label in ATTRIBUTES
        ]

    def _condition(self, text: str) -> list[BranchOption]:
        if not re.search(r"(?:若|如果|当|敌方有|自身有|本回合)", text):
            return []
        return [
            BranchOption(
                key=BranchKey(BranchDimension.CONDITION, "true", "条件满足"),
                probability=None,
                evidence="条件句",
            ),
            BranchOption(
                key=BranchKey(BranchDimension.CONDITION, "false", "条件不满足"),
                probability=None,
                evidence="条件句",
            ),
        ]

    def _flatten_options(self, branches: list[list[BranchOption]], evidence: str) -> list[BranchOption]:
        """保留原始 enum 选项；完整分支组合放在 ``branches``。"""
        if not branches or branches == [[]]:
            return [BranchOption(
                key=BranchKey(BranchDimension.CONDITION, "base", "无条件分支"),
                probability=1.0,
                evidence=evidence,
            )]
        unique: dict[str, BranchOption] = {}
        for branch in branches:
            for option in branch:
                unique.setdefault(option.key.code, option)
        return list(unique.values())

    def _effect_atoms(self, text: str) -> list[str]:
        atoms: list[str] = []
        patterns = {
            "damage": r"造成(?:物伤|魔伤|伤害)",
            "heal": r"(?:回复|恢复)",
            "buff": r"(?:获得|提升|增加|强化).{0,12}(?:攻|防|速度|威力|能耗)",
            "debuff": r"(?:降低|减少|削弱).{0,12}(?:攻|防|速度|威力|能耗)",
            "poison": r"中毒",
            "burn": r"灼烧",
            "freeze": r"冻结|冻伤",
            "energy": r"能量|耗能",
            "switch": r"更换精灵|换人|脱离",
            "weather": r"天气|雨天|雪天|沙暴",
        }
        for atom, pattern in patterns.items():
            if re.search(pattern, text):
                atoms.append(atom)
        return atoms

    def _looks_like_unhandled_condition(self, text: str, matched: list[str]) -> bool:
        condition_words = ("若", "如果", "当", "根据", "达到", "低于", "高于")
        return any(word in text for word in condition_words) and "condition" not in matched and not any(
            item in matched for item in ("self_attribute", "opponent_attribute", "gulu_ball")
        )
