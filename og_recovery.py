"""Backup-first OG.exe recovery for The Cube Beta's Broken Lands terminal.

Only the release URLs in :data:`OG_VERSIONS` are accepted.  Portable ZIPs are
unpacked into a staging directory first and are never written directly over a
running game.  A small external PowerShell helper performs the final overlay
after the current process exits, leaving a complete backup and manifest behind.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import time
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import urlparse


MAX_DOWNLOAD_BYTES = 900 * 1024 * 1024
ALLOWED_DOWNLOAD_HOSTS = {"github.com", "objects.githubusercontent.com", "nightly.link"}


class OGRecoveryError(RuntimeError):
    """Raised when an OG recovery cannot be prepared safely."""


@dataclass(frozen=True)
class OGVersion:
    version: str
    name: str
    edition: str
    mode: str
    urls: tuple[str, ...]
    available: bool = True
    note: str = ""


@dataclass(frozen=True)
class RecoveryPlan:
    version: str
    mode: str
    backup_dir: str
    stage_dir: str
    launcher: str
    manifest: str


OG_VERSIONS: dict[str, OGVersion] = {
    "6.3.0": OGVersion(
        "6.3.0",
        "Error Update",
        "CPE 0.0.2 repair edition",
        "portable",
        (
            "https://github.com/nuttyinc578/the-cube/releases/download/6.3.0/"
            "The-Cube-Beta-Error-Update-6.3.0-Portable.zip",
        ),
    ),
    "6.2.2": OGVersion(
        "6.2.2",
        "Fall Edition",
        "stable fall portable",
        "portable",
        (
            "https://github.com/nuttyinc578/the-cube/releases/download/6.2.2/"
            "The-Cube-Beta-Fall-6.2.2-Portable.zip",
        ),
    ),
    "6.2.1": OGVersion(
        "6.2.1",
        "Fall Rewrite",
        "nightly artifact expired",
        "portable",
        (
            "https://nightly.link/nuttyinc578/the-cube/workflows/build-6.2.1/main/"
            "The-Cube-Beta-6.2.1-Windows.zip",
        ),
        available=False,
        note="The original GitHub Actions artifact has expired; no release asset exists.",
    ),
    "5.1": OGVersion(
        "5.1",
        "Christmas Update",
        "original signed-in-place MSI package",
        "installer",
        (
            "https://github.com/nuttyinc578/the-cube/releases/download/5.1/"
            "TheCubeBeta_v5_1_Christmas.msi",
            "https://github.com/nuttyinc578/the-cube/releases/download/5.1/cab1.cab",
        ),
        note="Uses the published 5.1 MSI and CAB. The repository source is preserved; no decompilation is used.",
    ),
}


def normalize_version(value: str) -> str:
    cleaned = value.strip().lower().removeprefix("v")
    if cleaned not in OG_VERSIONS:
        raise OGRecoveryError(f"Unknown OG version: {value}")
    return cleaned


def parse_og_command(command: str) -> str | None:
    """Parse ``OG.exe -<version>`` and return a normalized catalog key."""
    parts = command.strip().split()
    if len(parts) != 2 or parts[0].lower() != "og.exe" or not parts[1].startswith("-"):
        return None
    token = parts[1][1:]
    if token.lower() in {"list", "help"}:
        return token.lower()
    return normalize_version(token)


def _safe_name(url: str) -> str:
    name = PurePosixPath(urlparse(url).path).name
    if not name or name in {".", ".."}:
        raise OGRecoveryError("The release URL has no safe filename")
    return name


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_DOWNLOAD_HOSTS:
        raise OGRecoveryError("OG.exe refused a download outside the trusted release hosts")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts:
                raise OGRecoveryError(f"Unsafe ZIP path: {entry.filename}")
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise OGRecoveryError(f"Symbolic links are not accepted: {entry.filename}")
            target = (destination / Path(*path.parts)).resolve()
            if target != root and root not in target.parents:
                raise OGRecoveryError(f"ZIP path escaped staging: {entry.filename}")
        bundle.extractall(destination)


def _payload_root(extracted: Path) -> Path:
    children = [item for item in extracted.iterdir() if item.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extracted


class OGRecoveryManager:
    """Download, verify, stage, back up, and hand off OG releases."""

    def __init__(self, app_root: Path):
        self.app_root = Path(app_root).resolve()
        self.work_root = self.app_root / "og-recovery"
        self.download_root = self.work_root / "downloads"
        self.stage_root = self.work_root / "staging"
        self.backup_root = self.app_root / "backup" / "og"
        for folder in (self.download_root, self.stage_root, self.backup_root):
            folder.mkdir(parents=True, exist_ok=True)

    def catalog(self) -> tuple[OGVersion, ...]:
        return tuple(OG_VERSIONS.values())

    def _download(
        self,
        url: str,
        destination: Path,
        progress: Callable[[str, float], None] | None,
    ) -> Path:
        _validate_url(url)
        request = urllib.request.Request(url, headers={"User-Agent": "The-Cube-Beta-6.4-OG-Recovery"})
        partial = destination.with_suffix(destination.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=45) as response, partial.open("wb") as output:
                length = int(response.headers.get("Content-Length", "0") or 0)
                if length > MAX_DOWNLOAD_BYTES:
                    raise OGRecoveryError("The release is larger than the OG.exe safety limit")
                received = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > MAX_DOWNLOAD_BYTES:
                        raise OGRecoveryError("The release exceeded the OG.exe safety limit")
                    output.write(chunk)
                    if progress:
                        ratio = received / length if length else 0.0
                        progress(f"DOWNLOADING {destination.name}", min(0.70, ratio * 0.70))
            partial.replace(destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return destination

    def _backup(self, version: str, progress: Callable[[str, float], None] | None) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self.backup_root / f"before-{version}-{stamp}"
        destination.mkdir(parents=True)
        excluded = {".git", "backup", "og-recovery", "build", "dist", "package-staging", "release-download"}
        copied: list[str] = []
        for source in self.app_root.iterdir():
            if source.name in excluded:
                continue
            target = destination / source.name
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif source.is_file():
                shutil.copy2(source, target)
            copied.append(source.name)
        manifest = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "target_version": version,
            "source_root": str(self.app_root),
            "entries": sorted(copied),
        }
        (destination / "backup-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if progress:
            progress("BACKUP SEALED", 0.82)
        return destination

    def _write_manifest(self, version: OGVersion, stage: Path, backup: Path) -> Path:
        files = []
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "path": path.relative_to(stage).as_posix(),
                        "size": path.stat().st_size,
                        "sha256": _sha256(path),
                    }
                )
        manifest = self.work_root / "pending-recovery.json"
        manifest.write_text(
            json.dumps(
                {
                    "version": asdict(version),
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "backup": str(backup),
                    "stage": str(stage),
                    "files": files,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return manifest

    def _portable_launcher(self, version: OGVersion, stage: Path) -> Path:
        executables = sorted(stage.glob("*.exe"))
        if not executables:
            executables = sorted(stage.rglob("*.exe"))
        if not executables:
            raise OGRecoveryError("The staged portable release contains no Windows executable")
        launch_relative = executables[0].relative_to(stage)
        script = self.work_root / f"apply-{version.version}.ps1"
        content = """param([int]$WaitForPid)
