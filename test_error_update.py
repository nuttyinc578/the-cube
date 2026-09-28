from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from cpe import CubePhysicsEngine, __version__ as CPE_VERSION
from error_update import (
    CPERepairController,
    ERROR_CODE,
    ERROR_SLOGAN,
    ERROR_SLOGAN_COUNT,
    EXPECTED_CPE_VERSION,
    REPAIR_FILES,
)


REPOSITORY = Path(__file__).resolve().parent


class FakeThemeStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.current = {
            "active_theme": "maple",
            "experience": "developer-beta",
            "cpe_channel": "dev-beta",
            "cpe_version": "broken",
            "last_backup": None,
        }
        self.backups = 0

    def create_backup(self, reason: str) -> Path:
        self.backups += 1
        path = self.root / "backup" / "themes" / f"{self.backups}-{reason}"
        path.mkdir(parents=True)
        return path

    def state(self) -> dict[str, object]:
        return dict(self.current)

    def _write_state(self, state: dict[str, object]) -> None:
        self.current = dict(state)


class ErrorUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "installed"
        self.payload_root = Path(self.temporary.name) / "payload" / "cpe"
        self.root.mkdir()
        for relative in REPAIR_FILES:
            source = REPOSITORY / "repair_payload" / "cpe" / relative
            payload = self.payload_root / relative
            installed = self.root / "cpe" / relative
            payload.parent.mkdir(parents=True, exist_ok=True)
            installed.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, payload)
            shutil.copy2(source, installed)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_error_update_identity_and_cpe_version(self) -> None:
        self.assertEqual(ERROR_CODE, "21CPE")
        self.assertEqual(ERROR_SLOGAN, "WE ARE DONE / WE ARE COOKED")
        self.assertEqual(ERROR_SLOGAN_COUNT, 5)
        self.assertEqual(CPE_VERSION, "0.0.2")
        self.assertEqual(EXPECTED_CPE_VERSION, CPE_VERSION)

    def test_cpe_health_report_uses_enhanced_renderer_runtime(self) -> None:
        engine = CubePhysicsEngine(400, 300, particle_seed=21)
        engine.execute_line("CPE/1 1 1 200 80 18 1 40 170 255")
        engine.step(1 / 30)
        report = engine.health_report()
        self.assertTrue(report["physics_online"])
        self.assertTrue(report["particles_online"])
        self.assertEqual(report["body_count"], 1)
        self.assertEqual(report["fixed_step_hz"], 120)
        self.assertEqual(report["quality"], "enhanced")

    def test_repair_restores_corrupt_bridge_and_persists(self) -> None:
        theme_store = FakeThemeStore(self.root)
        controller = CPERepairController(self.root, self.payload_root, theme_store)
        self.assertFalse(controller.repaired)
        damaged = self.root / "cpe" / "node-bridge" / "server.js"
        damaged.write_text("this bridge is cooked", encoding="utf-8")

        before = {check.name: check for check in controller.diagnostics()}
        self.assertFalse(before["node-bridge/server.js"].ok)
        report = controller.repair()

        self.assertTrue(report.ok, report.error)
        self.assertIn("node-bridge/server.js", report.restored_files)
        self.assertTrue(controller.repaired)
        self.assertEqual(damaged.read_bytes(), (self.payload_root / "node-bridge/server.js").read_bytes())
        self.assertEqual(theme_store.backups, 1)
        self.assertEqual(theme_store.current["cpe_version"], "0.0.2")
        self.assertEqual(theme_store.current["cpe_channel"], "stable")
        self.assertTrue((self.root / "backup" / "cpe" / str(report.backup) / "backup.json").is_file())

        restarted = CPERepairController(self.root, self.payload_root)
        self.assertTrue(restarted.repaired)

    def test_missing_payload_fails_without_claiming_repair(self) -> None:
        (self.payload_root / "go-cache" / "main.go").unlink()
        controller = CPERepairController(self.root, self.payload_root)
        report = controller.repair()
        self.assertFalse(report.ok)
        self.assertFalse(controller.repaired)
        self.assertIn("repair payload missing", report.error or "")


if __name__ == "__main__":
    unittest.main()
