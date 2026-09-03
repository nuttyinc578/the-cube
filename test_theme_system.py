"""Tests for safe themes, reversible modes, and publication staging."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from theme_system import (
    CPE_DEV_BETA_VERSION,
    DeveloperGate,
    LEGACY_PROFILES,
    THEMES_NIGHTLY_URL,
    ThemeError,
    ThemePublisher,
    ThemeStore,
    validate_theme_pair,
    validate_theme_repository,
)


class ThemeSystemTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    @staticmethod
    def manifest(slug: str = "amber-cube") -> dict[str, object]:
        return {
            "format_version": 1,
            "id": slug,
            "name": "Amber Cube",
            "version": "1.2.0",
            "author": "Theme Tester",
            "description": "A safe test theme.",
            "menu_title": "AMBER CUBE",
            "loading_message": "Loading amber physics",
            "palette": {
                "sky_top": [30, 40, 80],
                "sky_bottom": [220, 150, 80],
                "water": [70, 100, 110],
                "sand": [105, 65, 39],
                "sun": [255, 202, 80],
                "accent": [230, 110, 50],
                "panel": [255, 248, 230],
            },
        }

    def make_pair(self, manifest: dict[str, object] | None = None) -> tuple[Path, Path]:
        data = manifest or self.manifest()
        python_path = self.root / "theme.py"
        jar_path = self.root / "theme.jar"
        python_path.write_text(f"THEME = {data!r}\n", encoding="utf-8")
        with zipfile.ZipFile(jar_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("theme.json", json.dumps(data))
            archive.writestr("assets/readme.txt", "asset-only archive")
        return python_path, jar_path

    def test_matching_declarative_pair_is_verified(self):
        python_path, jar_path = self.make_pair()
        record = validate_theme_pair(python_path, jar_path)
        self.assertEqual(record.slug, "amber-cube")
        self.assertTrue(record.verified)

    def test_python_code_and_jar_classes_are_rejected(self):
        python_path, jar_path = self.make_pair()
        python_path.write_text("import os\nTHEME = {}\n", encoding="utf-8")
        with self.assertRaisesRegex(ThemeError, "only a literal THEME"):
            validate_theme_pair(python_path, jar_path)

        python_path, jar_path = self.make_pair()
        with zipfile.ZipFile(jar_path, "a") as archive:
            archive.writestr("Bad.class", b"not executable")
        with self.assertRaisesRegex(ThemeError, "executable content"):
            validate_theme_pair(python_path, jar_path)

    def test_install_uninstall_and_restore_are_backed_up(self):
        python_path, jar_path = self.make_pair()
        store = ThemeStore(self.root / "game")
        record, install_backup = store.install_pair(python_path, jar_path)
        self.assertEqual(store.state()["active_theme"], record.slug)
        self.assertTrue((install_backup / "backup.json").is_file())

        uninstall_backup = store.uninstall_active()
        self.assertEqual(store.state()["active_theme"], "maple")
        self.assertTrue((uninstall_backup / "active-theme").is_dir())
        restored = store.restore_latest()
        self.assertEqual(restored, uninstall_backup)
        self.assertEqual(store.state()["active_theme"], record.slug)
        self.assertTrue((store.themes_dir / record.slug).is_dir())

    def test_three_verified_clicks_unlock_ctrl_a_once(self):
        gate = DeveloperGate()
        self.assertEqual([gate.record_verification() for _ in range(3)], [2, 1, 0])
        self.assertTrue(gate.armed)
        self.assertTrue(gate.accept_hotkey(True, "a"))
        self.assertFalse(gate.accept_hotkey(True, "a"))

    def test_developer_and_all_legacy_profiles_rewrite_cpe_state(self):
        store = ThemeStore(self.root / "game")
        store.activate_experience("developer-beta")
        self.assertEqual(store.state()["cpe_version"], CPE_DEV_BETA_VERSION)
        self.assertTrue(store.state()["developer_enabled"])
        profile_ids = {profile["id"] for profile in LEGACY_PROFILES}
        self.assertIn("5.1-christmas", profile_ids)
        self.assertIn("6.1.2", profile_ids)
        for profile_id in profile_ids:
            store.activate_legacy(profile_id)
            self.assertEqual(store.state()["legacy_profile"], profile_id)

    def test_publisher_prepares_github_folder_and_readme(self):
        python_path, jar_path = self.make_pair()
        store = ThemeStore(self.root / "game")
        record, target = ThemePublisher(store).prepare_submission(
            python_path, jar_path, self.root / "checkout" / "themes"
        )
        self.assertEqual(target.name, record.slug)
        self.assertTrue((target / python_path.name).is_file())
        self.assertTrue((target / jar_path.name).is_file())
        self.assertIn(THEMES_NIGHTLY_URL, (target / "README.md").read_text(encoding="utf-8"))

    def test_repository_themes_are_valid(self):
        records = validate_theme_repository(Path(__file__).with_name("themes"))
        self.assertIn("fall-classic", {record.slug for record in records})


if __name__ == "__main__":
    unittest.main()
