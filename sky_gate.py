"""The Broken Lands DVD puzzle. State is local to each player, even online."""
import time

import pygame
from cube_core import WIDTH, bundle_path, save_settings
from fluent_ui import accent, panel, paragraph, text
from archive_ending import ArchiveEnding

HOLD_SECONDS = 1.35
ARCHIVE = (
    ('6.0', '6.0.0', '60.png', 'Source preview from the 6.0.0 tag (5.3 script); not a capture of the installer build.'),
    ('5.1 Christmas', '5.1', '51.png', 'Captured from the archived Christmas source.'),
    ('5.0', '5.0', '50.png', 'Captured from the original release script.'),
    ('4.9', '4.5', '49.png', 'Captured from the 4.9 script (GitHub tag 4.5).'),
    ('4.0', '4.1', '40.png', 'Captured from the 4.0 script (GitHub tag 4.1).'),
    ('3.0', '3.0', '30.png', 'Captured from the original release script.'),
    ('2.0 Demo', '2.0', '20.png', 'Captured from the original release script.'),
    ('1.0', '1.0.0.0', '10.png', 'Captured from the original release script.'),
)


def stage(app):
    n = app.settings.get('sky_gate_stage', 0)
    return n if type(n) is int and 0 <= n <= 4 else 0


def gate_retired(app):
    """Once earned, Special Player also retires the in-world aperture."""
    return app.settings.get('special_player_unlocked') is True


def advance(app, expected):
    if stage(app) != expected:
        return False
    app.settings['sky_gate_stage'] = expected + 1
    save_settings(app.settings)
    return True


def terminal_command(app, command):
    if command in ('key', 'take key', 'sky key'):
        if gate_retired(app):
            return ('SKY GATE CLOSED. SPECIAL PLAYER STATUS SAVED.',)
        fresh = advance(app, 0)
        return ('SKY GATE KEY ACQUIRED.' if fresh else 'SKY GATE KEY ALREADY RECOVERED.',
                'Enter solo or multiplayer. Hold E to open the Sky Gate.')
    if command in ('insert dvd', 'dvd'):
        if stage(app) < 3:
            return ('! DISC MISSING. Open the Sky Gate and pick up the DVD in play.',)
        advance(app, 3)
        show_archive(app)
        return ('ARCHIVE DVD READ. Historical gallery is now available.',)
    return ()


class ArchiveView:
    back = pygame.Rect(921, 55, 113, 38)
    previous = pygame.Rect(64, 622, 160, 41)
    following = pygame.Rect(877, 622, 159, 41)

    def __init__(self):
        self.index = 0
        self.images = {}
        self.ending = None

    def events(self, events, app, now=None):
        if self.ending is not None:
            return self.ending.events(app, events, now)
        for event in events:
            forward = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: return False
                if event.key == pygame.K_LEFT: self.index = max(0, self.index-1)
                forward = event.key in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_KP_ENTER)
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.back.collidepoint(event.pos): return False
                if self.previous.collidepoint(event.pos): self.index = max(0, self.index-1)
                forward = self.following.collidepoint(event.pos)
            if forward:
                if self.index == len(ARCHIVE)-1:
                    self.ending = ArchiveEnding()
                    return True
                self.index += 1
        return True

    def draw(self, app):
        if self.ending is not None:
            self.ending.draw(app)
            return
        app.screen.fill((10, 17, 29))
        title, tag, image, note = ARCHIVE[self.index]
        color = (152, 240, 215)
        text(app, f'SKY GATE DVD  /  {self.index + 1:02} OF {len(ARCHIVE):02}', (64, 42), color, app.tiny)
        text(app, 'The Cube Beta ' + title, (63, 68), font=app.large)
        preview = pygame.Rect(64, 140, 972, 430)
        panel(app, preview, color=(21, 33, 49))
        if image not in self.images:
            try:
                raw = pygame.image.load(str(bundle_path('archive_assets/' + image))) if image else None
                if raw is not None:
                    scale = min(940/raw.get_width(), 405/raw.get_height())
                    raw = pygame.transform.smoothscale(raw, (round(raw.get_width()*scale), round(raw.get_height()*scale)))
                self.images[image] = raw
            except (OSError, pygame.error):
                self.images[image] = None
        shot = self.images[image]
        if shot is not None:
            app.screen.blit(shot, shot.get_rect(center=preview.center))
        else:
            paragraph(app, 'No verified screenshot available.\nArchive release: ' + tag,
                      pygame.Rect(113, 310, 810, 110), color, app.font)
        text(app, note if shot is not None or image is None else 'Capture missing from this copy of the DVD.',
             (65, 589), width=970)
        next_label = 'Credits  →' if self.index == len(ARCHIVE)-1 else 'Next  →'
        for rect, label in ((self.back, 'Close / Esc'), (self.previous, '←  Previous'), (self.following, next_label)):
            panel(app, rect, color=(36, 56, 72), radius=9)
            text(app, label, (rect.x+19, rect.y+8))
        text(app, '← / → Browse    ·    Esc closes the reader', (363, 631), color, app.tiny)


