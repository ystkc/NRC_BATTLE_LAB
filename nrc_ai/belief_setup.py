"""Build particle beliefs from complete candidate setup hypotheses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .belief import Particle, ParticleBelief
from .contracts import CoreBackend


def belief_from_setups(backend: CoreBackend, root_setup: Mapping[str, Any], candidate_path: str | Path | None, *, seed: int = 0) -> tuple[ParticleBelief, str]:
    """Build a belief and explicitly label whether it is oracle or candidate-based."""
    if candidate_path is None:
        return ParticleBelief([Particle(backend.new_game(root_setup, seed))]), "oracle-full-state"
    payload = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("belief setup file must be a non-empty JSON array")
    particles = []
    reference_own = None
    reference_shared = None
    for item in payload:
        if isinstance(item, Mapping) and "setup" in item:
            setup = item["setup"]
            weight = float(item.get("weight", 1.0))
        else:
            setup = item
            weight = 1.0
        if not isinstance(setup, Mapping):
            raise ValueError("each belief candidate must be a setup object")
        own = json.dumps(setup.get("own_team", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        shared = json.dumps(setup.get("shared", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if reference_own is None:
            reference_own, reference_shared = own, shared
        elif own != reference_own or shared != reference_shared:
            raise ValueError("belief candidates must keep own_team and shared state identical")
        particles.append(Particle(backend.new_game(setup, seed), weight))
    return ParticleBelief(particles), "candidate-setups"
