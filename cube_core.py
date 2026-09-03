"""Core physics, networking, settings, and add-on support for The Cube Beta."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import queue
import random
import shutil
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymunk

from cpe import CPEBridgeRuntime, CubePhysicsEngine, NumericCommand


APP_TITLE = "The Cube Beta Fall Edition"
VERSION = "6.2.2"
WIDTH, HEIGHT = 1100, 720
FLOOR_Y = HEIGHT - 54
FPS = 60
DEFAULT_PORT = 50505
FALL_START_UTC = datetime(2026, 9, 23, 0, 5, tzinfo=timezone.utc)

WHITE = (248, 252, 255)
INK = (18, 43, 66)
MUTED = (80, 111, 128)
NAVY = (13, 48, 78)
CORAL = (255, 100, 92)
YELLOW = (255, 211, 92)
MINT = (80, 214, 172)
SKY = (80, 187, 238)

FALL_PALETTE = [
    (187, 62, 38),
    (222, 108, 39),
    (240, 156, 49),
    (250, 198, 72),
    (145, 92, 48),
    (128, 52, 39),
    (102, 122, 58),
]

# Backward-compatible alias for existing add-ons that imported the old name.
SUMMER_PALETTE = FALL_PALETTE

THEMES = {
    "maple": {
        "sky_top": (72, 126, 158),
        "sky_bottom": (244, 184, 115),
        "water": (104, 113, 71),
        "sand": (112, 70, 42),
        "sun": (255, 198, 92),
    },
    "harvest": {
        "sky_top": (128, 83, 112),
        "sky_bottom": (245, 148, 79),
        "water": (126, 101, 55),
        "sand": (91, 57, 35),
        "sun": (255, 190, 85),
    },
    "twilight": {
        "sky_top": (34, 42, 73),
        "sky_bottom": (128, 76, 72),
        "water": (64, 76, 58),
        "sand": (66, 45, 38),
        "sun": (238, 214, 174),
    },
}

DEFAULT_SETTINGS = {
    "theme": "maple",
    "gravity": 900,
    "fullscreen": False,
    "music": True,
    "sound": True,
    "event_interval": 18,
}


def fall_countdown(now: datetime | None = None) -> tuple[str, int]:
    """Return a live countdown to the 2026 September equinox."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    remaining = max(0, int((FALL_START_UTC - current.astimezone(timezone.utc)).total_seconds()))
    if remaining == 0:
        return "FALL IS HERE!", 0
    days, remainder = divmod(remaining, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days:02d}D  {hours:02d}H  {minutes:02d}M  {seconds:02d}S", remaining


def bundle_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / name


def app_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


SETTINGS_FILE = app_path() / "settings.json"
ADDONS_DIR = app_path() / "addons"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_color(value: Any, fallback: tuple[int, int, int] = CORAL) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return fallback
    try:
        return tuple(int(clamp(float(channel), 0, 255)) for channel in value)
    except (TypeError, ValueError):
        return fallback


def save_settings(settings: dict[str, Any]) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_settings() -> dict[str, Any]:
    data: dict[str, Any] = {}
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = DEFAULT_SETTINGS | {k: v for k, v in data.items() if k in DEFAULT_SETTINGS}
    if merged["theme"] not in THEMES:
        merged["theme"] = DEFAULT_SETTINGS["theme"]
    merged["gravity"] = int(clamp(float(merged["gravity"]), 150, 2200))
    merged["event_interval"] = int(clamp(float(merged["event_interval"]), 8, 60))
    save_settings(merged)
    return merged


@dataclass
class ShapeSpec:
    name: str
    kind: str = "polygon"
    sides: int = 4
    size: float = 30
    color: tuple[int, int, int] | None = None
    weight: float = 1.0


@dataclass
class Entity:
    entity_id: int
    body: pymunk.Body
    shape: pymunk.Shape
    spec: ShapeSpec
    color: tuple[int, int, int]
    owner: str = "host"


@dataclass
class AddonRecord:
    filename: str
    name: str
    version: str
    author: str
    description: str
    language: str
    ok: bool
    detail: str = ""


