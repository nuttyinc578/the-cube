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
SERVICE_VERSION = "1.4.2"
PROFILE_JARS = (
    "nuttymod_loader_patch.jar",
    "nuttymod_root_mode_profile.jar",
)


def _game_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    location = Path(__file__).resolve().parent
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
        name: (root / name).is_file() or (addons / name).is_file()
        for name in PROFILE_JARS
    }
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "game_root": str(root),
        "source_root": str(source_root),
        "permanent_install": permanent,
        "cube_core_removed": cube_removed,
        "nuttymod_core": (source_root / "nuttymod_core.py").is_file(),
        "nuttymod_cube_core": (source_root / "nuttymod_cube_core.py").is_file(),
        "profile_jars": jars,
        "healthy": all(jars.values()) and (not permanent or (cube_removed and core_ready)),
    }


def register(api: Any) -> None:
    api.about(
        name=SERVICE_NAME,
        version=SERVICE_VERSION,
        author="NuttyMod Studios",
        description=(
            "Local Root Mode health and Permanent Install status service; "
            "not an operating-system service."
        ),
    )
