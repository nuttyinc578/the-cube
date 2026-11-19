"""DVD credits, local achievement, and a read-only flight through the game."""
import math
import time
import webbrowser

import pygame
from cube_core import save_settings
from fluent_ui import FluentButton, background, buttons, cube, panel, paragraph, text

COLOR = (149, 239, 211)
REPO = 'https://github.com/nuttyinc578/the-cube'
CONTRIBUTE_URLS = {'issue': REPO + '/issues/new', 'fork': REPO + '/fork', 'pull': REPO + '/compare'}
SCENES = (
    ('Sky Gate', 'The DVD spins. Something pulls you into the sky.', 3.4),
    ('Main menu', 'The workshop shrinks beneath you as you pass through it.', 2.4),
    ('Binary code map', 'Follow the signal across the memory grid.', 2.8),
    ('Cube Physics Engine', 'CPE steps the world. IPE lights up the trail.', 3.2),
    ('Game main menu code', 'You found the return path behind the menu.', 3.0),
)
FLIGHT_TIME = sum(duration for _, _, duration in SCENES)


def flight_frame(elapsed):
    remaining = max(0.0, elapsed)
    for i, (_, _, duration) in enumerate(SCENES):
        if remaining < duration:
            return i, remaining / duration
        remaining -= duration
    return len(SCENES)-1, 1.0


def open_contribution(kind):
    url = CONTRIBUTE_URLS.get(kind)
    if url is None:
        return False
    try:
        return bool(webbrowser.open_new_tab(url))
    except (OSError, webbrowser.Error):
        return False