class AddonBuilder:
    """Small API exposed to Python add-ons."""

    def __init__(self, filename: str):
        self.manifest: dict[str, Any] = {
            "name": Path(filename).stem.replace("_", " ").title(),
            "version": "1.0",
            "author": "Unknown creator",
            "description": "A community add-on",
            "shapes": [],
            "events": [],
        }

    def about(
        self,
        name: str,
        version: str = "1.0",
        author: str = "Unknown creator",
        description: str = "",
    ) -> None:
        self.manifest.update(
            name=str(name),
            version=str(version),
            author=str(author),
            description=str(description),
        )

    def shape(
        self,
        name: str,
        sides: int = 5,
        size: int = 30,
        color: tuple[int, int, int] = CORAL,
        weight: float = 1.0,
        kind: str = "polygon",
    ) -> None:
        self.manifest["shapes"].append(
            {
                "name": name,
                "kind": kind,
                "sides": sides,
                "size": size,
                "color": list(color),
                "weight": weight,
            }
        )

    def event(
        self,
        name: str,
        duration: float = 7,
        wind: float = 0,
        gravity_scale: float = 1,
        spawn_count: int = 0,
        banner: str = "",
        color: tuple[int, int, int] = YELLOW,
    ) -> None:
        self.manifest["events"].append(
            {
                "name": name,
                "duration": duration,
                "wind": wind,
                "gravity_scale": gravity_scale,
                "spawn_count": spawn_count,
                "banner": banner,
                "color": list(color),
            }
        )


