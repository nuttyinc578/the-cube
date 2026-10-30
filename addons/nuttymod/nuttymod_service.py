"""Local health service for NuttyMod.

This is an in-game Python service module, not a Windows service. It never asks
for administrator privileges and does not run when the game is closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


SERVICE_NAME = "NuttyMod Service"
SERVICE_VERSION = "1.4.5"
BETA_SERVICE_VERSION = "1.5.0-beta"
SUPPORTED_GAME_VERSIONS = ("6.4.0", "6.4.1", "6.4.2-nightly")
CPELOADER_COMPONENTS = (
    "cpeloader.py",
    "cpeloader_core_runtime.js",
    "cpeloader_core.rb",
)
PROFILE_JARS = (
    "nuttymod_loader_patch.jar",
    "nuttymod_root_mode_profile.jar",
)


def _game_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    location = Path(__file__).resolve().parent
    if location.name.casefold() == "nuttymod" and location.parent.name.casefold() == "addons":
        return location.parent.parent
    return location.parent if location.name.casefold() == "addons" else location


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def health_report(game_root: Path | None = None) -> dict[str, Any]:
    root = _game_root() if game_root is None else Path(game_root).resolve()
    addons = root / "addons"
    isolated = addons / "nuttymod"
    state = _read_json(isolated / ".nuttymod_permanent_install.json")
    if not state:
        state = _read_json(addons / ".nuttymod_permanent_install.json")
    if not state:
        state = _read_json(root / "dist" / "addons" / ".nuttymod_permanent_install.json")
    permanent = bool(state)
    source_value = str(state.get("source_root", "")).strip() if permanent else ""
    source_root = Path(source_value).resolve() if source_value else root
    cube_removed = not (source_root / "cube_core.py").exists()
    core_ready = (
        (source_root / "nuttymod_core.py").is_file()
        and (source_root / "nuttymod_cube_core.py").is_file()
    )
    jars = {
        name: (isolated / name).is_file() or (root / name).is_file() or (addons / name).is_file()
        for name in PROFILE_JARS
    }
    update_state = _read_json(isolated / ".nuttymod_update_state.json")
    beta = str(update_state.get("channel", "stable")).casefold() == "beta"
    selected_version = BETA_SERVICE_VERSION if beta else SERVICE_VERSION
    cpeloader_state = _read_json(root / "cpeloader_state.json")
    component_state = cpeloader_state.get("components", {})
    cpeloader_unlocked = (
        cpeloader_state.get("unlocked") is True
        and isinstance(component_state, dict)
        and all(
            component_state.get(name) is True and (root / name).is_file()
            for name in CPELOADER_COMPONENTS
        )
    )
    return {
        "service": SERVICE_NAME,
        "version": selected_version,
        "stable_version": SERVICE_VERSION,
        "beta_version": BETA_SERVICE_VERSION,
        "supported_game_versions": list(SUPPORTED_GAME_VERSIONS),
        "channel": "beta" if beta else "stable",
        "game_root": str(root),
        "source_root": str(source_root),
        "permanent_install": permanent,
        "cube_core_removed": cube_removed,
        "nuttymod_core": (source_root / "nuttymod_core.py").is_file(),
        "nuttymod_cube_core": (source_root / "nuttymod_cube_core.py").is_file(),
        "profile_jars": jars,
        "cpeloader_unlocked": cpeloader_unlocked,
        "healthy": (
            all(jars.values())
            and cpeloader_unlocked
            and (not permanent or (cube_removed and core_ready))
        ),
    }


def register(api: Any) -> None:
    api.about(
        name=SERVICE_NAME,
        version=SERVICE_VERSION,
        author="NuttyMod Studios",
        description=(
            "Local Halloween compatibility, CPELoader unlock, and isolated "
            "Root Mode health service; not an operating-system service."
        ),
    )
