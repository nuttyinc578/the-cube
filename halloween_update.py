"""The Cube Beta 6.4 Halloween / Broken Lands experience."""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any
from types import MethodType

import pygame

from cube_core import FPS, HEIGHT, INK, THEMES, VERSION, WHITE, WIDTH, app_path, save_settings
from halloween_music import (
    HalloweenMusicError,
    HalloweenMusicManager,
    TRACK_ARTIST,
    TRACK_PAGE,
    TRACK_TITLE,
)
from og_recovery import OGRecoveryError, OGRecoveryManager, OG_VERSIONS, RecoveryPlan, parse_og_command


ORANGE = (255, 128, 40)
PUMPKIN = (214, 72, 24)
PURPLE = (132, 76, 191)
ACID = (158, 242, 82)
MIDNIGHT = (13, 9, 28)
ASH = (168, 168, 184)
RED = (246, 72, 82)


def _halloween_init(original: Any):
    def wrapped(app: Any, *args: Any, **kwargs: Any) -> None:
        original(app, *args, **kwargs)
        # The Error Update initializer installed an instance method; class-level
        # overrides alone cannot replace it.
        app.fall_update_screen = MethodType(_halloween_loading_screen, app)
        state_path = app_path() / "halloween_update_state.json"
        if not state_path.exists():
            app.settings["theme"] = "halloween"
            save_settings(app.settings)
            try:
                state_path.write_text('{"introduced_theme": true}\n', encoding="utf-8")
            except OSError:
                pass
        app.og_recovery = OGRecoveryManager(app_path())
        app.halloween_music = HalloweenMusicManager(app_path() / "halloween_music.mp3")
        app.halloween_music_status = "CONNECTING TO PIXABAY..."
        app.halloween_music_error = ""
        app.halloween_update_state_path = state_path
        pygame.display.set_caption(f"The Cube Beta Halloween Update v{VERSION}")
        _load_halloween_music(app)

    return wrapped


def _load_halloween_music(app: Any) -> bool:
    if not pygame.mixer.get_init() or not getattr(app, "halloween_music", None):
        return False
    if not app.halloween_music.ready:
        return False
    try:
        pygame.mixer.music.load(str(app.halloween_music.destination))
        pygame.mixer.music.set_volume(0.30)
        if app.settings.get("music"):
            pygame.mixer.music.play(-1)
        return True
    except (pygame.error, OSError):
        return False


def _draw_night(app: Any, ticks: float) -> None:
    app.screen.fill(MIDNIGHT)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = (int(13 + 21 * ratio), int(9 + 10 * ratio), int(28 + 23 * ratio))
        pygame.draw.line(app.screen, color, (0, y), (WIDTH, y))
    moon_x = 865
    pygame.draw.circle(app.screen, (241, 232, 179), (moon_x, 115), 62)
    pygame.draw.circle(app.screen, (30, 19, 49), (moon_x + 25, 96), 58)
    for index in range(42):
        x = (index * 83 + 31) % WIDTH
        y = 22 + (index * 47) % 350
        glow = 145 + int(90 * abs(math.sin(ticks * 0.6 + index)))
        pygame.draw.circle(app.screen, (glow, glow, min(255, glow + 25)), (x, y), 1 + index % 2)
    pygame.draw.polygon(app.screen, (24, 20, 36), [(0, 500), (165, 372), (310, 505), (488, 338), (655, 500), (840, 354), (1100, 500), (1100, 720), (0, 720)])
    pygame.draw.rect(app.screen, (21, 16, 29), (0, 560, WIDTH, 160))
    for index, x in enumerate(range(30, WIDTH, 95)):
        sway = int(math.sin(ticks + index) * 4)
        pygame.draw.line(app.screen, (48, 37, 52), (x, 600), (x + sway, 462), 8)
        pygame.draw.line(app.screen, (48, 37, 52), (x + sway, 505), (x - 28, 475), 5)
        pygame.draw.line(app.screen, (48, 37, 52), (x + sway, 492), (x + 31, 452), 5)
    for index, x in enumerate((95, 245, 765, 985)):
        pygame.draw.circle(app.screen, PUMPKIN, (x, 625), 31)
        pygame.draw.rect(app.screen, (74, 90, 42), (x - 4, 586, 8, 14))
        eye_y = 616 + index % 2
        pygame.draw.polygon(app.screen, (255, 218, 74), [(x - 15, eye_y), (x - 5, eye_y - 8), (x - 3, eye_y + 4)])
        pygame.draw.polygon(app.screen, (255, 218, 74), [(x + 15, eye_y), (x + 5, eye_y - 8), (x + 3, eye_y + 4)])