def show_archive(app):
    view = ArchiveView()
    while True:
        events = pygame.event.get()
        if not app.common_events(events) or not view.events(events, app):
            return
        view.draw(app)
        pygame.display.flip()
        app.clock.tick(60)


class PlayGate:
    hold_button = pygame.Rect(779, 87, 287, 44)
    dvd = pygame.Rect(517, 153, 66, 66)
    computer = pygame.Rect(815, 174, 218, 86)

    def __init__(self):
        self.held = None
        self.origin = None
        self.view = None

    def process(self, app, events, now=None):
        """Keep the normal E tap for events. Hold E (or the on-screen button) for the key."""
        now = time.monotonic() if now is None else now
        if self.view:
            if not self.view.events(events, app, now):
                self.view = None
            events.clear()  # physics and network still tick; only local inputs are muted
            return False
        if gate_retired(app):
            self.held = self.origin = None
            return False
        tap = False
        for event in list(events):
            if event.type == pygame.WINDOWFOCUSLOST:
                self.held = self.origin = None
            elif stage(app) == 1 and event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                events.remove(event)
                if self.held is None and not getattr(event, 'repeat', False):
                    self.held, self.origin = now, 'key'
            elif event.type == pygame.KEYUP and event.key == pygame.K_e and self.origin == 'key':
                tap = now - self.held < HOLD_SECONDS
                if not tap: advance(app, 1)
                self.held = self.origin = None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                n = stage(app)
                target = self.hold_button if n == 1 else self.dvd if n == 2 else self.computer if n >= 3 else None
                if target is not None and target.collidepoint(event.pos):
                    events.remove(event)
                    if n == 1 and self.held is None:
                        self.held, self.origin = now, 'mouse'
                    elif n == 2:
                        advance(app, 2)
                    elif n >= 3:
                        advance(app, 3)
                        self.view = ArchiveView()
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.origin == 'mouse':
                if self.hold_button.collidepoint(event.pos) and now - self.held >= HOLD_SECONDS: advance(app, 1)
                self.held = self.origin = None
            elif event.type == pygame.MOUSEMOTION and self.origin == 'mouse' and not self.hold_button.collidepoint(event.pos):
                self.held = self.origin = None
        if self.held is not None and now - self.held >= HOLD_SECONDS:
            advance(app, 1)
            self.held = self.origin = None
        return tap

    def draw(self, app, now=None):
        if self.view:
            self.view.draw(app)
            return
        if gate_retired(app):
            return
        n = stage(app)
        color = (152, 240, 215)
        if n == 1:
            box = self.hold_button
            panel(app, box, color=(20, 40, 53), radius=11)
            text(app, 'SKY GATE  /  Hold E', (box.x+18, box.y+8), color)
            if self.held is not None:
                now = time.monotonic() if now is None else now
                w = round(box.width*min(1, max(0, (now-self.held)/HOLD_SECONDS)))
                pygame.draw.rect(app.screen, color, (box.x, box.bottom-4, w, 4))
        if n >= 2:
            # A luminous aperture breaks the sky above the sandbox without touching physics.
            pygame.draw.ellipse(app.screen, (44, 82, 111), (382, 99, 336, 149))
            pygame.draw.ellipse(app.screen, (12, 27, 53), (393, 106, 314, 134))
            pygame.draw.ellipse(app.screen, color, (393, 106, 314, 134), 3)
            text(app, 'S K Y   G A T E   /   O P E N', (461, 119), color, app.tiny)
        if n == 2:
            pygame.draw.circle(app.screen, (210, 216, 252), self.dvd.center, 25)
            pygame.draw.circle(app.screen, (64, 72, 114), self.dvd.center, 7)
            pygame.draw.arc(app.screen, (240, 150, 255), self.dvd.inflate(-29, -29), 0.1, 2.9, 4)
            text(app, 'Click the archive DVD', (484, 255), color, app.tiny)
        elif n >= 3:
            panel(app, self.computer, color=(31, 51, 66), radius=10)
            label = 'Insert archive DVD' if n == 3 else 'Open DVD gallery'
            text(app, 'BROKEN LANDS  /  PC', (self.computer.x+14, self.computer.y+11), color, app.tiny)
            text(app, label, (self.computer.x+14, self.computer.y+41))
