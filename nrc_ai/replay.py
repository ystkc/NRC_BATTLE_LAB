"""Versioned trajectory records, independent of any tensor framework."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterator, Mapping, Iterable


@dataclass
class StepRecord:
    decision_index: int
    turn: int
    phase: str
    observation: Mapping[str, Any]
    legal_action_keys: tuple[str, ...]
    action_key: str
    reward: float
    terminated: bool
    winner: int | None = None
    search_policy: Mapping[str, float] | None = None
    source: str = "self_play"


@dataclass
class Episode:
    episode_id: str
    manifest: Mapping[str, Any]
    steps: list[StepRecord] = field(default_factory=list)
    terminal_winner: int | None = None
    truncated: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def append(self, step: StepRecord) -> None:
        if self.steps and step.decision_index <= self.steps[-1].decision_index:
            raise ValueError("decision_index must increase within an episode")
        if step.action_key not in step.legal_action_keys:
            raise ValueError(f"action {step.action_key!r} is not legal")
        self.steps.append(step)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Episode":
        episode = cls(str(payload["episode_id"]), dict(payload.get("manifest", {})), terminal_winner=payload.get("terminal_winner"), truncated=bool(payload.get("truncated", False)), metadata=dict(payload.get("metadata", {})))
        for raw_step in payload.get("steps", []):
            raw_step = dict(raw_step)
            raw_step["legal_action_keys"] = tuple(raw_step["legal_action_keys"])
            episode.append(StepRecord(**raw_step))
        return episode


class ReplayBuffer:
    def __init__(self, episodes: Iterable[Episode] = ()) -> None:
        self.episodes = list(episodes)

    def add(self, episode: Episode) -> None:
        if not episode.steps:
            raise ValueError("cannot add an empty episode")
        self.episodes.append(episode)

    def __len__(self) -> int:
        return len(self.episodes)

    def steps(self) -> Iterator[StepRecord]:
        for episode in self.episodes:
            yield from episode.steps

    def save_jsonl(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            for episode in self.episodes:
                handle.write(json.dumps(episode.to_dict(), ensure_ascii=False) + "\n")

    @classmethod
    def load_jsonl(cls, path: str | Path) -> "ReplayBuffer":
        episodes = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    episodes.append(Episode.from_dict(json.loads(line)))
        return cls(episodes)