def _music_worker(app: Any) -> None:
    try:
        app.halloween_music_status = "DOWNLOADING THE OFFICIAL PIXABAY TRACK..."
        app.halloween_music.download()
        app.halloween_music_status = "HALLOWEEN MUSIC VERIFIED"
        app.halloween_music_error = ""
        _load_halloween_music(app)
    except HalloweenMusicError as exc:
        app.halloween_music_status = "PIXABAY NEEDS YOUR BROWSER"
        app.halloween_music_error = str(exc)
    except Exception as exc:  # defensive UI boundary
        app.halloween_music_status = "MUSIC DOWNLOAD PAUSED"
        app.halloween_music_error = str(exc)


def _halloween_loading_screen(app: Any) -> bool:
    from root_mode_runtime import loading_event
    loading_event(app, 'Halloween loading / music preparing')
    if not app.halloween_music.ready:
        threading.Thread(target=_music_worker, args=(app,), daemon=True).start()
    started = time.monotonic()
    while True:
        elapsed = time.monotonic() - started
        events = pygame.event.get()
        if not app.common_events(events):
            return False
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key in {pygame.K_RETURN, pygame.K_SPACE} and (app.halloween_music.ready or app.halloween_music_error or elapsed > 8):
                    loading_event(app, 'game running; loading complete')
                    return True
                if event.key == pygame.K_o:
                    app.halloween_music.open_official_page()
                if event.key == pygame.K_d:
                    app.halloween_music_error = ""
                    threading.Thread(target=_music_worker, args=(app,), daemon=True).start()
        if app.halloween_music.import_from_downloads():
            app.halloween_music_status = "HALLOWEEN MUSIC IMPORTED + VERIFIED"
            app.halloween_music_error = ""
            _load_halloween_music(app)

        ticks = pygame.time.get_ticks() / 1000
        _draw_night(app, ticks)
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((6, 3, 15, 145))
        app.screen.blit(veil, (0, 0))
        title = app.hero.render("HALLOWEEN UPDATE", True, ORANGE)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 115)))
        for index, text in enumerate(("PUMPKINS / PHYSICS / PARTICLES", "CPE IS WAKING UP", "THE BROKEN LANDS ARE CALLING")):
            label = app.font.render(text, True, (255, 235 - index * 42, 192 - index * 38))
            app.screen.blit(label, label.get_rect(center=(WIDTH // 2, 200 + index * 39)))
        panel = pygame.Rect(150, 355, 800, 220)
        pygame.draw.rect(app.screen, (15, 10, 30), panel, border_radius=16)
        pygame.draw.rect(app.screen, PURPLE, panel, 2, border_radius=16)
        status = app.font.render(app.halloween_music_status[:70], True, ACID if app.halloween_music.ready else ORANGE)
        app.screen.blit(status, status.get_rect(center=(WIDTH // 2, 405)))
        track = app.small.render(f'{TRACK_TITLE} — {TRACK_ARTIST}  /  Pixabay Content License', True, WHITE)
        app.screen.blit(track, track.get_rect(center=(WIDTH // 2, 448)))
        if app.halloween_music_error:
            error = app.tiny.render(app.halloween_music_error[:104], True, (255, 157, 136))
            app.screen.blit(error, error.get_rect(center=(WIDTH // 2, 486)))
            hint = "O: open official Pixabay page   D: retry/import Downloads   Enter: continue silently"
        else:
            hint = "The game is downloading the exact track requested. Enter continues when ready."
        line = app.tiny.render(hint, True, ASH)
        app.screen.blit(line, line.get_rect(center=(WIDTH // 2, 531)))
        source = app.tiny.render(TRACK_PAGE, True, (167, 144, 206))
        app.screen.blit(source, source.get_rect(center=(WIDTH // 2, 610)))
        if getattr(app, 'cpeloader_changes', []):
            warning = app.tiny.render('WARNING: Modified game files detected after unlocking CPELoader.', True, RED)
            app.screen.blit(warning, warning.get_rect(center=(WIDTH // 2, HEIGHT - 22)))
        elif getattr(app, 'cpeloader', None) and app.cpeloader.unlocked:
            warning = app.tiny.render('CPELoader unlocked — NuttyMod update override enabled.' if app.cpeloader.unlocked_updates_enabled else 'CPELoader unlocked — updates require the external installer.', True, ORANGE)
            app.screen.blit(warning, warning.get_rect(center=(WIDTH // 2, HEIGHT - 22)))
        pygame.display.flip()
        app.clock.tick(FPS)


def _halloween_menu(app: Any) -> str:
    state = app.theme_store.state()
    entries = [
        ("PLAY SOLO", "single", ORANGE),
        ("PLAY MULTIPLAYER", "multiplayer", ACID),
        ("SECURITY ???", "security", PURPLE),
        ("THEME STORE", "themes", (193, 138, 243)),
        ("ADD-ONS", "addons", (255, 202, 90)),
        ("SETTINGS", "settings", WHITE),
    ]
    if state.get("developer_enabled"):
        entries.append(("DEVELOPER MODE", "developer", (255, 107, 119)))
    entries.append(("QUIT", "quit", (255, 139, 154)))
    buttons = []
    for index, (label, _, accent) in enumerate(entries):
        column, row = index % 2, index // 2
        buttons.append(app._experience_button_type((175 + column * 385, 305 + row * 72, 350, 52), label, accent))
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return "quit"
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return "quit"
        _draw_night(app, pygame.time.get_ticks() / 1000)
        panel = pygame.Surface((930, 625), pygame.SRCALPHA)
        pygame.draw.rect(panel, (8, 5, 20, 186), panel.get_rect(), border_radius=28)
        pygame.draw.rect(panel, (158, 88, 205, 120), panel.get_rect(), 2, border_radius=28)
        app.screen.blit(panel, (85, 45))
        badge_rect = pygame.Rect(360, 67, 380, 38)
        pygame.draw.rect(app.screen, ORANGE, badge_rect, border_radius=19)
        badge = app.small.render(f"HALLOWEEN UPDATE / v{VERSION}", True, INK)
        app.screen.blit(badge, badge.get_rect(center=badge_rect.center))
        title = app.hero.render("THE CUBE BETA", True, WHITE)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 159)))
        subtitle = app.font.render("CPE physics beyond the door / enter the Broken Lands", True, (219, 192, 245))
        app.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 220)))
        selected = app.wait_click(buttons, events)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is not None:
            action = entries[selected][1]
            if action == "security":
                _security_door(app)
                continue
            return action


def _security_door(app: Any) -> None:
    door = pygame.Rect(392, 140, 316, 475)
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return
        enter = False
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key in {pygame.K_RETURN, pygame.K_SPACE}:
                    enter = True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and door.collidepoint(event.pos):
                enter = True
        _draw_night(app, pygame.time.get_ticks() / 1000)
        pygame.draw.rect(app.screen, (8, 7, 12), door.inflate(30, 26), border_radius=8)
        pygame.draw.rect(app.screen, (53, 34, 68), door, border_radius=5)
        pygame.draw.rect(app.screen, PURPLE, door, 4, border_radius=5)
        for y in range(165, 600, 48):
            pygame.draw.line(app.screen, (86, 49, 104), (410, y), (690, y), 2)
        pygame.draw.circle(app.screen, ORANGE, (671, 390), 11)
        warning = app.large.render("SECURITY ???", True, RED)
        app.screen.blit(warning, warning.get_rect(center=(WIDTH // 2, 70)))
        hint = app.font.render("CLICK THE DOOR / ENTER  •  ESC TO TURN BACK", True, WHITE)
        app.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 665)))
        pygame.display.flip()
        app.clock.tick(FPS)
        if enter:
            _broken_lands_terminal(app)
            return


def _terminal_lines(app: Any, lines: list[str], command: str, unlocked: bool) -> pygame.Rect:
    app.screen.fill((2, 4, 9))
    pygame.draw.rect(app.screen, (5, 17, 21), (0, 0, WIDTH, 48))
    header = app.small.render(f"BROKEN LANDS SECURITY TERMINAL  /  CPE CHANNEL  /  {VERSION}", True, ACID)
    app.screen.blit(header, (18, 15))
    status = "AUTHENTICATED" if unlocked else "LOCKED"
    status_color = ACID if unlocked else RED
    badge = app.small.render(status, True, status_color)
    app.screen.blit(badge, (WIDTH - badge.get_width() - 20, 15))
    y = 76
    for value in lines[-22:]:
        color = ORANGE if value.startswith("!") else (190, 232, 206)
        label = app.tiny.render(value[:132], True, color)
        app.screen.blit(label, (24, y))
        y += 24
    prompt = app.small.render("BL:\\RECOVERY> " + command + ("_" if pygame.time.get_ticks() // 450 % 2 else ""), True, WHITE)
    app.screen.blit(prompt, (24, HEIGHT - 50))
    login_rect = pygame.Rect(WIDTH - 210, HEIGHT - 100, 180, 38)
    pygame.draw.rect(app.screen, ACID if not unlocked else PURPLE, login_rect, border_radius=5)
    login = app.small.render("LOGIN" if not unlocked else "OG MENU", True, INK)
    app.screen.blit(login, login.get_rect(center=login_rect.center))
    return login_rect


def _append_catalog(lines: list[str]) -> None:
    lines.append("OG.exe recovery catalog:")
    for item in OG_VERSIONS.values():
        suffix = "READY" if item.available else "UNAVAILABLE / ARTIFACT EXPIRED"
        lines.append(f"  OG.exe -{item.version:<5}  {item.name:<18}  {suffix}")


def _og_menu(app: Any, lines: list[str]) -> str | None:
    entries = list(OG_VERSIONS.values())
    buttons = [
        app._experience_button_type((185 + (index % 2) * 385, 270 + (index // 2) * 95, 350, 65), f"{item.version} / {item.name}", ORANGE if item.available else ASH)
        for index, item in enumerate(entries)
    ]
    back = app._experience_button_type((380, 515, 340, 52), "BACK TO TERMINAL", PURPLE)
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return None
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None
        _draw_night(app, pygame.time.get_ticks() / 1000)
        title = app.large.render("OG.exe RECOVERY MENU", True, ORANGE)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 105)))
        note = app.small.render("Every available recovery downloads first and creates a full backup before replacement.", True, WHITE)
        app.screen.blit(note, note.get_rect(center=(WIDTH // 2, 165)))
        selected = app.wait_click(buttons + [back], events)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        if selected == len(entries):
            return None
        item = entries[selected]
        if not item.available:
            lines.append(f"! {item.version}: {item.note}")
            return None
        return item.version


def _recovery_screen(app: Any, version: str) -> None:
    detail = "INITIALIZING"
    ratio = 0.0

    def progress(message: str, value: float) -> None:
        nonlocal detail, ratio
        detail, ratio = message, value
        pygame.event.pump()
        _draw_night(app, pygame.time.get_ticks() / 1000)
        panel = pygame.Rect(125, 120, 850, 480)
        pygame.draw.rect(app.screen, (7, 5, 18), panel, border_radius=20)
        pygame.draw.rect(app.screen, ORANGE, panel, 3, border_radius=20)
        title = app.large.render(f"RECOVERING {version}", True, WHITE)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 205)))
        track = pygame.Rect(235, 330, 630, 34)
        pygame.draw.rect(app.screen, (48, 29, 62), track, border_radius=8)
        pygame.draw.rect(app.screen, ORANGE, (track.x, track.y, int(track.width * ratio), track.height), border_radius=8)
        label = app.font.render(detail[:76], True, ACID)
        app.screen.blit(label, label.get_rect(center=(WIDTH // 2, 410)))
        warning = app.small.render("BACKUP FIRST  /  DOWNLOAD  /  VERIFY  /  STAGE  /  REPLACE AFTER EXIT", True, ASH)
        app.screen.blit(warning, warning.get_rect(center=(WIDTH // 2, 485)))
        pygame.display.flip()

    try:
        plan = app.og_recovery.prepare(version, progress)
    except Exception as exc:
        raise OGRecoveryError(str(exc)) from exc
    _confirm_recovery(app, plan)


def _confirm_recovery(app: Any, plan: RecoveryPlan) -> None:
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key == pygame.K_r:
                    app.og_recovery.launch(plan)
                    if plan.mode == "portable":
                        save_settings(app.settings)
                        pygame.quit()
                        raise SystemExit(0)
                    return
        _draw_night(app, pygame.time.get_ticks() / 1000)
        title = app.large.render("RECOVERY READY", True, ACID)
        app.screen.blit(title, title.get_rect(center=(WIDTH // 2, 135)))
        lines = (
            f"VERSION: {plan.version}",
            f"MODE: {plan.mode.upper()}",
            "A complete backup was created and the downloaded payload was staged.",
            "Press R to apply it. Portable files replace the active payload after this game exits.",
            "Press ESC to keep the current game; the backup and staged download remain available.",
        )
        for index, value in enumerate(lines):
            label = app.font.render(value[:91], True, WHITE if index < 2 else ASH)
            app.screen.blit(label, label.get_rect(center=(WIDTH // 2, 235 + index * 48)))
        prompt = app.large.render("R = APPLY     ESC = CANCEL", True, ORANGE)
        app.screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, 575)))
        pygame.display.flip()
        app.clock.tick(FPS)


def _broken_lands_terminal(app: Any) -> None:
    lines = [
        "THE BROKEN LANDS RECOVERY NODE AWAKENED.",
        "All surviving versions report through OG.exe.",
        "Click LOGIN on the abandoned computer or type login.",
        "After login: OG.exe -list or OG.exe -<version>.",
    ]
    command = ""
    unlocked = False
    pygame.key.start_text_input()
    try:
        while True:
            events = pygame.event.get()
            if not app.common_events(events):
                return
            login_rect = pygame.Rect(WIDTH - 210, HEIGHT - 100, 180, 38)
            execute: str | None = None
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_BACKSPACE:
                        command = command[:-1]
                    elif event.key == pygame.K_RETURN:
                        execute, command = command.strip(), ""
                elif event.type == pygame.TEXTINPUT:
                    if len(command) < 72 and event.text.isprintable():
                        command += event.text
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and login_rect.collidepoint(event.pos):
                    if not unlocked:
                        execute = "login"
                    else:
                        chosen = _og_menu(app, lines)
                        if chosen:
                            execute = f"OG.exe -{chosen}"

            if execute:
                lines.append("> " + execute)
                lowered = execute.lower()
                if lowered == "login":
                    unlocked = True
                    lines.extend(("LOGIN ACCEPTED.", "OG.exe is online. The recovery catalog is unlocked."))
                    chosen = _og_menu(app, lines)
                    if chosen:
                        execute = f"OG.exe -{chosen}"
                        lines.append("> " + execute)
                        lowered = execute.lower()
                    else:
                        execute = ""
                if execute and lowered in {"help", "?"}:
                    lines.extend(("login                 unlock the OG recovery computer", "OG.exe -list          show recoverable versions", "OG.exe -<version>     download, back up, and prepare replacement", "clear                 clear the terminal", "exit                  return to the door"))
                elif execute and lowered == "clear":
                    lines = []
                elif execute and lowered in {"exit", "quit"}:
                    return
                elif execute and lowered.startswith("og.exe"):
                    if not unlocked:
                        lines.append("! ACCESS DENIED. CLICK LOGIN FIRST.")
                    else:
                        try:
                            parsed = parse_og_command(execute)
                            if parsed in {"list", "help"}:
                                _append_catalog(lines)
                            elif parsed:
                                _recovery_screen(app, parsed)
                                lines.append(f"{parsed} recovery preparation closed.")
                            else:
                                lines.append("! SYNTAX: OG.exe -list OR OG.exe -<version>")
                        except OGRecoveryError as exc:
                            lines.append("! " + str(exc))
                elif execute and lowered != "login":
                    lines.append("! UNKNOWN COMMAND. TYPE help.")

            _terminal_lines(app, lines, command, unlocked)
            pygame.display.flip()
            app.clock.tick(FPS)
    finally:
        pygame.key.stop_text_input()


def install_halloween_update(game_app: type[Any], button_type: type[Any]) -> None:
    """Install the Halloween experience after the 6.3 repair compatibility layer."""
    if getattr(game_app, "_halloween_update_installed", False):
        return
    game_app._halloween_update_installed = True
    game_app._experience_button_type = button_type
    game_app.__init__ = _halloween_init(game_app.__init__)
    game_app.fall_update_screen = _halloween_loading_screen
    game_app.main_menu = _halloween_menu
    game_app.security_door = _security_door
    game_app.broken_lands_terminal = _broken_lands_terminal


__all__ = ["install_halloween_update"]
