"""The Cube Beta Legacy Versions add-on and launcher.

Copy this file to The Cube Beta Summer Edition/addons and choose
Add-ons -> Reload.  Run it directly to download and play an original build:

    python cube_legacy_versions.py popup

The legacy files are kept beside this add-on in legacy_versions/.  They never
replace the Summer Edition executable or its files.
"""

from __future__ import annotations

import argparse
import os
import runpy
import subprocess
import sys
import types
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
    "4.0": {
        "filename": "the_cube_beta_4.0.py",
        "url": "https://github.com/nuttyinc578/the-cube/releases/download/4.1/thecubebeta4.0.py",
        "label": "The Cube Beta 4.0",
    },
    "3.0": {
        "filename": "the_cube_beta_3.0.py",
        "url": "https://github.com/nuttyinc578/the-cube/releases/download/3.0/thecubebeta.py",
        "label": "The Cube Beta 3.0",
    },
    "2.0": {
        "filename": "the_cube_beta_2.0.py",
        "url": "https://github.com/nuttyinc578/the-cube/releases/download/2.0/my.pygame.v2.0.py",
        "label": "The Cube Beta 2.0 demo",
    },
    "5.1": {
        "filename": "the_cube_beta_v5_1_christmas.py",
        "label": "The Cube Beta 5.1 Christmas",
        "local": True,
    },
}

# Original source files may already be somewhere in the installed game folder.
# Only exact historical release filenames are accepted; add-on scripts are never
# treated as playable legacy builds.
LOCAL_FILENAMES = {
    "1.0": ("my.pygame.py",),
    "2.0": ("my.pygame.v2.0.py",),
    "3.0": ("thecubebeta.py",),
    "4.0": ("thecubebeta4.0.py",),
    "5.0": ("thecubebeta5.0.py",),
}


