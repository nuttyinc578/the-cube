"""NuttyMod Loader for The Cube Beta Halloween Update.

Stable uses NuttyMod 1.4.5 and the Beta channel uses 1.5.0-beta.  This
bootstrap deliberately stays inside ``addons/nuttymod`` and requires the
game's real CPELoader unlock before the preserved runtime can start.
"""

from __future__ import annotations

import importlib.util
import hashlib
import marshal
from pathlib import Path
import re
import sys


_BOOTSTRAP_DIR = Path(__file__).resolve().parent
_RUNTIME_FILE = _BOOTSTRAP_DIR / "nuttymod_runtime_v122.pyc"
STABLE_LOADER_VERSION = "1.4.5"
BETA_LOADER_VERSION = "1.5.0-beta"
SUPPORTED_GAME_VERSIONS = ("6.4.0", "6.4.1", "6.4.2-nightly", "6.4.2", "6.4.3-nightly", "6.4.3-nightly.2")
CPELOADER_COMPONENTS = (
    "cpeloader.py",
    "cpeloader_core_runtime.js",
    "cpeloader_core.rb",
)


def _find_game_root() -> Path:
    for candidate in (_BOOTSTRAP_DIR, *_BOOTSTRAP_DIR.parents):
        has_game = any((candidate/name).is_file() for name in
            ('cube_core.py', 'The Cube Beta Halloween Update.exe', 'The Cube Beta Nightly.exe'))
        if has_game and (candidate / "cpeloader.py").is_file():
            return candidate
    raise RuntimeError(
        "NuttyMod could not find the Halloween game root or CPELoader. "
        "Keep addons/nuttymod inside a complete game installation."
    )


def _windows_executable_version(path: Path) -> str | None:
    if sys.platform != "win32" or not path.is_file():
        return None
    try:
        import ctypes

        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(
            str(path), 0, size, buffer
        ):
            return None
        pointer = ctypes.c_void_p()
        length = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(
            buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)
        ):
            return None
        values = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
        major = values[2] >> 16
        minor = values[2] & 0xFFFF
        patch = values[3] >> 16
        version = f"{major}.{minor}.{patch}"
        return version + ("-nightly" if values[6] & values[7] & 0x2 else "")
    except (AttributeError, OSError, ValueError):
        return None


def _game_version(root: Path) -> str:
    core = root / ("release_info.py" if (root/"release_info.py").is_file() else "cube_core.py")
    if core.is_file():
        try:
            source = core.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise RuntimeError(f"NuttyMod could not read cube_core.py: {exc}") from exc
        match = re.search(
            r'^VERSION\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE
        )
        if match:
            return match.group(1)
    for name in ('The Cube Beta Nightly.exe', 'The Cube Beta Halloween Update.exe'):
        version = _windows_executable_version(root/name)
        if version:
            return version
    raise RuntimeError("NuttyMod could not identify the Halloween game version.")


def _require_supported_halloween_game(root: Path) -> str:
    version = _game_version(root)
    if version not in SUPPORTED_GAME_VERSIONS:
        supported = ", ".join(SUPPORTED_GAME_VERSIONS)
        raise RuntimeError(
            f"The Cube Beta {version} is not supported by this NuttyMod build. "
            f"Supported Halloween versions: {supported}."
        )
    return version


