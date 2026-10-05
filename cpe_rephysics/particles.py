"""Integrated Particle Engine (IPE) used by CPE."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    lifetime: float
    maximum_lifetime: float
    size: float
    color: tuple[int, int, int]
    gravity: float = 220.0
    drag: float = 0.985


class IntegratedParticleEngine:
    """A small deterministic particle system with a fixed memory ceiling."""

    def __init__(self, max_particles: int = 4_000, seed: int | None = None):
        self.max_particles = max(1, int(max_particles))
        self.particles: list[Particle] = []
        self.random = random.Random(seed)

    def emit(
        self,
        x: float,
        y: float,
        count: int = 24,
        speed: float = 260,
        lifetime: float = 1.1,
        color: tuple[int, int, int] = (250, 198, 72),
        size: float = 4.0,
    ) -> int:
        available = max(0, self.max_particles - len(self.particles))
        amount = min(max(0, int(count)), available, 500)
        clean_color = tuple(max(0, min(255, int(channel))) for channel in color)
        for _ in range(amount):
            angle = self.random.uniform(0, math.tau)
            velocity = max(0.0, float(speed)) * self.random.uniform(0.28, 1.0)
            particle_life = max(0.05, float(lifetime)) * self.random.uniform(0.72, 1.18)
            self.particles.append(
                Particle(
                    float(x),
                    float(y),
                    math.cos(angle) * velocity,
                    math.sin(angle) * velocity,
                    particle_life,
                    particle_life,
                    max(1.0, float(size) * self.random.uniform(0.6, 1.35)),
                    clean_color,
                )
            )
        return amount

    def update(self, dt: float) -> None:
        dt = max(0.0, min(float(dt), 0.1))
        survivors: list[Particle] = []
        drag = math.pow(0.985, dt * 60)
        for particle in self.particles:
            particle.lifetime -= dt
            if particle.lifetime <= 0:
                continue
            particle.vy += particle.gravity * dt
            particle.vx *= drag
            particle.vy *= drag
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            survivors.append(particle)
        self.particles = survivors

    def draw(self, surface: Any) -> None:
        import pygame

        for particle in self.particles:
            fade = max(0.0, min(1.0, particle.lifetime / particle.maximum_lifetime))
            color = tuple(int(channel * (0.35 + fade * 0.65)) for channel in particle.color)
            radius = max(1, int(particle.size * (0.45 + fade * 0.55)))
            pygame.draw.circle(surface, color, (round(particle.x), round(particle.y)), radius)

    def clear(self) -> None:
        self.particles.clear()

    def snapshot(self, limit: int = 200) -> list[dict[str, Any]]:
        return [
            {
                "x": round(particle.x, 3),
                "y": round(particle.y, 3),
                "life": round(particle.lifetime, 3),
                "size": round(particle.size, 3),
                "color": list(particle.color),
            }
            for particle in self.particles[: max(0, int(limit))]
        ]
