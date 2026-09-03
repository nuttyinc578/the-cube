"""Verified themes, reversible experience modes, and GitHub theme publishing."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable


THEME_FORMAT_VERSION = 1
CPE_STABLE_VERSION = "1.0.0"
CPE_DEV_BETA_VERSION = "0.0.2-dev-beta"
THEME_REPOSITORY = "nuttyinc578/the-cube"
THEMES_NIGHTLY_URL = (
    "https://nightly.link/nuttyinc578/the-cube/workflows/themes/main/"
    "The-Cube-Beta-Themes.zip"
)
UPDATE_NIGHTLY_URL = (
    "https://nightly.link/nuttyinc578/the-cube/workflows/build-6.2.2/main/"
    "The-Cube-Beta-6.2.2-Windows.zip"
)

THEME_DISCLAIMER = (
    "Community themes can rewrite the whole game experience, including menus, loading visuals, "
    "colors, layout settings, and CPE presentation. Theme files are not trusted automatically. "
    "The Cube Beta verifies the declarative Python manifest and treats the JAR only as an asset "
    "archive. A complete restore snapshot is created in the backup folder before every change."
)

PALETTE_KEYS = ("sky_top", "sky_bottom", "water", "sand", "sun", "accent", "panel")
BUILTIN_THEME_IDS = {"maple", "harvest", "twilight"}
UNSAFE_JAR_SUFFIXES = {
    ".class",
    ".com",
    ".dll",
    ".dylib",
    ".exe",
    ".js",
    ".msi",
    ".ps1",
    ".py",
    ".pyc",
    ".rb",
    ".sh",
    ".so",
    ".vbs",
}

LEGACY_PROFILES: tuple[dict[str, str], ...] = (
    {"id": "1.0.0.0", "name": "Original Cube 1.0", "edition": "OG physics"},
    {"id": "2.0", "name": "Cube 2.0", "edition": "Classic shapes"},
    {"id": "3.0", "name": "Cube 3.0", "edition": "Classic sandbox"},
    {"id": "4.0", "name": "Cube 4.0", "edition": "Fourth-generation UI"},
    {"id": "4.1", "name": "Cube 4.1", "edition": "Legacy maintenance"},
    {"id": "4.5", "name": "Cube 4.5", "edition": "Legacy feature update"},
    {"id": "5.0", "name": "Cube 5.0 (unsupported)", "edition": "Safe compatibility profile"},
    {"id": "5.1-christmas", "name": "Christmas Update 5.1", "edition": "Christmas compatibility"},
    {"id": "5.3", "name": "Cube 5.3", "edition": "Late 5.x compatibility"},
    {"id": "6.0", "name": "Cube 6.0", "edition": "Modern classic"},
    {"id": "6.1", "name": "Cube 6.1", "edition": "Summer compatibility"},
    {"id": "6.1.2", "name": "Cube 6.1.2", "edition": "Rewritten legacy profile"},
)


class ThemeError(ValueError):
    """Raised when a theme or experience operation is unsafe or invalid."""


@dataclass(slots=True)
class ThemeRecord:
    slug: str
    name: str
    version: str
    author: str
    description: str
    python_path: Path
    jar_path: Path
    palette: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    menu_title: str = "THE CUBE BETA"
    loading_message: str = "Preparing your theme"
    verified: bool = True
    error: str = ""


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,39}", text):
        raise ThemeError("Theme id must use 2-40 lowercase letters, numbers, or hyphens")
    return text


def _short_text(value: Any, field_name: str, maximum: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        raise ThemeError(f"Theme {field_name} is required")
    return text[:maximum]


def _version(value: Any) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}(?:[-+][a-zA-Z0-9.-]+)?", text):
        raise ThemeError("Theme version must look like 1.0.0")
    return text[:24]


def _color(value: Any, field_name: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ThemeError(f"Palette color {field_name} must contain three RGB numbers")
    try:
        result = tuple(int(channel) for channel in value)
    except (TypeError, ValueError) as exc:
        raise ThemeError(f"Palette color {field_name} contains a non-number") from exc
    if any(channel < 0 or channel > 255 for channel in result):
        raise ThemeError(f"Palette color {field_name} must stay between 0 and 255")
    return result  # type: ignore[return-value]


def _normalise_manifest(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ThemeError("Theme manifest must be a dictionary/object")
    try:
        format_version = int(raw.get("format_version", 0))
    except (TypeError, ValueError) as exc:
        raise ThemeError("Theme format_version must be a number") from exc
    if format_version != THEME_FORMAT_VERSION:
        raise ThemeError(f"Theme format_version must be {THEME_FORMAT_VERSION}")
    palette_raw = raw.get("palette")
    if not isinstance(palette_raw, dict):
        raise ThemeError("Theme palette must be a dictionary/object")
    missing = [key for key in PALETTE_KEYS[:5] if key not in palette_raw]
    if missing:
        raise ThemeError(f"Theme palette is missing: {', '.join(missing)}")
    palette = {key: _color(value, key) for key, value in palette_raw.items() if key in PALETTE_KEYS}
    palette.setdefault("accent", palette["sun"])
    palette.setdefault("panel", (246, 252, 255))
    return {
        "format_version": format_version,
        "id": _slug(raw.get("id")),
        "name": _short_text(raw.get("name"), "name", 48),
        "version": _version(raw.get("version")),
        "author": _short_text(raw.get("author"), "author", 48),
        "description": _short_text(raw.get("description"), "description", 160),
        "menu_title": _short_text(raw.get("menu_title", "THE CUBE BETA"), "menu title", 48),
        "loading_message": _short_text(
            raw.get("loading_message", "Preparing your theme"), "loading message", 72
        ),
        "palette": palette,
    }


def _python_manifest(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > 256_000:
            raise ThemeError("Theme Python manifest is larger than 256 KB")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=path.name)
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise ThemeError(f"Could not parse theme Python manifest: {exc}") from exc

    value_node: ast.AST | None = None
    for statement in tree.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(
            statement.value.value, str
        ):
            continue
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name) and target.id in {"THEME", "THEME_MANIFEST"}:
                if value_node is not None:
                    raise ThemeError("Theme Python manifest must declare THEME only once")
                value_node = statement.value
                continue
        raise ThemeError("Theme Python files may contain only a literal THEME dictionary")
    if value_node is None:
        raise ThemeError("Theme Python file must declare THEME = {...}")
    try:
        return _normalise_manifest(ast.literal_eval(value_node))
    except (ValueError, TypeError, MemoryError, RecursionError) as exc:
        if isinstance(exc, ThemeError):
            raise
        raise ThemeError("THEME must contain literal strings, numbers, lists, and dictionaries") from exc


def _jar_manifest(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > 10_000_000:
            raise ThemeError("Theme JAR is larger than 10 MB")
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > 128:
                raise ThemeError("Theme JAR contains more than 128 files")
            expanded = 0
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                parts = PurePosixPath(name).parts
                if name.startswith("/") or ".." in parts:
                    raise ThemeError("Theme JAR contains an unsafe path")
                if entry.file_size > 5_000_000:
                    raise ThemeError(f"Theme asset is too large: {name}")
                expanded += entry.file_size
                if expanded > 25_000_000:
                    raise ThemeError("Theme JAR expands beyond 25 MB")
                if Path(name).suffix.lower() in UNSAFE_JAR_SUFFIXES:
                    raise ThemeError(f"Theme JAR contains executable content: {name}")
            try:
                raw = archive.read("theme.json")
            except KeyError as exc:
                raise ThemeError("Theme JAR must contain theme.json at its root") from exc
    except (OSError, zipfile.BadZipFile) as exc:
        raise ThemeError(f"Could not read theme JAR: {exc}") from exc
    try:
        return _normalise_manifest(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ThemeError("theme.json must contain valid UTF-8 JSON") from exc


def validate_theme_pair(python_path: str | Path, jar_path: str | Path) -> ThemeRecord:
    py_path = Path(python_path).resolve()
    jar = Path(jar_path).resolve()
    if py_path.suffix.lower() != ".py" or jar.suffix.lower() != ".jar":
        raise ThemeError("A theme requires one .py manifest and one .jar asset archive")
    py_manifest = _python_manifest(py_path)
    jar_manifest = _jar_manifest(jar)
    for key in ("id", "name", "version", "author"):
        if py_manifest[key] != jar_manifest[key]:
            raise ThemeError(f"Python and JAR theme metadata disagree on {key}")
    if py_manifest["palette"] != jar_manifest["palette"]:
        raise ThemeError("Python and JAR theme palettes do not match")
    return ThemeRecord(
        slug=py_manifest["id"],
        name=py_manifest["name"],
        version=py_manifest["version"],
        author=py_manifest["author"],
        description=py_manifest["description"],
        python_path=py_path,
        jar_path=jar,
        palette=py_manifest["palette"],
        menu_title=py_manifest["menu_title"],
        loading_message=py_manifest["loading_message"],
    )


def theme_readme(record: ThemeRecord) -> str:
    return f"""# {record.name}

