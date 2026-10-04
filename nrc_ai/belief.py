"""Generic weighted particle belief state for hidden opponent information."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Callable, Iterable


@dataclass
class Particle:
    state: Any
    weight: float = 1.0
    metadata: dict[str, Any] | None = None


class ParticleBelief:
    def __init__(self, particles: Iterable[Particle] = ()) -> None:
        self.particles = list(particles)
        self.normalize()

    def normalize(self) -> None:
        total = sum(max(0.0, particle.weight) for particle in self.particles)
        if not self.particles:
            return
        if total <= 0.0:
            uniform = 1.0 / len(self.particles)
            for particle in self.particles:
                particle.weight = uniform
            return
        for particle in self.particles:
            particle.weight = max(0.0, particle.weight) / total

    def copy(self) -> "ParticleBelief":
        return ParticleBelief(Particle(p.state, p.weight, dict(p.metadata or {})) for p in self.particles)

    def effective_sample_size(self) -> float:
        return 1.0 / sum(p.weight * p.weight for p in self.particles) if self.particles else 0.0

    def sample(self, rng: random.Random) -> Particle:
        if not self.particles:
            raise ValueError("cannot sample an empty belief")
        return rng.choices(self.particles, weights=[p.weight for p in self.particles], k=1)[0]


class ParticleFilter:
    def __init__(self, *, resample_threshold: float = 0.5) -> None:
        if not 0.0 < resample_threshold <= 1.0:
            raise ValueError("resample_threshold must be in (0, 1]")
        self.resample_threshold = resample_threshold

    def update(self, belief: ParticleBelief, observation: Any, likelihood: Callable[[Any, Any], float], clone: Callable[[Any], Any] | None = None, rng: random.Random | None = None) -> ParticleBelief:
        rng = rng or random.Random()
        updated = [Particle(p.state, p.weight * max(0.0, float(likelihood(p.state, observation))), p.metadata) for p in belief.particles]
        result = ParticleBelief(updated)
        if result.effective_sample_size() < self.resample_threshold * max(1, len(result.particles)):
            result = self.resample(result, clone=clone, rng=rng)
        return result

    @staticmethod
    def resample(belief: ParticleBelief, *, clone: Callable[[Any], Any] | None = None, rng: random.Random | None = None) -> ParticleBelief:
        rng = rng or random.Random()
        if not belief.particles:
            return ParticleBelief()
        selected = rng.choices(belief.particles, weights=[p.weight for p in belief.particles], k=len(belief.particles))
        copier = clone or (lambda value: value)
        return ParticleBelief(Particle(copier(p.state), 1.0, dict(p.metadata or {})) for p in selected)


def categorical_entropy(probabilities: Iterable[float]) -> float:
    return -sum(p * math.log(max(p, 1e-12)) for p in probabilities if p > 0.0)
