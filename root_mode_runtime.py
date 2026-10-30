"""Root Mode v1 / library v1.2: game-only services for NuttyMod Root."""
import logging
from pathlib import Path

VERSION = '1'
LIB_VERSION = '1.2'


def install(app, root):
    import pygame
    app.cpeloader.require_flash()
    app.root_mode_enabled = True
    app.root_mode_path = Path(root)
    logger = logging.getLogger('rootmode')
    logger.setLevel(logging.INFO)
    log_path = (Path(root)/'userdata'/'nuttymod'/'vp-loading.log').resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not any(getattr(h, 'baseFilename', None) == str(log_path) for h in logger.handlers):
        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        logger.addHandler(handler)
    app.root_mode_logger = logger
    logger.info('Root Mode v1; Root Mode lib v1.2; NuttyMod Root v1; CPELoader unlocked')
    # All game screens already flip their display; one shared overlay keeps the
    # versions visible in loading, menus and gameplay without editing each scene.
    if not hasattr(pygame.display, '_rootmode_original_flip'):
        pygame.display._rootmode_original_flip = pygame.display.flip
        def flip():
            active = getattr(pygame.display, '_rootmode_app', None)
            if active and getattr(active, 'root_mode_enabled', False):
                draw_overlay(active)
            return pygame.display._rootmode_original_flip()
        pygame.display.flip = flip
    pygame.display._rootmode_app = app


def draw_overlay(app):
    import pygame
    screen = pygame.display.get_surface()
    if screen is None: return
    font = pygame.font.Font(None, 18)
    lines = ['root mode v1', 'root mode lib v1.2', 'nuttymod root v1']
    if app.nuttymod_root_settings.get('root_mode', {}).get('verbose_loading', True):
        lines.append(getattr(app, 'root_mode_loading_status', 'VP: game running'))
    for index, text in enumerate(lines):
        label = font.render(text[:100], True, (255, 214, 125))
        pygame.draw.rect(screen, (13, 9, 28), (6, 6+index*18, label.get_width()+8, 18))
        screen.blit(label, (10, 7+index*18))


def loading_event(app, message):
    if not getattr(app, 'root_mode_enabled', False): return
    app.root_mode_loading_status = 'VP: '+message
    if app.nuttymod_root_settings['root_mode']['verbose_loading']:
        app.root_mode_logger.info('Loading: %s', message)


def userdata_path(app, relative):
    """Library file access stays inside the game's userdata, never OS rooting."""
    base = (app.root_mode_path/'userdata').resolve()
    path = (base/relative).resolve()
    if not path.is_relative_to(base): raise ValueError('Root Mode file access must stay in userdata.')
    return path