class ArchiveEnding:
    def __init__(self):
        self.page = 'credits'
        self.focus = 0
        self.started = 0.0
        self.new_achievement = False
        self.status = ''

    def controls(self):
        def item(bounds, label, action, primary=False):
            return FluentButton(bounds, label, COLOR, primary=primary), action
        if self.page == 'credits':
            return [item((96, 619, 260, 49), 'Back to your game', 'close'),
                    item((737, 619, 265, 49), 'DEVS ONLY', 'flight', True)]
        if self.page == 'flight':
            return [item((838, 626, 166, 43), 'Skip flight', 'offer')]
        if self.page == 'offer':
            return [item((194, 546, 346, 57), 'No / Return to game', 'close'),
                    item((560, 546, 346, 57), 'Yes / GitHub contributions', 'contribute', True)]
        return [item((98, 615, 278, 48), 'Back to your game', 'close'),
                item((98, 449, 278, 52), 'Report an issue', 'issue'),
                item((411, 449, 278, 52), 'Fork the project', 'fork'),
                item((724, 449, 278, 52), 'Compare / open pull request', 'pull')]

    def events(self, app, events, now=None):
        now = time.monotonic() if now is None else now
        if self.page == 'flight' and now-self.started >= FLIGHT_TIME:
            self.page, self.focus = 'offer', 0
            return True  # do not let an input intended to skip the flight select Yes
        if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            return False
        items = self.controls()
        selection, self.focus = buttons(app, [btn for btn,_ in items], events, self.focus)
        if selection is None:
            return True
        action = items[selection][1]
        if action == 'close':
            return False
        if action == 'flight':
            self.new_achievement = app.settings.get('special_player_unlocked') is not True
            if self.new_achievement:
                app.settings['special_player_unlocked'] = True
                save_settings(app.settings)
            self.started = now
        if action in ('flight', 'offer', 'contribute'):
            self.page, self.focus = action, 0
        elif open_contribution(action):
            self.status = 'Opened GitHub. Review and submit there; the game posted nothing.'
        else:
            self.status = CONTRIBUTE_URLS[action]
        return True

    def draw(self, app, now=None):
        now = time.monotonic() if now is None else now
        if self.page == 'flight':
            self.draw_flight(app, now)
        else:
            background(app, now)
            if self.page == 'credits':
                self.draw_credits(app)
            elif self.page == 'offer':
                self.draw_offer(app)
            else:
                self.draw_contribute(app)
        buttons(app, [btn for btn,_ in self.controls()], [], self.focus)

    def draw_credits(self, app):
        text(app, 'ARCHIVE DVD  /  END OF DISC', (96, 50), COLOR)
        text(app, 'The Cube Beta', (92, 83), font=app.large)
        text(app, 'Christmas Workshop · Credits', (96, 151), COLOR, app.font)
        panel(app, pygame.Rect(75, 207, 950, 368))
        rows = (
            ('GAME & WORKSHOP', "nutty'inc  /  The Cube Beta"),
            ('PHYSICS & PARTICLES', 'Cube Physics Engine (CPE) · Integrated Particle Engine (IPE)'),
            ('THE ARCHIVE', 'The surviving game editions, from 6.0 back to 1.0'),
            ('THANK YOU', 'To the players, testers, and contributors who helped the Cube grow.'),
        )
        for i, (label, name) in enumerate(rows):
            y = 232 + 80*i
            text(app, label, (105, y), COLOR, app.tiny)
            text(app, name, (105, y+26), font=app.font, width=862)
        text(app, 'Easter egg · no developer permissions required', (387, 634), COLOR, app.tiny)

    def draw_flight(self, app, now):
        elapsed = now - self.started
        i, phase = flight_frame(elapsed)
        name, description, _ = SCENES[i]
        if i == 1:
            from nightly_ui import render_home
            controls, _ = render_home(app, elapsed)
            for control in controls:
                control.draw(app.screen, app.small, (-1, -1))
        else:
            app.screen.fill((9, 19, 32))
            if i == 0:
                from christmas_update import christmas_background
                if app.settings.get('theme') == 'christmas':
                    christmas_background(app, elapsed)
                else:
                    background(app, elapsed)
                pygame.draw.ellipse(app.screen, (43, 104, 116), (320, 150, 460, 188), width=8)
                pygame.draw.ellipse(app.screen, COLOR, (350, 164, 400, 160), width=2)
            elif i == 2:
                # Visual binary map, not an interpreter.
                for y in range(121, 585, 35):
                    pygame.draw.line(app.screen, (26, 54, 66), (72, y), (1028, y), 1)
                    phrase = '  '.join(f'{(y//7+n*39+int(elapsed*10))%256:08b}' for n in range(10))
                    text(app, phrase, (93, y+4), (63, 128, 136), app.tiny, 916)
            else:
                panel(app, pygame.Rect(76, 125, 948, 453), color=(13, 30, 44))
                source = 'CPE / physics tick' if i == 3 else 'THE CUBE BETA / game menu loop'
                lines = (('world = PhysicsWorld(gravity, addons)', 'world.update(dt, wind, gravity_scale)',
                          'snapshot = world.snapshot()', 'particle_snapshot = world.particle_snapshot()')
                         if i == 3 else ('action = "menu"', 'action = self.main_menu()', 'if action == "single":',
                                         '    self.run_simulation()'))
                text(app, source, (104, 158), COLOR, app.font)
                for line, value in enumerate(lines, 1):
                    text(app, f'{line:02d}    {value}', (104, 204+line*53), (172, 214, 222), app.font)
        # Animate the character across each stage, with a visible trajectory and comet trail.
        x = 118+864*phase
        y = (492-316*phase if i == 0 else 470-182*math.sin(phase*math.pi))
        for j in range(10, 0, -1):
            pygame.draw.circle(app.screen, (45+5*j, 119+7*j, 139+3*j),
                               (max(0, int(x-8*j)), int(y+4*j)), max(2, 11-j))
        cube(app, (int(x), int(y)), 25, elapsed)
        panel(app, pygame.Rect(71, 33, 958, 71), color=(13, 31, 42), radius=12)
        text(app, f'FLIGHT  /  {i+1:02d} OF {len(SCENES):02d}', (96, 49), COLOR, app.tiny)
        text(app, name, (96, 69), font=app.font)
        text(app, description, (485, 63), width=512)
        if elapsed < 3.4:
            panel(app, pygame.Rect(291, 537, 518, 68), color=(36, 55, 71), radius=12)
            text(app, 'ACHIEVEMENT UNLOCKED' if self.new_achievement else 'ACHIEVEMENT EARNED',
                 (314, 547), COLOR, app.tiny)
            text(app, 'You are a special', (313, 569), font=app.font)

    def draw_offer(self, app):
        panel(app, pygame.Rect(148, 128, 804, 502))
        text(app, 'SPECIAL PLAYER  /  ACHIEVEMENT', (192, 165), COLOR)
        text(app, 'You are a special player.', (190, 217), font=app.large, width=707)
        paragraph(app, 'Begin Special Player: GitHub Pull Requests & Issues. Would you like to contribute to The Cube Beta?\n'
                  'Yes opens the contribution choices. The badge is in-game only and grants no GitHub permissions.',
                  pygame.Rect(194, 318, 709, 164), font=app.font)

    def draw_contribute(self, app):
        text(app, 'SPECIAL PLAYER  /  CONTRIBUTE', (97, 63), COLOR)
        text(app, 'Make the Cube better.', (93, 110), font=app.large)
        panel(app, pygame.Rect(77, 204, 947, 374))
        paragraph(app, 'Issues are for useful bug reports and ideas. For code changes, fork the repository, push a branch to '
                  'your own fork, then compare it with the project and open a pull request.\n'
                  'GitHub handles sign-in, submission and credit. Nothing is posted from the game.',
                  pygame.Rect(98, 237, 888, 190), font=app.font)
        text(app, self.status, (98, 530), COLOR, width=890)
