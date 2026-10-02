import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from og_recovery import OGRecoveryError, OGRecoveryManager, _safe_extract, normalize_version, parse_og_command


class OGRecoveryTests(unittest.TestCase):
    def test_command_parser(self):
        self.assertEqual(parse_og_command("OG.exe -6.3.0"), "6.3.0")
        self.assertEqual(parse_og_command("og.exe -v5.1"), "5.1")
        self.assertEqual(parse_og_command("OG.exe -list"), "list")
        self.assertIsNone(parse_og_command("download 6.3.0"))

    def test_catalog_rejects_unknown_version(self):
        with self.assertRaises(OGRecoveryError):
            normalize_version("4.0")

    def test_expired_nightly_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = OGRecoveryManager(Path(folder))
            with self.assertRaisesRegex(OGRecoveryError, "expired"):
                manager.prepare("6.2.1")

    def test_zip_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../outside.txt", "not allowed")
            with self.assertRaises(OGRecoveryError):
                _safe_extract(archive, root / "extract")
            self.assertFalse((root / "outside.txt").exists())

    def test_portable_recovery_stages_then_backs_up(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "current.txt").write_text("current install", encoding="utf-8")
            manager = OGRecoveryManager(root)
            download = manager.download_root / "6.3.0" / "The-Cube-Beta-Error-Update-6.3.0-Portable.zip"
            download.parent.mkdir(parents=True)
            with zipfile.ZipFile(download, "w") as bundle:
                bundle.writestr("portable/game-payload.dat", b"verified historical payload")
                bundle.writestr("portable/README.md", "historical release")
            def test_launcher(_version, _stage):
                path = manager.work_root / "test-launcher.ps1"
                path.write_text("# test-only launcher", encoding="utf-8")
                return path
            with mock.patch.object(manager, "_portable_launcher", side_effect=test_launcher):
                plan = manager.prepare("6.3.0")
            self.assertTrue(Path(plan.stage_dir, "game-payload.dat").is_file())
            self.assertTrue(Path(plan.backup_dir, "current.txt").is_file())
            self.assertTrue(Path(plan.launcher).is_file())
            self.assertTrue(Path(plan.manifest).is_file())


if __name__ == "__main__":
    unittest.main()
