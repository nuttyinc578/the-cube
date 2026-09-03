"""Verified, side-by-side installer for historical The Cube Beta GitHub releases."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from theme_system import ThemeError, ThemeStore, _atomic_json


GITHUB_REPOSITORY = "nuttyinc578/the-cube"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases?per_page=100"
MAX_RELEASE_BYTES = 500_000_000
ALLOWED_ASSET_SUFFIXES = {".exe", ".msi", ".cab", ".py", ".zip"}
KNOWN_LEGACY_TAGS = (
    "6.2.2",
    "6.2.1",
    "6.2",
    "6.1",
    "6.0.0",
    "5.1",
    "5.0",
    "4.5",
    "4.1",
    "3.0",
    "2.0",
    "1.0.0.0",
)


class LegacyInstallError(ThemeError):
    """Raised when a legacy download or launch cannot be completed safely."""


class LegacyDownloadCancelled(LegacyInstallError):
    """Raised when the player cancels an in-progress GitHub download."""


@dataclass(slots=True)
class ReleaseAsset:
    name: str
    url: str
    size: int = 0


@dataclass(slots=True)
class LegacyRelease:
    tag: str
    name: str
    page_url: str
    assets: list[ReleaseAsset] = field(default_factory=list)
    source_only: bool = False
    unsupported: bool = False

    @property
    def label(self) -> str:
        title = "CHRISTMAS UPDATE 5.1" if self.tag == "5.1" else f"THE CUBE BETA {self.tag}"
        suffix = "  /  UNSUPPORTED" if self.unsupported else ""
        source = "  /  SOURCE" if self.source_only else ""
        return f"{title}{source}{suffix}"

    @property
    def total_bytes(self) -> int:
        return sum(max(0, asset.size) for asset in self.assets)


ProgressCallback = Callable[[str, int, int], None]


def _safe_tag(value: Any) -> str:
    tag = str(value or "").strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}", tag):
        raise LegacyInstallError("GitHub returned an invalid release tag")
    return tag


def _safe_asset_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name or Path(name).name != name or len(name) > 120:
        raise LegacyInstallError("GitHub returned an unsafe asset name")
    if Path(name).suffix.lower() not in ALLOWED_ASSET_SUFFIXES:
        raise LegacyInstallError(f"Unsupported legacy asset type: {name}")
    return name


def _version_key(tag: str) -> tuple[int, int, int, int]:
    parts = [int(item) for item in tag.split(".")]
    return tuple((parts + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


class GitHubLegacyInstaller:
    """Download exact release assets from GitHub and launch them side by side."""

    def __init__(self, app_root: str | Path, theme_store: ThemeStore):
        self.app_root = Path(app_root).resolve()
        self.theme_store = theme_store
        self.install_root = self.app_root / "legacy-versions"
        self.install_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _request(url: str, timeout: float = 20.0) -> urllib.request.Request:
        if not (
            url.startswith("https://api.github.com/repos/nuttyinc578/the-cube/")
            or url.startswith("https://github.com/nuttyinc578/the-cube/")
        ):
            raise LegacyInstallError("Refused a download outside the official GitHub repository")
        return urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "The-Cube-Beta-6.2.2-OG-Installer",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    @classmethod
    def from_payload(cls, payload: Any) -> list[LegacyRelease]:
        if not isinstance(payload, list):
            raise LegacyInstallError("GitHub releases response was not a list")
        releases: list[LegacyRelease] = []
        for raw in payload:
            if not isinstance(raw, dict) or raw.get("draft"):
                continue
            try:
                tag = _safe_tag(raw.get("tag_name"))
            except LegacyInstallError:
                continue
            if tag not in KNOWN_LEGACY_TAGS:
                continue
            assets: list[ReleaseAsset] = []
            for item in raw.get("assets") or []:
                if not isinstance(item, dict):
                    continue
                try:
                    name = _safe_asset_name(item.get("name"))
                except LegacyInstallError:
                    continue
                size = int(item.get("size") or 0)
                url = str(item.get("browser_download_url") or "")
                if size < 0 or size > MAX_RELEASE_BYTES:
                    continue
                if not url.startswith(
                    f"https://github.com/{GITHUB_REPOSITORY}/releases/download/{tag}/"
                ):
                    continue
                assets.append(ReleaseAsset(name, url, size))
            source_only = not assets
            if source_only:
                source_url = str(raw.get("zipball_url") or "")
                if not source_url.startswith(
                    f"https://api.github.com/repos/{GITHUB_REPOSITORY}/zipball/"
                ):
                    continue
                assets = [ReleaseAsset(f"The-Cube-Beta-{tag}-Source.zip", source_url)]
            display = str(raw.get("name") or "").strip() or f"The Cube Beta {tag}"
            if tag == "5.1":
                display = "Christmas Update 5.1"
            releases.append(
                LegacyRelease(
                    tag=tag,
                    name=display[:54],
                    page_url=str(raw.get("html_url") or ""),
                    assets=assets,
                    source_only=source_only,
                    unsupported=_version_key(tag) <= _version_key("5.0"),
                )
            )
        return sorted(releases, key=lambda release: _version_key(release.tag), reverse=True)

    def releases(self) -> list[LegacyRelease]:
        try:
            with urllib.request.urlopen(self._request(RELEASES_API), timeout=20) as response:
                payload = json.loads(response.read(2_000_000).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, urllib.error.URLError) as exc:
            raise LegacyInstallError(f"Could not load GitHub releases: {exc}") from exc
        releases = self.from_payload(payload)
        if not releases:
            raise LegacyInstallError("GitHub did not return any supported historical releases")
        return releases

    def _release_folder(self, tag: str) -> Path:
        target = (self.install_root / _safe_tag(tag)).resolve()
        if target.parent != self.install_root:
            raise LegacyInstallError("Legacy target escaped the legacy-versions folder")
        return target

    def _download_asset(
        self,
        asset: ReleaseAsset,
        destination: Path,
        callback: ProgressCallback | None,
        release_total: int,
        prior_bytes: int,
    ) -> dict[str, Any]:
        name = _safe_asset_name(asset.name)
        final_path = destination / name
        temporary = destination / f".{name}.part"
        digest = hashlib.sha256()
        downloaded = 0
        try:
            with urllib.request.urlopen(self._request(asset.url), timeout=45) as response, temporary.open("wb") as output:
                header_size = int(response.headers.get("Content-Length") or 0)
                expected = asset.size or header_size
                if expected > MAX_RELEASE_BYTES:
                    raise LegacyInstallError(f"Legacy asset is too large: {name}")
                while True:
                    chunk = response.read(262_144)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_RELEASE_BYTES:
                        raise LegacyInstallError(f"Legacy asset exceeded the safe size limit: {name}")
                    output.write(chunk)
                    digest.update(chunk)
                    if callback:
                        callback(name, prior_bytes + downloaded, release_total or expected)
            if asset.size and downloaded != asset.size:
                raise LegacyInstallError(
                    f"GitHub asset size mismatch for {name}: expected {asset.size}, received {downloaded}"
                )
            os.replace(temporary, final_path)
        except LegacyDownloadCancelled:
            temporary.unlink(missing_ok=True)
            raise
        except LegacyInstallError:
            temporary.unlink(missing_ok=True)
            raise
        except (OSError, urllib.error.URLError) as exc:
            temporary.unlink(missing_ok=True)
            raise LegacyInstallError(f"Could not download {name}: {exc}") from exc
        return {"name": name, "bytes": downloaded, "sha256": digest.hexdigest()}

    def download(
        self,
        release: LegacyRelease,
        callback: ProgressCallback | None = None,
    ) -> tuple[Path, Path]:
        backup = self.theme_store.create_backup(f"github-legacy-{release.tag}")
        destination = self._release_folder(release.tag)
        destination.mkdir(parents=True, exist_ok=True)
        completed: list[dict[str, Any]] = []
        prior = 0
        for asset in release.assets:
            result = self._download_asset(asset, destination, callback, release.total_bytes, prior)
            completed.append(result)
            prior += int(result["bytes"])
        _atomic_json(
            destination / ".legacy-release.json",
            {
                "repository": GITHUB_REPOSITORY,
                "tag": release.tag,
                "release_page": release.page_url,
                "source_only": release.source_only,
                "unsupported": release.unsupported,
                "backup": backup.name,
                "assets": completed,
            },
        )
        return destination, backup

    def launch(self, release: LegacyRelease, folder: Path) -> str:
        files = [folder / asset.name for asset in release.assets]
        installers = [path for path in files if path.suffix.lower() == ".msi"]
        setup_exes = [path for path in files if path.suffix.lower() == ".exe" and "setup" in path.name.lower()]
        executables = [path for path in files if path.suffix.lower() == ".exe"]
        python_files = [path for path in files if path.suffix.lower() == ".py"]
        command: list[str] | None = None
        if installers:
            command = ["msiexec.exe", "/i", str(installers[0])]
        elif setup_exes:
            command = [str(setup_exes[0])]
        elif executables:
            command = [str(executables[0])]
        elif python_files:
            runtime = None if getattr(sys, "frozen", False) else sys.executable
            runtime = runtime or shutil.which("pythonw") or shutil.which("python")
            if runtime:
                command = [runtime, str(python_files[0])]
        if command:
            subprocess.Popen(command, cwd=str(folder))
            return f"Downloaded and launched the real GitHub {release.tag} release."
        if os.name == "nt":
            os.startfile(str(folder))  # type: ignore[attr-defined]
        return (
            f"Downloaded GitHub {release.tag} to {folder}. "
            "This release contains source files instead of an installable application."
        )


__all__ = [
    "GitHubLegacyInstaller",
    "KNOWN_LEGACY_TAGS",
    "LegacyDownloadCancelled",
    "LegacyInstallError",
    "LegacyRelease",
    "ReleaseAsset",
]
