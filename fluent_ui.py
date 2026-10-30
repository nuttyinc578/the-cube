"""Shared, code-drawn Fluent-inspired surfaces for the game and CPELoader."""
from __future__ import annotations

import math
import pygame
from cube_core import THEMES, WIDTH, HEIGHT

TEXT = (242, 244, 251)
SECONDARY = (168, 177, 198)
BORDER = (66, 68, 88)
BUILTINS = ('christmas', 'halloween', 'aurora', 'midnight', 'rose', 'maple', 'harvest', 'twilight')


def accent(app):
    return THEMES.get(getattr(app, 'settings', {}).get('theme'), THEMES['halloween'])['sun']


def text(app, value, pos, color=TEXT, font=None, width=None):
    font = font or app.small
    value = str(value)
    if width:
        while value and font.size(value)[0] > width:
            value = value[:-2].rstrip() + '…' if len(value) > 2 else ''
    app.screen.blit(font.render(value, True, color), pos)


def paragraph(app, value, rect, color=SECONDARY, font=None):
    font = font or app.small
    y = rect.y
    for source in value.splitlines():
        current = ''
        for word in source.split():
            candidate = (current + ' ' + word).strip()
            if current and font.size(candidate)[0] > rect.width:
                text(app, current, (rect.x, y), color, font)
                y += font.get_linesize() + 5
                current = word
            else:
                current = candidate
        if y + font.get_linesize() > rect.bottom:
            return
        text(app, current, (rect.x, y), color, font)
        y += font.get_linesize() + 7


def panel(app, rect, color=(27, 29, 43), border=BORDER, radius=20):
    pygame.draw.rect(app.screen, (5, 7, 15), rect.move(0, 4), border_radius=radius)
    pygame.draw.rect(app.screen, color, rect, border_radius=radius)
    pygame.draw.rect(app.screen, border, rect, 1, border_radius=radius)


def background(app, ticks=0):
    theme_id = getattr(app, 'settings', {}).get('theme', 'halloween')
    cache = getattr(app, '_fluent_background', None)
    if cache is None or cache[0] != theme_id:
        surface = pygame.Surface((WIDTH, HEIGHT))
        palette = THEMES.get(theme_id, THEMES['halloween'])
        for y in range(HEIGHT):
            mix = y / HEIGHT
            color = tuple(int((palette['sky_top'][i] * (1 - mix) + palette['sky_bottom'][i] * mix) * .43) for i in range(3))
            pygame.draw.line(surface, color, (0, y), (WIDTH, y))
        app._fluent_background = (theme_id, surface)
    app.screen.blit(app._fluent_background[1], (0, 0))
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    color = accent(app)
    for i in range(6, 0, -1):
        pygame.draw.circle(glow, (*color, 3), (900, 140), 65 + i * 37)
    app.screen.blit(glow, (0, 0))
    if theme_id == 'christmas':
        from christmas_update import snow
        from cpe.performance import fast_enabled
        snow(app.screen, ticks, 18 if fast_enabled() else 55)
    for i in range(16):
        x = (i * 137 + 47) % WIDTH
        y = int(42 + (i * 71) % 600 + math.sin(ticks * .5 + i) * 9)
        pygame.draw.circle(app.screen, (80, 77, 99), (x, y), 1)


class FluentButton:
    def __init__(self, rect, text, accent=(255, 157, 83), dark_text=False, primary=False):
        self.rect = pygame.Rect(rect)
        self.text, self.accent, self.primary = text, accent, primary

    def draw(self, surface, font, mouse):
        hover = self.rect.collidepoint(mouse)
        fill = self.accent if self.primary else ((48, 50, 68) if hover else (35, 37, 53))
        pygame.draw.rect(surface, fill, self.rect, border_radius=12)
        pygame.draw.rect(surface, self.accent if hover else BORDER, self.rect, 1, border_radius=12)
        label = font.render(self.text, True, (18, 20, 30) if self.primary else TEXT)
        surface.blit(label, label.get_rect(center=self.rect.center))


def buttons(app, items, events, focus=0):
    """Mouse and keyboard have the same activation path and click sound."""
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_TAB, pygame.K_DOWN, pygame.K_UP):
                step = -1 if event.key == pygame.K_UP or getattr(event, 'mod', 0) & pygame.KMOD_SHIFT else 1
                focus = (focus + step) % len(items)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                app.play_click()
                return focus, focus
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for i, button in enumerate(items):
                if button.rect.collidepoint(event.pos):
                    app.play_click()
                    return i, i
    mouse = pygame.mouse.get_pos()
    for i, button in enumerate(items):
        button.draw(app.screen, app.small, mouse)
        if i == focus:
            pygame.draw.rect(app.screen, button.accent, button.rect.inflate(6, 6), 2, border_radius=14)
    return None, focus


def cube(app, center, size=64, ticks=0):
    x, y = center
    y += int(math.sin(ticks * 1.6) * 7)
    a = accent(app)
    top = [(x, y-size), (x+size, y-size//2), (x, y), (x-size, y-size//2)]
    left = [(x-size, y-size//2), (x, y), (x, y+size), (x-size, y+size//2)]
    right = [(x+size, y-size//2), (x, y), (x, y+size), (x+size, y+size//2)]
    for points, strength in ((top, 1), (left, .68), (right, .85)):
        pygame.draw.polygon(app.screen, tuple(int(c*strength) for c in a), points)
        pygame.draw.lines(app.screen, (255, 219, 179), True, points, 2)
    if getattr(app, 'settings', {}).get('theme', 'halloween') == 'halloween':
        for eye in (-23, 23):
            pygame.draw.polygon(app.screen, (35, 24, 40), [(x+eye-8, y+10), (x+eye+7, y+15), (x+eye, y+27)])
    elif getattr(app, 'settings', {}).get('theme') == 'christmas':
        pygame.draw.polygon(app.screen, (231, 70, 88),
                            [(x-size, y-size//2), (x+size//3, y-size*1.6), (x+size, y-size//2)])
        pygame.draw.line(app.screen, (246, 251, 255), (x-size, y-size//2), (x+size, y-size//2), max(4, size//6))
        pygame.draw.circle(app.screen, (246, 251, 255), (int(x+size//3), int(y-size*1.6)), max(4, size//7))


def confirmation(app, title, body, accept='CONTINUE', danger=False):
    items = [FluentButton((220, 527, 310, 52), 'Cancel / Esc'),
             FluentButton((550, 527, 330, 52), accept, (255, 151, 104) if danger else accent(app), primary=True)]
    focus = 0  # Destructive actions always default to Cancel.
    while True:
        events = pygame.event.get()
        if any(e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE) for e in events):
            return False
        background(app, pygame.time.get_ticks()/1000)
        panel(app, pygame.Rect(170, 123, 760, 492))
        text(app, 'CUBE BETA  /  CONFIRM YOUR CHOICE', (220, 163), accent(app))
        text(app, title, (220, 211), font=app.large, width=660)
        paragraph(app, body, pygame.Rect(220, 296, 660, 200))
        selected, focus = buttons(app, items, events, focus)
        pygame.display.flip()
        app.clock.tick(60)
        if selected is not None:
            return selected == 1
