"""Interactive 2.5D renderer and physics extension for The Cube Beta.

The companion ``physics_3d.rb`` file supplies the dimensional content,
material values, and shared color theme. Controls inside the simulation:

* Right click: dimensional shockwave
* Middle click or V: vortex impulse at the pointer
* Mouse wheel: change the amount of visible depth
* D: toggle the 3D renderer
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
import time
import weakref
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "badge": "PHYSICS 3D",
    "accent": [89, 238, 255],
    "secondary": [180, 100, 255],
    "hot": [255, 111, 72],
    "shadow": [8, 19, 45],
    "grid": [86, 218, 255],
    "extrusion": [7, 10],
    "materials": {
        "Holo Orb": {
            "elasticity": 0.94,
            "friction": 0.28,
            "drag": 0.997,
            "glow": 1.0,
        },
        "Depth Cube": {
            "elasticity": 0.42,
            "friction": 0.96,
            "drag": 0.992,
            "glow": 0.45,
        },
        "Kinetic Prism": {
            "elasticity": 0.76,
            "friction": 0.52,
            "drag": 0.995,
            "glow": 0.78,
        },
        "Glass D8": {
            "elasticity": 0.88,
            "friction": 0.34,
            "drag": 0.996,
            "glow": 0.9,
        },
        "Flux Ring": {
            "elasticity": 1.02,
            "friction": 0.18,
            "drag": 0.998,
            "glow": 1.0,
        },
    },
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _rgb(value: Any, fallback: Any) -> tuple[int, int, int]:
    try:
        result = tuple(int(_clamp(float(channel), 0, 255)) for channel in value)
    except (TypeError, ValueError):
        result = ()
    return result if len(result) == 3 else tuple(fallback)


def _pair(value: Any, fallback: Any) -> tuple[float, float]:
    try:
        result = tuple(float(channel) for channel in value)
    except (TypeError, ValueError):
        result = ()
    return result if len(result) == 2 else tuple(fallback)


def _shade(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(int(_clamp(channel * amount, 0, 255)) for channel in color)


def _mix(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
    amount: float,
) -> tuple[int, int, int]:
    amount = _clamp(amount, 0, 1)
    return tuple(
        int(first[index] * (1 - amount) + second[index] * amount)
        for index in range(3)
    )


def _ruby_config() -> dict[str, Any]:
    """Load material and color data from the Ruby companion when available."""
    config = {
        **DEFAULT_CONFIG,
        "materials": {
            name: dict(values)
            for name, values in DEFAULT_CONFIG["materials"].items()
        },
    }
    ruby_path = Path(__file__).with_suffix(".rb")
    if not ruby_path.exists():
        return config
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            ["ruby", str(ruby_path)],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=flags,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return config
        manifest = json.loads(completed.stdout.strip().splitlines()[-1])
        supplied = manifest.get("physics_3d", {})
        if not isinstance(supplied, dict):
            return config
        if supplied.get("badge"):
            config["badge"] = str(supplied["badge"])[:24]
        for key in ("accent", "secondary", "hot", "shadow", "grid"):
            config[key] = list(_rgb(supplied.get(key), config[key]))
        config["extrusion"] = list(
            _pair(supplied.get("extrusion"), config["extrusion"])
        )
        materials = supplied.get("materials", {})
        if isinstance(materials, dict):
            for name, values in materials.items():
                if isinstance(values, dict):
                    config["materials"][str(name)[:30]] = dict(values)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return config


def _find_game_module():
    for module_name in ("__main__", "the_cube_beta_summer"):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "GameApp"):
            return module
    return None


CONFIG = _ruby_config()

RUNTIME: dict[str, Any] = {
    "enabled": True,
    "depth_scale": 1.0,
    "world": None,
    "event": "",
    "event_color": _rgb(CONFIG["accent"], (89, 238, 255)),
    "trails": {},
    "waves": [],
}


def _material(name: str) -> dict[str, float]:
    raw = CONFIG.get("materials", {}).get(name, {})
    if not isinstance(raw, dict):
        raw = {}
    return {
        "elasticity": _clamp(float(raw.get("elasticity", 0.68)), 0.05, 1.2),
        "friction": _clamp(float(raw.get("friction", 0.58)), 0.05, 1.2),
        "drag": _clamp(float(raw.get("drag", 0.995)), 0.94, 1.0),
        "glow": _clamp(float(raw.get("glow", 0.55)), 0.0, 1.0),
    }


def _active_world():
    reference = RUNTIME.get("world")
    if isinstance(reference, weakref.ReferenceType):
        return reference()
    return None


def _wave(
    point: tuple[float, float],
    color: tuple[int, int, int],
    kind: str = "blast",
) -> None:
    RUNTIME["waves"].append(
        {
            "x": float(point[0]),
            "y": float(point[1]),
            "at": time.monotonic(),
            "color": color,
            "kind": kind,
        }
    )
    RUNTIME["waves"] = RUNTIME["waves"][-12:]


def _install_physics(game) -> None:
    world_class = game.PhysicsWorld
    event_class = game.SummerEventController
    if getattr(world_class, "_physics_3d_installed", False):
        return

    pymunk = sys.modules.get("pymunk")
    if pymunk is None:
        return

    original_init = world_class.__init__
    original_spawn = world_class.spawn
    original_burst = world_class.burst
    original_update = world_class.update
    original_snapshot = world_class.snapshot
    original_end_drag = world_class.end_drag
    original_clear = world_class.clear
    original_event_trigger = event_class.trigger
    original_event_update = event_class.update

    def world_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._physics_3d_time = 0.0
        self._physics_3d_event = ""
        RUNTIME["world"] = weakref.ref(self)

    def spawn(self, *args, **kwargs):
        entity = original_spawn(self, *args, **kwargs)
        material = _material(entity.spec.name)
        entity.shape.elasticity = material["elasticity"]
        entity.shape.friction = material["friction"]
        entity._physics_3d_drag = material["drag"]
        entity._physics_3d_glow = material["glow"]
        entity.body.angular_velocity += random.uniform(-2.4, 2.4)
        return entity

    def burst(self, point):
        original_burst(self, point)
        origin = pymunk.Vec2d(float(point[0]), float(point[1]))
        for entity in self.entities.values():
            offset = entity.body.position - origin
            distance = max(1.0, offset.length)
            if distance >= 285:
                continue
            amount = (285 - distance) / 285
            sideways = -1 if offset.x < 0 else 1
            entity.body.angular_velocity += sideways * amount * 8.0
            entity.body.apply_impulse_at_world_point(
                (0, -amount * 520 * entity.body.mass),
                entity.body.position,
            )
        _wave(point, _rgb(CONFIG["hot"], (255, 111, 72)), "blast")

    def vortex(self, point):
        origin = pymunk.Vec2d(float(point[0]), float(point[1]))
        for entity in self.entities.values():
            offset = entity.body.position - origin
            distance = max(20.0, offset.length)
            if distance >= 340:
                continue
            outward = offset.normalized() if offset.length else pymunk.Vec2d(0, -1)
            tangent = pymunk.Vec2d(-outward.y, outward.x)
            amount = (340 - distance) / 340
            impulse = (
                tangent * (1450 * amount)
                - outward * (540 * amount)
                + pymunk.Vec2d(0, -190 * amount)
            )
            entity.body.apply_impulse_at_world_point(
                impulse * entity.body.mass,
                entity.body.position,
            )
            entity.body.angular_velocity += amount * 7.5
        _wave(point, _rgb(CONFIG["secondary"], (180, 100, 255)), "vortex")

    def update(self, dt, wind=0, gravity_scale=1):
        self._physics_3d_time += float(dt)

        # Replace the rigid cursor lock with a springy grab that preserves
        # momentum, creates throw velocity, and adds a little rotational feel.
        dragging = self.dragging
        for player, (entity_id, target) in list(dragging.items()):
            entity = self.entities.get(entity_id)
            if entity is None:
                dragging.pop(player, None)
                continue
            delta = pymunk.Vec2d(float(target[0]), float(target[1])) - entity.body.position
            desired = delta * 11.5
            entity.body.velocity = entity.body.velocity * 0.58 + desired * 0.42
            entity.body.angular_velocity += _clamp(delta.x / 180, -0.8, 0.8)

        for entity in self.entities.values():
            damping = float(getattr(entity, "_physics_3d_drag", 0.995))
            frame_factor = damping ** max(0.25, float(dt) * 60)
            entity.body.velocity *= frame_factor
            entity.body.angular_velocity *= 0.998

        # Prevent the original update from replacing the spring velocity.
        self.dragging = {}
        try:
            original_update(self, dt, wind, gravity_scale)
        finally:
            self.dragging = dragging
        for player, (entity_id, _) in list(self.dragging.items()):
            if entity_id not in self.entities:
                self.dragging.pop(player, None)

    def end_drag(self, player):
        dragged = self.dragging.get(player)
        entity = self.entities.get(dragged[0]) if dragged else None
        original_end_drag(self, player)
        if entity is not None:
            entity.body.velocity *= 1.12
            entity.body.angular_velocity += _clamp(entity.body.velocity.x / 230, -3, 3)

    def snapshot(self):
        items = original_snapshot(self)
        for item in items:
            entity = self.entities.get(int(item.get("id", -1)))
            if entity is None:
                continue
            item["vx"] = round(entity.body.velocity.x, 2)
            item["vy"] = round(entity.body.velocity.y, 2)
            item["spin"] = round(entity.body.angular_velocity, 3)
            item["glow"] = round(
                float(getattr(entity, "_physics_3d_glow", 0.55)),
                2,
            )
        return items

    def clear(self):
        original_clear(self)
        RUNTIME["trails"].clear()
        RUNTIME["waves"].clear()

    def event_trigger(self, world):
        original_event_trigger(self, world)
        active = self.active or {}
        RUNTIME["event"] = str(active.get("name", ""))
        RUNTIME["event_color"] = _rgb(active.get("color"), CONFIG["accent"])
        _wave(
            (game.WIDTH / 2, game.FLOOR_Y * 0.52),
            RUNTIME["event_color"],
            "event",
        )

    def event_update(self, dt, world):
        result = original_event_update(self, dt, world)
        active = self.active or {}
        name = str(active.get("name", ""))
        world._physics_3d_event = name
        RUNTIME["event"] = name
        RUNTIME["event_color"] = _rgb(active.get("color"), CONFIG["accent"])
        if not name:
            return result

        tick = float(getattr(world, "_physics_3d_time", 0.0))
        center = pymunk.Vec2d(
            game.WIDTH / 2 + math.sin(tick * 0.72) * 155,
            game.FLOOR_Y * 0.47 + math.cos(tick * 0.9) * 62,
        )
        for entity in world.entities.values():
            offset = entity.body.position - center
            distance = max(55.0, offset.length)
            direction = offset.normalized() if offset.length else pymunk.Vec2d(0, -1)
            tangent = pymunk.Vec2d(-direction.y, direction.x)
            mass = entity.body.mass
            if name == "Zero-G Orbit":
                entity.body.apply_force_at_world_point(
                    (-direction * 520 + tangent * 620) * mass,
                    entity.body.position,
                )
            elif name == "Vortex Drive":
                strength = _clamp(390 / distance, 0.3, 2.1)
                entity.body.apply_force_at_world_point(
                    (-direction * 760 + tangent * 1120) * strength * mass,
                    entity.body.position,
                )
            elif name == "Neon Quake":
                pulse = math.sin(tick * 13)
                entity.body.apply_force_at_world_point(
                    (pulse * 1750 * mass, -abs(pulse) * 720 * mass),
                    entity.body.position,
                )
            elif name == "Gravity Lens":
                polarity = 1 if math.sin(tick * 2.2) > -0.2 else -0.58
                entity.body.apply_force_at_world_point(
                    -direction * polarity * 1050 * mass,
                    entity.body.position,
                )
        return result

    world_class.__init__ = world_init
    world_class.spawn = spawn
    world_class.burst = burst
    world_class.physics_3d_vortex = vortex
    world_class.update = update
    world_class.end_drag = end_drag
    world_class.snapshot = snapshot
    world_class.clear = clear
    event_class.trigger = event_trigger
    event_class.update = event_update
    world_class._physics_3d_installed = True


def _polygon_points(
    center: tuple[int, int],
    size: float,
    angle: float,
    sides: int,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    offset: tuple[float, float] = (0, 0),
) -> list[tuple[int, int]]:
    return [
        (
            int(
                center[0]
                + offset[0]
                + math.cos(angle - math.pi / 2 + index * math.tau / sides)
                * size
                * scale_x
            ),
            int(
                center[1]
                + offset[1]
                + math.sin(angle - math.pi / 2 + index * math.tau / sides)
                * size
                * scale_y
            ),
        )
        for index in range(sides)
    ]


def _install_renderer(game) -> None:
    game_app = game.GameApp
    if getattr(game_app, "_physics_3d_renderer_installed", False):
        return
    pygame = game.pygame
    width = int(game.WIDTH)
    height = int(game.HEIGHT)
    floor_y = int(game.FLOOR_Y)
    accent = _rgb(CONFIG["accent"], (89, 238, 255))
    secondary = _rgb(CONFIG["secondary"], (180, 100, 255))
    hot = _rgb(CONFIG["hot"], (255, 111, 72))
    shadow = _rgb(CONFIG["shadow"], (8, 19, 45))
    grid = _rgb(CONFIG["grid"], accent)
    base_extrusion = _pair(CONFIG["extrusion"], (7, 10))

    original_draw_world = game_app.draw_world
    original_hud = game_app.draw_game_hud
    original_common_events = game_app.common_events
    original_run_simulation = game_app.run_simulation

    def draw_entity_3d(self, item, mouse, dragging_id):
        center = (int(float(item["x"])), int(float(item["y"])))
        size = max(8, int(float(item["size"])))
        angle = float(item.get("a", 0))
        color = game.safe_color(item.get("color"), game.CORAL)
        owner = str(item.get("owner", "host"))
        outline = (105, 130, 255) if owner == "guest" else (244, 252, 255)
        sides = int(_clamp(float(item.get("sides", 4)), 3, 8))
        velocity_x = float(item.get("vx", 0))
        velocity_y = float(item.get("vy", 0))
        glow = _clamp(float(item.get("glow", _material(str(item.get("name", "")))["glow"])), 0, 1)
        depth = float(RUNTIME["depth_scale"])
        extrusion = (
            (base_extrusion[0] + _clamp(velocity_x / 360, -3, 3)) * depth,
            (base_extrusion[1] + _clamp(velocity_y / 650, -2, 3)) * depth,
        )
        near_floor = center[1] + size > floor_y - 14
        squash = (
            _clamp((velocity_y - 360) / 1800, 0, 0.18)
            if near_floor
            else 0
        )
        scale_x, scale_y = 1 + squash, 1 - squash
        hovered = math.dist(center, mouse) <= size + 7
        selected = item.get("id") == dragging_id
        line_width = 4 if selected else 3 if hovered else 2

        # Contact shadow and a small glow halo establish height and material.
        shadow_rect = pygame.Rect(0, 0, int(size * 1.72), max(7, int(size * 0.48)))
        shadow_rect.center = (
            center[0] + int(extrusion[0] * 0.8),
            center[1] + int(size * 0.78 + extrusion[1] * 0.65),
        )
        pygame.draw.ellipse(self.screen, _shade(shadow, 0.75), shadow_rect)
        if glow:
            glow_color = _mix(color, accent, 0.28)
            for index in range(3, 0, -1):
                pygame.draw.circle(
                    self.screen,
                    _shade(glow_color, 0.52 + index * 0.08),
                    center,
                    size + int(index * 3 * glow),
                    1,
                )

        if item.get("kind") == "circle":
            front = pygame.Rect(
                0,
                0,
                int(size * 2 * scale_x),
                int(size * 2 * scale_y),
            )
            front.center = center
            # Multiple offset layers produce a smooth cylindrical rim.
            for step in range(5, 0, -1):
                layer = front.move(
                    int(extrusion[0] * step / 5),
                    int(extrusion[1] * step / 5),
                )
                pygame.draw.ellipse(
                    self.screen,
                    _mix(_shade(color, 0.38 + step * 0.035), secondary, 0.12),
                    layer,
                )
            pygame.draw.ellipse(self.screen, color, front)
            inset = front.inflate(-max(8, size // 2), -max(8, size // 2))
            pygame.draw.ellipse(self.screen, _mix(color, (255, 255, 255), 0.18), inset)
            pygame.draw.ellipse(self.screen, outline, front, line_width)
            spoke = (
                int(center[0] + math.cos(angle) * size * 0.68),
                int(center[1] + math.sin(angle) * size * scale_y * 0.68),
            )
            pygame.draw.line(self.screen, (244, 252, 255), center, spoke, max(2, size // 8))
            pygame.draw.circle(
                self.screen,
                (255, 255, 255),
                (center[0] - size // 3, center[1] - size // 3),
                max(2, size // 8),
            )
        else:
            front_points = _polygon_points(
                center,
                size,
                angle,
                sides,
                scale_x,
                scale_y,
            )
            back_points = _polygon_points(
                center,
                size,
                angle,
                sides,
                scale_x,
                scale_y,
                extrusion,
            )
            pygame.draw.polygon(self.screen, _shade(color, 0.42), back_points)
            for index in range(sides):
                next_index = (index + 1) % sides
                face = [
                    front_points[index],
                    front_points[next_index],
                    back_points[next_index],
                    back_points[index],
                ]
                edge_x = front_points[next_index][0] - front_points[index][0]
                edge_y = front_points[next_index][1] - front_points[index][1]
                light = 0.48 + 0.18 * (
                    math.sin(math.atan2(edge_y, edge_x) + math.pi / 3) + 1
                )
                pygame.draw.polygon(
                    self.screen,
                    _mix(_shade(color, light), secondary, 0.13),
                    face,
                )
                pygame.draw.line(
                    self.screen,
                    _shade(outline, 0.65),
                    back_points[index],
                    back_points[next_index],
                    1,
                )
            pygame.draw.polygon(self.screen, color, front_points)
            inner = _polygon_points(
                center,
                size * 0.70,
                angle,
                sides,
                scale_x,
                scale_y,
            )
            pygame.draw.polygon(
                self.screen,
                _mix(color, (255, 255, 255), 0.20),
                inner,
            )
            pygame.draw.polygon(self.screen, outline, front_points, line_width)
            pygame.draw.lines(
                self.screen,
                _mix(color, (255, 255, 255), 0.48),
                True,
                inner,
                2,
            )

        if hovered or selected:
            pygame.draw.circle(
                self.screen,
                accent if selected else secondary,
                center,
                size + 9,
                2,
            )
        if hovered:
            name = str(item.get("name", "DIMENSIONAL SHAPE"))[:24].upper()
            label = self.tiny.render(name, True, (248, 252, 255))
            label_rect = label.get_rect(
                midbottom=(center[0], center[1] - size - 11)
            ).inflate(14, 7)
            pygame.draw.rect(self.screen, shadow, label_rect, border_radius=7)
            pygame.draw.rect(self.screen, accent, label_rect, 1, border_radius=7)
            self.screen.blit(label, label.get_rect(center=label_rect.center))

    def draw_grid(self, ticks):
        overlay = getattr(self, "_physics_3d_grid_surface", None)
        if overlay is None or overlay.get_size() != (width, height):
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            self._physics_3d_grid_surface = overlay
        overlay.fill((0, 0, 0, 0))
        horizon = 164
        vanishing = (width // 2, horizon)
        event_name = str(RUNTIME.get("event", ""))
        pulse = 0.5 + 0.5 * math.sin(ticks * (6 if event_name else 2))
        alpha = int(26 + pulse * (23 if event_name else 8))
        for index in range(-10, 11):
            bottom_x = width // 2 + index * 92
            pygame.draw.line(
                overlay,
                (*grid, alpha),
                vanishing,
                (bottom_x, floor_y),
                1,
            )
        scroll = (ticks * 0.28) % 1
        for index in range(13):
            fraction = (index + scroll) / 13
            y = int(horizon + (floor_y - horizon) * fraction**2.15)
            pygame.draw.line(
                overlay,
                (*grid, int(alpha * (0.35 + fraction * 0.65))),
                (0, y),
                (width, y),
                1,
            )
        self.screen.blit(overlay, (0, 0))

    def draw_fx(self, snapshot, now):
        overlay = getattr(self, "_physics_3d_fx_surface", None)
        if overlay is None or overlay.get_size() != (width, height):
            overlay = pygame.Surface((width, height), pygame.SRCALPHA)
            self._physics_3d_fx_surface = overlay
        overlay.fill((0, 0, 0, 0))
        live_ids = set()
        trails = RUNTIME["trails"]
        for item in snapshot:
            try:
                entity_id = int(item["id"])
                point = (int(float(item["x"])), int(float(item["y"])))
                color = game.safe_color(item.get("color"), accent)
            except (KeyError, TypeError, ValueError):
                continue
            live_ids.add(entity_id)
            trail = trails.setdefault(entity_id, [])
            if not trail or math.dist(point, trail[-1][0]) >= 3:
                trail.append((point, now))
            trail[:] = [
                entry for entry in trail[-14:] if now - entry[1] < 0.72
            ]
            for index in range(1, len(trail)):
                age = now - trail[index][1]
                trail_alpha = int(95 * max(0, 1 - age / 0.72))
                pygame.draw.line(
                    overlay,
                    (*_mix(color, accent, 0.25), trail_alpha),
                    trail[index - 1][0],
                    trail[index][0],
                    max(1, int(5 - age * 5)),
                )
        for entity_id in list(trails):
            if entity_id not in live_ids:
                trails.pop(entity_id, None)

        kept_waves = []
        for wave in RUNTIME["waves"]:
            age = now - float(wave["at"])
            limit = 1.15 if wave["kind"] == "event" else 0.82
            if age >= limit:
                continue
            kept_waves.append(wave)
            progress = age / limit
            radius = int(24 + progress * (430 if wave["kind"] == "event" else 300))
            wave_color = _rgb(wave["color"], accent)
            wave_alpha = int(210 * (1 - progress))
            pygame.draw.circle(
                overlay,
                (*wave_color, wave_alpha),
                (int(wave["x"]), int(wave["y"])),
                radius,
                max(1, int(6 * (1 - progress))),
            )
            if wave["kind"] == "vortex":
                pygame.draw.circle(
                    overlay,
                    (*secondary, wave_alpha // 2),
                    (int(wave["x"]), int(wave["y"])),
                    max(5, radius - 18),
                    2,
                )
        RUNTIME["waves"] = kept_waves
        self.screen.blit(overlay, (0, 0))

    def draw_world(self, snapshot, mouse, dragging_id):
        if not RUNTIME["enabled"]:
            return original_draw_world(self, snapshot, mouse, dragging_id)
        ticks = pygame.time.get_ticks() / 1000
        now = time.monotonic()
        draw_grid(self, ticks)
        draw_fx(self, snapshot, now)
        for item in sorted(
            snapshot,
            key=lambda entry: (
                float(entry.get("y", 0)),
                int(entry.get("id", 0)),
            ),
        ):
            try:
                draw_entity_3d(self, item, mouse, dragging_id)
            except (KeyError, TypeError, ValueError, pygame.error):
                continue
        if dragging_id:
            selected = next(
                (
                    item
                    for item in snapshot
                    if int(item.get("id", -1)) == int(dragging_id)
                ),
                None,
            )
            if selected:
                start = (int(float(selected["x"])), int(float(selected["y"])))
                pygame.draw.line(self.screen, secondary, start, mouse, 3)
                pygame.draw.circle(self.screen, accent, mouse, 8, 2)
        pygame.draw.line(
            self.screen,
            _mix((255, 240, 191), accent, 0.32),
            (0, floor_y),
            (width, floor_y),
            4,
        )

    def draw_game_hud(
        self,
        shape_count,
        energy,
        event,
        peer,
        is_host,
        paused,
        clear_rect,
        menu_rect,
    ):
        RUNTIME["event"] = str(event.get("name", RUNTIME.get("event", "")))
        RUNTIME["event_color"] = _rgb(event.get("color"), accent)
        original_hud(
            self,
            shape_count,
            energy,
            event,
            peer,
            is_host,
            paused,
            clear_rect,
            menu_rect,
        )
        panel_rect = pygame.Rect(14, 77, 226, 78)
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel.fill((*shadow, 232))
        pygame.draw.rect(
            panel,
            (*accent, 245),
            panel.get_rect(),
            2,
            border_radius=13,
        )
        self.screen.blit(panel, panel_rect)
        status = "ON" if RUNTIME["enabled"] else "BYPASS"
        title = self.small.render(
            f"{CONFIG['badge']}  //  {status}",
            True,
            (248, 252, 255),
        )
        self.screen.blit(title, (panel_rect.x + 11, panel_rect.y + 8))
        scale = self.tiny.render(
            f"DEPTH {RUNTIME['depth_scale']:.1f}x   D: VIEW   WHEEL: DEPTH",
            True,
            accent,
        )
        controls = self.tiny.render(
            "RMB: SHOCKWAVE   MMB / V: VORTEX",
            True,
            (196, 214, 232),
        )
        self.screen.blit(scale, (panel_rect.x + 11, panel_rect.y + 32))
        self.screen.blit(controls, (panel_rect.x + 11, panel_rect.y + 52))

    def common_events(self, events):
        if getattr(self, "_physics_3d_in_simulation", False):
            for event in list(events):
                if event.type == pygame.KEYDOWN and event.key == pygame.K_d:
                    RUNTIME["enabled"] = not RUNTIME["enabled"]
                    self.notify(
                        f"Physics 3D renderer: {'ON' if RUNTIME['enabled'] else 'BYPASS'}",
                        2,
                    )
                elif event.type == pygame.MOUSEWHEEL:
                    RUNTIME["depth_scale"] = _clamp(
                        float(RUNTIME["depth_scale"]) + event.y * 0.1,
                        0.4,
                        1.8,
                    )
                elif (
                    event.type == pygame.KEYDOWN
                    and event.key == pygame.K_v
                ) or (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 2
                ):
                    world = _active_world()
                    if world is not None:
                        world.physics_3d_vortex(pygame.mouse.get_pos())
                        self.play_click()
                        self.notify("Dimensional vortex launched!", 1.5)
                    else:
                        self.notify("Vortex controls are available to the host.", 2)
        return original_common_events(self, events)

    def run_simulation(self, *args, **kwargs):
        self._physics_3d_in_simulation = True
        RUNTIME["trails"].clear()
        RUNTIME["waves"].clear()
        try:
            return original_run_simulation(self, *args, **kwargs)
        finally:
            self._physics_3d_in_simulation = False
            RUNTIME["world"] = None
            RUNTIME["event"] = ""

    game_app.draw_entity = draw_entity_3d
    game_app.draw_world = draw_world
    game_app.draw_game_hud = draw_game_hud
    game_app.common_events = common_events
    game_app.run_simulation = run_simulation
    game_app._physics_3d_renderer_installed = True


def _install() -> None:
    game = _find_game_module()
    if game is None:
        return
    try:
        _install_physics(game)
        _install_renderer(game)
    except (AttributeError, TypeError):
        # A future game build can still load this add-on's normal shapes and
        # events even if an internal optional extension hook has moved.
        return


_install()


def register(api):
    api.about(
        name="Physics 3D: Interactive Dimension",
        version="1.0.0",
        author="Cube Labs",
        description=(
            "Adds extruded 3D rendering, trails, material physics, elastic "
            "grabbing, shockwaves, vortex controls, and dimensional events."
        ),
    )
    api.shape(
        name="Glass D8",
        kind="polygon",
        sides=8,
        size=34,
        color=(78, 210, 255),
        weight=0.9,
    )
    api.shape(
        name="Flux Ring",
        kind="circle",
        size=31,
        color=(224, 91, 255),
        weight=0.85,
    )
    api.event(
        name="Gravity Lens",
        duration=10,
        wind=0,
        gravity_scale=0.18,
        spawn_count=8,
        banner="A pulsing gravity lens bends every trajectory through the lab!",
        color=(119, 102, 255),
    )
    api.event(
        name="Kinetic Rain",
        duration=7,
        wind=360,
        gravity_scale=0.72,
        spawn_count=14,
        banner="Dimensional shapes streak in with bright motion trails!",
        color=(72, 232, 255),
    )