class AddonManager:
    def __init__(self, directory: Path = ADDONS_DIR):
        self.directory = directory
        self.records: list[AddonRecord] = []
        self.shapes: list[ShapeSpec] = []
        self.events: list[dict[str, Any]] = []
        self.last_message = ""
        self._ensure_folder()
        self.reload()

    def _ensure_folder(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        packaged = bundle_path("addons")
        if packaged.resolve() == self.directory.resolve() or not packaged.exists():
            return
        for source in packaged.rglob("*"):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            destination = self.directory / source.relative_to(packaged)
            if not destination.exists():
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                except OSError:
                    pass

    def reload(self) -> None:
        self.records.clear()
        self.shapes.clear()
        self.events.clear()
        for path in sorted(self.directory.iterdir()):
            if path.suffix.lower() not in {".py", ".rb"} or path.name.startswith("_"):
                continue
            try:
                manifest = self._load_python(path) if path.suffix.lower() == ".py" else self._load_ruby(path)
                self._accept_manifest(path, manifest)
            except Exception as exc:
                self.records.append(
                    AddonRecord(
                        path.name,
                        path.stem,
                        "â€”",
                        "â€”",
                        "Could not load",
                        path.suffix[1:].upper(),
                        False,
                        str(exc)[:110],
                    )
                )
        good = sum(record.ok for record in self.records)
        self.last_message = f"Loaded {good} of {len(self.records)} add-ons"

    def _load_python(self, path: Path) -> dict[str, Any]:
        module_name = f"cube_addon_{path.stem}_{path.stat().st_mtime_ns}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ValueError("Python could not open this add-on")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        builder = AddonBuilder(path.name)
        if hasattr(module, "register"):
            result = module.register(builder)
            if isinstance(result, dict):
                builder.manifest.update(result)
            return builder.manifest
        manifest = getattr(module, "ADDON", None)
        if not isinstance(manifest, dict):
            raise ValueError("Add register(api) or an ADDON dictionary")
        return manifest

    def _load_ruby(self, path: Path) -> dict[str, Any]:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            ["ruby", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=flags,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError((completed.stderr or "Ruby returned an error").strip())
        output = completed.stdout.strip()
        if not output:
            raise ValueError("Ruby add-on did not print its JSON manifest")
        try:
            return json.loads(output.splitlines()[-1])
        except json.JSONDecodeError as exc:
            raise ValueError("Last output line must be a JSON manifest") from exc

    def _accept_manifest(self, path: Path, manifest: dict[str, Any]) -> None:
        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be a dictionary/object")
        name = str(manifest.get("name") or path.stem)[:40]
        author = str(manifest.get("author") or "Unknown creator")[:40]
        version = str(manifest.get("version") or "1.0")[:16]
        description = str(manifest.get("description") or "A community add-on")[:100]
        for raw in manifest.get("shapes", [])[:20]:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("kind", "polygon")).lower()
            if kind not in {"polygon", "circle"}:
                kind = "polygon"
            self.shapes.append(
                ShapeSpec(
                    name=str(raw.get("name", "Addon shape"))[:30],
                    kind=kind,
                    sides=int(clamp(float(raw.get("sides", 5)), 3, 8)),
                    size=clamp(float(raw.get("size", 30)), 15, 58),
                    color=safe_color(raw.get("color"), random.choice(FALL_PALETTE)),
                    weight=clamp(float(raw.get("weight", 1)), 0.1, 10),
                )
            )
        for raw in manifest.get("events", [])[:12]:
            if not isinstance(raw, dict):
                continue
            self.events.append(
                {
                    "name": str(raw.get("name", "Addon event"))[:35],
                    "duration": clamp(float(raw.get("duration", 7)), 2, 20),
                    "wind": clamp(float(raw.get("wind", 0)), -1600, 1600),
                    "gravity_scale": clamp(float(raw.get("gravity_scale", 1)), -0.5, 2.5),
                    "spawn_count": int(clamp(float(raw.get("spawn_count", 0)), 0, 30)),
                    "banner": str(raw.get("banner", ""))[:80],
                    "color": safe_color(raw.get("color"), YELLOW),
                }
            )
        self.records.append(
            AddonRecord(
                path.name,
                name,
                version,
                author,
                description,
                path.suffix[1:].upper(),
                True,
            )
        )

    def install(self, source_name: str) -> tuple[bool, str]:
        source = Path(source_name)
        if source.suffix.lower() not in {".py", ".rb"}:
            return False, "Drop a .py or .rb add-on file"
        try:
            destination = self.directory / source.name
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            self.reload()
            record = next((r for r in self.records if r.filename == source.name), None)
            if record and record.ok:
                return True, f"{record.name} is ready!"
            return False, record.detail if record else "The add-on could not be loaded"
        except OSError as exc:
            return False, f"Could not copy add-on: {exc}"


BUILTIN_SHAPES = [
    ShapeSpec("Apple", "circle", 0, 28, None, 1.35),
    ShapeSpec("Maple block", "polygon", 4, 29, None, 1.1),
    ShapeSpec("Leaf triangle", "polygon", 3, 34, None, 0.9),
    ShapeSpec("Amber diamond", "polygon", 4, 31, None, 0.75),
    ShapeSpec("Harvest star", "polygon", 5, 31, None, 0.8),
    ShapeSpec("Acorn hex", "polygon", 6, 30, None, 0.75),
]


def regular_vertices(sides: int, radius: float, diamond: bool = False) -> list[tuple[float, float]]:
    offset = 0 if diamond else -math.pi / 2
    return [
        (
            math.cos(offset + index * math.tau / sides) * radius,
            math.sin(offset + index * math.tau / sides) * radius,
        )
        for index in range(sides)
    ]


class PhysicsWorld:
    def __init__(self, gravity: int, addons: AddonManager):
        self.addons = addons
        self.base_gravity = gravity
        self.base_gravity_x = 0.0
        self.cpe = CubePhysicsEngine(
            WIDTH,
            HEIGHT,
            (0, gravity),
            floor_y=FLOOR_Y,
            boundary_friction=0.95,
            boundary_elasticity=0.35,
        )
        self.space = self.cpe.space
        self.bridge = CPEBridgeRuntime()
        self.entities: dict[int, Entity] = {}
        self.next_id = 1
        self.dragging: dict[str, tuple[int, tuple[float, float]]] = {}
        self._cache_elapsed = 0.0

    def _make_boundaries(self) -> None:
        floor = pymunk.Segment(self.space.static_body, (0, FLOOR_Y), (WIDTH, FLOOR_Y), 6)
        left = pymunk.Segment(self.space.static_body, (2, 0), (2, FLOOR_Y), 6)
        right = pymunk.Segment(self.space.static_body, (WIDTH - 2, 0), (WIDTH - 2, FLOOR_Y), 6)
        for boundary in (floor, left, right):
            boundary.friction = 0.95
            boundary.elasticity = 0.35
        self.space.add(floor, left, right)

    def random_spec(self) -> ShapeSpec:
        pool = BUILTIN_SHAPES + self.addons.shapes
        return random.choices(pool, weights=[item.weight for item in pool], k=1)[0]

    def spawn(
        self,
        x: float,
        y: float,
        owner: str = "host",
        spec: ShapeSpec | None = None,
        color: tuple[int, int, int] | None = None,
    ) -> Entity:
        if len(self.entities) >= 180:
            self.remove(min(self.entities))
        spec = spec or self.random_spec()
        x = clamp(x, 25, WIDTH - 25)
        y = clamp(y, 80, FLOOR_Y - 25)
        size = float(spec.size) * random.uniform(0.82, 1.16)
        mass = clamp(size / 22, 0.7, 3.4)
        chosen = color or spec.color or random.choice(FALL_PALETTE)
        if spec.kind == "circle":
            moment = pymunk.moment_for_circle(mass, 0, size)
            body = pymunk.Body(mass, moment)
            shape: pymunk.Shape = pymunk.Circle(body, size)
        else:
            vertices = regular_vertices(spec.sides, size, spec.name.lower().endswith("diamond"))
            moment = pymunk.moment_for_poly(mass, vertices)
            body = pymunk.Body(mass, moment)
            shape = pymunk.Poly(body, vertices)
        body.position = (x, y)
        body.angle = random.uniform(-math.pi, math.pi)
        shape.friction = random.uniform(0.55, 0.92)
        shape.elasticity = random.uniform(0.35, 0.78)
        self.space.add(body, shape)
        entity = Entity(self.next_id, body, shape, ShapeSpec(spec.name, spec.kind, spec.sides, size), chosen, owner)
        self.entities[entity.entity_id] = entity
        self.cpe.register_body(
            entity.entity_id,
            spec.kind,
            body,
            shape,
            chosen,
            size,
            sides=spec.sides,
        )
        self.next_id += 1
        return entity

    def remove(self, entity_id: int) -> None:
        entity = self.entities.pop(entity_id, None)
        if entity:
            try:
                if not self.cpe.remove(entity_id):
                    self.space.remove(entity.shape, entity.body)
            except Exception:
                pass

    def clear(self) -> None:
        for entity_id in list(self.entities):
            self.remove(entity_id)
        self.dragging.clear()
        self.cpe.particles.clear()

    def entity_at(self, point: tuple[float, float]) -> Entity | None:
        nearest: Entity | None = None
        nearest_distance = 10_000.0
        for entity in self.entities.values():
            distance = entity.shape.point_query(point).distance
            if distance <= 7 and distance < nearest_distance:
                nearest, nearest_distance = entity, distance
        return nearest

    def begin_drag(self, player: str, point: tuple[float, float], entity_id: int | None = None) -> int | None:
        entity = self.entities.get(entity_id) if entity_id else self.entity_at(point)
        if not entity:
            return None
        self.dragging[player] = (entity.entity_id, point)
        entity.body.activate()
        return entity.entity_id

    def move_drag(self, player: str, point: tuple[float, float]) -> None:
        if player in self.dragging:
            entity_id, _ = self.dragging[player]
            self.dragging[player] = (entity_id, point)

    def end_drag(self, player: str) -> None:
        self.dragging.pop(player, None)

    def burst(self, point: tuple[float, float]) -> None:
        origin = pymunk.Vec2d(float(point[0]), float(point[1]))
        self.cpe.particles.emit(origin.x, origin.y, 54, 420, 1.15, (250, 198, 72), 5)
        for entity in self.entities.values():
            offset = entity.body.position - origin
            distance = max(30, offset.length)
            if distance < 230:
                direction = offset.normalized() if offset.length > 0 else pymunk.Vec2d(0, -1)
                strength = (235 - distance) * 17
                entity.body.apply_impulse_at_world_point(direction * strength, entity.body.position)

    def _apply_cpe_command(self, command: NumericCommand) -> None:
        values = command.values
        if command.opcode in {1, 2}:
            x, y, size, _mass, red, green, blue = values
            kind = "polygon" if command.opcode == 1 else "circle"
            name = "CPE Box" if command.opcode == 1 else "CPE Circle"
            sides = 4 if command.opcode == 1 else 8
            self.spawn(x, y, owner="cpe-java", spec=ShapeSpec(name, kind, sides, size), color=(int(red), int(green), int(blue)))
        elif command.opcode == 3:
            x, y, sides, size, _mass, red, green, blue = values
            self.spawn(
                x,
                y,
                owner="cpe-java",
                spec=ShapeSpec("CPE Polygon", "polygon", int(sides), size),
                color=(int(red), int(green), int(blue)),
            )
        elif command.opcode == 10:
            self.base_gravity_x = float(values[0])
            self.base_gravity = float(values[1])
        elif command.opcode in {11, 12}:
            entity = self.entities.get(int(values[0]))
            if entity is not None:
                vector = pymunk.Vec2d(values[1], values[2])
                if command.opcode == 11:
                    entity.body.apply_impulse_at_local_point(vector)
                else:
                    entity.body.apply_force_at_local_point(vector)
        elif command.opcode == 20:
            x, y, count, speed, lifetime, red, green, blue = values
            self.cpe.particles.emit(x, y, int(count), speed, lifetime, (int(red), int(green), int(blue)), 5)
        elif command.opcode == 30:
            self.clear()
        elif command.opcode == 40:
            self.cpe.paused = bool(values[0])

    def process_cpe_commands(self) -> int:
        commands = self.bridge.drain_commands()
        for command in commands:
            self._apply_cpe_command(command)
        return len(commands)

    def _publish_cpe_cache(self, dt: float) -> None:
        self._cache_elapsed += max(0.0, float(dt))
        if self._cache_elapsed < 0.2:
            return
        self._cache_elapsed = 0.0
        self.bridge.publish_cache(self.cache_snapshot())

    def update(self, dt: float, wind: float = 0, gravity_scale: float = 1) -> None:
        self.process_cpe_commands()
        self.space.gravity = (self.base_gravity_x, self.base_gravity * gravity_scale)
        if self.cpe.paused:
            self.cpe.step(dt)
            self._publish_cpe_cache(dt)
            return
        for player, (entity_id, target) in list(self.dragging.items()):
            entity = self.entities.get(entity_id)
            if not entity:
                self.dragging.pop(player, None)
                continue
            delta = pymunk.Vec2d(float(target[0]), float(target[1])) - entity.body.position
            entity.body.velocity = delta * 15
            entity.body.angular_velocity *= 0.86
        if wind:
            for entity in self.entities.values():
                entity.body.apply_force_at_world_point((wind * entity.body.mass, 0), entity.body.position)
        self.cpe.step(dt)
        for entity_id, entity in list(self.entities.items()):
            x, y = entity.body.position
            if y > HEIGHT + 200 or x < -250 or x > WIDTH + 250:
                self.remove(entity_id)
        self._publish_cpe_cache(dt)

    def particle_snapshot(self) -> list[dict[str, Any]]:
        return self.cpe.particle_snapshot()

    def cache_snapshot(self) -> dict[str, Any]:
        particles = self.particle_snapshot()
        return {
            "engine": "CPE",
            "protocol": "CPE/1",
            "bodies": self.snapshot(),
            "particles": particles,
            "particle_count": len(particles),
            "gravity": [round(self.space.gravity.x, 3), round(self.space.gravity.y, 3)],
            "paused": self.cpe.paused,
            "bridge": self.bridge.status(),
        }

    def cpe_status(self) -> dict[str, Any]:
        return self.bridge.status()

    def close(self) -> None:
        self.bridge.close()

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "id": entity.entity_id,
                "x": round(entity.body.position.x, 2),
                "y": round(entity.body.position.y, 2),
                "a": round(entity.body.angle, 3),
                "name": entity.spec.name,
                "kind": entity.spec.kind,
                "sides": entity.spec.sides,
                "size": round(entity.spec.size, 2),
                "color": list(entity.color),
                "owner": entity.owner,
            }
            for entity in self.entities.values()
        ]


