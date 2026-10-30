"""6.4.2 nightly: Fluent home, theme gallery, settings and official updater."""
from __future__ import annotations

import json
import queue
import threading
import time
import webbrowser
from datetime import datetime, timezone
from types import MethodType

import pygame
from cube_core import FPS, HEIGHT, WIDTH, VERSION, THEMES, app_path, bundle_path, save_settings
from cube_updater import CubeUpdater, RELEASES_URL, NIGHTLY_URL
from fluent_ui import (BUILTINS, TEXT, SECONDARY, FluentButton, accent, background,
                       buttons, confirmation, cube, panel, paragraph, text)


def power_countdown(target=None, now=None):
    if not target:
        return 'RELEASE DATE TO BE ANNOUNCED'
    try:
        end = datetime.fromisoformat(target.replace('Z', '+00:00'))
        if end.tzinfo is None:
            raise ValueError('Time zone required')
        current = now or datetime.now(timezone.utc)
        seconds = max(0, int((end-current).total_seconds()))
    except (ValueError, TypeError, AttributeError):
        return 'RELEASE DATE TO BE ANNOUNCED'
    if seconds == 0:
        return 'COUNTDOWN COMPLETE / CHECK RELEASES'
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return f'{days:02d}D   {hours:02d}H   {minutes:02d}M   {seconds:02d}S'


def countdown_target():
    try:
        config = json.loads(bundle_path('nightly-config.json').read_text(encoding='utf-8'))
        return config.get('power_remastered_release_utc') if isinstance(config, dict) else None
    except (OSError, ValueError):
        return None


def set_theme(app, theme):
    if theme not in THEMES:
        raise ValueError('Theme is not installed.')
    app.theme_store.set_active_theme(theme)
    app.settings['theme'] = theme
    app.background_cache.clear()
    save_settings(app.settings)


def home_items(app):
    items = [('Home', 'home'), ('Themes', 'themes'), ('Cube Beta Updater', 'updater'),
             ('Settings', 'settings'), ('Security ???', 'security')]
    if app.theme_store.state().get('developer_enabled'):
        items.append(('Developer mode', 'developer'))
    items.append(('Exit game', 'quit'))
    return items


def render_home(app, ticks=0):
    background(app, ticks)
    a = accent(app)
    panel(app, pygame.Rect(24, 24, 235, 672), color=(20, 22, 34))
    cube(app, (69, 81), 25, ticks)
    text(app, 'THE CUBE', (112, 51), font=app.font)
    text(app, 'BETA / NIGHTLY', (112, 80), SECONDARY)
    items = home_items(app)
    controls = [FluentButton((41, 153+i*58, 201, 46), label, a) for i, (label, _) in enumerate(items)]
    text(app, '6.4.2-nightly', (45, 599), a)
    text(app, 'Tab to navigate · Enter to select', (45, 631), SECONDARY, app.tiny, 192)
    text(app, 'F11 fullscreen', (45, 655), SECONDARY, app.tiny)
    text(app, 'YOUR PHYSICS. YOUR WORLD.', (291, 37), a)
    text(app, 'Welcome back.', (289, 70), font=app.large)
    text(app, 'Halloween by default. A fresh space to create.', (292, 130), SECONDARY)
    panel(app, pygame.Rect(283, 179, 793, 238), color=(32, 31, 47))
    text(app, 'HALLOWEEN / FLUENT EXPERIENCE', (311, 204), a)
    text(app, 'Make a little chaos.', (310, 241), font=app.large)
    text(app, 'Grab, throw and build with CPE + IPE particles.', (313, 302), SECONDARY)
    cube(app, (960, 290), 57, ticks)
    controls += [FluentButton((311, 348, 229, 46), 'Play solo  →', a, primary=True),
                 FluentButton((556, 348, 226, 46), 'Multiplayer', a)]
    panel(app, pygame.Rect(283, 435, 386, 115))
    text(app, 'Make it yours', (305, 451), font=app.font)
    text(app, f'Active theme: {app.settings["theme"].title()}', (305, 480), SECONDARY)
    controls.append(FluentButton((500, 500, 148, 33), 'Browse themes', a))
    panel(app, pygame.Rect(686, 435, 390, 115))
    text(app, 'Add-on workshop', (708, 451), font=app.font)
    text(app, 'Python + Ruby extensions', (708, 480), SECONDARY)
    controls.append(FluentButton((903, 500, 150, 33), 'Open add-ons', a))
    panel(app, pygame.Rect(283, 568, 793, 128))
    text(app, 'NEXT CHAPTER', (305, 585), a, app.tiny)
    text(app, 'The Cube Beta · Power & Remastered', (305, 609), font=app.font)
    text(app, power_countdown(getattr(app, 'power_release_utc', None)), (305, 649), SECONDARY)
    unlocked = getattr(app, 'cpeloader', None) and app.cpeloader.unlocked
    text(app, 'LOADER UNLOCKED' if unlocked else 'CPELOADER LOCKED', (858, 649), a, app.tiny)
    return controls, [key for _, key in items]+['single', 'multiplayer', 'themes', 'addons']


