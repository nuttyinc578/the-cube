"""Christmas visuals and session-only CPE performance controls."""
from __future__ import annotations

import math
import pygame

from cube_core import WIDTH, HEIGHT, FPS, THEMES, bundle_path
from cpe.performance import fast_enabled, set_fast_mode
from fluent_ui import FluentButton, accent, background, buttons, confirmation, panel, paragraph, text


def snow(surface, ticks, count=55):
    for i in range(count):
        x = int((i * 113 + math.sin(ticks * .7 + i) * 19) % WIDTH)
        y = int((i * 79 + ticks * (22 + i % 19)) % HEIGHT)
        pygame.draw.circle(surface, (223, 245, 255), (x, y), 1 + i % 3)


def christmas_background(app, ticks, simple=False):
    theme = THEMES[app.settings['theme']]
    app.screen.fill(theme['sky_top'])
    pygame.draw.circle(app.screen, (225, 240, 254), (910, 100), 47)
    for i, x in enumerate(range(20, WIDTH, 145)):
        base = 605 + i % 2 * 18
        pygame.draw.rect(app.screen, (78, 54, 48), (x+22, base-20, 12, 55))
        for layer in range(3):
            top = base-160+layer*40
            half = 28+layer*15
            pygame.draw.polygon(app.screen, (26, 81+layer*13, 67),
                                [(x+28, top), (x+28-half, top+80), (x+28+half, top+80)])
            pygame.draw.line(app.screen, (221, 241, 247), (x+28, top), (x+28-half, top+80), 4)
        for light in range(4):
            pygame.draw.circle(app.screen, ((246, 110, 105), (246, 212, 127))[light % 2],
                               (x+8+(light%2)*36, base-95+light*20), 4)
    pygame.draw.rect(app.screen, (195, 224, 234), (0, 640, WIDTH, HEIGHT-640))
    snow(app.screen, ticks, 18 if fast_enabled() else 55)


def christmas_icon(size=64):
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surface, (52, 172, 143), (9, 22, 46, 37), border_radius=8)
    pygame.draw.rect(surface, (211, 248, 243), (9, 22, 46, 37), 2, border_radius=8)
    pygame.draw.polygon(surface, (230, 65, 83), [(8, 23), (44, 3), (55, 23)])
    pygame.draw.line(surface, (250, 252, 255), (10, 24), (54, 24), 7)
    pygame.draw.circle(surface, (250, 252, 255), (45, 6), 5)
    pygame.draw.circle(surface, (15, 43, 45), (24, 38), 3)
    pygame.draw.circle(surface, (15, 43, 45), (42, 38), 3)
    pygame.draw.arc(surface, (15, 43, 45), (24, 40, 18, 12), math.pi, math.tau, 2)
    return surface


def render_fast_warning(app):
    app.screen.fill((12, 17, 27))
    text(app, 'CPE 0.0.3-NIGHTLY / EXPERIMENTAL PERFORMANCE', (80, 63), (255, 191, 112))
    text(app, 'Before you go fast.', (77, 123), font=app.large)
    panel(app, pygame.Rect(80, 218, 940, 286), color=(38, 32, 40))
    paragraph(app,
        'Fast CPE lowers solver iterations from 20 to 12 and limits IPE to 800 particles. '
        'Complex stacks may wobble or collide less accurately. Existing particles above the limit are discarded.\n'
        'The 120 Hz timestep, cache protection and loader checks stay enabled. This is experimental; FPS gains are not guaranteed.\n'
        'This setting is session-only. Ctrl+Alt+T restores normal quality.',
        pygame.Rect(109, 245, 881, 233), (244, 217, 185), app.font)
    text(app, 'Choose Cancel to keep normal quality.', (80, 645))
    return [FluentButton((80, 551, 442, 54), 'Cancel / Esc'),
            FluentButton((544, 551, 476, 54), 'I understand / Enable Fast CPE', accent(app), primary=True)]


def fast_warning(app):
    """Full display warning; always restore the user's previous display mode."""
    was_fullscreen = bool(app.settings.get('fullscreen', False))
    focus = 0
    try:
        app.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
        while True:
            events = pygame.event.get()
            if any(e.type == pygame.QUIT for e in events):
                return None
            if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
                return False
            selected, focus = buttons(app, render_fast_warning(app), events, focus)
            pygame.display.flip()
            app.clock.tick(FPS)
            if selected is not None:
                return selected == 1
    finally:
        app.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN if was_fullscreen else 0)


def toggle_fast(app):
    if fast_enabled():
        set_fast_mode(False)
        app.notify('CPE normal quality restored')
        return True
    from cpe.backend import BACKEND
    if BACKEND != 'classic':
        app.notify('Fast CPE is supported by the bundled CPE backend only.', 5)
        return True
    if not confirmation(app, 'Enable Fast CPE?',
                        'Trade some physics accuracy and particle detail for lower processing cost? '
                        'A full-screen warning follows. Nothing changes until you accept both screens.',
                        'Review warning', danger=True):
        return True
    accepted = fast_warning(app)
    if accepted is None:
        return False
    if accepted:
        set_fast_mode(True)
        app.notify('Fast CPE enabled / Ctrl+Alt+T restores quality', 5)
    return True


def install_christmas_update(game_app):
    if getattr(game_app, '_christmas_installed', False):
        return
    game_app._christmas_installed = True
    original_init, original_events, original_background = game_app.__init__, game_app.common_events, game_app.draw_background

    def initialize(app, *args, **kwargs):
        original_init(app, *args, **kwargs)
        pygame.display.set_icon(christmas_icon())
        # Do not download Halloween audio for the Christmas edition.
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.load(str(bundle_path('fall_music.mp3')))
                pygame.mixer.music.set_volume(.3)
            except (OSError, pygame.error):
                pass

    def events(app, incoming):
        for event in list(incoming):
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_t
                    and event.mod & pygame.KMOD_CTRL and event.mod & pygame.KMOD_ALT):
                incoming.remove(event)
                if not getattr(event, 'repeat', False) and not toggle_fast(app):
                    return False
        return original_events(app, incoming)

    def draw(app, ticks, simple=False):
        if app.settings.get('theme') == 'christmas':
            christmas_background(app, ticks, simple)
        else:
            original_background(app, ticks, simple)

    game_app.__init__, game_app.common_events, game_app.draw_background = initialize, events, draw