$ErrorActionPreference = 'Stop'
$appRoot = [System.IO.Path]::GetFullPath('__APP_ROOT__')
$stage = [System.IO.Path]::GetFullPath('__STAGE__')
$launchRelative = '__LAUNCH__'
while (Get-Process -Id $WaitForPid -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 400 }
Get-ChildItem -LiteralPath $stage -Force | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $appRoot -Recurse -Force
}
$state = @{ version='__VERSION__'; applied_utc=[DateTime]::UtcNow.ToString('o'); backup='__BACKUP_NOTE__' }
$state | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $appRoot 'og-current-version.json') -Encoding UTF8
Start-Process -FilePath (Join-Path $appRoot $launchRelative) -WorkingDirectory $appRoot
"""
        def escape(value: object) -> str:
            return str(value).replace("'", "''")
        content = (
            content.replace("__APP_ROOT__", escape(self.app_root))
            .replace("__STAGE__", escape(stage))
            .replace("__LAUNCH__", escape(launch_relative))
            .replace("__VERSION__", escape(version.version))
            .replace("__BACKUP_NOTE__", "See backup\\og for the full restore point")
        )
        script.write_text(content, encoding="utf-8-sig")
        return script

    def prepare(
        self,
        version_value: str,
        progress: Callable[[str, float], None] | None = None,
    ) -> RecoveryPlan:
        key = normalize_version(version_value)
        version = OG_VERSIONS[key]
        if not version.available:
            raise OGRecoveryError(version.note or "That OG release is unavailable")
        if progress:
            progress("RECOVERY CHANNEL OPEN", 0.03)
        destination = self.download_root / key
        destination.mkdir(parents=True, exist_ok=True)
        downloaded = []
        for url in version.urls:
            target = destination / _safe_name(url)
            if not target.exists() or target.stat().st_size == 0:
                self._download(url, target, progress)
            downloaded.append(target)

        backup = self._backup(key, progress)
        if version.mode == "installer":
            manifest = self._write_manifest(version, destination, backup)
            return RecoveryPlan(key, version.mode, str(backup), str(destination), str(downloaded[0]), str(manifest))

        stage = self.stage_root / key
        if stage.exists():
            shutil.rmtree(stage)
        extracted = self.stage_root / f".{key}-extracting"
        if extracted.exists():
            shutil.rmtree(extracted)
        _safe_extract(downloaded[0], extracted)
        payload = _payload_root(extracted)
        if payload == extracted:
            extracted.replace(stage)
        else:
            shutil.move(str(payload), str(stage))
            shutil.rmtree(extracted, ignore_errors=True)
        if progress:
            progress("PORTABLE PAYLOAD VERIFIED", 0.92)
        launcher = self._portable_launcher(version, stage)
        manifest = self._write_manifest(version, stage, backup)
        if progress:
            progress("RECOVERY READY", 1.0)
        return RecoveryPlan(key, version.mode, str(backup), str(stage), str(launcher), str(manifest))

    def launch(self, plan: RecoveryPlan, *, pid: int | None = None) -> None:
        """Launch the prepared external installer/updater after explicit UI consent."""
        if plan.mode == "installer":
            subprocess.Popen(["msiexec.exe", "/i", plan.launcher], cwd=plan.stage_dir)
            return
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                plan.launcher,
                "-WaitForPid",
                str(pid or os.getpid()),
            ],
            cwd=str(self.app_root),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )


__all__ = [
    "OGRecoveryError",
    "OGRecoveryManager",
    "OGVersion",
    "OG_VERSIONS",
    "RecoveryPlan",
    "normalize_version",
    "parse_og_command",
]