def _main_menu(app):
    focus = 0
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            return 'quit'
        if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            return 'quit'
        controls, actions = render_home(app, pygame.time.get_ticks()/1000)
        selected, focus = buttons(app, controls, events, focus)
        app.draw_toast()
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        action = actions[selected]
        if action == 'home':
            continue
        if action == 'security':
            from halloween_update import _security_door
            _security_door(app)
        elif action == 'themes':
            _themes_menu(app)
        elif action == 'updater':
            if _updater_menu(app):
                return 'quit'
        else:
            return action


def _themes_menu(app):
    focus = 0
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            raise SystemExit
        if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            return
        background(app)
        text(app, 'PERSONALIZE YOUR CUBE', (56, 34), accent(app))
        text(app, 'Themes', (53, 62), font=app.large)
        text(app, 'Live previews. Shared across your menu, loading screens and game.', (56, 123), SECONDARY)
        controls = []
        for i, theme in enumerate(BUILTINS):
            rect = pygame.Rect(56+(i%4)*251, 179+(i//4)*187, 233, 166)
            palette = THEMES[theme]
            panel(app, rect, color=palette['sky_top'])
            pygame.draw.circle(app.screen, palette['sun'], (rect.x+184, rect.y+39), 18)
            pygame.draw.rect(app.screen, palette['sand'], (rect.x+1, rect.y+75, 231, 26))
            name = ('Active: ' if app.settings['theme'] == theme else '')+theme.title()
            controls.append(FluentButton((rect.x+12, rect.y+112, 209, 40), name, palette['sun']))
        controls += [FluentButton((56, 594, 315, 50), 'Community theme store', accent(app)),
                     FluentButton((390, 594, 240, 50), 'Back', accent(app))]
        text(app, 'Built-in themes change instantly. Community themes keep verification and backups.', (56, 672), SECONDARY)
        selected, focus = buttons(app, controls, events, focus)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is not None:
            if selected < len(BUILTINS):
                set_theme(app, BUILTINS[selected])
            elif selected == len(BUILTINS):
                app.theme_store_menu()
            else:
                return


def _settings_menu(app):
    focus = 0
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            raise SystemExit
        if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            return
        background(app)
        text(app, 'MAKE YOURSELF AT HOME', (80, 47), accent(app))
        text(app, 'Settings', (77, 83), font=app.large)
        rows = [('Music', 'music'), ('Click sounds', 'sound'), ('Fullscreen', 'fullscreen'),
                ('Gravity', 'gravity'), ('Event interval', 'event_interval')]
        controls = []
        for i, (label, key) in enumerate(rows):
            y = 179+i*76
            panel(app, pygame.Rect(80, y, 940, 64), radius=14)
            text(app, label, (103, y+19), font=app.font)
            value = app.settings[key]
            display = ('On' if value else 'Off') if type(value) is bool else str(value)+(' s' if key == 'event_interval' else '')
            controls.append(FluentButton((768, y+10, 231, 44), display+' / change', accent(app)))
        controls.append(FluentButton((80, 601, 275, 50), 'Back', accent(app)))
        text(app, 'Changes save immediately. Original click sound retained.', (80, 675), SECONDARY)
        selected, focus = buttons(app, controls, events, focus)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        if selected == len(rows):
            return
        key = rows[selected][1]
        if key in ('music', 'sound', 'fullscreen'):
            app.settings[key] = not app.settings[key]
            if key == 'fullscreen':
                app.apply_display()
            if key == 'music' and pygame.mixer.get_init():
                app.start_music() if app.settings[key] else pygame.mixer.music.pause()
        else:
            choices = [450, 700, 900, 1200, 1600] if key == 'gravity' else [8, 12, 18, 30, 45, 60]
            old = app.settings[key]
            app.settings[key] = choices[(choices.index(old)+1)%len(choices)] if old in choices else choices[0]
        save_settings(app.settings)


def _updater_menu(app):
    manager = CubeUpdater(app_path(), VERSION)
    messages = queue.Queue()
    cancelled = threading.Event()
    busy, updates, downloaded, focus = False, [], None, 0
    status = 'Check GitHub for newer official builds. Nothing installs automatically.'
    def run(action):
        nonlocal busy
        busy = True
        def worker():
            try:
                result = manager.check() if action == 'check' else manager.download(updates[0], lambda s: messages.put(('status', s)), cancelled)
                messages.put((action, result))
            except Exception as exc:
                messages.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()
    while True:
        events = pygame.event.get()
        if not app.common_events(events):
            cancelled.set()
            return True
        if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            cancelled.set()
            return False
        while not messages.empty():
            kind, result = messages.get_nowait()
            if kind == 'status':
                status = result
            else:
                busy = False
                if kind == 'check':
                    updates, downloaded = result, None
                    status = f'Available: {updates[0].version} / {updates[0].name}' if updates else 'No newer checksum-verified release is available. Nightly artifacts are listed separately.'
                elif kind == 'download':
                    downloaded = result
                    status = 'Download verified. '+('Run the installer below, then the game exits.' if updates[0].installer else 'Open the download folder; close the game before installing with the launcher.')
                else:
                    status = 'Update stopped: '+result
        try:
            manager.require_update()
            blocked = ''
        except (OSError, ValueError, PermissionError) as exc:
            blocked = str(exc)
        background(app)
        text(app, 'OFFICIAL DOWNLOADS ONLY', (70, 44), accent(app))
        text(app, 'Cube Beta Updater', (67, 83), font=app.large)
        text(app, f'Installed: {VERSION} / Python 3.15.2 nightly', (70, 147), SECONDARY)
        panel(app, pygame.Rect(70, 201, 960, 228))
        text(app, 'Updates blocked' if blocked else 'You stay in control.', (95, 227), font=app.font)
        paragraph(app, blocked or status, pygame.Rect(95, 273, 904, 131), (255, 166, 130) if blocked else SECONDARY)
        paragraph(app, 'Downloads require a GitHub SHA-256 digest. The running game is never overwritten. Unlocked, partially unlocked or custom builds must use their owner’s installer. Keep your backups.', pygame.Rect(70, 452, 950, 100))
        labels = ['Check for updates', 'Download verified build', 'Run installer + exit' if downloaded and updates and updates[0].installer else 'Open download folder', 'Nightly builds', 'Back']
        controls = [FluentButton((70+(i%3)*325, 568+(i//3)*61, 310, 46), label, accent(app)) for i, label in enumerate(labels)]
        selected, focus = buttons(app, controls, events, focus)
        if busy:
            text(app, 'Working… Back cancels a download.', (70, 698), accent(app), app.tiny)
        pygame.display.flip()
        app.clock.tick(FPS)
        if selected is None:
            continue
        if selected == 4:
            cancelled.set()
            return False
        if busy:
            continue
        if selected == 0:
            run('check')
        elif selected in (1, 2) and blocked:
            status = blocked
        elif selected == 1:
            if not updates:
                status = 'Check for an available update first.'
            elif confirmation(app, 'Download this update?', f'{updates[0].version}\n{updates[0].name}\nOnly the download is performed. Your current game and backups stay in place.', 'DOWNLOAD'):
                run('download')
        elif selected == 2 and downloaded:
            if updates[0].installer:
                if confirmation(app, 'Run installer and exit?', 'The game will exit after starting this verified installer. Choose a separate installation folder when required. Existing mods and backups are not deleted.', 'RUN + EXIT'):
                    try:
                        manager.launch_installer(updates[0], downloaded)
                        return True
                    except (OSError, ValueError, PermissionError) as exc:
                        status = str(exc)
            else:
                webbrowser.open(downloaded.parent.as_uri())
        elif selected == 3:
            if blocked:
                status = blocked
            elif confirmation(app, 'Open nightly downloads?', 'Nightly builds are experimental. This opens nightly.link for the official GitHub Actions artifact. It is not a verified update or an automatic installation.', 'OPEN NIGHTLY.LINK'):
                webbrowser.open(NIGHTLY_URL)


def render_loading(app, progress, ticks=0, status='Preparing your physics world'):
    background(app, ticks)
    panel(app, pygame.Rect(170, 88, 760, 544))
    text(app, f'THE CUBE BETA / {VERSION}', (212, 123), accent(app))
    cube(app, (550, 280), 70, ticks)
    text(app, 'A little spooky. A lot of physics.', (240, 381), font=app.font)
    text(app, status, (212, 427), SECONDARY, width=674)
    track = pygame.Rect(212, 474, 676, 8)
    pygame.draw.rect(app.screen, (54, 55, 73), track, border_radius=4)
    pygame.draw.rect(app.screen, accent(app), (track.x, track.y, max(1, int(track.width*progress)), 8), border_radius=4)
    text(app, f'{int(progress*100):02d}%  /  CPE + IPE', (212, 502), SECONDARY)
    text(app, 'POWER & REMASTERED', (212, 550), accent(app), app.tiny)
    text(app, power_countdown(getattr(app, 'power_release_utc', None)), (212, 578), SECONDARY)


def _loading_screen(app):
    from halloween_update import _load_halloween_music
    from halloween_music import HalloweenMusicError
    from root_mode_runtime import loading_event
    started = time.monotonic()
    def music():
        try:
            app.halloween_music.download()
            app.halloween_music_status = 'Halloween music ready'
        except (HalloweenMusicError, OSError) as exc:
            app.halloween_music_error = str(exc)
    if not app.halloween_music.ready:
        threading.Thread(target=music, daemon=True).start()
    stages = ['Preparing CPE and IPE', 'Applying Fluent theme', 'Preparing Halloween audio', 'Your world is ready']
    while True:
        progress = min(1, (time.monotonic()-started)/4)
        events = pygame.event.get()
        if not app.common_events(events):
            return False
        if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            return False
        skip = progress >= .5 and any(e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE) for e in events)
        render_loading(app, progress, pygame.time.get_ticks()/1000, stages[min(3, int(progress*4))])
        warning = 'Modified game files detected' if getattr(app, 'cpeloader_changes', []) else ('CPELoader unlocked / use the external installer' if app.cpeloader.unlocked else 'CPELoader locked / official updates enabled')
        text(app, warning, (212, 659), accent(app))
        pygame.display.flip()
        app.clock.tick(FPS)
        if progress >= 1 or skip:
            _load_halloween_music(app)
            app.start_music()
            loading_event(app, 'Fluent Halloween nightly ready')
            return True


def install_nightly_ui(game_app):
    if getattr(game_app, '_nightly_ui_installed', False):
        return
    game_app._nightly_ui_installed = True
    original = game_app.__init__
    def initialize(app, *args, **kwargs):
        original(app, *args, **kwargs)
        if not app.settings.get('fluent_ui_seen'):
            set_theme(app, 'halloween')
            app.settings['fluent_ui_seen'] = True
            save_settings(app.settings)
        app.power_release_utc = countdown_target()
        pygame.display.set_caption(f'The Cube Beta / {VERSION} / Fluent Halloween')
        # Error Update binds an instance method, which wins over class patches.
        # Explicitly replace it so the real running game gets the new home.
        app.main_menu = MethodType(_main_menu, app)
        app.fall_update_screen = MethodType(_loading_screen, app)
        try:
            pygame.display.set_icon(pygame.image.load(str(bundle_path('halloween_cube_icon.png'))))
        except (OSError, pygame.error):
            pass
    game_app.__init__ = initialize
    game_app.main_menu = _main_menu
    game_app.settings_menu = _settings_menu
    game_app.fall_update_screen = _loading_screen
    game_app._experience_button_type = FluentButton
