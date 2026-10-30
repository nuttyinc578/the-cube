from __future__ import annotations

import importlib.util
import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cube_core import AddonManager


ROOT = Path(__file__).resolve().parent


def load_nuttymod_patch():
    patch_path = ROOT / "addons" / "nuttymod" / "_nuttymod_v140_patch.py"
    spec = importlib.util.spec_from_file_location("nuttymod_isolation_test", patch_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the NuttyMod patch")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_cpeloader_game(folder: str, version: str) -> Path:
    root = Path(folder)
    (root / "cube_core.py").write_text(
        f'APP_TITLE = "The Cube Beta Halloween Update"\nVERSION = "{version}"\n',
        encoding="utf-8",
    )
    shutil.copy2(ROOT / "cpeloader.py", root / "cpeloader.py")
    (root / "cpeloader_core_runtime.js").write_text("// test runtime\n", encoding="utf-8")
    (root / "cpeloader_core.rb").write_text("# test runtime\n", encoding="utf-8")
    return root


class NuttyModIsolationTests(unittest.TestCase):
    def test_optional_packs_are_only_in_nuttymod_addons(self):
        for name in ('fun_mode.py', 'fun_mode.rb', 'physics_3d.py', 'physics_3d.rb'):
            self.assertFalse((ROOT / 'addons' / name).exists(), name)
            self.assertTrue((ROOT / 'addons' / 'nuttymod' / 'addons' / name).is_file(), name)

    def test_addon_manager_does_not_scan_nuttymod_subfolder(self):
        with tempfile.TemporaryDirectory() as folder:
            addons = Path(folder)
            isolated = addons / "nuttymod"
            isolated.mkdir()
            (isolated / "nuttymod_loader.py").write_text(
                "raise RuntimeError('must never auto-load')\n",
                encoding="utf-8",
            )
            (addons / "safe.py").write_text(
                "ADDON = {'name': 'Safe', 'version': '1.0'}\n",
                encoding="utf-8",
            )
            with mock.patch("cube_core.bundle_path", return_value=addons):
                manager = AddonManager(addons)
            self.assertEqual([record.filename for record in manager.records], ["safe.py"])
            self.assertTrue(manager.records[0].ok)

    def test_permanent_rewrite_is_disabled_in_isolated_mode(self):
        module = load_nuttymod_patch()
        with tempfile.TemporaryDirectory() as folder:
            ok, message = module.install_permanent(Path(folder), Path(folder) / "addons")
        self.assertFalse(ok)
        self.assertIn("disabled", message.lower())
        self.assertTrue(module.ISOLATED_MODE)

    def test_halloween_versions_are_supported(self):
        module = load_nuttymod_patch()
        self.assertEqual(module.STABLE_LOADER_VERSION, "1.4.5")
        self.assertEqual(module.BETA_LOADER_VERSION, "1.5.0-beta")
        for version in ("6.4.0", "6.4.1", "6.4.2-nightly"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                root = make_cpeloader_game(folder, version)
                self.assertEqual(module._require_supported_game(root), version)

    def test_cpeloader_unlock_is_required(self):
        module = load_nuttymod_patch()
        with tempfile.TemporaryDirectory() as folder:
            root = make_cpeloader_game(folder, "6.4.1")
            with self.assertRaises(PermissionError):
                module._require_cpeloader_unlock(root)
            module._cpeloader(root).unlock()
            self.assertTrue(module._require_cpeloader_unlock(root).unlocked)

    def test_channel_switch_never_rewrites_cube_core(self):
        module = load_nuttymod_patch()
        with tempfile.TemporaryDirectory() as folder:
            root = make_cpeloader_game(folder, "6.4.2-nightly")
            module._cpeloader(root).unlock()
            core = root / "cube_core.py"
            original = core.read_bytes()
            update_state = root / ".nuttymod_update_state.json"
            with (
                mock.patch.object(module, "_game_root", return_value=root),
                mock.patch.object(module, "_update_state_path", return_value=update_state),
                mock.patch.object(module, "_ensure_profile_assets"),
            ):
                self.assertEqual(module._set_isolated_update_channel("beta"), "beta")
                state = json.loads(update_state.read_text(encoding="utf-8"))
                self.assertEqual(state["loader_version"], "1.5.0-beta")
                self.assertEqual(core.read_bytes(), original)
                self.assertEqual(module._set_isolated_update_channel("stable"), "stable")
                state = json.loads(update_state.read_text(encoding="utf-8"))
                self.assertEqual(state["loader_version"], "1.4.5")
                self.assertEqual(core.read_bytes(), original)

    def test_python312_uses_readable_compatibility_runtime(self):
        package = ROOT / "addons" / "nuttymod"
        runtime = package / "nuttymod_runtime_v122.pyc"
        if runtime.read_bytes()[:4] == importlib.util.MAGIC_NUMBER:
            self.skipTest("Legacy visual runtime matches this interpreter")
        with tempfile.TemporaryDirectory() as folder:
            game = make_cpeloader_game(folder, "6.4.1")
            isolated = game / "addons" / "nuttymod"
            isolated.mkdir(parents=True)
            for name in (
                "nuttymod_loader.py",
                "_nuttymod_v140_patch.py",
                "nuttymod_runtime_v122.pyc",
                "nuttymod_service.py",
                "nuttymod_loader_patch.jar",
                "nuttymod_root_mode_profile.jar",
            ):
                shutil.copy2(package / name, isolated / name)
            optional = isolated / "addons"
            optional.mkdir()
            (optional / "sample.batch").write_text("@echo off\n", encoding="utf-8")
            module_path = isolated / "nuttymod_loader.py"
            spec = importlib.util.spec_from_file_location(
                "nuttymod_python312_compatibility_test", module_path
            )
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            with self.assertRaises(PermissionError):
                spec.loader.exec_module(module)
            module._load_cpeloader(game).CPELoader(game).unlock()
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.LOADER_VERSION, "1.4.5")
            self.assertEqual(module.ADDON["version"], "1.4.5")
            self.assertEqual(module.verify_addons()[0]["filename"], "sample.batch")
            before = (game / "cube_core.py").read_bytes()
            ok, message = module.select_update_channel("beta")
            self.assertTrue(ok, message)
            self.assertEqual((game / "cube_core.py").read_bytes(), before)
            state = json.loads(
                (isolated / ".nuttymod_update_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["loader_version"], "1.5.0-beta")

    def test_portable_build_reads_version_from_executable(self):
        package = ROOT / "addons" / "nuttymod"
        runtime = package / "nuttymod_runtime_v122.pyc"
        if runtime.read_bytes()[:4] == importlib.util.MAGIC_NUMBER:
            self.skipTest("Legacy visual runtime matches this interpreter")
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            shutil.copy2(
                ROOT / "dist" / "The Cube Beta Halloween Update.exe",
                game / "The Cube Beta Halloween Update.exe",
            )
            for name in ("cpeloader.py", "cpeloader_core_runtime.js", "cpeloader_core.rb"):
                shutil.copy2(ROOT / name, game / name)
            (game / "cpeloader_state.json").write_text(
                json.dumps(
                    {
                        "unlocked": True,
                        "components": {
                            "cpeloader.py": True,
                            "cpeloader_core_runtime.js": True,
                            "cpeloader_core.rb": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            isolated = game / "addons" / "nuttymod"
            isolated.mkdir(parents=True)
            for name in (
                "nuttymod_loader.py",
                "_nuttymod_v140_patch.py",
                "nuttymod_runtime_v122.pyc",
                "nuttymod_service.py",
                "nuttymod_loader_patch.jar",
                "nuttymod_root_mode_profile.jar",
            ):
                shutil.copy2(package / name, isolated / name)
            spec = importlib.util.spec_from_file_location(
                "nuttymod_portable_version_test", isolated / "nuttymod_loader.py"
            )
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module._NUTTYMOD_GAME_VERSION, "6.4.1")
            self.assertEqual(module.LOADER_VERSION, "1.4.5")

    def test_security_door_is_main_game_code(self):
        source = (ROOT / "halloween_update.py").read_text(encoding="utf-8")
        self.assertIn('"SECURITY ???"', source)
        self.assertIn("def _security_door", source)
        security_door = source.split("def _security_door", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("nuttymod", security_door.lower())


if __name__ == "__main__":
    unittest.main()
