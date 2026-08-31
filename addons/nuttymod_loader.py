"""NuttyMod Loader 1.4.2 bootstrap for The Cube Beta Fall Edition 6.2.

The preserved runtime supplies Add-ons, stable Mods, Studios, verification,
and update screens. The readable feature layer adds the upgraded Fall Edition
menu, the two-minute local Node.js v22 / Go Auth / Electron-compatible
connection, an in-game health service, game-root JAR profiles, and reversible
Permanent Install.
"""

from __future__ import annotations

import importlib.util
import marshal
from pathlib import Path


_BOOTSTRAP_DIR = Path(__file__).resolve().parent
_RUNTIME_FILE = _BOOTSTRAP_DIR / "nuttymod_runtime_v122.pyc"

if not _RUNTIME_FILE.is_file():
    raise RuntimeError(
        "NuttyMod runtime is missing. Reinstall nuttymod_runtime_v122.pyc."
    )

_runtime_bytes = _RUNTIME_FILE.read_bytes()
if _runtime_bytes[:4] != importlib.util.MAGIC_NUMBER:
    raise RuntimeError(
        "NuttyMod runtime does not match this Python version. Reinstall NuttyMod."
    )

exec(marshal.loads(_runtime_bytes[16:]), globals(), globals())

_patch_path = _BOOTSTRAP_DIR / "_nuttymod_v140_patch.py"
_patch_spec = importlib.util.spec_from_file_location(
    "_nuttymod_v140_patch_runtime",
    _patch_path,
)
if _patch_spec is None or _patch_spec.loader is None:
    raise RuntimeError("NuttyMod 1.4.2 patch could not be opened.")
_patch_module = importlib.util.module_from_spec(_patch_spec)
_patch_spec.loader.exec_module(_patch_module)
_patch_module.activate(globals())
