"""把 mitmproxy 归一化结果匹配到审计分支。

匹配器故意不做模糊猜测：只有观测指标与候选分支唯一对应时才返回成功，
否则交给人工审计，避免错误标记污染审计表。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from nrc_core.schema import ResolutionBranch


@dataclass
class BranchMatch:
    status: str
    branch_id: str | None = None
    reason: str = ""


def match_observed_branch(
    branches: Iterable[ResolutionBranch],
    observed_codes: set[str],
) -> BranchMatch:
    candidates = []
    for branch in branches:
        branch_codes = {option.key.code for option in branch.options}
        if branch_codes and branch_codes.issubset(observed_codes):
            candidates.append(branch)
    if len(candidates) == 1:
        return BranchMatch("matched", candidates[0].branch_id)
    if not candidates:
        return BranchMatch("failed", reason="没有候选分支与观测指标匹配")
    return BranchMatch("ambiguous", reason=f"有 {len(candidates)} 个候选分支")

