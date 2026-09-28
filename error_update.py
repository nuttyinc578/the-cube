"""The Cube Beta 6.3 Error Update presentation and CPE recovery system.

The blue-screen errors are an intentional game theme.  The repair action is
real: it verifies CPE, restores the packaged bridge files, runs a physics and
particle self-test, creates backups, and persists the repaired state.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType
from typing import Any

import pygame

from cpe import CubePhysicsEngine, __version__ as CPE_VERSION
from cube_core import FPS, HEIGHT, VERSION, WIDTH, app_path, bundle_path


ERROR_CODE = "21CPE"
ERROR_SLOGAN = "WE ARE DONE / WE ARE COOKED"
ERROR_SLOGAN_COUNT = 5
EXPECTED_CPE_VERSION = "0.0.2"

REPAIR_FILES = (
    "node-bridge/package.json",
    "node-bridge/server.js",
    "go-cache/go.mod",
    "go-cache/main.go",
    "java-client/README.md",
    "java-client/src/main/java/com/nuttyinc/cpe/CpeClient.java",
    "CPE.AppHost/CPE.AppHost.csproj",
    "CPE.AppHost/Program.cs",
    "CPE.AppHost/Properties/launchSettings.json",
)

BLUE = (0, 87, 183)
DEEP_BLUE = (0, 25, 76)
CYAN = (38, 224, 255)
PALE_BLUE = (195, 239, 255)
WHITE = (247, 252, 255)
INK = (8, 28, 54)
MUTED = (116, 166, 197)
GREEN = (92, 238, 177)
RED = (255, 95, 112)


@dataclass(slots=True)
class RepairCheck:
    name: str
    ok: bool
    detail: str


@dataclass(slots=True)
class RepairReport:
    ok: bool
    checks: list[RepairCheck]
    restored_files: list[str]
    backup: str | None
    error: str | None = None


class CPERepairController:
    """Verify and transactionally restore the external CPE bridge files."""

    def __init__(
        self,
        root: str | Path | None = None,
        packaged_root: str | Path | None = None,
        theme_store: Any | None = None,
    ) -> None:
        self.root = Path(root or app_path()).resolve()
        self.packaged_root = Path(packaged_root or bundle_path("repair_payload/cpe")).resolve()
        self.target_root = self.root / "cpe"
        self.state_path = self.root / "error_update_state.json"
        self.backup_root = self.root / "backup" / "cpe"
        self.theme_store = theme_store

    def state(self) -> dict[str, Any]:
        default = {
            "repaired": False,
            "error_code": ERROR_CODE,
            "cpe_version": EXPECTED_CPE_VERSION,
            "repaired_at": None,
            "last_backup": None,
        }
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        if isinstance(raw, dict):
            default.update({key: raw[key] for key in default if key in raw})
        return default

    @property
    def repaired(self) -> bool:
        return bool(self.state().get("repaired"))

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _write_state(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_name(f".{self.state_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def _bridge_checks(self) -> list[RepairCheck]:
        checks: list[RepairCheck] = []
        for relative in REPAIR_FILES:
            source = self.packaged_root / relative
            target = self.target_root / relative
            if not source.is_file():
                checks.append(RepairCheck(relative, False, "clean repair payload is missing"))
            elif not target.is_file():
                checks.append(RepairCheck(relative, False, "installed bridge file is missing"))
            else:
                same = self._sha256(source) == self._sha256(target)
                checks.append(RepairCheck(relative, same, "verified" if same else "checksum mismatch"))
        return checks

    @staticmethod
    def _runtime_check() -> RepairCheck:
        if CPE_VERSION != EXPECTED_CPE_VERSION:
            return RepairCheck(
                "CPE runtime",
                False,
                f"expected {EXPECTED_CPE_VERSION}, loaded {CPE_VERSION}",
            )
        try:
            engine = CubePhysicsEngine(480, 320, particle_seed=2102)
            spawned = engine.execute_line("CPE/1 1 1 240 70 22 1 31 184 255")
            burst = engine.execute_line("CPE/1 2 20 240 70 12 160 0.6 35 220 255")
            engine.step(1 / 30)
            snapshot = engine.snapshot()
            ok = (
                bool(spawned.get("entity_id"))
                and int(burst.get("particles", 0)) > 0
                and len(snapshot.get("bodies", [])) == 1
                and int(snapshot.get("particle_count", 0)) > 0
            )
            detail = f"CPE {CPE_VERSION}: 1 body, {snapshot.get('particle_count', 0)} IPE particles"
            return RepairCheck("CPE + IPE self-test", ok, detail)
        except Exception as exc:  # The result is displayed as a recovery diagnostic.
            return RepairCheck("CPE + IPE self-test", False, f"{type(exc).__name__}: {exc}")

    def diagnostics(self) -> list[RepairCheck]:
        return [
            RepairCheck(
                "CPE version",
                CPE_VERSION == EXPECTED_CPE_VERSION,
                f"loaded {CPE_VERSION}; expected {EXPECTED_CPE_VERSION}",
            ),
            *self._bridge_checks(),
            self._runtime_check(),
        ]

    def _backup_files(self) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        destination = self.backup_root / f"{stamp}-error-update-repair"
        destination.mkdir(parents=True, exist_ok=False)
        copied: list[str] = []
        for relative in REPAIR_FILES:
            source = self.target_root / relative
            if not source.is_file():
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(relative)
        (destination / "backup.json").write_text(
            json.dumps(
                {
                    "reason": "Error Update CPE repair",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "files": copied,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return destination

    def repair(self) -> RepairReport:
        restored: list[str] = []
        backup: Path | None = None
        try:
            if self.theme_store is not None:
                self.theme_store.create_backup("error-update-cpe-repair")
            backup = self._backup_files()
            for relative in REPAIR_FILES:
                source = self.packaged_root / relative
                if not source.is_file():
                    raise FileNotFoundError(f"repair payload missing: {relative}")
                target = self.target_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_file() and self._sha256(source) == self._sha256(target):
                    continue
                temporary = target.with_name(f".{target.name}.{os.getpid()}.repair")
                shutil.copy2(source, temporary)
                os.replace(temporary, target)
                restored.append(relative)

            checks = self.diagnostics()
            ok = all(check.ok for check in checks)
            if not ok:
                raise RuntimeError("one or more CPE verification checks failed")

            if self.theme_store is not None:
                theme_state = self.theme_store.state()
                theme_state.update(
                    cpe_channel="stable",
                    cpe_version=EXPECTED_CPE_VERSION,
                    experience="stable",
                    last_backup=backup.name if backup else None,
                )
                self.theme_store._write_state(theme_state)

            self._write_state(
                {
                    "repaired": True,
                    "error_code": ERROR_CODE,
                    "cpe_version": EXPECTED_CPE_VERSION,
                    "repaired_at": datetime.now(timezone.utc).isoformat(),
                    "last_backup": backup.name if backup else None,
                    "restored_files": restored,
                    "checks": [asdict(check) for check in checks],
                }
            )
            return RepairReport(True, checks, restored, backup.name if backup else None)
        except Exception as exc:
            checks = self.diagnostics()
            try:
                self._write_state(
                    {
                        "repaired": False,
                        "error_code": ERROR_CODE,
                        "cpe_version": EXPECTED_CPE_VERSION,
                        "repaired_at": None,
                        "last_backup": backup.name if backup else None,
                        "error": str(exc),
                    }
                )
            except OSError:
                pass
            return RepairReport(False, checks, restored, backup.name if backup else None, str(exc))


def _fit_image(image: pygame.Surface, maximum: tuple[int, int]) -> pygame.Surface:
    width, height = image.get_size()
    scale = min(maximum[0] / max(1, width), maximum[1] / max(1, height))
    return pygame.transform.smoothscale(image, (max(1, int(width * scale)), max(1, int(height * scale))))


def _load_error_logo(app: Any) -> pygame.Surface | None:
    if getattr(app, "_error_logo", None) is not None:
        return app._error_logo
    try:
        app._error_logo = _fit_image(
            pygame.image.load(str(bundle_path("error_update_logo.png"))).convert_alpha(),
            (190, 190),
        )
    except (pygame.error, OSError):
        app._error_logo = None
    return app._error_logo


def _apply_icon(app: Any) -> None:
    selected = "normal_icon.ico" if app.cpe_repair.repaired else "icon.ico"
    try:
        pygame.display.set_icon(pygame.image.load(str(bundle_path(selected))))
    except (pygame.error, OSError):
        pass


def _error_init(original_init: Any):
    def wrapped(app: Any) -> None:
        original_init(app)
        app.cpe_repair = CPERepairController(theme_store=getattr(app, "theme_store", None))
        app.main_menu = MethodType(_main_menu, app)
        app.fall_update_screen = MethodType(_error_loading_screen, app)
        app.repair_cpe_screen = MethodType(_repair_screen, app)
        _load_error_logo(app)
        _apply_icon(app)
        pygame.display.set_caption(f"The Cube Beta {VERSION} — Error Update — {ERROR_CODE}")

    return wrapped


def _draw_error_background(app: Any, ticks: float) -> None:
    app.screen.fill(DEEP_BLUE)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = (0, int(35 + 45 * ratio), int(92 + 82 * ratio))
        pygame.draw.line(app.screen, color, (0, y), (WIDTH, y))
    for y in range(0, HEIGHT, 6):
        pygame.draw.line(app.screen, (0, 46, 112), (0, y), (WIDTH, y))
    seed = int(ticks * 8)
    rng = random.Random(seed)
    for _ in range(12):
        width = rng.randint(28, 180)
        x = rng.randint(0, WIDTH - width)
        y = rng.randint(0, HEIGHT - 4)
        pygame.draw.rect(app.screen, rng.choice((CYAN, WHITE, (40, 118, 255))), (x, y, width, rng.randint(1, 4)))


def _draw_error_popup(app: Any, rect: pygame.Rect, title: str, body: str, phase: float = 0.0) -> None:
    dx = int(math.sin(phase * 13 + rect.x) * 2)
    dy = int(math.cos(phase * 9 + rect.y) * 2)
    rect = rect.move(dx, dy)
    pygame.draw.rect(app.screen, (2, 8, 26), rect.move(7, 8), border_radius=4)
    pygame.draw.rect(app.screen, (225, 238, 247), rect, border_radius=4)
    pygame.draw.rect(app.screen, BLUE, (rect.x, rect.y, rect.width, 28), border_top_left_radius=4, border_top_right_radius=4)
    pygame.draw.rect(app.screen, CYAN, rect, 2, border_radius=4)
    label = app.tiny.render(title, True, WHITE)
    app.screen.blit(label, (rect.x + 10, rect.y + 6))
    pygame.draw.rect(app.screen, (226, 48, 71), (rect.right - 27, rect.y + 5, 18, 18), border_radius=2)
    close = app.tiny.render("X", True, WHITE)
    app.screen.blit(close, close.get_rect(center=(rect.right - 18, rect.y + 14)))
    lines = body.split("\n")
    for index, line in enumerate(lines[:3]):
        message = app.tiny.render(line[:38], True, INK)
        app.screen.blit(message, (rect.x + 12, rect.y + 40 + index * 19))


def _error_loading_screen(app: Any, duration: float = 5.2) -> bool:
    """Always show the Error Update loader, including after a successful repair."""
    app.start_music()
    started = time.monotonic()
    duration = max(0.05, duration)
    stages = (
        "BOOTING CPE 0.0.2...",
        "ERROR 21CPE — CPE CONNECT FILE ERROR",
        "RECOVERING NUMERIC PHYSICS PIPELINE...",
        "CHECKING IPE PARTICLE MEMORY...",
        "ERROR UPDATE VISUAL MODE READY",
    )
    while True:
        progress = min(1.0, (time.monotonic() - started) / duration)
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_F11:
                    app.settings["fullscreen"] = not app.settings["fullscreen"]
                    app.apply_display()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and progress >= 0.2:
                    progress = 1.0

        ticks = pygame.time.get_ticks() / 1000
        _draw_error_background(app, ticks)
        logo = _load_error_logo(app)
        jitter_x = int(math.sin(ticks * 31) * (5 if progress < 0.92 else 1))
        if logo:
            app.screen.blit(logo, logo.get_rect(center=(WIDTH // 2 + jitter_x, 155)))

        heading = app.hero.render(f"ERROR {ERROR_CODE}", True, WHITE)
        app.screen.blit(heading, heading.get_rect(center=(WIDTH // 2 + jitter_x, 275)))
        detail = app.font.render("CPE CONNECT FILE ERROR", True, PALE_BLUE)
        app.screen.blit(detail, detail.get_rect(center=(WIDTH // 2, 326)))

        for index in range(ERROR_SLOGAN_COUNT):
            rect = pygame.Rect(90 + index * 184, 362 + (index % 2) * 8, 172, 42)
            pygame.draw.rect(app.screen, (1, 41, 112), rect, border_radius=5)
            pygame.draw.rect(app.screen, CYAN if index == int(progress * 5) % 5 else BLUE, rect, 2, border_radius=5)
            line1 = app.tiny.render("WE ARE DONE", True, WHITE)
            line2 = app.tiny.render("WE ARE COOKED", True, PALE_BLUE)
            app.screen.blit(line1, line1.get_rect(center=(rect.centerx, rect.y + 13)))
            app.screen.blit(line2, line2.get_rect(center=(rect.centerx, rect.y + 29)))

        track = pygame.Rect(150, 450, 800, 34)
        pygame.draw.rect(app.screen, (1, 27, 75), track, border_radius=4)
        fill_width = int(track.width * progress)
        if fill_width:
            pygame.draw.rect(app.screen, CYAN, (track.x, track.y, fill_width, track.height), border_radius=4)
        stage = stages[min(len(stages) - 1, int(progress * len(stages)))]
        status = app.small.render(stage, True, WHITE)
        app.screen.blit(status, status.get_rect(center=(WIDTH // 2, 526)))
        mode_text = (
            "CPE REPAIR VERIFIED — THE ERROR LOADER REMAINS BY DESIGN"
            if app.cpe_repair.repaired
            else "RECOVERY REQUIRED — USE REPAIR CPE IN THE MAIN MENU"
        )
        mode = app.tiny.render(mode_text, True, GREEN if app.cpe_repair.repaired else RED)
        app.screen.blit(mode, mode.get_rect(center=(WIDTH // 2, 570)))
        footer = app.tiny.render(
            f"THE CUBE BETA {VERSION} / ERROR UPDATE    ENTER OR SPACE TO SKIP",
            True,
            MUTED,
        )
        app.screen.blit(footer, footer.get_rect(center=(WIDTH // 2, 652)))
        pygame.display.flip()
        app.clock.tick(FPS)
        if progress >= 1.0:
            return True


def _broken_menu(app: Any) -> str:
    entries = [
        ("REPAIR CPE 0.0.2", "repair"),
        ("PL▲Y // BUTTON_FAULT", "single"),
        ("MULTIPLAYER // NULL", "multiplayer"),
        ("THEME_STORE.err", "themes"),
        ("ADD-ONS [BROKEN]", "addons"),
        ("SETTINGS ???", "settings"),
        ("QUIT.exe", "quit"),
    ]
    buttons = [app._experience_button_type((370, 278 + i * 49, 360, 41), label, WHITE) for i, (label, _) in enumerate(entries)]
    fault = "MENU SHELL NOT RESPONDING — REPAIR CPE TO RESTORE CONTROLS"
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return "quit"
        ticks = pygame.time.get_ticks() / 1000
        _draw_error_background(app, ticks)
        shake = 7
        title_x = WIDTH // 2 + int(math.sin(ticks * 34) * shake)
        title_y = 85 + int(math.cos(ticks * 29) * 4)
        title = app.hero.render("THE CUBE BETA — ERROR", True, WHITE)
        app.screen.blit(title, title.get_rect(center=(title_x, title_y)))
        for offset, color in ((-4, RED), (5, CYAN)):
            ghost = app.hero.render("ERROR", True, color)
            ghost.set_alpha(115)
            app.screen.blit(ghost, ghost.get_rect(center=(WIDTH // 2 + offset, 165)))
        error = app.large.render(f"ERROR {ERROR_CODE}", True, WHITE)
        app.screen.blit(error, error.get_rect(center=(WIDTH // 2, 165)))
        message = app.small.render(fault, True, PALE_BLUE)
        app.screen.blit(message, message.get_rect(center=(WIDTH // 2, 218)))

        _draw_error_popup(app, pygame.Rect(34, 225, 285, 116), "CPE CONNECT FILE ERROR", "Bridge checksum failed\nIPE memory unavailable", ticks)
        _draw_error_popup(app, pygame.Rect(770, 238, 295, 116), "WINDOW ERROR", "MainMenu.dll is cooked\nButtons returned NULL", ticks + 0.5)
        _draw_error_popup(app, pygame.Rect(25, 470, 305, 116), "FATAL BUT REPAIRABLE", "ERROR 21CPE\nClick REPAIR CPE", ticks + 1.0)
        _draw_error_popup(app, pygame.Rect(785, 485, 280, 112), "CUBE STATUS", "WE ARE DONE\nWE ARE COOKED", ticks + 1.5)

        selected = app.wait_click(buttons, events)
        pygame.draw.rect(app.screen, CYAN, buttons[0].rect, 3, border_radius=14)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        action = entries[selected][1]
        if action == "repair":
            if app.repair_cpe_screen():
                return "menu"
        elif action == "quit":
            return "quit"
        else:
            fault = f"{entries[selected][0]} FAILED — ERROR {ERROR_CODE} — REPAIR CPE FIRST"


def _draw_fluent_background(app: Any, ticks: float) -> None:
    top = (7, 28, 58)
    bottom = (19, 99, 126)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        pygame.draw.line(app.screen, color, (0, y), (WIDTH, y))
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for index in range(10):
        x = int((90 + index * 137 + ticks * (16 + index % 3 * 7)) % (WIDTH + 160)) - 80
        y = 100 + (index * 79) % 560 + int(math.sin(ticks + index) * 24)
        radius = 16 + (index % 4) * 8
        pygame.draw.rect(glow, (34, 214, 232, 35), (x, y, radius, radius), border_radius=5)
        pygame.draw.rect(glow, (170, 246, 255, 75), (x, y, radius, radius), 2, border_radius=5)
    app.screen.blit(glow, (0, 0))


def _fluent_menu(app: Any) -> str:
    state = app.theme_store.state()
    entries = [
        ("PLAY SOLO", "single", CYAN),
        ("PLAY MULTIPLAYER", "multiplayer", GREEN),
        ("THEME STORE", "themes", (178, 146, 255)),
        ("ADD-ONS", "addons", (255, 204, 95)),
        ("SETTINGS", "settings", WHITE),
    ]
    if state.get("developer_enabled"):
        entries.append(("DEVELOPER MODE", "developer", (255, 154, 96)))
    entries.append(("QUIT", "quit", (255, 139, 154)))
    columns = 2
    buttons = []
    for index, (label, _, accent) in enumerate(entries):
        column, row = index % columns, index // columns
        buttons.append(app._experience_button_type((175 + column * 385, 325 + row * 78, 350, 58), label, accent))

    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return "quit"
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "quit"
        ticks = pygame.time.get_ticks() / 1000
        _draw_fluent_background(app, ticks)
        panel = pygame.Surface((920, 600), pygame.SRCALPHA)
        pygame.draw.rect(panel, (4, 27, 52, 178), panel.get_rect(), border_radius=30)
        pygame.draw.rect(panel, (131, 236, 248, 105), panel.get_rect(), 2, border_radius=30)
        app.screen.blit(panel, (90, 58))

        badge_rect = pygame.Rect(362, 82, 376, 38)
        pygame.draw.rect(app.screen, (28, 206, 213), badge_rect, border_radius=19)
        badge = app.small.render(f"CPE {EXPECTED_CPE_VERSION} REPAIR VERIFIED", True, INK)
        app.screen.blit(badge, badge.get_rect(center=badge_rect.center))
        title = app.hero.render("THE CUBE BETA", True, WHITE)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 177)))
        subtitle = app.font.render("Fluent physics. Restored particles. Stable bridges.", True, PALE_BLUE)
        app.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 238)))
        status = app.tiny.render(
            f"ERROR UPDATE {VERSION}   /   ERROR {ERROR_CODE} REPAIRED   /   CPE + IPE ONLINE",
            True,
            MUTED,
        )
        app.screen.blit(status, status.get_rect(center=(WIDTH // 2, 280)))
        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is not None:
            return entries[selected][1]


def _main_menu(app: Any) -> str:
    return _fluent_menu(app) if app.cpe_repair.repaired else _broken_menu(app)


def _draw_repair_status(app: Any, title: str, detail: str, progress: float, color: tuple[int, int, int]) -> None:
    ticks = pygame.time.get_ticks() / 1000
    _draw_error_background(app, ticks)
    panel = pygame.Rect(145, 100, 810, 520)
    pygame.draw.rect(app.screen, (4, 20, 54), panel, border_radius=18)
    pygame.draw.rect(app.screen, color, panel, 3, border_radius=18)
    heading = app.large.render(title, True, WHITE)
    app.screen.blit(heading, heading.get_rect(center=(WIDTH // 2, 175)))
    code = app.small.render(f"RECOVERY CONSOLE / ERROR {ERROR_CODE} / CPE {EXPECTED_CPE_VERSION}", True, PALE_BLUE)
    app.screen.blit(code, code.get_rect(center=(WIDTH // 2, 225)))
    track = pygame.Rect(235, 320, 630, 34)
    pygame.draw.rect(app.screen, (1, 35, 83), track, border_radius=6)
    pygame.draw.rect(app.screen, color, (track.x, track.y, int(track.width * progress), track.height), border_radius=6)
    message = app.font.render(detail[:72], True, WHITE)
    app.screen.blit(message, message.get_rect(center=(WIDTH // 2, 405)))
    percent = app.small.render(f"{int(progress * 100)}%", True, PALE_BLUE)
    app.screen.blit(percent, percent.get_rect(center=(WIDTH // 2, 467)))
    pygame.display.flip()


def _repair_screen(app: Any) -> bool:
    stages = (
        "Creating recovery backups...",
        "Restoring CPE bridge source files...",
        "Testing Pymunk numeric pipeline...",
        "Testing Integrated Particle Engine...",
    )
    for index, stage in enumerate(stages):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        _draw_repair_status(app, "REPAIRING CPE", stage, (index + 1) / (len(stages) + 2), CYAN)
        app.clock.tick(8)
    report = app.cpe_repair.repair()
    if report.ok:
        _apply_icon(app)
        detail = f"Verified {len(report.checks)} checks; restored {len(report.restored_files)} file(s)."
        _draw_repair_status(app, "CPE REPAIR COMPLETE", detail, 1.0, GREEN)
        pygame.time.wait(1100)
        return True

    detail = f"Repair stopped safely: {report.error or 'verification failed'}"
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONUP:
                return False
        _draw_repair_status(app, "CPE REPAIR NEEDS ATTENTION", detail, 1.0, RED)
        app.clock.tick(FPS)
    return False


def install_error_update(game_app: type[Any], button_type: type[Any]) -> None:
    """Install the 6.3 Error Update over the current game experience."""
    if getattr(game_app, "_error_update_installed", False):
        return
    game_app._error_update_installed = True
    game_app._experience_button_type = button_type
    game_app.__init__ = _error_init(game_app.__init__)
    game_app.fall_update_screen = _error_loading_screen
    game_app.main_menu = _main_menu
    game_app.repair_cpe_screen = _repair_screen


__all__ = [
    "CPERepairController",
    "ERROR_CODE",
    "ERROR_SLOGAN",
    "ERROR_SLOGAN_COUNT",
    "EXPECTED_CPE_VERSION",
    "REPAIR_FILES",
    "RepairCheck",
    "RepairReport",
    "install_error_update",
]