def _load_cpeloader(root: Path):
    path = root / "cpeloader.py"
    spec = importlib.util.spec_from_file_location("_nuttymod_cpeloader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("NuttyMod could not open cpeloader.py.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _require_cpeloader_unlock(root: Path) -> None:
    missing = [name for name in CPELOADER_COMPONENTS if not (root / name).is_file()]
    if missing:
        raise RuntimeError(
            "CPELoader is incomplete. Reinstall the game; missing: "
            + ", ".join(missing)
        )
    loader = _load_cpeloader(root).CPELoader(root)
    loader.require_flash()


_NUTTYMOD_GAME_ROOT = _find_game_root()
_NUTTYMOD_GAME_VERSION = _require_supported_halloween_game(_NUTTYMOD_GAME_ROOT)
_require_cpeloader_unlock(_NUTTYMOD_GAME_ROOT)

_patch_path = _BOOTSTRAP_DIR / "_nuttymod_v140_patch.py"
_patch_spec = importlib.util.spec_from_file_location(
    "_nuttymod_v140_patch_runtime",
    _patch_path,
)
if _patch_spec is None or _patch_spec.loader is None:
    raise RuntimeError("NuttyMod 1.4.5 / 1.5.0-beta patch could not be opened.")
_patch_module = importlib.util.module_from_spec(_patch_spec)
_patch_spec.loader.exec_module(_patch_module)
_patch_module._RUNTIME.update(
    {
        "_NUTTYMOD_GAME_ROOT": _NUTTYMOD_GAME_ROOT,
        "_NUTTYMOD_GAME_VERSION": _NUTTYMOD_GAME_VERSION,
    }
)

if not _RUNTIME_FILE.is_file():
    raise RuntimeError(
        "NuttyMod runtime is missing. Reinstall nuttymod_runtime_v122.pyc "
        "from the NuttyMod 1.4.5 / 1.5.0-beta package."
    )

_runtime_bytes = _RUNTIME_FILE.read_bytes()
if _runtime_bytes[:4] == importlib.util.MAGIC_NUMBER:
    exec(marshal.loads(_runtime_bytes[16:]), globals(), globals())
    _patch_module.activate(globals())
else:
    # The preserved visual runtime was compiled for Python 3.10. Halloween
    # builds use Python 3.12, so they receive this readable compatibility API
    # instead of attempting to execute incompatible bytecode.
    LOADER_VERSION = _patch_module._current_loader_version()
    SUPPORTED_ADDON_SUFFIXES = {
        ".py",
        ".rb",
        ".bat",
        ".batch",
        ".cs",
        ".c#",
        ".jar",
    }
    ADDON = {
        "name": "NuttyMod Halloween Loader",
        "version": LOADER_VERSION,
        "author": "NuttyMod Studios",
        "description": (
            "CPELoader-locked Stable/Beta loader for Halloween 6.4.x."
        ),
        "shapes": [
            {
                "name": "Root Prism",
                "kind": "polygon",
                "sides": 6,
                "size": 35,
                "color": [171, 99, 255],
                "weight": 1.15,
            }
        ],
        "events": [
            {
                "name": "Kernel Pulse",
                "duration": 6,
                "wind": 480,
                "gravity_scale": 0.45,
                "spawn_count": 5,
                "banner": "NuttyMod Kernel Pulse is active!",
                "color": [199, 139, 255],
            }
        ],
    }

    def select_update_channel(channel: str) -> tuple[bool, str]:
        """Select Stable or Beta without changing any game-core file."""
        if str(channel).casefold() == "beta":
            return _patch_module._install_isolated_beta()
        return _patch_module._restore_isolated_stable()

    def verify_addons() -> list[dict[str, str]]:
        """Return SHA-256 verification rows without executing optional packs."""
        directory = _BOOTSTRAP_DIR / "addons"
        rows: list[dict[str, str]] = []
        if not directory.is_dir():
            return rows
        for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
            if not path.is_file() or path.suffix.casefold() not in SUPPORTED_ADDON_SUFFIXES:
                continue
            rows.append(
                {
                    "filename": path.name,
                    "type": path.suffix.casefold(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        return rows

    def register(api):
        api.about(
            name=ADDON["name"],
            version=ADDON["version"],
            author=ADDON["author"],
            description=ADDON["description"],
        )
        for shape in ADDON["shapes"]:
            api.shape(**shape)
        for event in ADDON["events"]:
            api.event(**event)

    def on_load(app, userdata=None) -> None:
        """Attach the version/channel controller to a verified Root session."""
        _require_cpeloader_unlock(_NUTTYMOD_GAME_ROOT)
        app.nuttymod_loader_version = LOADER_VERSION
        app.nuttymod_loader_channel = _patch_module._selected_channel()
        app.nuttymod_supported_game_versions = SUPPORTED_GAME_VERSIONS
        app.nuttymod_verify_addons = verify_addons
        app.nuttymod_select_update_channel = select_update_channel
