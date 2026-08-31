"""Pymunk/Pygame implementation of Cube Physics Engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pymunk

from .particles import IntegratedParticleEngine
from .protocol import NumericCommand, ProtocolError, parse_numeric_line


@dataclass(slots=True)
class BodyRecord:
    entity_id: int
    kind: str
    body: pymunk.Body
    shape: pymunk.Shape
    color: tuple[int, int, int]
    size: float
    sides: int = 4


class CubePhysicsEngine:
    """Execute CPE/1 instructions as a deterministic 2D physics world."""

    def __init__(
        self,
        width: int = 1100,
        height: int = 720,
        gravity: tuple[float, float] = (0, 900),
        *,
        floor_y: int | None = None,
        boundary_friction: float = 0.82,
        boundary_elasticity: float = 0.52,
        particle_limit: int = 4_000,
        particle_seed: int | None = None,
    ):
        self.width = max(160, int(width))
        self.height = max(120, int(height))
        self.floor_y = int(floor_y if floor_y is not None else self.height - 38)
        self.boundary_friction = float(boundary_friction)
        self.boundary_elasticity = float(boundary_elasticity)
        self.space = pymunk.Space()
        self.space.gravity = tuple(float(value) for value in gravity)
        self.space.iterations = 20
        self.particles = IntegratedParticleEngine(particle_limit, particle_seed)
        self.bodies: dict[int, BodyRecord] = {}
        self._shape_colors: dict[pymunk.Shape, tuple[int, int, int]] = {}
        self._next_entity_id = 1
        self._accumulator = 0.0
        self._fixed_step = 1 / 120
        self._simulation_time = 0.0
        self._collision_times: dict[tuple[int, int], float] = {}
        self.paused = False
        self._create_boundaries()
        self._install_collision_particles()

    def _create_boundaries(self) -> None:
        static = self.space.static_body
        segments = (
            pymunk.Segment(static, (2, 0), (2, self.floor_y), 5),
            pymunk.Segment(static, (self.width - 2, 0), (self.width - 2, self.floor_y), 5),
            pymunk.Segment(static, (0, self.floor_y), (self.width, self.floor_y), 6),
        )
        for segment in segments:
            segment.friction = self.boundary_friction
            segment.elasticity = self.boundary_elasticity
            segment.collision_type = 1
        self.space.add(*segments)

    def _install_collision_particles(self) -> None:
        if hasattr(self.space, "on_collision"):
            self.space.on_collision(None, None, post_solve=self._on_collision)
        else:  # Pymunk 6 compatibility.
            handler = self.space.add_default_collision_handler()
            handler.post_solve = self._on_collision

    def _on_collision(self, arbiter: pymunk.Arbiter, _space: pymunk.Space, _data: Any) -> None:
        impulse = float(arbiter.total_impulse.length)
        if impulse < 110:
            return
        first, second = arbiter.shapes
        key = tuple(sorted((id(first), id(second))))
        if self._simulation_time - self._collision_times.get(key, -10.0) < 0.09:
            return
        self._collision_times[key] = self._simulation_time
        points = arbiter.contact_point_set.points
        if not points:
            return
        point = points[0].point_a
        color = self._shape_colors.get(first) or self._shape_colors.get(second) or (250, 198, 72)
        self.particles.emit(point.x, point.y, min(22, max(3, int(impulse / 160))), min(420, impulse / 3), 0.55, color, 3)

    @staticmethod
    def _vertices(sides: int, radius: float) -> list[tuple[float, float]]:
        offset = -math.pi / 2
        return [
            (math.cos(offset + index * math.tau / sides) * radius, math.sin(offset + index * math.tau / sides) * radius)
            for index in range(sides)
        ]

    def spawn(
        self,
        kind: str,
        x: float,
        y: float,
        size: float,
        mass: float,
        color: tuple[int, int, int],
        *,
        sides: int = 4,
    ) -> int:
        kind = kind.lower()
        size = max(4.0, min(250.0, float(size)))
        mass = max(0.05, min(1_000.0, float(mass)))
        sides = max(3, min(12, int(sides)))
        if kind == "circle":
            moment = pymunk.moment_for_circle(mass, 0, size)
            body = pymunk.Body(mass, moment)
            shape: pymunk.Shape = pymunk.Circle(body, size)
        else:
            vertices = self._vertices(4 if kind == "box" else sides, size)
            moment = pymunk.moment_for_poly(mass, vertices)
            body = pymunk.Body(mass, moment)
            shape = pymunk.Poly(body, vertices)
        body.position = float(x), float(y)
        shape.friction = 0.72
        shape.elasticity = 0.48
        shape.collision_type = 2
        self.space.add(body, shape)
        entity_id = self._next_entity_id
        self._next_entity_id += 1
        clean_color = tuple(max(0, min(255, int(channel))) for channel in color)
        record = BodyRecord(entity_id, kind, body, shape, clean_color, size, sides)
        self.bodies[entity_id] = record
        self._shape_colors[shape] = clean_color
        self.particles.emit(x, y, 10, 115, 0.45, clean_color, 3)
        return entity_id

    def register_body(
        self,
        entity_id: int,
        kind: str,
        body: pymunk.Body,
        shape: pymunk.Shape,
        color: tuple[int, int, int],
        size: float,
        *,
        sides: int = 4,
        emit_particles: bool = True,
    ) -> BodyRecord:
        """Adopt a game-created body so CPE remains the authoritative runtime."""

        entity_id = int(entity_id)
        clean_color = tuple(max(0, min(255, int(channel))) for channel in color)
        record = BodyRecord(entity_id, str(kind), body, shape, clean_color, float(size), int(sides))
        self.bodies[entity_id] = record
        self._shape_colors[shape] = clean_color
        self._next_entity_id = max(self._next_entity_id, entity_id + 1)
        if emit_particles:
            self.particles.emit(body.position.x, body.position.y, 10, 115, 0.45, clean_color, 3)
        return record

    def remove(self, entity_id: int) -> bool:
        record = self.bodies.pop(int(entity_id), None)
        if record is None:
            return False
        self._shape_colors.pop(record.shape, None)
        if record.shape in self.space.shapes:
            self.space.remove(record.shape, record.body)
        return True

    def clear(self) -> None:
        for entity_id in list(self.bodies):
            self.remove(entity_id)
        self.particles.clear()

    def particle_snapshot(self, limit: int = 400) -> list[dict[str, Any]]:
        return self.particles.snapshot(limit)

    def execute(self, command: NumericCommand) -> dict[str, Any]:
        values = command.values
        result: dict[str, Any] = {"sequence": command.sequence, "command": command.name, "ok": True}
        if command.opcode in {1, 2}:
            x, y, size, mass, red, green, blue = values
            kind = "box" if command.opcode == 1 else "circle"
            result["entity_id"] = self.spawn(kind, x, y, size, mass, (int(red), int(green), int(blue)))
        elif command.opcode == 3:
            x, y, sides, size, mass, red, green, blue = values
            result["entity_id"] = self.spawn(
                "polygon", x, y, size, mass, (int(red), int(green), int(blue)), sides=int(sides)
            )
        elif command.opcode == 10:
            self.space.gravity = values[0], values[1]
            result["gravity"] = list(self.space.gravity)
        elif command.opcode in {11, 12}:
            entity_id, x, y = int(values[0]), values[1], values[2]
            record = self.bodies.get(entity_id)
            if record is None:
                raise ProtocolError(f"entity {entity_id} does not exist")
            vector = pymunk.Vec2d(x, y)
            if command.opcode == 11:
                record.body.apply_impulse_at_local_point(vector)
            else:
                record.body.apply_force_at_local_point(vector)
        elif command.opcode == 20:
            x, y, count, speed, lifetime, red, green, blue = values
            result["particles"] = self.particles.emit(
                x, y, int(count), speed, lifetime, (int(red), int(green), int(blue))
            )
        elif command.opcode == 30:
            self.clear()
        elif command.opcode == 40:
            self.paused = bool(values[0])
            result["paused"] = self.paused
        return result

    def execute_line(self, line: str) -> dict[str, Any]:
        return self.execute(parse_numeric_line(line))

    def step(self, dt: float) -> None:
        dt = max(0.0, min(float(dt), 0.25))
        self.particles.update(dt)
        if self.paused:
            return
        self._accumulator += dt
        substeps = 0
        while self._accumulator >= self._fixed_step and substeps < 30:
            self.space.step(self._fixed_step)
            self._simulation_time += self._fixed_step
            self._accumulator -= self._fixed_step
            substeps += 1
        if substeps == 30:
            self._accumulator = 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "engine": "CPE",
            "protocol": "CPE/1",
            "simulation_time": round(self._simulation_time, 4),
            "paused": self.paused,
            "gravity": [round(self.space.gravity.x, 3), round(self.space.gravity.y, 3)],
            "particle_count": len(self.particles.particles),
            "bodies": [
                {
                    "id": record.entity_id,
                    "kind": record.kind,
                    "x": round(record.body.position.x, 3),
                    "y": round(record.body.position.y, 3),
                    "vx": round(record.body.velocity.x, 3),
                    "vy": round(record.body.velocity.y, 3),
                    "angle": round(record.body.angle, 5),
                    "size": round(record.size, 3),
                    "sides": record.sides,
                    "color": list(record.color),
                }
                for record in self.bodies.values()
            ],
        }

    def render(self, surface: Any, *, clear: bool = True) -> None:
        import pygame

        if clear:
            surface.fill((24, 32, 42))
        pygame.draw.line(surface, (202, 132, 65), (0, self.floor_y), (self.width, self.floor_y), 5)
        self.particles.draw(surface)
        for record in self.bodies.values():
            outline = tuple(max(0, channel - 55) for channel in record.color)
            if isinstance(record.shape, pymunk.Circle):
                center = round(record.body.position.x), round(record.body.position.y)
                radius = max(1, round(record.shape.radius))
                pygame.draw.circle(surface, record.color, center, radius)
                pygame.draw.circle(surface, outline, center, radius, 3)
                spoke = record.body.local_to_world((record.shape.radius * 0.7, 0))
                pygame.draw.line(surface, (250, 244, 226), center, (round(spoke.x), round(spoke.y)), 3)
            else:
                points = [
                    (round(point.x), round(point.y))
                    for point in (record.body.local_to_world(vertex) for vertex in record.shape.get_vertices())
                ]
                pygame.draw.polygon(surface, record.color, points)
                pygame.draw.polygon(surface, outline, points, 3)
