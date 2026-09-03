"""Regression tests for real GitHub OG-version downloads."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from legacy_versions import GitHubLegacyInstaller, LegacyRelease, ReleaseAsset
from theme_system import ThemeStore


class FakeResponse:
    def __init__(self, data: bytes):
        self.stream = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)


class LegacyVersionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = ThemeStore(self.root / "game")
        self.installer = GitHubLegacyInstaller(self.root / "game", self.store)

    def test_github_payload_uses_assets_and_source_fallback(self):
        payload = [
            {
                "tag_name": "6.2",
                "name": "The Cube Beta 6.2",
                "draft": False,
                "html_url": "https://github.com/nuttyinc578/the-cube/releases/tag/6.2",
                "zipball_url": "https://api.github.com/repos/nuttyinc578/the-cube/zipball/6.2",
                "assets": [
                    {
                        "name": "the.cube.beta.setup.exe",
                        "size": 25,
                        "browser_download_url": "https://github.com/nuttyinc578/the-cube/releases/download/6.2/the.cube.beta.setup.exe",
                    }
                ],
            },
            {
                "tag_name": "6.2.1",
                "name": "",
                "draft": False,
                "html_url": "https://github.com/nuttyinc578/the-cube/releases/tag/6.2.1",
                "zipball_url": "https://api.github.com/repos/nuttyinc578/the-cube/zipball/6.2.1",
                "assets": [],
            },
        ]
        releases = GitHubLegacyInstaller.from_payload(payload)
        self.assertEqual([release.tag for release in releases], ["6.2.1", "6.2"])
        self.assertTrue(releases[0].source_only)
        self.assertEqual(releases[1].assets[0].name, "the.cube.beta.setup.exe")

    def test_download_creates_backup_file_and_sha256_manifest(self):
        data = b"real historical release bytes"
        release = LegacyRelease(
            tag="6.1",
            name="The Cube Beta 6.1",
            page_url="https://github.com/nuttyinc578/the-cube/releases/tag/6.1",
            assets=[
                ReleaseAsset(
                    "the.cube.beta.summer.edition.exe",
                    "https://github.com/nuttyinc578/the-cube/releases/download/6.1/the.cube.beta.summer.edition.exe",
                    len(data),
                )
            ],
        )
        progress: list[int] = []
        with patch("urllib.request.urlopen", return_value=FakeResponse(data)):
            folder, backup = self.installer.download(
                release, lambda _name, received, _total: progress.append(received)
            )
        self.assertEqual((folder / release.assets[0].name).read_bytes(), data)
        self.assertTrue((backup / "backup.json").is_file())
        manifest = json.loads((folder / ".legacy-release.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["tag"], "6.1")
        self.assertEqual(len(manifest["assets"][0]["sha256"]), 64)
        self.assertEqual(progress[-1], len(data))

    def test_setup_exe_is_launched_from_side_by_side_folder(self):
        folder = self.root / "game" / "legacy-versions" / "6.2"
        folder.mkdir(parents=True)
        executable = folder / "the.cube.beta.setup.exe"
        executable.write_bytes(b"fixture")
        release = LegacyRelease(
            tag="6.2",
            name="The Cube Beta 6.2",
            page_url="https://github.com/nuttyinc578/the-cube/releases/tag/6.2",
            assets=[ReleaseAsset(executable.name, "https://github.com/example", 7)],
        )
        with patch("subprocess.Popen") as launch:
            message = self.installer.launch(release, folder)
        launch.assert_called_once_with([str(executable)], cwd=str(folder))
        self.assertIn("real GitHub 6.2 release", message)


if __name__ == "__main__":
    unittest.main()