[![Download all verified themes](https://img.shields.io/badge/nightly.link-download_themes-7c3aed?style=for-the-badge)]({THEMES_NIGHTLY_URL})

Version `{record.version}` by **{record.author}**.

{record.description}

## Install

Drag both `{record.python_path.name}` and `{record.jar_path.name}` onto The Cube Beta Theme Store, then click **Install dropped pair**.

> [!WARNING]
> {THEME_DISCLAIMER}

The Python file is parsed as a literal manifest and is not executed. The JAR is inspected as an asset archive and cannot contain executable classes or scripts.
"""


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


class DeveloperGate:
    """Three successful Verify & Reload clicks arm Ctrl+A for one use."""

    def __init__(self, timeout: float = 45.0):
        self.timeout = max(5.0, float(timeout))
        self.clicks = 0
        self.last_click = 0.0

    def record_verification(self, now: float | None = None) -> int:
        moment = time.monotonic() if now is None else float(now)
        if self.last_click and moment - self.last_click > self.timeout:
            self.clicks = 0
        self.last_click = moment
        self.clicks = min(3, self.clicks + 1)
        return max(0, 3 - self.clicks)

    @property
    def armed(self) -> bool:
        return self.clicks >= 3 and time.monotonic() - self.last_click <= self.timeout

    def accept_hotkey(self, ctrl_pressed: bool, key: str) -> bool:
        accepted = bool(ctrl_pressed and key.lower() == "a" and self.armed)
        if accepted:
            self.clicks = 0
            self.last_click = 0.0
        return accepted


class ThemeStore:
    """Transactional theme and experience-mode manager."""

    def __init__(self, app_root: str | Path, packaged_themes: str | Path | None = None):
        self.app_root = Path(app_root).resolve()
        self.themes_dir = self.app_root / "themes"
        self.inbox_dir = self.themes_dir / "inbox"
        self.publish_dir = self.themes_dir / "publish-work"
        self.backup_dir = self.app_root / "backup" / "themes"
        self.state_path = self.themes_dir / ".theme_state.json"
        self.settings_path = self.app_root / "settings.json"
        self.cpe_state_path = self.app_root / "cpe" / ".cpe_channel.json"
        self.packaged_themes = Path(packaged_themes).resolve() if packaged_themes else None
        self.ensure_layout()

    def ensure_layout(self) -> None:
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.publish_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        source = self.packaged_themes
        if source and source.is_dir() and source != self.themes_dir:
            for item in source.rglob("*"):
                relative = item.relative_to(source)
                if any(part in {"inbox", "publish-work", "__pycache__"} for part in relative.parts):
                    continue
                destination = self.themes_dir / relative
                if item.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, destination)
        if not self.state_path.exists():
            self._write_state(self.default_state())

    @staticmethod
    def default_state() -> dict[str, Any]:
        return {
            "active_theme": "maple",
            "experience": "stable",
            "developer_enabled": False,
            "legacy_profile": None,
            "cpe_channel": "stable",
            "cpe_version": CPE_STABLE_VERSION,
            "last_backup": None,
        }

    def state(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        state = self.default_state()
        if isinstance(raw, dict):
            state.update({key: raw[key] for key in state if key in raw})
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        _atomic_json(self.state_path, state)
        _atomic_json(
            self.cpe_state_path,
            {
                "channel": state.get("cpe_channel", "stable"),
                "version": state.get("cpe_version", CPE_STABLE_VERSION),
                "experience": state.get("experience", "stable"),
            },
        )

    def discover(self) -> list[ThemeRecord]:
        records: list[ThemeRecord] = []
        for folder in sorted(self.themes_dir.iterdir(), key=lambda path: path.name.lower()):
            if not folder.is_dir() or folder.name.startswith(".") or folder.name in {"inbox", "publish-work"}:
                continue
            python_files = sorted(folder.glob("*.py"))
            jar_files = sorted(folder.glob("*.jar"))
            if not python_files and not jar_files:
                continue
            try:
                if len(python_files) != 1 or len(jar_files) != 1:
                    raise ThemeError("Theme folder must contain exactly one .py file and one .jar file")
                if folder.name in BUILTIN_THEME_IDS:
                    raise ThemeError("Built-in theme ids are reserved")
                record = validate_theme_pair(python_files[0], jar_files[0])
                if record.slug != folder.name:
                    raise ThemeError("Theme folder name must match the theme id")
                records.append(record)
            except ThemeError as exc:
                records.append(
                    ThemeRecord(
                        slug=folder.name,
                        name=folder.name.replace("-", " ").title(),
                        version="-",
                        author="Unknown",
                        description="Theme verification failed",
                        python_path=python_files[0] if python_files else folder / "missing.py",
                        jar_path=jar_files[0] if jar_files else folder / "missing.jar",
                        verified=False,
                        error=str(exc),
                    )
                )
        return records

    def palettes(self) -> dict[str, dict[str, tuple[int, int, int]]]:
        return {record.slug: record.palette for record in self.discover() if record.verified}

    def set_active_theme(self, slug: str) -> None:
        requested = _slug(slug)
        available = BUILTIN_THEME_IDS | set(self.palettes())
        if requested not in available:
            raise ThemeError("Theme is not installed and verified")
        state = self.state()
        state["active_theme"] = requested
        self._write_state(state)

    def _safe_theme_folder(self, slug: str) -> Path:
        target = (self.themes_dir / _slug(slug)).resolve()
        if target.parent != self.themes_dir:
            raise ThemeError("Theme target escaped the themes directory")
        return target

    def create_backup(self, reason: str) -> Path:
        state = self.state()
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        label = re.sub(r"[^a-z0-9-]+", "-", reason.lower()).strip("-")[:40] or "change"
        destination = self.backup_dir / f"{stamp}-{time.time_ns() % 1_000_000:06d}-{label}"
        destination.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, Any] = {"reason": reason, "created_at": stamp, "state": state, "files": []}
        for source, name in ((self.settings_path, "settings.json"), (self.cpe_state_path, "cpe-channel.json")):
            if source.is_file():
                shutil.copy2(source, destination / name)
                manifest["files"].append(name)
        active = str(state.get("active_theme") or "")
        if active not in BUILTIN_THEME_IDS:
            active_folder = self._safe_theme_folder(active)
            if active_folder.is_dir():
                shutil.copytree(active_folder, destination / "active-theme")
                manifest["active_theme_folder"] = active
        _atomic_json(destination / "backup.json", manifest)
        return destination

    def install_pair(self, python_path: str | Path, jar_path: str | Path) -> tuple[ThemeRecord, Path]:
        record = validate_theme_pair(python_path, jar_path)
        if record.slug in BUILTIN_THEME_IDS:
            raise ThemeError("Built-in theme ids are reserved")
        backup = self.create_backup(f"install-{record.slug}")
        target = self._safe_theme_folder(record.slug)
        temporary = self.themes_dir / f".install-{record.slug}-{os.getpid()}"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True)
        shutil.copy2(record.python_path, temporary / record.python_path.name)
        shutil.copy2(record.jar_path, temporary / record.jar_path.name)
        (temporary / "README.md").write_text(theme_readme(record), encoding="utf-8")
        validate_theme_pair(temporary / record.python_path.name, temporary / record.jar_path.name)
        if target.exists():
            shutil.copytree(target, backup / "replaced-theme")
            shutil.rmtree(target)
        os.replace(temporary, target)
        state = self.state()
        state.update(active_theme=record.slug, last_backup=backup.name)
        self._write_state(state)
        return validate_theme_pair(target / record.python_path.name, target / record.jar_path.name), backup

    def uninstall_active(self) -> Path:
        state = self.state()
        active = str(state.get("active_theme") or "maple")
        if active in BUILTIN_THEME_IDS:
            raise ThemeError("Built-in themes cannot be uninstalled")
        target = self._safe_theme_folder(active)
        if not target.is_dir():
            raise ThemeError("The active custom theme folder is missing")
        backup = self.create_backup(f"uninstall-{active}")
        shutil.rmtree(target)
        state.update(active_theme="maple", last_backup=backup.name)
        self._write_state(state)
        return backup

    def activate_experience(self, experience: str) -> Path:
        if experience not in {"stable", "developer-beta", "experimental-beta"}:
            raise ThemeError("Unknown experience channel")
        backup = self.create_backup(f"experience-{experience}")
        state = self.state()
        developer = experience in {"developer-beta", "experimental-beta"}
        state.update(
            experience=experience,
            developer_enabled=developer,
            legacy_profile=None,
            cpe_channel="dev-beta" if developer else "stable",
            cpe_version=CPE_DEV_BETA_VERSION if developer else CPE_STABLE_VERSION,
            last_backup=backup.name,
        )
        self._write_state(state)
        return backup

    def activate_legacy(self, profile_id: str) -> Path:
        profiles = {profile["id"]: profile for profile in LEGACY_PROFILES}
        if profile_id not in profiles:
            raise ThemeError("Unknown legacy compatibility profile")
        backup = self.create_backup(f"legacy-{profile_id}")
        state = self.state()
        state.update(
            experience="legacy",
            developer_enabled=True,
            legacy_profile=profile_id,
            cpe_channel="compatibility",
            cpe_version=CPE_DEV_BETA_VERSION,
            last_backup=backup.name,
        )
        self._write_state(state)
        return backup

    def backups(self) -> list[Path]:
        return sorted(
            (path for path in self.backup_dir.iterdir() if path.is_dir() and (path / "backup.json").is_file()),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )

    def restore_latest(self) -> Path:
        backups = self.backups()
        if not backups:
            raise ThemeError("No theme or experience backup is available")
        backup = backups[0]
        try:
            manifest = json.loads((backup / "backup.json").read_text(encoding="utf-8"))
            state = manifest["state"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ThemeError("Latest backup manifest is damaged") from exc
        active_folder = manifest.get("active_theme_folder")
        source_theme = backup / "active-theme"
        if active_folder and source_theme.is_dir():
            target = self._safe_theme_folder(str(active_folder))
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source_theme, target)
        if (backup / "settings.json").is_file():
            shutil.copy2(backup / "settings.json", self.settings_path)
        state["last_backup"] = backup.name
        self._write_state(state)
        return backup


class ThemePublisher:
    """Prepare a verified theme folder and create a GitHub pull request via gh."""

    def __init__(self, store: ThemeStore, repository: str = THEME_REPOSITORY):
        self.store = store
        self.repository = repository

    def prepare_submission(
        self,
        python_path: str | Path,
        jar_path: str | Path,
        themes_root: str | Path,
    ) -> tuple[ThemeRecord, Path]:
        record = validate_theme_pair(python_path, jar_path)
        if record.slug in BUILTIN_THEME_IDS:
            raise ThemeError("Built-in theme ids are reserved")
        root = Path(themes_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / record.slug).resolve()
        if target.parent != root:
            raise ThemeError("Theme submission escaped the themes folder")
        if target.exists():
            shutil.rmtree(target)
        target.mkdir()
        shutil.copy2(record.python_path, target / record.python_path.name)
        shutil.copy2(record.jar_path, target / record.jar_path.name)
        (target / "README.md").write_text(theme_readme(record), encoding="utf-8")
        return record, target

    @staticmethod
    def _run(args: list[str], cwd: Path | None = None, timeout: int = 180) -> str:
        environment = os.environ.copy()
        environment.setdefault("GIT_TERMINAL_PROMPT", "0")
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "command failed").strip()
            raise ThemeError(f"{' '.join(args[:3])}: {detail[:500]}")
        return completed.stdout.strip()

    def publish_pull_request(self, python_path: str | Path, jar_path: str | Path) -> str:
        if not shutil.which("gh") or not shutil.which("git"):
            raise ThemeError("Install Git and GitHub CLI before publishing a theme")
        self._run(["gh", "auth", "status"], timeout=30)
        login = self._run(["gh", "api", "user", "--jq", ".login"], timeout=30).splitlines()[-1].strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
            raise ThemeError("GitHub CLI returned an invalid account name")
        record = validate_theme_pair(python_path, jar_path)
        self.store.publish_dir.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=f"{record.slug}-", dir=self.store.publish_dir))

        fork = subprocess.run(
            ["gh", "repo", "fork", self.repository, "--clone=false", "--remote=false"],
            capture_output=True,
            text=True,
            timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        fork_detail = (fork.stderr or fork.stdout or "").lower()
        if fork.returncode != 0 and "already exists" not in fork_detail:
            raise ThemeError(f"Could not create or reuse GitHub fork: {fork_detail[:400]}")

        checkout = work / "the-cube"
        self._run(["gh", "repo", "clone", f"{login}/the-cube", str(checkout), "--", "--depth", "1"], timeout=180)
        branch = f"theme/{record.slug}-{int(time.time())}"
        self._run(["git", "checkout", "-b", branch], checkout)
        self._run(["git", "config", "user.name", login], checkout)
        self._run(["git", "config", "user.email", f"{login}@users.noreply.github.com"], checkout)
        self.prepare_submission(python_path, jar_path, checkout / "themes")
        self._run(["git", "add", f"themes/{record.slug}"], checkout)
        self._run(["git", "commit", "-m", f"Publish theme: {record.name} {record.version}"], checkout)
        self._run(["git", "push", "--set-upstream", "origin", branch], checkout, timeout=180)
        body = (
            f"Publishes **{record.name} {record.version}** by {record.author}.\n\n"
            "Both files passed The Cube Beta's declarative Python and non-executable JAR checks."
        )
        output = self._run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                self.repository,
                "--base",
                "main",
                "--head",
                f"{login}:{branch}",
                "--title",
                f"Theme: {record.name} {record.version}",
                "--body",
                body,
            ],
            checkout,
            timeout=90,
        )
        url = next((line for line in output.splitlines() if line.startswith("https://github.com/")), output)
        return url.strip()


def validate_theme_repository(themes_root: str | Path) -> list[ThemeRecord]:
    root = Path(themes_root).resolve()
    temporary_root = Path(tempfile.mkdtemp(prefix="cube-theme-validation-"))
    try:
        store = ThemeStore(temporary_root)
        for folder in root.iterdir():
            if folder.is_dir() and not folder.name.startswith(".") and folder.name not in {"inbox", "publish-work"}:
                shutil.copytree(folder, store.themes_dir / folder.name, dirs_exist_ok=True)
        records = store.discover()
        failures = [record for record in records if not record.verified]
        if failures:
            raise ThemeError("; ".join(f"{record.slug}: {record.error}" for record in failures))
        return records
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
