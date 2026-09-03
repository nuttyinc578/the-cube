"""Pygame experience UI for verified themes and reversible developer modes."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import pygame

from cube_core import (
    FPS,
    HEIGHT,
    INK,
    MINT,
    MUTED,
    NAVY,
    THEMES,
    VERSION,
    WHITE,
    WIDTH,
    YELLOW,
    app_path,
    bundle_path,
    save_settings,
)
from theme_system import (
    CPE_DEV_BETA_VERSION,
    DeveloperGate,
    LEGACY_PROFILES,
    THEME_DISCLAIMER,
    THEMES_NIGHTLY_URL,
    UPDATE_NIGHTLY_URL,
    ThemeError,
    ThemePublisher,
    ThemeStore,
    validate_theme_pair,
)


def _wrap(font: pygame.font.Font, text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if current and font.size(candidate)[0] > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_lines(
    app: Any,
    text: str,
    rect: pygame.Rect,
    color: tuple[int, int, int] = MUTED,
    font: pygame.font.Font | None = None,
    center: bool = False,
) -> int:
    selected_font = font or app.small
    y = rect.y
    for paragraph in text.splitlines():
        lines = _wrap(selected_font, paragraph, rect.width) if paragraph else [""]
        for line in lines:
            surface = selected_font.render(line, True, color)
            x = rect.centerx - surface.get_width() // 2 if center else rect.x
            app.screen.blit(surface, (x, y))
            y += surface.get_height() + 4
        y += 2
    return y


def _confirm(app: Any, title: str, body: str, accept: str = "CONTINUE") -> bool:
    button_type = app._experience_button_type
    buttons = [
        button_type((310, 545, 235, 52), "CANCEL", (255, 181, 165)),
        button_type((555, 545, 235, 52), accept, MINT),
    ]
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return False
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
        app.draw_background(pygame.time.get_ticks() / 1000)
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((8, 24, 35, 175))
        app.screen.blit(shade, (0, 0))
        app.draw_panel(pygame.Rect(180, 105, 740, 525), 252)
        heading = app.large.render(title, True, NAVY)
        app.screen.blit(heading, heading.get_rect(center=(WIDTH // 2, 165)))
        warning = app.font.render("BACKUP + VERIFIED REWRITE", True, (166, 72, 38))
        app.screen.blit(warning, warning.get_rect(center=(WIDTH // 2, 215)))
        _draw_lines(app, body, pygame.Rect(245, 255, 610, 245), INK, app.small, center=True)
        selected = app.wait_click(buttons, events)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is not None:
            return selected == 1


def _refresh_themes(app: Any) -> list[Any]:
    records = app.theme_store.discover()
    for slug in getattr(app, "_store_theme_ids", set()):
        THEMES.pop(slug, None)
    app._store_theme_ids = {record.slug for record in records if record.verified}
    for record in records:
        if record.verified:
            THEMES[record.slug] = record.palette
    state = app.theme_store.state()
    requested = str(state.get("active_theme") or "maple")
    app.settings["theme"] = requested if requested in THEMES else "maple"
    app.background_cache.clear()
    save_settings(app.settings)
    return records


def _experience_init(original_init: Any):
    def wrapped(app: Any) -> None:
        original_init(app)
        app.theme_store = ThemeStore(app_path(), bundle_path("themes"))
        app.theme_publisher = ThemePublisher(app.theme_store)
        app.developer_gate = DeveloperGate()
        app.theme_drop_files: dict[str, Path] = {}
        app._store_theme_ids: set[str] = set()
        app.theme_status = "Drop one .py manifest and one .jar asset pack here."
        _refresh_themes(app)

    return wrapped


def _loading_screen(app: Any, duration: float = 4.8) -> bool:
    """Show a staged CPE/theme/backups loader with an animated physics cube."""
    app.start_music()
    started = time.monotonic()
    duration = max(0.01, duration)
    state = app.theme_store.state()
    records = app.theme_store.discover()
    verified_count = sum(record.verified for record in records)
    stages = [
        "Starting Cube Physics Engine",
        "Verifying theme manifests and asset packs",
        "Indexing reversible backups",
        "Connecting multiplayer and add-on services",
        "Ready for fall physics",
    ]
    while True:
        progress = min(1.0, (time.monotonic() - started) / duration)
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_F11:
                    app.settings["fullscreen"] = not app.settings["fullscreen"]
                    save_settings(app.settings)
                    app.apply_display()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and progress >= 0.25:
                    progress = 1.0

        ticks = pygame.time.get_ticks() / 1000
        app.draw_background(ticks)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((22, 22, 39, 150))
        app.screen.blit(veil, (0, 0))
        app.draw_panel(pygame.Rect(105, 62, 890, 596), 248)

        badge = app.small.render(f"THE CUBE BETA {VERSION}  /  MAJOR REWRITE", True, (146, 76, 42))
        app.screen.blit(badge, badge.get_rect(center=(WIDTH // 2, 103)))
        title = app.large.render("BUILDING YOUR CUBE WORLD", True, NAVY)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 152)))

        # A rotating isometric cube gives the loader a clear, physics-first identity.
        center_x, center_y = WIDTH // 2, 258
        bob = int(math.sin(ticks * 3.2) * 8)
        size = 62
        top = [(center_x, center_y - size + bob), (center_x + size, center_y - 28 + bob),
               (center_x, center_y + 8 + bob), (center_x - size, center_y - 28 + bob)]
        left = [(center_x - size, center_y - 28 + bob), (center_x, center_y + 8 + bob),
                (center_x, center_y + size + bob), (center_x - size, center_y + 24 + bob)]
        right = [(center_x + size, center_y - 28 + bob), (center_x, center_y + 8 + bob),
                 (center_x, center_y + size + bob), (center_x + size, center_y + 24 + bob)]
        pygame.draw.polygon(app.screen, (255, 207, 88), top)
        pygame.draw.polygon(app.screen, (226, 108, 52), left)
        pygame.draw.polygon(app.screen, (80, 178, 166), right)
        for points in (top, left, right):
            pygame.draw.lines(app.screen, WHITE, True, points, 3)

        stage_index = min(len(stages) - 1, int(progress * len(stages)))
        stage = app.font.render(stages[stage_index], True, INK)
        app.screen.blit(stage, stage.get_rect(center=(WIDTH // 2, 352)))
        track = pygame.Rect(210, 390, 680, 32)
        pygame.draw.rect(app.screen, (210, 220, 224), track, border_radius=16)
        fill = pygame.Rect(track.x, track.y, int(track.width * progress), track.height)
        if fill.width:
            pygame.draw.rect(app.screen, (222, 108, 39), fill, border_radius=16)
        percent = app.small.render(f"{int(progress * 100)}%", True, INK)
        app.screen.blit(percent, percent.get_rect(center=track.center))

        chips = [
            f"CPE {state.get('cpe_version', '1.0.0')}",
            f"THEME {str(state.get('active_theme', 'maple')).upper()}",
            f"{verified_count} VERIFIED STORE THEME{'S' if verified_count != 1 else ''}",
        ]
        for index, label in enumerate(chips):
            rect = pygame.Rect(170 + index * 260, 463, 240, 44)
            pygame.draw.rect(app.screen, (229, 240, 239), rect, border_radius=13)
            text = app.tiny.render(label[:36], True, NAVY)
            app.screen.blit(text, text.get_rect(center=rect.center))

        source = app.tiny.render(
            "Verified themes + backups  |  Update and theme bundles available through nightly.link",
            True,
            MUTED,
        )
        app.screen.blit(source, source.get_rect(center=(WIDTH // 2, 555)))
        hint = app.tiny.render("Enter or Space skips after 25%  /  Esc exits", True, MUTED)
        app.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 605)))
        pygame.display.flip()
        app.clock.tick(FPS)
        if progress >= 1.0:
            return True


def _main_menu(app: Any) -> str:
    button_type = app._experience_button_type
    state = app.theme_store.state()
    entries = [
        ("PLAY SOLO", "single", YELLOW),
        ("PLAY MULTIPLAYER", "multiplayer", MINT),
        ("THEME STORE", "themes", (192, 163, 255)),
        ("ADD-ONS", "addons", WHITE),
        ("SETTINGS", "settings", WHITE),
    ]
    if state.get("developer_enabled"):
        entries.append(("DEVELOPER MODE", "developer", (255, 180, 103)))
    entries.append(("QUIT", "quit", (255, 181, 165)))
    height = 46 if len(entries) > 6 else 50
    gap = 53 if len(entries) > 6 else 57
    start_y = 285
    buttons = [
        button_type((370, start_y + index * gap, 360, height), label, accent)
        for index, (label, _, accent) in enumerate(entries)
    ]
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return "quit"
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "quit"
        app.draw_background(pygame.time.get_ticks() / 1000)
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((8, 55, 83, 48))
        app.screen.blit(shade, (0, 0))
        badge = app.small.render(f"FALL EDITION  /  v{VERSION} MAJOR REWRITE", True, NAVY)
        badge_rect = badge.get_rect(center=(WIDTH // 2, 69)).inflate(28, 13)
        pygame.draw.rect(app.screen, (255, 238, 162), badge_rect, border_radius=14)
        app.screen.blit(badge, badge.get_rect(center=badge_rect.center))
        title = app.hero.render("THE CUBE BETA", True, WHITE)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 139)))
        mode = str(state.get("experience", "stable")).replace("-", " ").upper()
        subtitle = app.font.render(f"CPE-powered fall physics  /  {mode}", True, WHITE)
        app.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 202)))
        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is not None:
            return entries[selected][1]


def _theme_store_menu(app: Any) -> None:
    button_type = app._experience_button_type
    buttons = [
        button_type((165, 500, 240, 48), "VERIFY & RELOAD", YELLOW),
        button_type((430, 500, 240, 48), "INSTALL DROPPED PAIR", MINT),
        button_type((695, 500, 240, 48), "PUBLISH THEME", (192, 163, 255)),
        button_type((298, 565, 240, 48), "UNINSTALL ACTIVE", (255, 181, 165)),
        button_type((562, 565, 240, 48), "BACK", WHITE),
    ]
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            raise SystemExit
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                ctrl = bool(event.mod & pygame.KMOD_CTRL)
                if app.developer_gate.accept_hotkey(ctrl, pygame.key.name(event.key)):
                    _developer_install_menu(app)
            elif event.type == pygame.DROPFILE:
                path = Path(event.file).resolve()
                suffix = path.suffix.lower()
                if suffix in {".py", ".jar"} and path.is_file():
                    app.theme_drop_files[suffix] = path
                    app.theme_status = f"Loaded {path.name}. Drop the matching theme file."
                else:
                    app.theme_status = "Theme Store accepts only one .py and one .jar file."

        records = app.theme_store.discover()
        state = app.theme_store.state()
        app.draw_background(pygame.time.get_ticks() / 1000)
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((8, 35, 57, 112))
        app.screen.blit(shade, (0, 0))
        app.title_block("Verified + reversible", "Theme Store", "Drop a .py manifest and matching .jar asset pack.", 55)
        app.draw_panel(pygame.Rect(80, 175, 940, 460), 248)

        active = str(state.get("active_theme", "maple"))
        summary = app.font.render(
            f"ACTIVE  {active.upper()}     /     {sum(r.verified for r in records)} VERIFIED COMMUNITY THEMES",
            True,
            NAVY,
        )
        app.screen.blit(summary, (125, 205))
        py_name = app.theme_drop_files.get(".py")
        jar_name = app.theme_drop_files.get(".jar")
        pair = app.small.render(
            f"PY  {py_name.name if py_name else 'waiting...'}     JAR  {jar_name.name if jar_name else 'waiting...'}",
            True,
            INK,
        )
        app.screen.blit(pair, (125, 245))
        _draw_lines(app, app.theme_status, pygame.Rect(125, 280, 850, 44), (37, 111, 93), app.small)
        warning_rect = pygame.Rect(115, 330, 870, 132)
        pygame.draw.rect(app.screen, (255, 241, 215), warning_rect, border_radius=14)
        warning = app.small.render("THEME INSTALL WARNING", True, (166, 72, 38))
        app.screen.blit(warning, (140, 349))
        _draw_lines(app, THEME_DISCLAIMER, pygame.Rect(140, 382, 820, 70), INK, app.tiny)

        remaining = max(0, 3 - app.developer_gate.clicks)
        gate = "Ctrl+A unlocked for 45 seconds" if app.developer_gate.armed else f"Developer unlock: {remaining} verified reloads remaining"
        gate_label = app.tiny.render(gate, True, MUTED)
        app.screen.blit(gate_label, gate_label.get_rect(center=(WIDTH // 2, 479)))

        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        if selected == 4:
            return
        pair_ready = ".py" in app.theme_drop_files and ".jar" in app.theme_drop_files
        if selected == 0:
            try:
                if pair_ready:
                    record = validate_theme_pair(app.theme_drop_files[".py"], app.theme_drop_files[".jar"])
                    app.theme_status = f"Verified {record.name} {record.version} by {record.author}."
                else:
                    failed = [record for record in records if not record.verified]
                    if failed:
                        raise ThemeError(f"{failed[0].slug}: {failed[0].error}")
                    app.theme_status = f"Reloaded store: {sum(r.verified for r in records)} themes verified."
                remaining = app.developer_gate.record_verification()
                if remaining == 0:
                    app.theme_status += " Press Ctrl+A within 45 seconds for Developer Mode."
            except ThemeError as exc:
                app.theme_status = f"Verification failed: {exc}"
        elif selected in {1, 2} and not pair_ready:
            app.theme_status = "Drop both matching files before installing or publishing."
        elif selected == 1:
            if _confirm(app, "INSTALL THIS THEME?", THEME_DISCLAIMER, "BACK UP + INSTALL"):
                try:
                    record, backup = app.theme_store.install_pair(
                        app.theme_drop_files[".py"], app.theme_drop_files[".jar"]
                    )
                    _refresh_themes(app)
                    app.theme_status = f"Installed {record.name}. Restore point: {backup.name}"
                except ThemeError as exc:
                    app.theme_status = f"Install stopped safely: {exc}"
        elif selected == 2:
            publish_warning = (
                THEME_DISCLAIMER
                + " Publishing creates a branch in your GitHub fork and opens a pull request to "
                  "nuttyinc578/the-cube. GitHub CLI must be signed in."
            )
            if _confirm(app, "PUBLISH TO GITHUB?", publish_warning, "CREATE PULL REQUEST"):
                try:
                    url = app.theme_publisher.publish_pull_request(
                        app.theme_drop_files[".py"], app.theme_drop_files[".jar"]
                    )
                    app.theme_status = f"Pull request created: {url}"
                except ThemeError as exc:
                    app.theme_status = f"Publish needs attention: {exc}"
        elif selected == 3:
            if active in {"maple", "harvest", "twilight"}:
                app.theme_status = "Built-in themes stay installed. Select a custom theme first."
            elif _confirm(
                app,
                "UNINSTALL ACTIVE THEME?",
                "The active theme is copied into the backup folder before removal. The Maple theme becomes active. You can restore the latest backup from Developer Mode.",
                "BACK UP + UNINSTALL",
            ):
                try:
                    backup = app.theme_store.uninstall_active()
                    _refresh_themes(app)
                    app.theme_status = f"Theme removed. Backup saved as {backup.name}."
                except ThemeError as exc:
                    app.theme_status = f"Uninstall stopped: {exc}"


def _developer_install_menu(app: Any) -> None:
    button_type = app._experience_button_type
    buttons = [
        button_type((260, 385, 270, 56), "DEVELOPER BETA", (255, 180, 103)),
        button_type((570, 385, 270, 56), "EXPERIMENTAL BETA", (192, 163, 255)),
        button_type((415, 475, 270, 52), "CANCEL", WHITE),
    ]
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            raise SystemExit
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
        app.draw_background(pygame.time.get_ticks() / 1000)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((25, 17, 42, 178))
        app.screen.blit(veil, (0, 0))
        app.draw_panel(pygame.Rect(155, 95, 790, 505), 250)
        title = app.large.render("INSTALL DEVELOPER EXPERIENCE", True, NAVY)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 155)))
        subtitle = app.font.render(f"CPE {CPE_DEV_BETA_VERSION}", True, (146, 76, 42))
        app.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 205)))
        _draw_lines(
            app,
            "Developer and Experimental Beta rewrite the active game configuration, menus, theme channel, and CPE channel. A full configuration and active-theme backup is created first. This does not run untrusted theme code or replace the signed executable.",
            pygame.Rect(235, 250, 630, 100),
            INK,
            app.small,
            center=True,
        )
        selected = app.wait_click(buttons, events)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        if selected == 2:
            return
        mode = "developer-beta" if selected == 0 else "experimental-beta"
        if _confirm(
            app,
            f"ENABLE {mode.replace('-', ' ').upper()}?",
            f"This changes the full experience profile and rewrites CPE to {CPE_DEV_BETA_VERSION}. A backup is created first.",
            "INSTALL EXPERIENCE",
        ):
            backup = app.theme_store.activate_experience(mode)
            _refresh_themes(app)
            app.notify(f"{mode.replace('-', ' ').title()} installed. Backup: {backup.name}", 8)
            return


def _developer_menu(app: Any) -> None:
    button_type = app._experience_button_type
    while True:
        state = app.theme_store.state()
        entries = [
            ("THEME STORE", "themes", (192, 163, 255)),
            ("OG / LEGACY VERSIONS", "legacy", YELLOW),
            ("SWITCH DEVELOPER BETA", "developer-beta", (255, 180, 103)),
            ("SWITCH EXPERIMENTAL BETA", "experimental-beta", (192, 163, 255)),
            ("RESTORE LATEST BACKUP", "restore", MINT),
            ("RETURN TO STABLE", "stable", WHITE),
            ("BACK", "back", WHITE),
        ]
        buttons = [
            button_type((330, 230 + index * 58, 440, 48), label, accent)
            for index, (label, _, accent) in enumerate(entries)
        ]
        events = pygame.event.get()
        if not app.common_events(events):
            raise SystemExit
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
        app.draw_background(pygame.time.get_ticks() / 1000)
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((22, 15, 38, 125))
        app.screen.blit(shade, (0, 0))
        app.title_block(
            f"CPE {state.get('cpe_version')}",
            "Developer Mode",
            f"Active experience: {str(state.get('experience')).replace('-', ' ').title()}",
            50,
        )
        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        action = entries[selected][1]
        if action == "back":
            return
        if action == "themes":
            _theme_store_menu(app)
        elif action == "legacy":
            _legacy_menu(app)
        elif action in {"developer-beta", "experimental-beta", "stable"}:
            if _confirm(
                app,
                f"SWITCH TO {action.replace('-', ' ').upper()}?",
                "The current experience configuration and active custom theme are backed up before the mode and CPE channel change.",
                "BACK UP + SWITCH",
            ):
                backup = app.theme_store.activate_experience(action)
                _refresh_themes(app)
                app.notify(f"Switched experience. Backup: {backup.name}", 7)
                if action == "stable":
                    return
        elif action == "restore":
            if _confirm(
                app,
                "RESTORE LATEST BACKUP?",
                "The latest verified theme and experience snapshot will replace the current configuration.",
                "RESTORE",
            ):
                try:
                    restored = app.theme_store.restore_latest()
                    _refresh_themes(app)
                    app.notify(f"Restored {restored.name}", 7)
                except ThemeError as exc:
                    app.notify(str(exc), 7)


def _legacy_menu(app: Any) -> None:
    button_type = app._experience_button_type
    entries = list(LEGACY_PROFILES)
    buttons = []
    for index, profile in enumerate(entries):
        column = index % 2
        row = index // 2
        accent = (255, 181, 165) if profile["id"] == "5.0" else (255, 238, 190)
        buttons.append(
            button_type((90 + column * 470, 205 + row * 62, 440, 50), profile["name"], accent)
        )
    back = button_type((410, 604, 280, 48), "BACK", WHITE)
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            raise SystemExit
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
        app.draw_background(pygame.time.get_ticks() / 1000)
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((8, 35, 57, 120))
        app.screen.blit(shade, (0, 0))
        app.title_block(
            "OG library / safe compatibility",
            "Legacy Versions",
            "All editions run through the rewritten 6.2.2 engine; 5.0 remains unsupported.",
            48,
        )
        selected = app.wait_click(buttons + [back], events)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        if selected == len(buttons):
            return
        profile = entries[selected]
        detail = (
            f"Install the {profile['name']} presentation as a compatibility profile on the current 6.2.2 engine. "
            f"Edition: {profile['edition']}. CPE uses {CPE_DEV_BETA_VERSION}. "
            "No obsolete executable is downloaded. A backup is created first."
        )
        if _confirm(app, f"INSTALL {profile['name'].upper()}?", detail, "INSTALL LEGACY PROFILE"):
            backup = app.theme_store.activate_legacy(profile["id"])
            _refresh_themes(app)
            app.notify(f"Installed {profile['name']}. Backup: {backup.name}", 8)
            return


def _run(app: Any) -> None:
    if not app.licence_dialog():
        save_settings(app.settings)
        pygame.quit()
        return
    if not app.fall_update_screen():
        save_settings(app.settings)
        pygame.quit()
        return
    action = "menu"
    while action != "quit":
        try:
            app.theme_store.set_active_theme(str(app.settings.get("theme", "maple")))
        except ThemeError:
            app.settings["theme"] = "maple"
            app.theme_store.set_active_theme("maple")
        if action == "menu":
            action = app.main_menu()
        elif action == "single":
            app.run_simulation()
            action = "menu"
        elif action == "multiplayer":
            action = app.multiplayer_menu()
        elif action == "addons":
            app.addons_menu()
            action = "menu"
        elif action == "settings":
            app.settings_menu()
            action = "menu"
        elif action == "themes":
            app.theme_store_menu()
            action = "menu"
        elif action == "developer":
            app.developer_mode_menu()
            action = "menu"
        else:
            action = "menu"
    save_settings(app.settings)
    pygame.quit()


def install_experience_ui(game_app: type[Any], button_type: type[Any]) -> None:
    """Attach the 6.2.2 experience without disturbing the physics implementation."""
    if getattr(game_app, "_experience_ui_installed", False):
        return
    game_app._experience_ui_installed = True
    game_app._experience_button_type = button_type
    game_app.__init__ = _experience_init(game_app.__init__)
    game_app.fall_update_screen = _loading_screen
    game_app.run = _run
    game_app.main_menu = _main_menu
    game_app.theme_store_menu = _theme_store_menu
    game_app.developer_install_menu = _developer_install_menu
    game_app.developer_mode_menu = _developer_menu
    game_app.legacy_versions_menu = _legacy_menu
    game_app.refresh_themes = _refresh_themes


__all__ = [
    "THEMES_NIGHTLY_URL",
    "UPDATE_NIGHTLY_URL",
    "install_experience_ui",
]
