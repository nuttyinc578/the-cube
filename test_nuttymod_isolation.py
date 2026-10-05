from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cube_core import AddonManager


ROOT = Path(__file__).resolve().parent


class NuttyModIsolationTests(unittest.TestCase):
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
        patch_path = ROOT / "addons" / "nuttymod" / "_nuttymod_v140_patch.py"
        spec = importlib.util.spec_from_file_location("nuttymod_isolation_test", patch_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            ok, message = module.install_permanent(Path(folder), Path(folder) / "addons")
        self.assertFalse(ok)
        self.assertIn("disabled", message.lower())
        self.assertTrue(module.ISOLATED_MODE)

    def test_security_door_is_main_game_code(self):
        source = (ROOT / "halloween_update.py").read_text(encoding="utf-8")
        self.assertIn('"SECURITY ???"', source)
        self.assertIn("def _security_door", source)
        self.assertNotIn("nuttymod", source.lower())


if __name__ == "__main__":
    unittest.main()
