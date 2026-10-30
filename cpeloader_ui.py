"""CPELoader unlock, reset and startup warning screens."""
import time
from types import MethodType
import pygame
from cpeloader import CPELoader
from cube_core import app_path, WIDTH, HEIGHT, FPS
from fluent_ui import (FluentButton, accent, background, buttons, panel,
                       paragraph, text)


class LoaderReset(Exception):
    """Return to a new GameApp after changing loader state."""


def line(app, text, y, color=(248, 252, 255), large=False):
    label = (app.large if large else app.small).render(text, True, color)
    app.screen.blit(label, label.get_rect(center=(WIDTH//2, y)))


def unlock_screen(app):
    started = time.monotonic()
    error = ''
    focus = 0
    while True:
        progress = min(1, (time.monotonic()-started)/1.2)
        events = pygame.event.get()
        requested = False
        for event in events:
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or (event.key == pygame.K_n and event.mod & pygame.KMOD_SHIFT): return True
                if progress == 1 and event.key == pygame.K_y: requested = True
        if requested:
            try: app.cpeloader.unlock()
            except (RuntimeError, OSError) as exc: error = str(exc)
            else: raise LoaderReset()
        render_unlock(app, progress, error)
        items = [FluentButton((207, 553, 315, 48), 'Keep locked / Shift+N', accent(app)),
                 FluentButton((542, 553, 350, 48), 'Unlock + restart / Y' if progress == 1 else 'Preparing controls…', (255, 155, 111))]
        selected, focus = buttons(app, items, events, focus)
        if selected == 0: return True
        if selected == 1 and progress == 1:
            try: app.cpeloader.unlock()
            except (RuntimeError, OSError) as exc: error = str(exc)
            else: raise LoaderReset()
        pygame.display.flip(); app.clock.tick(FPS)


def render_unlock(app, progress=1, error=''):
    background(app)
    panel(app, pygame.Rect(162, 72, 776, 576))
    text(app, 'CPELOADER v2 / DEVICE INTEGRITY', (207, 109), accent(app))
    text(app, 'Unlock your cube?', (204, 156), font=app.large, width=683)
    paragraph(app, 'Unlocking lets trusted tools change the engine and game files. Modified code can run with your user permissions. Only flash projects you trust.', pygame.Rect(207, 238, 679, 108))
    panel(app, pygame.Rect(207, 364, 685, 132), color=(43, 34, 43), radius=12)
    paragraph(app, 'The game restarts after unlocking. Official nightly updates will be blocked; use the external installer. Your existing backups are not deleted.\nComponents: Python · Node.js · Ruby', pygame.Rect(228, 382, 643, 106), (255, 195, 160))
    if error:
        text(app, error, (207, 513), (255, 143, 130), width=685)
    else:
        pygame.draw.rect(app.screen, (56, 54, 68), (207, 519, 685, 4), border_radius=2)
        pygame.draw.rect(app.screen, accent(app), (207, 519, max(1, int(685*progress)), 4), border_radius=2)


def render_loader_warning(app, changes, modified=False):
    background(app)
    panel(app, pygame.Rect(150, 70, 800, 580))
    text(app, 'CPELOADER v2 / REVIEW BEFORE CONTINUING', (192, 109), (255, 162, 119))
    text(app, 'Your game has changed.' if modified else 'Your loader is unlocked.', (189, 159), font=app.large, width=711)
    paragraph(app, 'Files differ from the original release, or verification is unavailable. Continue only if you trust these modifications.' if modified else 'Loading paused at 50%. Flashing is enabled for Python, Node.js and Ruby. This is not an error, but modified code is not verified by the game.', pygame.Rect(192, 241, 714, 95))
    panel(app, pygame.Rect(192, 356, 716, 152), color=(38, 31, 43), radius=12)
    override = app.cpeloader.unlocked_updates_enabled
    info = ('NuttyMod override present. The new official updater still blocks unlocked games.' if override else 'Official updates are blocked while CPELoader is unlocked. Use the external installer.')
    paragraph(app, info, pygame.Rect(213, 373, 674, 56), (255, 198, 165))
    detail = ', '.join(changes[:3]) if changes else 'Keep backups and review every flashed project.'
    text(app, f'{len(changes)} integrity warning(s)' if changes else 'Your lock state is unchanged.', (213, 442), font=app.small)
    text(app, detail, (213, 471), width=672)
    text(app, 'Enter to continue  ·  Esc to close', (192, 606), font=app.small)


def unlocked_warning(app, changes):
    focus = 0
    while True:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): return True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return False
        render_loader_warning(app, changes)
        items = [FluentButton((192, 540, 716, 46), 'I understand · Continue / Enter', accent(app))]
        selected, focus = buttons(app, items, [e for e in events if e.type != pygame.KEYDOWN or e.key != pygame.K_SPACE], focus)
        if selected is not None: return True
        pygame.display.flip(); app.clock.tick(FPS)


def modified_warning(app, changes):
    while True:
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): return True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE: return False
        render_loader_warning(app, changes, modified=True)
        button = FluentButton((192, 540, 716, 46), 'I trust these changes · Continue / Enter', accent(app))
        button.draw(app.screen, app.small, pygame.mouse.get_pos())
        if any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 and button.rect.collidepoint(e.pos) for e in events):
            app.play_click()
            return True
        pygame.display.flip(); app.clock.tick(FPS)