def register(api):
    """Register content that is safe for the Summer Edition add-on API."""
    api.about(
        name=ADDON_NAME,
        version="1.0.0",
        author="Cube Community",
        description=(
            "A launcher for the official 1.0 through 5.1 Python releases, including Christmas 5.1. "
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


def find_local_source(version: str) -> Path | None:
    """Find an original legacy source anywhere under the game install folder."""
    filenames = LOCAL_FILENAMES.get(version, ())
    if not filenames:
        return None
    game_root = Path(__file__).resolve().parent.parent
    # Search game content first, then the add-ons folder (where users often
    # place release downloads). Do not accept this launcher or generated mods.
    for root in (game_root / "the cube beta", game_root / "addons"):
        if not root.is_dir():
            continue
        for filename in filenames:
            for candidate in root.rglob(filename):
                if candidate.resolve() != Path(__file__).resolve():
                    return candidate
    return None


def source_path(version: str) -> Path:
    """Return the separate source path for a downloaded or bundled version."""
    info = version_info(version)
    if info.get("local"):
        return (
            Path(__file__).resolve().parent.parent
            / "the cube beta"
            / "legacy_christmas"
            / info["filename"]
        )
    local_source = find_local_source(version)
    if local_source is not None:
        return local_source
    return legacy_dir() / info["filename"]


def version_info(version: str) -> dict[str, str]:
    try:
        return RELEASES[version]
    except KeyError as exc:
        raise ValueError("Choose one of: " + ", ".join(RELEASES)) from exc


def install(version: str) -> Path:
    """Download one official source release only after an explicit command."""
    info = version_info(version)
    destination = source_path(version)
    if info.get("local"):
        if not destination.is_file():
            raise RuntimeError(f"The local Christmas 5.1 source is missing: {destination}")
        print(f"Christmas 5.1 is already installed: {destination}")
        return destination
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
    source = source_path(version)
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


def run_in_current_process(version: str) -> None:
    """Replace the current menu with a legacy build in this same app process.

    The selected source owns pygame after this call, so it intentionally does
    not return to the Summer Edition menu when the older build is closed.
    """
    info = version_info(version)
    source = source_path(version)
    if not source.is_file():
        install(version)
        source = source_path(version)
    if not source.is_file():
        raise RuntimeError(f"Could not find {info['label']} after installation.")

    previous_cwd = Path.cwd()
    source_parent = source.parent
    inserted_path = str(source_parent)
    try:
        os.chdir(source_parent)
        if inserted_path not in sys.path:
            sys.path.insert(0, inserted_path)
        install_pymunk_pygame_compat()
        runpy.run_path(str(source), run_name="__main__")
    except SystemExit:
        # Older releases commonly use sys.exit() when their window closes.
        pass
    finally:
        os.chdir(previous_cwd)
        if sys.path and sys.path[0] == inserted_path:
            sys.path.pop(0)


def install_pymunk_pygame_compat() -> None:
    """Supply the removed ``pymunk.pygame_util`` module to old Cube builds.

    Recent Pymunk packages no longer bundle this optional helper. The old game
    builds import it only for ``DrawOptions`` and ``Space.debug_draw``.
    """
    try:
        import pymunk
        import pygame
    except ImportError:
        return
    try:
        import pymunk.pygame_util  # type: ignore[import-not-found]
        return
    except ModuleNotFoundError:
        pass
    if not hasattr(pymunk, "SpaceDebugDrawOptions"):
        return

    def color(value):
        return (round(value.r), round(value.g), round(value.b))

    def point(value):
        return (round(value.x), round(value.y))

    class DrawOptions(pymunk.SpaceDebugDrawOptions):
        def __init__(self, surface):
            super().__init__()
            self.surface = surface

        def draw_circle(self, position, angle, radius, outline_color, fill_color):
            pygame.draw.circle(self.surface, color(fill_color), point(position), max(1, round(radius)))
            pygame.draw.circle(self.surface, color(outline_color), point(position), max(1, round(radius)), 1)

        def draw_segment(self, start, end, draw_color):
            pygame.draw.line(self.surface, color(draw_color), point(start), point(end), 1)

        def draw_fat_segment(self, start, end, radius, outline_color, fill_color):
            width = max(1, round(radius * 2))
            pygame.draw.line(self.surface, color(fill_color), point(start), point(end), width)
            pygame.draw.line(self.surface, color(outline_color), point(start), point(end), 1)

        def draw_polygon(self, vertices, radius, outline_color, fill_color):
            points = [point(vertex) for vertex in vertices]
            if len(points) >= 3:
                pygame.draw.polygon(self.surface, color(fill_color), points)
                pygame.draw.polygon(self.surface, color(outline_color), points, 1)

        def draw_dot(self, size, position, draw_color):
            pygame.draw.circle(self.surface, color(draw_color), point(position), max(1, round(size)))

    module = types.ModuleType("pymunk.pygame_util")
    module.DrawOptions = DrawOptions
    sys.modules["pymunk.pygame_util"] = module
    pymunk.pygame_util = module


def popup() -> int:
    """Open a small visual legacy-version selector used by the in-game button."""
    try:
        import pygame
    except ImportError:
        print("The version picker needs pygame. Use 'install VERSION' and 'launch VERSION' instead.")
        return 1

    pygame.init()
    screen = pygame.display.set_mode((680, 540))
    pygame.display.set_caption("The Cube Beta — Legacy Versions")
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("arial", 30, bold=True)
    font = pygame.font.SysFont("arial", 19, bold=True)
    small = pygame.font.SysFont("arial", 14)
    buttons = []
    versions = tuple(RELEASES)
    for index, version in enumerate(versions):
        column, row = index % 2, index // 2
        buttons.append((pygame.Rect(45 + column * 320, 150 + row * 104, 270, 76), version))
    close = pygame.Rect(245, 472, 190, 40)
    message = "Choose a version. Downloads use the official GitHub release."

    active = True
    while active:
        mouse = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                active = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                active = False
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if close.collidepoint(event.pos):
                    active = False
                    continue
                for rect, version in buttons:
                    if not rect.collidepoint(event.pos):
                        continue
                    try:
                        source = source_path(version)
                        if not source.is_file():
                            message = f"Downloading {version}..."
                            pygame.display.flip()
                            install(version)
                        launch(version)
                        active = False
                    except RuntimeError as exc:
                        message = str(exc)
                    break

        screen.fill((15, 55, 76))
        pygame.draw.rect(screen, (23, 81, 108), (16, 16, 648, 508), border_radius=20)
        title = title_font.render("LEGACY VERSIONS", True, (255, 245, 210))
        screen.blit(title, title.get_rect(center=(340, 60)))
        subtitle = small.render("Select a release to download (if needed) and launch it separately.", True, (220, 240, 245))
        screen.blit(subtitle, subtitle.get_rect(center=(340, 95)))
        for rect, version in buttons:
            info = RELEASES[version]
            installed = source_path(version).is_file()
            color = (222, 92, 105) if version == "5.1" else (75, 196, 160)
            if rect.collidepoint(mouse):
                color = tuple(min(255, channel + 25) for channel in color)
            pygame.draw.rect(screen, color, rect, border_radius=13)
            name = font.render(f"v{version}", True, (10, 43, 56))
            screen.blit(name, name.get_rect(center=(rect.centerx, rect.y + 24)))
            action = "LAUNCH" if installed else "DOWNLOAD + LAUNCH"
            detail = small.render(f"{info['label']}  •  {action}", True, (10, 43, 56))
            screen.blit(detail, detail.get_rect(center=(rect.centerx, rect.y + 53)))
        pygame.draw.rect(screen, (238, 238, 238), close, border_radius=10)
        close_label = font.render("CLOSE", True, (15, 55, 76))
        screen.blit(close_label, close_label.get_rect(center=close.center))
        note = small.render(message[:92], True, (220, 240, 245))
        screen.blit(note, note.get_rect(center=(340, 447)))
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or launch The Cube Beta legacy releases.")
    parser.add_argument("command", choices=("list", "install", "launch", "popup"))
    parser.add_argument("version", nargs="?", choices=tuple(RELEASES))
    args = parser.parse_args()

    if args.command == "list":
        for version, info in RELEASES.items():
            print(f"{version}: {info['label']}")
        return 0
    if args.command == "popup":
        return popup()
    if args.version is None:
        parser.error("install and launch require a version: " + ", ".join(RELEASES))
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
