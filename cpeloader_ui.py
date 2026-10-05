"""CPELoader unlock, reset and startup warning screens."""
import time
import pygame
from cpeloader import CPELoader
from cube_core import app_path, WIDTH, HEIGHT, FPS


class LoaderReset(Exception):
    """Return to a new GameApp after changing loader state."""


def line(app, text, y, color=(248, 252, 255), large=False):
    label = (app.large if large else app.small).render(text, True, color)
    app.screen.blit(label, label.get_rect(center=(WIDTH//2, y)))


def unlock_screen(app):
    started = time.monotonic()
    error = ''
    while True:
        progress = min(1, (time.monotonic()-started)/1.2)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_n and event.mod & pygame.KMOD_SHIFT: return True
                if progress == 1 and event.key == pygame.K_y:
                    try: app.cpeloader.unlock()
                    except (RuntimeError, OSError) as exc: error = str(exc)
                    else: raise LoaderReset()
        app.screen.fill((13, 9, 28))
        line(app, 'CPELOADER UNLOCK', 130, (255, 128, 40), True)
        line(app, 'WARNING: Unlocking allows engine flashing and changes to game files.', 240)
        line(app, 'In-game updates will be disabled. Use the external installer for updates.', 285)
        line(app, 'Unlock: cpeloader.py / cpeloader_core_runtime.js / cpeloader_core.rb', 330)
        line(app, 'The game will reset after unlocking.', 375)
        pygame.draw.rect(app.screen, (50, 35, 65), (180, 430, 740, 18), border_radius=8)
        pygame.draw.rect(app.screen, (255, 128, 40), (180, 430, int(740*progress), 18), border_radius=8)
        line(app, 'Y: UNLOCK AND RESET     SHIFT+N: KEEP CURRENT LOCK STATE', 510)
        line(app, 'Preparing loader controls...' if progress < 1 else 'Ready for your choice', 560)
        if error: line(app, error[:110], HEIGHT-35, (255, 100, 92))
        pygame.display.flip(); app.clock.tick(FPS)


def unlocked_warning(app, changes):
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER): return True
        app.screen.fill((25, 10, 20))
        line(app, 'CPELOADER IS UNLOCKED', 155, (255, 105, 85), True)
        line(app, 'Loading paused at 50%', 235)
        line(app, 'Game updates are blocked while the loader is unlocked.', 305)
        line(app, 'Update using the external installer.', 345)
        line(app, f'Modified files detected: {len(changes)}' if changes else 'Flashing is enabled for all three loader components.', 400)
        line(app, 'PRESS ENTER TO CONTINUE', 505, (255, 211, 92))
        pygame.display.flip(); app.clock.tick(FPS)


def loader_loading(app):
    changes = app.cpeloader.changes()
    app.cpeloader_changes = changes
    started, acknowledged = time.monotonic(), False
    while True:
        progress = min(1, (time.monotonic()-started)/3)
        if progress >= .5 and app.cpeloader.state().get('unlocked') is True and not acknowledged:
            progress = .5
            paused = time.monotonic()
            if not unlocked_warning(app, changes): return False
            started += time.monotonic()-paused
            acknowledged = True
        events = pygame.event.get()
        if not app.common_events(events): return False
        app.screen.fill((13, 9, 28))
        line(app, 'CPELOADER', 165, (255, 128, 40), True)
        line(app, 'Loading base game / CPE / IPE and verifying managed files', 270)
        line(app, 'UNLOCKED' if app.cpeloader.unlocked else 'LOCKED — ENGINE FLASHING BLOCKED', 320)
        pygame.draw.rect(app.screen, (50, 35, 65), (180, 400, 740, 22), border_radius=8)
        pygame.draw.rect(app.screen, (255, 128, 40), (180, 400, int(740*progress), 22), border_radius=8)
        line(app, f'{int(progress*100)}%', 455)
        line(app, 'Ctrl+A: CPELoader unlock screen', 530)
        if changes:
            line(app, f'WARNING: Game file modifications detected ({len(changes)} files).', HEIGHT-42, (255, 100, 92))
        elif app.cpeloader.unlocked:
            line(app, 'WARNING: CPELoader unlocked. Updates require the installer.', HEIGHT-42, (255, 211, 92))
        pygame.display.flip(); app.clock.tick(FPS)
        if progress >= 1: return True


def install_cpeloader_ui(game_app):
    init, common, loading = game_app.__init__, game_app.common_events, game_app.fall_update_screen
    def initialize(app, *args, **kwargs):
        init(app, *args, **kwargs)
        app.cpeloader = CPELoader(app_path())
    def events(app, incoming):
        for event in list(incoming):
            if event.type == pygame.KEYDOWN and event.key == pygame.K_a and event.mod & pygame.KMOD_CTRL:
                incoming.remove(event)  # Reserve Ctrl+A; avoid the older developer-mode shortcut.
                if not unlock_screen(app): return False
        return common(app, incoming)
    def startup(app):
        return loader_loading(app) and loading(app)
    game_app.__init__, game_app.common_events, game_app.fall_update_screen = initialize, events, startup