BUILTIN_EVENTS = [
    {
        "name": "Autumn Gust",
        "duration": 8,
        "wind": 620,
        "gravity_scale": 1,
        "spawn_count": 0,
        "banner": "A crisp autumn gust pushes everything east!",
        "color": (222, 108, 39),
    },
    {
        "name": "Harvest Moon Gravity",
        "duration": 8,
        "wind": 0,
        "gravity_scale": 0.28,
        "spawn_count": 5,
        "banner": "The harvest moon makes everything feel lighter.",
        "color": (250, 198, 72),
    },
    {
        "name": "Leaf Shower",
        "duration": 6,
        "wind": -180,
        "gravity_scale": 0.78,
        "spawn_count": 14,
        "banner": "A cascade of colorful leaves is falling!",
        "color": (240, 156, 49),
    },
    {
        "name": "Pumpkin Roll",
        "duration": 7,
        "wind": -820,
        "gravity_scale": 1.1,
        "spawn_count": 3,
        "banner": "A rolling harvest wind sweeps across the sandbox.",
        "color": (187, 62, 38),
    },
]


class FallEventController:
    def __init__(self, interval: int, addons: AddonManager):
        self.interval = interval
        self.addons = addons
        self.elapsed = 0.0
        self.next_event = float(interval)
        self.active: dict[str, Any] | None = None
        self.remaining = 0.0
        self.last_name = ""

    def trigger(self, world: PhysicsWorld) -> None:
        choices = BUILTIN_EVENTS + self.addons.events
        filtered = [event for event in choices if event["name"] != self.last_name] or choices
        event = dict(random.choice(filtered))
        self.active = event
        self.remaining = float(event["duration"])
        self.elapsed = 0
        self.next_event = self.interval + random.uniform(-3, 4)
        self.last_name = event["name"]
        for index in range(int(event["spawn_count"])):
            x = 60 + (index * 79) % (WIDTH - 120)
            world.spawn(x, random.randint(85, 160), owner="fall")

    def update(self, dt: float, world: PhysicsWorld) -> tuple[float, float]:
        self.elapsed += dt
        if self.active:
            self.remaining -= dt
            if self.remaining <= 0:
                self.active = None
                self.remaining = 0
        elif self.elapsed >= self.next_event:
            self.trigger(world)
        if self.active:
            return float(self.active["wind"]), float(self.active["gravity_scale"])
        return 0, 1

    def state(self) -> dict[str, Any]:
        if self.active:
            return {
                "name": self.active["name"],
                "banner": self.active["banner"],
                "color": list(self.active["color"]),
                "remaining": round(self.remaining, 1),
                "next": 0,
            }
        return {
            "name": "",
            "banner": "",
            "color": list(YELLOW),
            "remaining": 0,
            "next": max(0, round(self.next_event - self.elapsed, 1)),
        }


