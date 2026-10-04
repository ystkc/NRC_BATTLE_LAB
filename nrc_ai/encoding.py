"""Deterministic JSON observation encoding for the first GRU baseline."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import numpy as np


def _tokens(value: Any, prefix: str = "root") -> list[str]:
    if isinstance(value, Mapping):
        result = []
        for key in sorted(value):
            result.extend(_tokens(value[key], f"{prefix}.{key}"))
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for index, item in enumerate(value):
            result.extend(_tokens(item, f"{prefix}[{index}]"))
        return result
    if isinstance(value, bool):
        return [f"{prefix}={str(value).lower()}"]
    if value is None:
        return [f"{prefix}=null"]
    return [f"{prefix}={value}"]


class JsonObservationEncoder:
    def __init__(self, dimension: int = 256) -> None:
        if dimension < 8:
            raise ValueError("dimension must be at least 8")
        self.dimension = dimension

    def encode(self, observation: Mapping[str, Any]) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        for token in _tokens(observation):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimension
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        norm = float(np.linalg.norm(vector))
        return vector / norm if norm > 0 else vector

    def fingerprint(self, observation: Mapping[str, Any]) -> str:
        payload = json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
