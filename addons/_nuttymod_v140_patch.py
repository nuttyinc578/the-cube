"""Readable NuttyMod 1.4.2 connection and permanent-install layer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any, Callable
import zipfile


PATCH_VERSION = "1.4.2"
GAME_EDITION = "6.2"
GAME_VERSION = "6.2.0"
TERMS_VERSION = "2026-08-26-account-settings-v142"
PERMANENT_STATE_NAME = ".nuttymod_permanent_install.json"
RUNTIME_NAME = "nuttymod_runtime_v122.pyc"
PATCH_NAME = "_nuttymod_v140_patch.py"
PATCH_JAR_NAME = "nuttymod_loader_patch.jar"
PROFILE_JAR_NAME = "nuttymod_root_mode_profile.jar"
SERVICE_NAME = "nuttymod_service.py"
CONNECTION_MODULE_NAME = "_nuttymod_connection.py"
CONNECTION_SECONDS = 120.0

PERMANENT_INSTALL_SECONDS = 60.0
SUPPORTED_PERMANENT_VERSIONS = {"1.3.0", "1.4.0", "1.4.1", PATCH_VERSION}

_RUNTIME: dict[str, Any] = {}
_LEGACY_LOADING_SCREEN: Callable[[Any], bool] | None = None
_LEGACY_SETTINGS_MENU: Callable[[Any], None] | None = None
_LEGACY_JAR_RUNNER: Callable[[Path], dict[str, Any]] | None = None
_CONNECTION_MODULE: Any | None = None

_STABLE_MOD_TEXT = {
    "Verified add-ons, experimental Mods, Studios, and safe stable/beta updates.":
        "Verified add-ons, stable Mods, Studios, and safe Stable/Beta updates.",
    "These terms cover Add-ons, experimental Mods, and verified updates in Root Mode.":
        "These terms cover Add-ons, stable Mods, and verified updates in Root Mode.",
    "No add-ons or experimental Mods found.": "No add-ons or stable Mods found.",
    "ESC cancels  |  Windowed mode only  |  Experimental Mods are clearly separated":
        "ESC cancels  |  Windowed mode only  |  Stable Mods are clearly separated",
    "Verified Add-ons  |  Experimental Mods  |  Windowed mode":
        "Verified Add-ons  |  Stable Mods  |  Windowed mode",
    "BETA MODS": "MODS",
    "Experimental Mod ": "Mod ",
    "Experimental Mods use .rb, .cs, or .batch files":
        "Stable Mods use .rb, .cs, or .batch files",
    "Experimental feature": "Stable feature",
    "Experimental Ruby, C#, and .batch Mods live in addons/mods.":
        "Stable Ruby, C#, and .batch Mods live in addons/mods.",
    " experimental Mods": " stable Mods",
}


def _stable_mod_constant(value: Any, code_type: type) -> Any:
    if isinstance(value, str):
        replacement = _STABLE_MOD_TEXT.get(value, value)
        return (
            replacement.replace("experimental Mods", "stable Mods")
            .replace("Experimental Mods", "Stable Mods")
            .replace("experimental_mods", "stable_mods")
            .replace("BETA MODS", "MODS")
        )
    if isinstance(value, code_type):
        return _stable_mod_code(value)
    if isinstance(value, tuple):
        items = tuple(_stable_mod_constant(item, code_type) for item in value)
        return items if items != value else value
    if isinstance(value, frozenset):
        items = frozenset(_stable_mod_constant(item, code_type) for item in value)
        return items if items != value else value
    return value


def _stable_mod_code(code: Any) -> Any:
    """Replace legacy Mods labels without changing Beta update-channel text."""
    constants = tuple(
        _stable_mod_constant(value, type(code)) for value in code.co_consts
    )
    return code.replace(co_consts=constants) if constants != code.co_consts else code

def _promote_runtime_mods(runtime: dict[str, Any]) -> None:
    seen: set[int] = set()
    for value in runtime.values():
        code = getattr(value, "__code__", None)
        if code is None or id(value) in seen:
            continue
        seen.add(id(value))
        value.__code__ = _stable_mod_code(code)


def _loader_dir() -> Path:
    return Path(__file__).resolve().parent


def _read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return value


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, indent=2).encode("utf-8") + b"\n")


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    resolved_root = root.resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


def _jar_manifest(name: str, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "version": PATCH_VERSION,
        "author": "NuttyMod Studios",
        "description": description,
        "shapes": [],
        "events": [],
        "nuttymod_profile": True,
        "game_edition": GAME_EDITION,
    }


def _jar_bytes(manifest: dict[str, Any]) -> bytes:
    def member(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, date_time=(2026, 8, 3, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        return info

    with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as stream:
        with zipfile.ZipFile(
            stream,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(
                member("META-INF/MANIFEST.MF"),
                "Manifest-Version: 1.0\n"
                "Created-By: NuttyMod Studios\n"
                f"Implementation-Version: {PATCH_VERSION}\n\n",
            )
            archive.writestr(
                member("nuttymod.json"),
                json.dumps(manifest, indent=2) + "\n",
            )
        stream.seek(0)
        return stream.read()


def _profile_assets() -> dict[str, bytes]:
    return {
        PATCH_JAR_NAME: _jar_bytes(
            _jar_manifest(
                "NuttyMod Loader Patch",
                "NuttyMod 1.4.2 loader profile with Node.js 22+ local connection support.",
            )
        ),
        PROFILE_JAR_NAME: _jar_bytes(
            _jar_manifest(
                "NuttyMod Root Mode Profile",
                "Root Mode profile for The Cube Beta Fall Edition 6.2.",
            )
        ),
    }


def _ensure_profile_assets(directory: Path | None = None) -> None:
    root = _loader_dir() if directory is None else Path(directory)
    for name, payload in _profile_assets().items():
        path = root / name
        current = path.read_bytes() if path.is_file() else None
        if current != payload:
            _atomic_write(path, payload)


def _ensure_game_sidecars() -> None:
    loader_root = _loader_dir()
    game_root = Path(_RUNTIME["ADDONS_DIR"]).resolve().parent
    for name in (SERVICE_NAME, PATCH_JAR_NAME, PROFILE_JAR_NAME):
        source = loader_root / name
        if not source.is_file():
            raise ValueError(f"NuttyMod game-side file is missing: {name}")
        destination = game_root / name
        payload = source.read_bytes()
        if not destination.is_file() or destination.read_bytes() != payload:
            _atomic_write(destination, payload)

def _embedded_jar_manifest(path: Path) -> dict[str, Any] | None:
    if not zipfile.is_zipfile(path):
        return None
    try:
        with zipfile.ZipFile(path, "r") as archive:
            raw = archive.read("nuttymod.json")
    except KeyError:
        return None
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"Could not read JAR add-on: {exc}") from exc
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JAR nuttymod.json must contain valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("JAR nuttymod.json must contain a JSON object")
    return manifest


def _run_jar_addon(path: Path) -> dict[str, Any]:
    embedded = _embedded_jar_manifest(path)
    if embedded is not None:
        return embedded
    if _LEGACY_JAR_RUNNER is None:
        raise ValueError("Executable JAR support is unavailable")
    return _LEGACY_JAR_RUNNER(path)


def _state_file() -> Path:
    return Path(_RUNTIME["STATE_FILE"])


def _merge_loader_state(**changes: Any) -> None:
    path = _state_file()
    state = _read_json(path, {})
    if not isinstance(state, dict):
        state = {}
    state.update(changes)
    try:
        _atomic_json(path, state)
    except OSError:
        pass


def _first_install_required() -> bool:
    state = _read_json(_state_file(), {})
    return not isinstance(state, dict) or state.get("install_version") != PATCH_VERSION


def _mark_first_install_complete() -> None:
    _merge_loader_state(
        install_version=PATCH_VERSION,
        install_completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        loader_version=PATCH_VERSION,
        game_edition=GAME_EDITION,
        root_mode=True,
    )


def _quick_verification_screen(app: Any) -> bool:
    pygame = _RUNTIME["_pygame"]()
    width, height = app.screen.get_size()
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    coral = _RUNTIME["_color"]("CORAL", (245, 130, 115))
    fps = int(getattr(_RUNTIME.get("_GAME_MODULE"), "FPS", 60))

    app.addons.reload()
    rows = list(_RUNTIME["_verification_rows"](app.addons))
    started = time.monotonic()
    duration = 3.4
    stages = [
        ("VERIFYING ADD-ONS", "Checking manifests and SHA-256 fingerprints"),
        ("ROOTING GAME", "Activating the local NuttyMod profile"),
        ("UPGRADING MODIFIED MENU", f"Fall Edition {GAME_EDITION} controls ready"),
        ("READY", "Root Mode verification complete"),
    ]

    while True:
        elapsed = time.monotonic() - started
        ratio = min(1.0, elapsed / duration)
        if ratio >= 1.0:
            _merge_loader_state(
                last_verified_at=time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(),
                ),
                loader_version=PATCH_VERSION,
                root_mode=True,
            )
            return True
        for event in pygame.event.get():
            if _RUNTIME["_common_window_event"](app, event) == "quit":
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        stage_index = min(len(stages) - 1, int(ratio * len(stages)))
        title, detail = stages[stage_index]
        app.draw_background(pygame.time.get_ticks() / 1000, simple=True)
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((4, 26, 42, 180))
        app.screen.blit(shade, (0, 0))
        panel = pygame.Rect(120, 85, width - 240, height - 170)
        app.draw_panel(panel, 247)

        badge = app.small.render(
            f"NUTTYMOD {PATCH_VERSION}  /  FALL EDITION {GAME_EDITION}",
            True,
            navy,
        )
        app.screen.blit(badge, badge.get_rect(center=(width // 2, 126)))
        heading = app.large.render(title, True, navy)
        app.screen.blit(heading, heading.get_rect(center=(width // 2, 177)))
        detail_label = app.small.render(detail, True, muted)
        app.screen.blit(detail_label, detail_label.get_rect(center=(width // 2, 218)))

        list_rect = pygame.Rect(175, 250, width - 350, 260)
        pygame.draw.rect(app.screen, (246, 251, 253), list_rect, border_radius=14)
        pygame.draw.rect(app.screen, (184, 207, 216), list_rect, 2, border_radius=14)
        y = list_rect.y + 18
        for record, state, fingerprint in rows[:6]:
            color = mint if state == "VERIFIED" else coral
            if state == "DISABLED":
                color = muted
            pygame.draw.circle(app.screen, color, (list_rect.x + 20, y + 9), 6)
            label = app.small.render(
                _RUNTIME["_fit_text"](app.small, record.name, 390),
                True,
                navy,
            )
            app.screen.blit(label, (list_rect.x + 36, y))
            status = app.tiny.render(
                f"{record.language}  |  {state}",
                True,
                color,
            )
            app.screen.blit(status, (list_rect.right - 175, y + 2))
            hash_label = app.tiny.render(
                _RUNTIME["_fit_text"](app.tiny, fingerprint, 500),
                True,
                muted,
            )
            app.screen.blit(hash_label, (list_rect.x + 36, y + 23))
            y += 40

        progress = pygame.Rect(175, 548, width - 350, 18)
        pygame.draw.rect(app.screen, (207, 222, 228), progress, border_radius=9)
        pygame.draw.rect(
            app.screen,
            mint,
            (progress.x, progress.y, max(18, int(progress.width * ratio)), progress.height),
            border_radius=9,
        )
        count = app.small.render(
            f"{sum(state == 'VERIFIED' for _, state, _ in rows)} of "
            f"{len(rows)} files verified",
            True,
            navy,
        )
        app.screen.blit(count, count.get_rect(center=(width // 2, 590)))
        pygame.display.flip()
        app.clock.tick(fps)


def _connection_runtime() -> Any:
    global _CONNECTION_MODULE
    if _CONNECTION_MODULE is not None:
        return _CONNECTION_MODULE
    path = _loader_dir() / CONNECTION_MODULE_NAME
    if not path.is_file():
        raise RuntimeError(f"NuttyMod connection module is missing: {path.name}")
    spec = importlib.util.spec_from_file_location("_nuttymod_connection_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("NuttyMod connection module could not be opened")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CONNECTION_MODULE = module
    return module


def _connection_screen(app: Any, duration: float = CONNECTION_SECONDS) -> bool:
    pygame = _RUNTIME["_pygame"]()
    width, height = app.screen.get_size()
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    coral = _RUNTIME["_color"]("CORAL", (245, 130, 115))
    yellow = _RUNTIME["_color"]("YELLOW", (255, 225, 105))
    fps = int(getattr(_RUNTIME.get("_GAME_MODULE"), "FPS", 60))
    session = _connection_runtime().ConnectionSession(
        Path(_RUNTIME["ADDONS_DIR"]),
        duration=max(0.2, float(duration)),
    )
    session.start()
    success_at: float | None = None
    try:
        while True:
            state = session.snapshot()
            done = bool(state.get("done"))
            success = bool(state.get("success"))
            if done and success:
                success_at = success_at or time.monotonic()
                if time.monotonic() - success_at >= 0.65:
                    return True

            for event in pygame.event.get():
                if _RUNTIME["_common_window_event"](app, event) == "quit":
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
                    if done and not success and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        return False

            ratio = float(state.get("progress", 0.0))
            stage = str(state.get("stage", "PREPARING CONNECTION"))
            detail = str(state.get("detail", "Starting the local NuttyMod connection stack"))
            if done and not success:
                detail = str(state.get("error") or detail)

            app.draw_background(pygame.time.get_ticks() / 1000, simple=True)
            shade = pygame.Surface((width, height), pygame.SRCALPHA)
            shade.fill((4, 26, 42, 190))
            app.screen.blit(shade, (0, 0))
            panel = pygame.Rect(105, 62, width - 210, height - 124)
            app.draw_panel(panel, 248)

            accent = coral if done and not success else (mint if success else yellow)
            badge = app.small.render(
                "NUTTYMOD LOCAL CONNECTION  |  TWO-MINUTE STARTUP  |  NODE.JS 22+",
                True,
                accent,
            )
            app.screen.blit(badge, badge.get_rect(center=(width // 2, panel.y + 40)))
            heading = app.large.render(stage, True, navy)
            app.screen.blit(heading, heading.get_rect(center=(width // 2, panel.y + 92)))
            detail_label = app.small.render(
                _RUNTIME["_fit_text"](app.small, detail, panel.width - 110),
                True,
                muted,
            )
            app.screen.blit(detail_label, detail_label.get_rect(center=(width // 2, panel.y + 133)))

            services = [
                ("NODE.JS v22+", int(state.get("node_port", 0)), "Local bootstrap bridge"),
                ("GO AUTH", int(state.get("go_port", 0)), "Local account authentication"),
                ("NUTTYMOD_BOOTSTRAP", bool(state.get("bootstrap_url")), "Local 127.0.0.1 website"),
                (
                    "ELECTRON PORT",
                    int(state.get("electron_port", 0)),
                    str(state.get("electron_runtime") or "Electron-compatible fallback"),
                ),
            ]
            list_rect = pygame.Rect(panel.x + 70, panel.y + 166, panel.width - 140, 208)
            pygame.draw.rect(app.screen, (246, 251, 253), list_rect, border_radius=14)
            pygame.draw.rect(app.screen, (184, 207, 216), list_rect, 2, border_radius=14)
            y = list_rect.y + 16
            for label_text, value, description in services:
                ready = bool(value)
                pygame.draw.circle(app.screen, mint if ready else muted, (list_rect.x + 22, y + 11), 7)
                label = app.small.render(label_text, True, navy)
                app.screen.blit(label, (list_rect.x + 42, y))
                status_text = f"PORT {value}" if type(value) is int and value else ("CONNECTED" if ready else "WAITING")
                status = app.tiny.render(status_text, True, mint if ready else muted)
                app.screen.blit(status, (list_rect.right - 135, y + 3))
                sub = app.tiny.render(
                    _RUNTIME["_fit_text"](app.tiny, description, list_rect.width - 230),
                    True,
                    muted,
                )
                app.screen.blit(sub, (list_rect.x + 42, y + 22))
                y += 48

            progress = pygame.Rect(panel.x + 70, panel.bottom - 116, panel.width - 140, 22)
            pygame.draw.rect(app.screen, (207, 222, 228), progress, border_radius=11)
            fill_width = max(0, int(progress.width * max(0.0, min(1.0, ratio))))
            if fill_width:
                pygame.draw.rect(
                    app.screen,
                    accent,
                    (progress.x, progress.y, fill_width, progress.height),
                    border_radius=11,
                )
            remaining = max(0, int(float(duration) - float(state.get("elapsed", 0.0)) + 0.999))
            progress_text = app.small.render(
                f"{int(ratio * 100):02d}%  |  about {remaining} seconds remaining",
                True,
                navy,
            )
            app.screen.blit(progress_text, progress_text.get_rect(center=(width // 2, progress.bottom + 28)))

            if state.get("account_required"):
                footer_text = "ACCOUNT SETUP: complete the PowerShell window; the setup phrase is never saved."
            elif done and not success:
                footer_text = "Connection failed. Press ENTER or ESC to close, correct the issue, and relaunch."
            elif state.get("repaired"):
                footer_text = f"Repaired {len(state['repaired'])} protected helper file(s) from embedded sources."
            else:
                footer_text = "LOCAL ONLY  |  127.0.0.1  |  SERVICES CLOSE AFTER HANDSHAKE"
            footer = app.tiny.render(
                _RUNTIME["_fit_text"](app.tiny, footer_text, panel.width - 90),
                True,
                coral if done and not success else muted,
            )
            app.screen.blit(footer, footer.get_rect(center=(width // 2, panel.bottom - 22)))
            pygame.display.flip()
            app.clock.tick(fps)
    finally:
        session.cancel()
        session.join(1.0)

def _loading_screen(app: Any) -> bool:
    _ensure_profile_assets()
    app.addons.reload()
    if _first_install_required():
        if _LEGACY_LOADING_SCREEN is None or not _LEGACY_LOADING_SCREEN(app):
            return False
        _mark_first_install_complete()
        app.addons.reload()
    if not _connection_screen(app):
        return False
    app.addons.reload()
    return _quick_verification_screen(app)


def _default_source_root() -> Path:
    add_on_root = Path(_RUNTIME["ADDONS_DIR"]).resolve()
    game_or_dist = add_on_root.parent
    if game_or_dist.name.casefold() == "dist":
        return game_or_dist.parent
    return game_or_dist


def _permanent_state_path(addons_dir: Path | None = None) -> Path:
    root = Path(_RUNTIME["ADDONS_DIR"]) if addons_dir is None else Path(addons_dir)
    return root / PERMANENT_STATE_NAME


def _permanent_targets(source_root: Path) -> dict[str, Path]:
    root = Path(source_root).resolve()
    addons = root / "addons"
    targets = {
        "cube_core.py": root / "cube_core.py",
        "the_cube_beta_summer.py": root / "the_cube_beta_summer.py",
        "nuttymod_core.py": root / "nuttymod_core.py",
        "nuttymod_cube_core.py": root / "nuttymod_cube_core.py",
        SERVICE_NAME: root / SERVICE_NAME,
        PATCH_JAR_NAME: root / PATCH_JAR_NAME,
        PROFILE_JAR_NAME: root / PROFILE_JAR_NAME,
        "addons/nuttymod_loader.py": addons / "nuttymod_loader.py",
        f"addons/{PATCH_NAME}": addons / PATCH_NAME,
        f"addons/{RUNTIME_NAME}": addons / RUNTIME_NAME,
        "addons/nuttymod_loader.rb": addons / "nuttymod_loader.rb",
        f"addons/{SERVICE_NAME}": addons / SERVICE_NAME,
        f"addons/{PATCH_JAR_NAME}": addons / PATCH_JAR_NAME,
        f"addons/{PROFILE_JAR_NAME}": addons / PROFILE_JAR_NAME,
        f"addons/{CONNECTION_MODULE_NAME}": addons / CONNECTION_MODULE_NAME,
        "addons/nuttymod_bootstrap/nuttymod_auth.exe": (
            addons / "nuttymod_bootstrap" / "nuttymod_auth.exe"
        ),
    }
    test_file = root / "test_summer_game.py"
    if test_file.is_file():
        targets["test_summer_game.py"] = test_file
    return targets

def _full_core_source(source_root: Path) -> str:
    root = source_root.resolve()
    cube = root / "cube_core.py"
    split = root / "nuttymod_cube_core.py"
    source_path: Path | None = None
    wrapper = ""
    if cube.is_file():
        try:
            wrapper = cube.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Could not read cube_core.py: {exc}") from exc
        source_path = cube
    if split.is_file() and (
        source_path is None
        or "from nuttymod_cube_core import *" in wrapper
        or "from nuttymod_core import *" in wrapper
    ):
        source_path = split
    if source_path is None:
        raise ValueError("Neither cube_core.py nor nuttymod_cube_core.py contains the game core")
    try:
        source = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read the full core implementation: {exc}") from exc
    source, title_count = re.subn(
        r"^APP_TITLE\s*=.*$",
        'APP_TITLE = "The Cube Beta Fall Edition"',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    source, version_count = re.subn(
        r"^VERSION\s*=.*$",
        f'VERSION = "{GAME_VERSION}"',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    if title_count != 1 or version_count != 1:
        raise ValueError("The core is missing APP_TITLE or VERSION declarations")
    marker = (
        "\n\nNUTTYMOD_PERMANENT_PROFILE = {\n"
        f'    "loader_version": "{PATCH_VERSION}",\n'
        f'    "game_edition": "{GAME_EDITION}",\n'
        '    "root_mode": True,\n'
        "}\n"
    )
    source = re.sub(
        r"\n\nNUTTYMOD_PERMANENT_PROFILE\s*=\s*\{.*?\}\s*$",
        "",
        source,
        count=1,
        flags=re.DOTALL,
    ).rstrip() + marker
    compile(source, str(root / "nuttymod_cube_core.py"), "exec")
    return source

def _patched_entrypoint_source(source_root: Path) -> str:
    path = source_root.resolve() / "the_cube_beta_summer.py"
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Could not read the game entry point: {exc}") from exc
    old_import = "from cube_core import ("
    new_import = "from nuttymod_core import ("
    if source.count(old_import) == 1:
        source = source.replace(old_import, new_import, 1)
    elif source.count(new_import) != 1:
        raise ValueError("The game entry point has no recognized core import")
    source = re.sub(
        r'^"""The Cube Beta .*?(?:Summer|Fall) Edition.*?"""$',
        '"""The Cube Beta 6.2 - Fall Edition with NuttyMod Core."""',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    compile(source, str(path), "exec")
    return source


def _patched_test_source(source_root: Path) -> str | None:
    path = source_root.resolve() / "test_summer_game.py"
    if not path.is_file():
        return None
    source = path.read_text(encoding="utf-8")
    old_import = "from cube_core import "
    new_import = "from nuttymod_core import "
    if source.count(old_import) == 1:
        source = source.replace(old_import, new_import, 1)
    elif source.count(new_import) != 1:
        raise ValueError("The regression suite has no recognized core import")
    compile(source, str(path), "exec")
    return source

def _permanent_payloads(source_root: Path) -> dict[str, bytes | None]:
    loader_root = _loader_dir()
    _ensure_profile_assets(loader_root)
    full_core = _full_core_source(source_root)
    entrypoint = _patched_entrypoint_source(source_root)
    test_source = _patched_test_source(source_root)
    compatibility = (
        '"""NuttyMod permanent core for The Cube Beta Fall Edition 6.2."""\n\n'
        "from nuttymod_cube_core import *\n"
        "from nuttymod_service import health_report as nuttymod_health_report\n\n"
        "NUTTYMOD_PERMANENT = True\n"
        f'NUTTYMOD_VERSION = "{PATCH_VERSION}"\n'
        f'NUTTYMOD_GAME_EDITION = "{GAME_EDITION}"\n'
    )
    compile(compatibility, "nuttymod_core.py", "exec")
    required = {
        SERVICE_NAME: loader_root / SERVICE_NAME,
        PATCH_JAR_NAME: loader_root / PATCH_JAR_NAME,
        PROFILE_JAR_NAME: loader_root / PROFILE_JAR_NAME,
        "addons/nuttymod_loader.py": loader_root / "nuttymod_loader.py",
        f"addons/{PATCH_NAME}": loader_root / PATCH_NAME,
        f"addons/{RUNTIME_NAME}": loader_root / RUNTIME_NAME,
        "addons/nuttymod_loader.rb": loader_root / "nuttymod_loader.rb",
        f"addons/{SERVICE_NAME}": loader_root / SERVICE_NAME,
        f"addons/{PATCH_JAR_NAME}": loader_root / PATCH_JAR_NAME,
        f"addons/{PROFILE_JAR_NAME}": loader_root / PROFILE_JAR_NAME,
        f"addons/{CONNECTION_MODULE_NAME}": loader_root / CONNECTION_MODULE_NAME,
        "addons/nuttymod_bootstrap/nuttymod_auth.exe": (
            loader_root / "nuttymod_bootstrap" / "nuttymod_auth.exe"
        ),
    }
    payloads: dict[str, bytes | None] = {
        "cube_core.py": None,
        "the_cube_beta_summer.py": entrypoint.encode("utf-8"),
        "nuttymod_core.py": compatibility.encode("utf-8"),
        "nuttymod_cube_core.py": full_core.encode("utf-8"),
    }
    if test_source is not None:
        payloads["test_summer_game.py"] = test_source.encode("utf-8")
    for key, path in required.items():
        if not path.is_file():
            raise ValueError(f"Required permanent-install file is missing: {path.name}")
        payloads[key] = path.read_bytes()
    jar_keys = (
        PATCH_JAR_NAME,
        PROFILE_JAR_NAME,
        f"addons/{PATCH_JAR_NAME}",
        f"addons/{PROFILE_JAR_NAME}",
    )
    for key in jar_keys:
        payload = payloads[key]
        if payload is None:
            raise ValueError(f"JAR payload is missing: {key}")
        with tempfile.NamedTemporaryFile(suffix=".jar", delete=False) as stream:
            stream.write(payload)
            check_path = Path(stream.name)
        try:
            if _embedded_jar_manifest(check_path) is None:
                raise ValueError(f"{Path(key).name} has no embedded NuttyMod manifest")
        finally:
            check_path.unlink(missing_ok=True)
    return payloads

def _backup_root(addons_dir: Path) -> Path:
    root = Path(addons_dir) / "update_backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _unique_backup_directory(addons_dir: Path) -> Path:
    root = _backup_root(addons_dir)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    candidate = root / f"{stamp}-permanent-v142"
    index = 2
    while candidate.exists():
        candidate = root / f"{stamp}-permanent-v142-{index}"
        index += 1
    candidate.mkdir(parents=True)
    return candidate


def _targets_from_state(state: dict[str, Any], source_root: Path) -> dict[str, Path]:
    root = source_root.resolve()
    entries = state.get("files", {})
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Permanent-install file manifest is invalid")
    allowed = set(_permanent_targets(root))
    allowed.add("addons/_nuttymod_v130_patch.py")
    targets: dict[str, Path] = {}
    for key in entries:
        if not isinstance(key, str) or key not in allowed:
            raise ValueError(f"Permanent-install target is not allowed: {key}")
        relative = Path(*key.replace("\\", "/").split("/"))
        target = (root / relative).resolve()
        if not _inside(target, root):
            raise ValueError(f"Permanent-install target escaped the game folder: {key}")
        targets[key] = target
    return targets


def _validate_permanent_state(
    state: dict[str, Any],
    source_root: Path,
    addons_dir: Path,
) -> tuple[Path, dict[str, Path]]:
    if state.get("version") not in SUPPORTED_PERMANENT_VERSIONS:
        raise ValueError("Permanent-install state belongs to an unsupported version")
    saved_root = Path(str(state.get("source_root", ""))).resolve()
    if saved_root != source_root.resolve():
        raise ValueError("Permanent-install state points to a different game folder")
    backup_name = str(state.get("backup_directory", ""))
    backup = (_backup_root(addons_dir) / backup_name).resolve()
    if not _inside(backup, _backup_root(addons_dir)) or not backup.is_dir():
        raise ValueError("Permanent-install backup directory is missing or invalid")
    return backup, _targets_from_state(state, source_root)

def permanent_status(
    source_root: Path | None = None,
    addons_dir: Path | None = None,
) -> tuple[bool, str]:
    root = _default_source_root() if source_root is None else Path(source_root)
    add_root = Path(_RUNTIME["ADDONS_DIR"]) if addons_dir is None else Path(addons_dir)
    state = _read_json(_permanent_state_path(add_root), {})
    if not isinstance(state, dict) or not state:
        return False, "Not permanently installed"
    version = str(state.get("version", "unknown"))
    if version != PATCH_VERSION:
        return False, f"Permanent Install {version} is active and needs upgrade to {PATCH_VERSION}"
    try:
        _, targets = _validate_permanent_state(state, root, add_root)
    except ValueError as exc:
        return False, str(exc)
    entries = state.get("files", {})
    for key, target in targets.items():
        entry = entries.get(key)
        if not isinstance(entry, dict):
            return False, f"Permanent file metadata is missing: {key}"
        action = entry.get("installed_action", "write")
        if action == "delete":
            if target.exists():
                return False, f"Permanent deletion was reversed: {key}"
            continue
        if action != "write" or not target.is_file():
            return False, f"Permanent file is missing: {key}"
        try:
            current_hash = _digest_file(target)
        except OSError:
            return False, f"Could not verify permanent file: {key}"
        if current_hash != entry.get("installed_sha256"):
            return False, f"Permanent file changed: {key}"
    return True, f"Permanent Install {PATCH_VERSION} verified"

def _snapshot_layout(targets: dict[str, Path], snapshot: Path) -> None:
    layout: dict[str, bool] = {}
    for key, target in targets.items():
        existed = target.is_file()
        layout[key] = existed
        if existed:
            destination = snapshot / "files" / key
            destination.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(destination, target.read_bytes())
    _atomic_json(snapshot / "layout.json", layout)


def _restore_layout_snapshot(targets: dict[str, Path], snapshot: Path) -> None:
    layout = _read_json(snapshot / "layout.json", {})
    if not isinstance(layout, dict):
        raise ValueError("Upgrade rollback layout is invalid")
    for key, target in targets.items():
        if layout.get(key) is True:
            source = snapshot / "files" / key
            if not source.is_file():
                raise ValueError(f"Upgrade rollback file is missing: {key}")
            _atomic_write(target, source.read_bytes())
        else:
            target.unlink(missing_ok=True)


def _upgrade_permanent_install(
    root: Path,
    add_root: Path,
    existing_state: dict[str, Any],
    update_active_loader_state: bool,
) -> tuple[bool, str]:
    try:
        old_targets = _targets_from_state(existing_state, root)
        all_targets = dict(_permanent_targets(root))
        all_targets.update(old_targets)
        rollback = _unique_backup_directory(add_root)
        _snapshot_layout(all_targets, rollback)
        _atomic_json(rollback / "previous-permanent-state.json", existing_state)
    except (OSError, ValueError) as exc:
        return False, f"Permanent Install upgrade could not create its rollback snapshot: {exc}"

    ok, message = uninstall_permanent(root, add_root)
    if ok:
        ok, message = install_permanent(root, add_root, _migrating=True)
    if ok:
        if update_active_loader_state:
            state = _read_json(_permanent_state_path(add_root), {})
            _merge_loader_state(
                permanent_install=True,
                permanent_version=PATCH_VERSION,
                permanent_installed_at=state.get("installed_at"),
            )
        return True, (
            f"Permanent Install upgraded to {PATCH_VERSION}. cube_core.py was removed, "
            "NuttyMod Service and both JARs were installed beside the game files."
        )

    try:
        _restore_layout_snapshot(all_targets, rollback)
        _atomic_json(_permanent_state_path(add_root), existing_state)
    except Exception as rollback_exc:
        return False, (
            f"Upgrade failed: {message}. Automatic rollback also failed: {rollback_exc}. "
            f"Recovery snapshot: {rollback}"
        )
    return False, f"Upgrade failed and the previous permanent layout was restored: {message}"


def install_permanent(
    source_root: Path | None = None,
    addons_dir: Path | None = None,
    *,
    _migrating: bool = False,
) -> tuple[bool, str]:
    update_active_loader_state = addons_dir is None
    root = _default_source_root() if source_root is None else Path(source_root).resolve()
    add_root = (
        Path(_RUNTIME["ADDONS_DIR"]).resolve()
        if addons_dir is None
        else Path(addons_dir).resolve()
    )
    existing_state = _read_json(_permanent_state_path(add_root), {})
    if isinstance(existing_state, dict) and existing_state:
        if existing_state.get("version") != PATCH_VERSION and not _migrating:
            return _upgrade_permanent_install(
                root,
                add_root,
                existing_state,
                update_active_loader_state,
            )
        verified, detail = permanent_status(root, add_root)
        if verified:
            return True, detail
        return False, f"{detail}. Uninstall before repairing Permanent Install."

    targets = _permanent_targets(root)
    for target in targets.values():
        if not _inside(target, root):
            return False, f"Blocked permanent-install path: {target}"
    try:
        payloads = _permanent_payloads(root)
        if set(payloads) != set(targets):
            missing = sorted(set(targets) - set(payloads))
            extra = sorted(set(payloads) - set(targets))
            raise ValueError(f"Payload/target mismatch; missing={missing}, extra={extra}")
        backup = _unique_backup_directory(add_root)
    except (OSError, ValueError) as exc:
        return False, f"Permanent Install could not start: {exc}"

    entries: dict[str, dict[str, Any]] = {}
    committed: list[str] = []
    try:
        for key, target in targets.items():
            existed = target.is_file()
            entry: dict[str, Any] = {"existed_before": existed}
            if existed:
                before = target.read_bytes()
                entry["before_sha256"] = _digest_bytes(before)
                backup_path = backup / key
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write(backup_path, before)
            payload = payloads[key]
            if payload is None:
                entry["installed_action"] = "delete"
            else:
                entry["installed_action"] = "write"
                entry["installed_sha256"] = _digest_bytes(payload)
            entries[key] = entry

        for key, target in targets.items():
            payload = payloads[key]
            if payload is None:
                target.unlink(missing_ok=True)
                if target.exists():
                    raise OSError(f"Verification failed after deleting {key}")
            else:
                _atomic_write(target, payload)
                if _digest_file(target) != entries[key]["installed_sha256"]:
                    raise OSError(f"Verification failed after writing {key}")
            committed.append(key)

        manifest = {
            "schema_version": 2,
            "version": PATCH_VERSION,
            "game_edition": GAME_EDITION,
            "installed_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(),
            ),
            "source_root": str(root),
            "backup_directory": backup.name,
            "files": entries,
        }
        _atomic_json(backup / "permanent-install-manifest.json", manifest)
        _atomic_json(_permanent_state_path(add_root), manifest)
        if update_active_loader_state:
            _merge_loader_state(
                permanent_install=True,
                permanent_version=PATCH_VERSION,
                permanent_installed_at=manifest["installed_at"],
            )
        return True, (
            f"Permanent Install {PATCH_VERSION} completed. cube_core.py was removed; "
            "the launcher now imports nuttymod_core and NuttyMod Service is active. "
            "Restart and rebuild the game."
        )
    except Exception as exc:
        for key in reversed(committed):
            target = targets[key]
            entry = entries[key]
            try:
                if entry["existed_before"]:
                    _atomic_write(target, (backup / key).read_bytes())
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            _atomic_json(
                backup / "FAILED.txt.json",
                {"error": str(exc), "committed": committed},
            )
        except OSError:
            pass
        return False, f"Permanent Install failed and was rolled back: {exc}"

def uninstall_permanent(
    source_root: Path | None = None,
    addons_dir: Path | None = None,
) -> tuple[bool, str]:
    update_active_loader_state = addons_dir is None
    root = _default_source_root() if source_root is None else Path(source_root).resolve()
    add_root = (
        Path(_RUNTIME["ADDONS_DIR"]).resolve()
        if addons_dir is None
        else Path(addons_dir).resolve()
    )
    state_path = _permanent_state_path(add_root)
    state = _read_json(state_path, {})
    if not isinstance(state, dict) or not state:
        return True, "Permanent Install is not active"
    try:
        backup, targets = _validate_permanent_state(state, root, add_root)
    except ValueError as exc:
        return False, f"Uninstall blocked: {exc}"
    entries = state.get("files", {})
    if not isinstance(entries, dict):
        return False, "Uninstall blocked: file manifest is invalid"

    rollback_snapshot = backup / "before-uninstall"
    try:
        _snapshot_layout(targets, rollback_snapshot)
        for key, target in targets.items():
            entry = entries.get(key)
            if not isinstance(entry, dict):
                raise ValueError(f"Missing uninstall metadata for {key}")
            if target.is_file():
                current = target.read_bytes()
                installed_hash = entry.get("installed_sha256")
                if installed_hash and _digest_bytes(current) != installed_hash:
                    changed = backup / "post-install-changes" / key
                    changed.parent.mkdir(parents=True, exist_ok=True)
                    _atomic_write(changed, current)
            if entry.get("existed_before") is True:
                original = backup / key
                if not original.is_file():
                    raise ValueError(f"Original backup is missing for {key}")
                original_data = original.read_bytes()
                if _digest_bytes(original_data) != entry.get("before_sha256"):
                    raise ValueError(f"Original backup hash failed for {key}")
                _atomic_write(target, original_data)
            else:
                target.unlink(missing_ok=True)

        state_path.unlink(missing_ok=True)
        if update_active_loader_state:
            _merge_loader_state(
                permanent_install=False,
                permanent_uninstalled_at=time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(),
                ),
            )
        return True, (
            "Permanent Install was removed and every tracked file was restored, "
            "including cube_core.py and the original launcher import. Restart and rebuild."
        )
    except Exception as exc:
        try:
            _restore_layout_snapshot(targets, rollback_snapshot)
        except Exception as rollback_exc:
            return False, (
                f"Uninstall failed: {exc}. Installed-layout rollback also failed: "
                f"{rollback_exc}. Backup: {backup}"
            )
        return False, f"Uninstall failed and restored the installed layout: {exc}"

def _confirm(
    app: Any,
    title: str,
    lines: list[str],
    confirm_text: str,
    danger: bool = False,
) -> bool:
    pygame = _RUNTIME["_pygame"]()
    width, height = app.screen.get_size()
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    coral = _RUNTIME["_color"]("CORAL", (245, 130, 115))
    button_type = _RUNTIME["_GAME_MODULE"].Button
    fps = int(getattr(_RUNTIME["_GAME_MODULE"], "FPS", 60))
    no_button = button_type((290, 520, 230, 48), "NO / CANCEL", (230, 238, 242))
    yes_button = button_type(
        (580, 520, 230, 48),
        confirm_text,
        coral if danger else mint,
    )
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return False
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
        app.draw_background(pygame.time.get_ticks() / 1000, simple=True)
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((5, 28, 46, 175))
        app.screen.blit(shade, (0, 0))
        panel = pygame.Rect(165, 105, width - 330, 510)
        app.draw_panel(panel, 248)
        badge = app.small.render("NUTTYMOD PERMANENT INSTALL", True, coral if danger else mint)
        app.screen.blit(badge, badge.get_rect(center=(width // 2, 150)))
        heading = app.large.render(title, True, navy)
        app.screen.blit(heading, heading.get_rect(center=(width // 2, 205)))
        y = 260
        for paragraph in lines:
            for wrapped in _RUNTIME["_wrap_text"](app.small, paragraph, panel.width - 100):
                label = app.small.render(wrapped, True, muted)
                app.screen.blit(label, label.get_rect(center=(width // 2, y)))
                y += 25
            y += 7
        selected = app.wait_click([no_button, yes_button], events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(fps)
        if selected == 0:
            return False
        if selected == 1:
            return True


def _draw_operation(app: Any, title: str, detail: str) -> None:
    pygame = _RUNTIME["_pygame"]()
    width, height = app.screen.get_size()
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    app.draw_background(pygame.time.get_ticks() / 1000, simple=True)
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    shade.fill((5, 28, 46, 180))
    app.screen.blit(shade, (0, 0))
    panel = pygame.Rect(190, 180, width - 380, 300)
    app.draw_panel(panel, 248)
    badge = app.small.render(f"NUTTYMOD {PATCH_VERSION}", True, mint)
    app.screen.blit(badge, badge.get_rect(center=(width // 2, 225)))
    heading = app.large.render(title, True, navy)
    app.screen.blit(heading, heading.get_rect(center=(width // 2, 292)))
    text = app.small.render(detail, True, muted)
    app.screen.blit(text, text.get_rect(center=(width // 2, 355)))
    pygame.display.flip()


def _timed_permanent_install_screen(
    app: Any,
    operation: Callable[[], tuple[bool, str]],
    duration: float = PERMANENT_INSTALL_SECONDS,
) -> tuple[bool, str]:
    pygame = _RUNTIME["_pygame"]()
    width, height = app.screen.get_size()
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    coral = _RUNTIME["_color"]("CORAL", (245, 130, 115))
    fps = int(getattr(_RUNTIME["_GAME_MODULE"], "FPS", 60))
    duration = max(0.05, float(duration))
    commit_at = min(3.0, duration * 0.08)
    started = time.monotonic()
    executed = False
    result = (False, "Permanent Install did not run")
    failed_at: float | None = None
    stages = [
        (0.00, "PREPARING BACKUP", "Fingerprinting the current game and loader files"),
        (0.08, "REWRITING GAME", "Removing cube_core.py and installing NuttyMod Core"),
        (0.35, "INSTALLING SERVICE", "Adding nuttymod_service.py beside the game"),
        (0.58, "INSTALLING PROFILE JARS", "Copying both JARs into the game folder"),
        (0.78, "VERIFYING FILES", "Checking every installed SHA-256 fingerprint"),
        (0.94, "FINALISING ROOT MODE", "Preparing the Fall Edition 6.2 menu"),
    ]
    while True:
        elapsed = time.monotonic() - started
        if not executed and elapsed >= commit_at:
            result = operation()
            executed = True
            if not result[0]:
                failed_at = time.monotonic()
        ratio = min(1.0, elapsed / duration)
        if executed and result[0] and ratio >= 1.0:
            return result
        if failed_at is not None and time.monotonic() - failed_at >= min(3.0, duration):
            return result

        for event in pygame.event.get():
            if _RUNTIME["_common_window_event"](app, event) == "quit":
                if not executed:
                    return False, "Permanent Install cancelled before file changes"
            if (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_ESCAPE
                and not executed
            ):
                return False, "Permanent Install cancelled before file changes"

        stage, detail = stages[0][1], stages[0][2]
        for threshold, candidate, candidate_detail in stages:
            if ratio >= threshold:
                stage, detail = candidate, candidate_detail
        if failed_at is not None:
            stage, detail = "INSTALL FAILED", result[1]

        app.draw_background(pygame.time.get_ticks() / 1000, simple=True)
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((5, 28, 46, 185))
        app.screen.blit(shade, (0, 0))
        panel = pygame.Rect(135, 105, width - 270, 505)
        app.draw_panel(panel, 248)
        badge = app.small.render(
            f"NUTTYMOD {PATCH_VERSION}  /  ONE-MINUTE PERMANENT INSTALL",
            True,
            mint if failed_at is None else coral,
        )
        app.screen.blit(badge, badge.get_rect(center=(width // 2, 155)))
        heading = app.large.render(stage, True, navy)
        app.screen.blit(heading, heading.get_rect(center=(width // 2, 225)))
        detail_label = app.small.render(
            _RUNTIME["_fit_text"](app.small, detail, panel.width - 100),
            True,
            muted,
        )
        app.screen.blit(detail_label, detail_label.get_rect(center=(width // 2, 278)))

        progress = pygame.Rect(205, 350, width - 410, 26)
        pygame.draw.rect(app.screen, (207, 222, 228), progress, border_radius=13)
        fill_width = max(0, int(progress.width * ratio))
        if fill_width:
            pygame.draw.rect(
                app.screen,
                mint if failed_at is None else coral,
                (progress.x, progress.y, fill_width, progress.height),
                border_radius=13,
            )
        percent = app.large.render(f"{int(ratio * 100):02d}%", True, navy)
        app.screen.blit(percent, percent.get_rect(center=(width // 2, 430)))
        time_left = max(0, int(duration - elapsed + 0.999))
        timer = app.small.render(
            f"About {time_left} second{'s' if time_left != 1 else ''} remaining",
            True,
            muted,
        )
        app.screen.blit(timer, timer.get_rect(center=(width // 2, 478)))
        note = app.tiny.render(
            "ESC cancels only before the backup transaction begins.",
            True,
            muted,
        )
        app.screen.blit(note, note.get_rect(center=(width // 2, 542)))
        pygame.display.flip()
        app.clock.tick(fps)


def _account_settings_menu(app: Any) -> None:
    pygame = _RUNTIME["_pygame"]()
    white = _RUNTIME["_color"]("WHITE", (255, 255, 255))
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    coral = _RUNTIME["_color"]("CORAL", (245, 130, 115))
    button_type = _RUNTIME["_GAME_MODULE"].Button
    fps = int(getattr(_RUNTIME["_GAME_MODULE"], "FPS", 60))
    buttons = [
        button_type((650, 285, 420, 52), "LOG OUT", coral),
        button_type((650, 515, 420, 52), "BACK", (230, 238, 242)),
    ]

    while True:
        connection = _connection_runtime()
        account = connection.local_account_status()
        signed_in = bool(account.get("signed_in"))
        credential_present = bool(account.get("credential_present"))
        can_logout = signed_in or credential_present
        username = str(account.get("username") or "No active account")
        buttons[0].text = "LOG OUT" if can_logout else "NO ACCOUNT TO LOG OUT"
        buttons[0].accent = coral if can_logout else muted

        events = pygame.event.get()
        if not app.common_events(events):
            return
        app.draw_background(pygame.time.get_ticks() / 1000, simple=True)
        shade = pygame.Surface(app.screen.get_size(), pygame.SRCALPHA)
        shade.fill((8, 35, 57, 125))
        app.screen.blit(shade, (0, 0))
        app.title_block(
            f"NuttyMod {PATCH_VERSION}",
            "Account Settings",
            "Manage the local NuttyMod account used by Go Auth.",
            70,
        )

        panel = pygame.Rect(90, 205, 490, 360)
        app.draw_panel(panel, 246)
        status_text = "SIGNED IN LOCALLY" if signed_in else "SIGNED OUT"
        status = app.font.render(status_text, True, mint if signed_in else muted)
        app.screen.blit(status, (126, 245))
        detail_lines = [
            f"Account: {username}",
            "",
            "The login token is stored only on this computer.",
            "Your setup phrase is never stored.",
            "",
            "Log Out removes the active local token and the",
            "last connection state. The current game remains",
            "open; the next launch requests account setup.",
        ]
        y = 294
        for value in detail_lines:
            label = app.small.render(
                _RUNTIME["_fit_text"](app.small, value, panel.width - 70),
                True,
                navy if value else muted,
            )
            app.screen.blit(label, (126, y))
            y += 31

        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(fps)
        if selected is None:
            continue
        if selected == 0:
            if not can_logout:
                app.notify("No active local NuttyMod account was found.", 5)
                continue
            confirmed = _confirm(
                app,
                "LOG OUT OF NUTTYMOD?",
                [
                    f"Account: {username}",
                    "This permanently removes the active local login token from this computer.",
                    "The current game stays open. Next launch requires local account setup.",
                ],
                "YES, LOG OUT",
                danger=True,
            )
            if confirmed:
                ok, message = connection.logout_local_account(
                    Path(_RUNTIME["ADDONS_DIR"])
                )
                app.notify(message, 9)
        elif selected == 1:
            return

def _nuttymod_settings_menu(app: Any) -> None:
    pygame = _RUNTIME["_pygame"]()
    white = _RUNTIME["_color"]("WHITE", (255, 255, 255))
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    coral = _RUNTIME["_color"]("CORAL", (245, 130, 115))
    yellow = _RUNTIME["_color"]("YELLOW", (255, 225, 105))
    button_type = _RUNTIME["_GAME_MODULE"].Button
    fps = int(getattr(_RUNTIME["_GAME_MODULE"], "FPS", 60))
    buttons = [
        button_type((555, 205, 420, 48), "UPDATES & GAME SETTINGS", yellow),
        button_type((555, 267, 420, 48), "VERIFY ADD-ONS & MODS", mint),
        button_type((555, 329, 420, 48), "PERMANENT INSTALL", white),
        button_type((555, 391, 420, 48), "ACCOUNT SETTINGS", white),
        button_type((555, 453, 420, 48), "TERMS OF SERVICE", white),
        button_type((555, 577, 420, 48), "BACK", (230, 238, 242)),
    ]

    while True:
        state = _read_json(_permanent_state_path(), {})
        has_state = isinstance(state, dict) and bool(state)
        state_version = str(state.get("version", "")) if has_state else ""
        installed, permanent_detail = permanent_status()
        needs_upgrade = has_state and state_version != PATCH_VERSION
        remove_mode = has_state and not needs_upgrade
        if needs_upgrade:
            buttons[2].text = f"UPGRADE PERMANENT INSTALL  |  {PATCH_VERSION}"
            buttons[2].accent = yellow
        elif remove_mode:
            buttons[2].text = "UNINSTALL PERMANENT INSTALL"
            buttons[2].accent = coral
        else:
            buttons[2].text = "PERMANENT INSTALL  |  1 MINUTE"
            buttons[2].accent = mint

        events = pygame.event.get()
        if not app.common_events(events):
            return
        app.draw_background(pygame.time.get_ticks() / 1000, simple=True)
        shade = pygame.Surface(app.screen.get_size(), pygame.SRCALPHA)
        shade.fill((8, 35, 57, 115))
        app.screen.blit(shade, (0, 0))
        app.title_block(
            f"NuttyMod {PATCH_VERSION}",
            "NuttyMod Settings",
            "Account, updates, verification, and reversible Permanent Install.",
            70,
        )
        info = pygame.Rect(90, 205, 405, 358)
        app.draw_panel(info, 245)
        if needs_upgrade:
            status, status_color = "PERMANENT MODE UPGRADE READY", yellow
        elif installed:
            status, status_color = "PERMANENT MODE ACTIVE", mint
        elif has_state:
            status, status_color = "PERMANENT MODE NEEDS UNINSTALL", coral
        else:
            status, status_color = "SESSION MODE", muted
        heading = app.font.render(status, True, status_color)
        app.screen.blit(heading, (126, 242))
        detail_lines = [
            f"Game: The Cube Beta Fall Edition {GAME_EDITION}",
            f"Loader / Service: NuttyMod {PATCH_VERSION}",
            permanent_detail,
            "",
            "The one-minute installer deletes cube_core.py",
            "after backup, rewrites the launcher to use",
            "nuttymod_core, and puts both JARs plus",
            "nuttymod_service.py beside the game files.",
            "Uninstall restores every verified original.",
        ]
        y = 287
        for text in detail_lines:
            label = app.small.render(
                _RUNTIME["_fit_text"](app.small, text, info.width - 55),
                True,
                navy if text else muted,
            )
            app.screen.blit(label, (126, y))
            y += 27
        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(fps)
        if selected is None:
            continue
        if selected == 0:
            if _LEGACY_SETTINGS_MENU is not None:
                _LEGACY_SETTINGS_MENU(app)
        elif selected == 1:
            app.addons.reload()
            _RUNTIME["_verification_screen"](app)
        elif selected == 2:
            if remove_mode:
                confirmed = _confirm(
                    app,
                    "UNINSTALL PERMANENT MODE?",
                    [
                        "This restores cube_core.py, the original launcher import, and "
                        "every other tracked game and loader file from verified backups.",
                        "Files changed after installation are preserved in update_backups "
                        "before restoration. Restart and rebuild afterward.",
                    ],
                    "YES, UNINSTALL",
                    danger=True,
                )
                if confirmed:
                    _draw_operation(app, "RESTORING BACKUPS", "Restoring cube_core.py and removing NuttyMod service files")
                    ok, message = uninstall_permanent()
                    app.notify(message, 10)
            else:
                verb = "UPGRADE" if needs_upgrade else "INSTALL"
                confirmed = _confirm(
                    app,
                    f"{verb} PERMANENT MODE?",
                    [
                        "The one-minute installer creates verified backups, rewrites "
                        "the game launcher to import nuttymod_core, and removes cube_core.py.",
                        "It installs nuttymod_service.py and both NuttyMod profile JARs "
                        "beside the game files and in source add-ons.",
                        "A failed transaction restores the previous permanent or Stable layout.",
                    ],
                    f"YES, {verb}",
                )
                if confirmed:
                    ok, message = _timed_permanent_install_screen(app, install_permanent)
                    app.notify(message, 12)
        elif selected == 3:
            _account_settings_menu(app)
        elif selected == 4:
            _RUNTIME["_terms_dialog"](app, force=True)
        elif selected == 5:
            return

def _modified_main_menu(app: Any) -> str:
    pygame = _RUNTIME["_pygame"]()
    width, _ = app.screen.get_size()
    white = _RUNTIME["_color"]("WHITE", (255, 255, 255))
    ink = _RUNTIME["_color"]("INK", (15, 50, 70))
    navy = _RUNTIME["_color"]("NAVY", (20, 70, 100))
    muted = _RUNTIME["_color"]("MUTED", (90, 115, 125))
    yellow = _RUNTIME["_color"]("YELLOW", (255, 225, 105))
    mint = _RUNTIME["_color"]("MINT", (73, 205, 160))
    coral = _RUNTIME["_color"]("CORAL", (245, 130, 115))
    button_type = _RUNTIME["_GAME_MODULE"].Button
    fps = int(getattr(_RUNTIME["_GAME_MODULE"], "FPS", 60))
    pygame_version, pymunk_version = _RUNTIME["_runtime_versions"]()

    labels = [
        "PLAY SOLO",
        "PLAY MULTIPLAYER",
        "NUTTYMOD ADD-ONS",
        "NUTTYMOD MODS  |  STABLE",
        "NUTTYMOD STUDIOS",
        "NUTTYMOD SETTINGS",
        "QUIT",
    ]
    actions = [
        "single",
        "multiplayer",
        "addons",
        "mods",
        "studios",
        "nutty_settings",
        "quit",
    ]
    accents = [yellow, mint, white, white, mint, white, (255, 181, 165)]
    buttons = [
        button_type((590, 205 + index * 56, 420, 44), label, accents[index])
        for index, label in enumerate(labels)
    ]

    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return "quit"
        records = list(app.addons.records)
        active = sum(bool(record.ok) for record in records)
        disabled = sum(
            record.detail == _RUNTIME["DISABLED_DETAIL"] for record in records
        )
        failed = max(0, len(records) - active - disabled)
        permanent, _ = permanent_status()

        app.draw_background(pygame.time.get_ticks() / 1000)
        shade = pygame.Surface(app.screen.get_size(), pygame.SRCALPHA)
        shade.fill((8, 35, 57, 110))
        app.screen.blit(shade, (0, 0))
        badge = app.small.render(
            f"NUTTYMOD {PATCH_VERSION}  /  "
            f"{'PERMANENT' if permanent else 'SESSION'} ROOT MODE",
            True,
            navy,
        )
        badge_rect = badge.get_rect(center=(width // 2, 39)).inflate(34, 13)
        pygame.draw.rect(app.screen, (255, 238, 162), badge_rect, border_radius=14)
        app.screen.blit(badge, badge.get_rect(center=badge_rect.center))

        title_a = app.large.render("THE CUBE BETA", True, white)
        title_b = app.large.render(f"FALL EDITION {GAME_EDITION}", True, white)
        app.screen.blit(title_a, title_a.get_rect(center=(width // 2, 91)))
        app.screen.blit(title_b, title_b.get_rect(center=(width // 2, 137)))
        below = app.small.render(
            "NuttyMod Root Mode  |  Add-ons  |  Mods  |  Studios",
            True,
            white,
        )
        app.screen.blit(below, below.get_rect(center=(width // 2, 174)))

        panel = pygame.Rect(75, 205, 455, 374)
        app.draw_panel(panel, 244)
        cube = pygame.Rect(112, 243, 88, 88)
        pygame.draw.rect(app.screen, mint, cube, border_radius=20)
        pygame.draw.rect(app.screen, white, cube, 3, border_radius=20)
        root_label = app.large.render("ROOT", True, ink)
        app.screen.blit(root_label, (226, 247))
        active_label = app.font.render("MODE IS ACTIVE", True, navy)
        app.screen.blit(active_label, (228, 295))
        pygame.draw.line(app.screen, (202, 220, 228), (110, 354), (495, 354), 2)

        stats = [
            ("ACTIVE", str(active), mint),
            ("DISABLED", str(disabled), muted),
            ("FAILED", str(failed), coral),
        ]
        for index, (label, value, color) in enumerate(stats):
            center_x = 152 + index * 130
            number = app.large.render(value, True, color)
            app.screen.blit(number, number.get_rect(center=(center_x, 402)))
            caption = app.tiny.render(label, True, muted)
            app.screen.blit(caption, caption.get_rect(center=(center_x, 440)))
        pygame.draw.line(app.screen, (202, 220, 228), (110, 466), (495, 466), 2)
        runtime_a = app.small.render(f"Pygame {pygame_version}", True, navy)
        runtime_b = app.small.render(f"Pymunk {pymunk_version}", True, navy)
        app.screen.blit(runtime_a, (113, 490))
        app.screen.blit(runtime_b, (305, 490))
        status = app.small.render(
            "Permanent core verified" if permanent else "Permanent Install available in settings",
            True,
            mint if permanent else muted,
        )
        app.screen.blit(status, (113, 532))

        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(fps)
        if selected is None:
            continue
        action = actions[selected]
        if action == "studios":
            _RUNTIME["_studios_menu"](app)
        elif action == "mods":
            _RUNTIME["_modified_mods_menu"](app)
        elif action == "nutty_settings":
            _nuttymod_settings_menu(app)
        elif action == "single":
            if _RUNTIME["_single_player_loading_screen"](app):
                return "single"
        else:
            return action


def activate(runtime: dict[str, Any]) -> None:
    global _RUNTIME
    global _LEGACY_LOADING_SCREEN
    global _LEGACY_SETTINGS_MENU
    global _LEGACY_JAR_RUNNER

    _RUNTIME = runtime
    _promote_runtime_mods(runtime)
    _LEGACY_LOADING_SCREEN = runtime["_loading_screen"]
    _LEGACY_SETTINGS_MENU = runtime["_modified_settings_menu"]
    _LEGACY_JAR_RUNNER = runtime["_run_jar_addon"]

    runtime["LOADER_VERSION"] = PATCH_VERSION
    runtime["TERMS_VERSION"] = TERMS_VERSION
    runtime["INSTALL_DURATION_SECONDS"] = 60.0
    runtime["CONNECTION_DURATION_SECONDS"] = CONNECTION_SECONDS
    runtime["EXTRA_ADDON_SUFFIXES"] = {
        ".bat",
        ".cs",
        ".c#",
        ".jar",
    }
    runtime["SUPPORTED_ADDON_SUFFIXES"] = {
        ".py",
        ".rb",
        ".bat",
        ".cs",
        ".c#",
        ".jar",
    }
    protected = set(runtime.get("PROTECTED_ADDONS", set()))
    protected.update(
        {
            "nuttymod_loader.py",
            CONNECTION_MODULE_NAME,
            SERVICE_NAME,
            PATCH_JAR_NAME,
            PROFILE_JAR_NAME,
        }
    )
    runtime["PROTECTED_ADDONS"] = protected
    runtime["_run_jar_addon"] = _run_jar_addon
    runtime["_loading_screen"] = _loading_screen
    runtime["_connection_screen"] = _connection_screen
    runtime["_modified_main_menu"] = _modified_main_menu
    runtime["_nuttymod_settings_menu"] = _nuttymod_settings_menu
    runtime["_account_settings_menu"] = _account_settings_menu
    runtime["_install_permanent"] = install_permanent
    runtime["_uninstall_permanent"] = uninstall_permanent
    runtime["_permanent_status"] = permanent_status

    _ensure_profile_assets()
    _ensure_game_sidecars()
    game_module = runtime.get("_GAME_MODULE")
    game_class = getattr(game_module, "GameApp", None)
    if game_class is not None:
        game_class.main_menu = _modified_main_menu
        game_class.nuttymod_settings_menu = _nuttymod_settings_menu
        game_class.account_settings_menu = _account_settings_menu