# Backward-compatible name for add-ons and older scripts.
SummerEventController = FallEventController


class NetworkPeer:
    def __init__(self, role: str, host: str = "", port: int = DEFAULT_PORT):
        self.role = role
        self.host = host
        self.port = port
        self.inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self.connected = False
        self.status = "Startingâ€¦"
        self.error = ""
        self._server: socket.socket | None = None
        self._conn: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            if self.role == "host":
                self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._server.bind(("", self.port))
                self._server.listen(1)
                self._server.settimeout(0.5)
                self.status = f"Waiting on port {self.port}"
                while not self._stop.is_set():
                    try:
                        self._conn, address = self._server.accept()
                        self.status = f"Guest joined from {address[0]}"
                        break
                    except socket.timeout:
                        continue
            else:
                self.status = f"Connecting to {self.host}:{self.port}"
                self._conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._conn.settimeout(6)
                self._conn.connect((self.host, self.port))
                self.status = "Connected to host"
            if not self._conn:
                return
            self.connected = True
            self._conn.settimeout(0.5)
            buffer = b""
            while not self._stop.is_set():
                try:
                    chunk = self._conn.recv(65536)
                    if not chunk:
                        raise ConnectionError("The other player left")
                    buffer += chunk
                    while b"\n" in buffer:
                        raw, buffer = buffer.split(b"\n", 1)
                        if raw:
                            message = json.loads(raw.decode("utf-8"))
                            if isinstance(message, dict):
                                self.inbox.put(message)
                except socket.timeout:
                    continue
        except Exception as exc:
            if not self._stop.is_set():
                self.error = str(exc)
                self.status = f"Connection ended: {exc}"
        finally:
            self.connected = False

    def send(self, message: dict[str, Any]) -> None:
        if not self.connected or not self._conn:
            return
        packet = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with self._send_lock:
                self._conn.sendall(packet)
        except OSError as exc:
            self.error = str(exc)
            self.connected = False

    def messages(self) -> list[dict[str, Any]]:
        output = []
        while True:
            try:
                output.append(self.inbox.get_nowait())
            except queue.Empty:
                return output

    def close(self) -> None:
        self._stop.set()
        for sock in (self._conn, self._server):
            if sock:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    sock.close()
                except OSError:
                    pass


def local_ip() -> str:
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
        return next((address for address in addresses if not address.startswith("127.")), "127.0.0.1")
    except OSError:
        return "127.0.0.1"