def loader_loading(app):
    from root_mode_runtime import loading_event
    loading_event(app, 'verifying game files / Root Mode core / userdata')
    changes = app.cpeloader.changes()
    if getattr(app, 'nuttymod_root_error', ''):
        changes.append('NuttyMod Root disabled: '+app.nuttymod_root_error)
    app.cpeloader_changes = changes
    if changes:
        loading_event(app, 'file modification warning; waiting for Enter')
        if not modified_warning(app, changes): return False
    started, acknowledged = time.monotonic(), False
    recorded = -1
    while True:
        progress = min(1, (time.monotonic()-started)/3)
        milestone = int(progress*10)*10
        if milestone != recorded:
            loading_event(app, str(milestone)+'% CPELoader loading'); recorded = milestone
        if progress >= .5 and app.cpeloader.state().get('unlocked') is True and not acknowledged:
            progress = .5
            paused = time.monotonic()
            loading_event(app, '50% unlocked loader warning; waiting for Enter')
            if not unlocked_warning(app, changes): return False
            started += time.monotonic()-paused
            acknowledged = True
        events = pygame.event.get()
        if not app.common_events(events): return False
        background(app)
        panel(app, pygame.Rect(150, 100, 800, 510))
        text(app, 'CPELOADER v2 / STARTUP', (195, 140), accent(app))
        text(app, 'Preparing your cube.', (192, 193), font=app.large)
        text(app, 'Verifying the base game, CPE and IPE managed files', (195, 281))
        text(app, 'UNLOCKED' if app.cpeloader.unlocked else 'LOCKED / ENGINE FLASHING BLOCKED', (195, 332), accent(app))
        pygame.draw.rect(app.screen, (50, 45, 65), (195, 402, 710, 8), border_radius=4)
        pygame.draw.rect(app.screen, accent(app), (195, 402, max(1, int(710*progress)), 8), border_radius=4)
        text(app, f'{int(progress*100)}% / Integrity checks', (195, 435))
        text(app, 'Ctrl+A to review CPELoader unlock options', (195, 550))
        if changes:
            line(app, f'WARNING: Game file modifications detected ({len(changes)} files).', HEIGHT-42, (255, 100, 92))
        elif app.cpeloader.unlocked:
            line(app, 'WARNING: Unlocked loader / NuttyMod updates enabled.' if app.cpeloader.unlocked_updates_enabled else 'WARNING: CPELoader unlocked. Updates require the installer.', HEIGHT-42, (255, 211, 92))
        pygame.display.flip(); app.clock.tick(FPS)
        if progress >= 1:
            loading_event(app, 'CPELoader complete; Christmas loading screen next')
            return True


def install_cpeloader_ui(game_app):
    init, common, loading = game_app.__init__, game_app.common_events, game_app.fall_update_screen
    def initialize(app, *args, **kwargs):
        init(app, *args, **kwargs)
        app.cpeloader = CPELoader(app_path())
        app.fall_update_screen = MethodType(startup, app)
        from flashed_runtime import initialize_profile
        initialize_profile(app, app_path())
    def events(app, incoming):
        for event in list(incoming):
            if event.type == pygame.KEYDOWN and event.key == pygame.K_a and event.mod & pygame.KMOD_CTRL:
                incoming.remove(event)  # Reserve Ctrl+A; avoid the older developer-mode shortcut.
                if not unlock_screen(app): return False
        return common(app, incoming)
    def startup(app):
        return loader_loading(app) and loading(app)
    game_app.__init__, game_app.common_events, game_app.fall_update_screen = initialize, events, startup
