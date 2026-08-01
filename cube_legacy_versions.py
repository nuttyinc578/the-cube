"""The Cube Beta Legacy Versions add-on and launcher.

Copy this file to The Cube Beta Summer Edition/addons and choose
Add-ons -> Reload.  Run it directly to download and play an original build:

    python cube_legacy_versions.py install 1.0
    python cube_legacy_versions.py launch 1.0

The legacy files are kept beside this add-on in legacy_versions/.  They never
replace the Summer Edition executable or its files.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path


ADDON_NAME = "Legacy Versions: 1.0 + 5.0"
RELEASES = {
    "1.0": {
        "filename": "the_cube_beta_1.0.py",
        "url": "https://github.com/nuttyinc578/the-cube/releases/download/1.0.0.0/my.pygame.py",
        "label": "The Cube Beta 1.0 demo",
    },
    "5.0": {
        "filename": "the_cube_beta_5.0.py",
        "url": "https://github.com/nuttyinc578/the-cube/releases/download/5.0/thecubebeta5.0.py",
        "label": "The Cube Beta 5.0",
    },
}


def register(api):
    """Register content that is safe for the Summer Edition add-on API."""
    api.about(
        name=ADDON_NAME,
        version="1.0.0",
        author="Cube Community",
        description=(
            "A launcher for the official 1.0 and 5.0 Python releases. "
            "Run this file directly to download or launch a legacy build."
        ),
    )
    api.shape(
        name="Classic Cube",
        kind="polygon",
        sides=4,
        size=32,
        color=(70, 155, 255),
        weight=1.0,
    )
    api.shape(
        name="Beta Prism",
        kind="polygon",
        sides=5,
        size=28,
        color=(255, 190, 65),
        weight=0.8,
    )
    api.event(
        name="Legacy Breeze",
        duration=8,
        wind=-420,
        gravity_scale=0.9,
        spawn_count=5,
        banner="Legacy Breeze! A little piece of Cube Beta history returns.",
        color=(90, 180, 255),
    )


def legacy_dir() -> Path:
    return Path(__file__).resolve().parent / "legacy_versions"


def version_info(version: str) -> dict[str, str]:
    try:
        return RELEASES[version]
    except KeyError as exc:
        raise ValueError("Choose one of: " + ", ".join(RELEASES)) from exc


def install(version: str) -> Path:
    """Download one official source release only after an explicit command."""
    info = version_info(version)
    destination = legacy_dir() / info["filename"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {info['label']} from the official GitHub release...")
    try:
        urllib.request.urlretrieve(info["url"], destination)
    except OSError as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc
    print(f"Saved to: {destination}")
    return destination


def launch(version: str) -> int:
    """Start an already-downloaded legacy build in a separate process."""
    info = version_info(version)
    source = legacy_dir() / info["filename"]
    if not source.is_file():
        print(f"{info['label']} is not installed. Run: install {version}")
        return 1
    try:
        subprocess.Popen([sys.executable, str(source)], cwd=str(source.parent))
    except OSError as exc:
        print(f"Could not launch {info['label']}: {exc}")
        return 1
    print(f"Started {info['label']} separately from the Summer Edition.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or launch The Cube Beta legacy releases.")
    parser.add_argument("command", choices=("list", "install", "launch"))
    parser.add_argument("version", nargs="?", choices=tuple(RELEASES))
    args = parser.parse_args()

    if args.command == "list":
        for version, info in RELEASES.items():
            print(f"{version}: {info['label']}")
        return 0
    if args.version is None:
        parser.error("install and launch require a version: 1.0 or 5.0")
    if args.command == "install":
        install(args.version)
        return 0
    return launch(args.version)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
