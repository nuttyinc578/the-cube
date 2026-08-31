"""Fun Mode party pack and GUI extension for The Cube Beta.

Drop this file and ``fun_mode.rb`` into the game's add-ons folder, then reload
add-ons. The Ruby companion supplies extra content and the shared GUI colors.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path


DEFAULT_GUI = {
    "badge": "FUN MODE  PY + RB",
    "panel_title": "FUN METER",
    "action": "PARTY EVENT  [F]",
    "accent": [255, 75, 170],
    "secondary": [65, 235, 205],
    "confetti_colors": [
        [255, 75, 170],
        [65, 235, 205],
        [255, 205, 55],
        [135, 115, 255],
    ],
}


def _color(value, fallback):
    """Return a safe RGB tuple from Ruby's GUI configuration."""
    try:
        channels = tuple(max(0, min(255, int(item))) for item in value)
    except (TypeError, ValueError):
        return tuple(fallback)
    return channels if len(channels) == 3 else tuple(fallback)


def _ruby_gui():
    """Read the GUI theme from the Ruby companion, with a Python fallback."""
    config = dict(DEFAULT_GUI)
    ruby_path = Path(__file__).with_suffix(".rb")
    if not ruby_path.exists():
        return config

    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            ["ruby", str(ruby_path)],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=flags,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            manifest = json.loads(completed.stdout.strip().splitlines()[-1])
            ruby_config = manifest.get("gui", {})
            if isinstance(ruby_config, dict):
                for key in ("badge", "panel_title", "action"):
                    if ruby_config.get(key):
                        config[key] = str(ruby_config[key])[:28]
                for key in ("accent", "secondary"):
                    config[key] = list(_color(ruby_config.get(key), config[key]))
                raw_colors = ruby_config.get("confetti_colors")
                if isinstance(raw_colors, list) and raw_colors:
                    config["confetti_colors"] = [
                        list(_color(item, config["accent"])) for item in raw_colors[:8]
                    ]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return config


def _find_game_module():
    """Locate the running source or packaged game module."""
    for module_name in ("__main__", "the_cube_beta_summer"):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "GameApp"):
            return module
    return None


def _install_gui_patch():
    """Add Fun Mode visuals and controls without changing game files."""
    game = _find_game_module()
    if game is None:
        return

    game_app = game.GameApp
    if getattr(game_app, "_fun_mode_gui_installed", False):
        return

    try:
        pygame = game.pygame
    except AttributeError:
        return

    gui = _ruby_gui()
    accent = _color(gui["accent"], DEFAULT_GUI["accent"])
    secondary = _color(gui["secondary"], DEFAULT_GUI["secondary"])
    confetti_colors = tuple(
        _color(item, accent) for item in gui.get("confetti_colors", [])
    ) or (accent, secondary)
    width = int(getattr(game, "WIDTH", 1100))
    height = int(getattr(game, "HEIGHT", 720))

    original_background = game_app.draw_background
    original_toast = game_app.draw_toast
    original_hud = game_app.draw_game_hud
    original_common_events = game_app.common_events
    original_simulation = game_app.run_simulation

    def draw_background(self, ticks, simple=False):
        original_background(self, ticks, simple)

        # Animated confetti stays behind the menus, HUD, and game pieces.
        for index in range(30):
            speed = 24 + (index % 5) * 8
            x = int((index * 97 + ticks * speed) % (width + 50)) - 25
            y = int((index * 61 + ticks * (34 + index % 4 * 9)) % (height + 70)) - 35
            color = confetti_colors[index % len(confetti_colors)]
            radius = 3 + index % 3
            if index % 2:
                end_x = x + int(math.cos(ticks * 2 + index) * 8)
                end_y = y + 8
                pygame.draw.line(self.screen, color, (x, y), (end_x, end_y), radius)
            else:
                pygame.draw.circle(self.screen, color, (x, y), radius)

    def draw_toast(self):
        original_toast(self)

        # This persistent badge makes the active GUI extension obvious.
        pulse = (math.sin(pygame.time.get_ticks() / 330) + 1) / 2
        border = tuple(
            int(accent[channel] * (0.72 + pulse * 0.28))
            for channel in range(3)
        )
        badge = pygame.Rect(14, height - 82, 192, 30)
        pygame.draw.rect(
            self.screen,
            (9, 42, 68),
            badge.move(0, 3),
            border_radius=11,
        )
        pygame.draw.rect(self.screen, (24, 48, 73), badge, border_radius=11)
        pygame.draw.rect(self.screen, border, badge, 2, border_radius=11)
        pygame.draw.circle(self.screen, secondary, (badge.x + 15, badge.centery), 5)
        label = self.tiny.render(str(gui["badge"]), True, (248, 252, 255))
        self.screen.blit(
            label,
            label.get_rect(midleft=(badge.x + 27, badge.centery)),
        )

    def draw_game_hud(
        self,
        shape_count,
        energy,
        event,
        peer,
        is_host,
        paused,
        clear_rect,
        menu_rect,
    ):
        original_hud(
            self,
            shape_count,
            energy,
            event,
            peer,
            is_host,
            paused,
            clear_rect,
            menu_rect,
        )

        panel_rect = pygame.Rect(width - 238, 78, 224, 94)
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel.fill((9, 42, 68, 232))
        pygame.draw.rect(
            panel,
            (*accent, 245),
            panel.get_rect(),
            2,
            border_radius=14,
        )
        self.screen.blit(panel, panel_rect)

        title = self.tiny.render(
            f"{gui['panel_title']}   {energy}",
            True,
            (248, 252, 255),
        )
        self.screen.blit(title, (panel_rect.x + 12, panel_rect.y + 8))

        meter_back = pygame.Rect(panel_rect.x + 12, panel_rect.y + 31, 200, 9)
        pygame.draw.rect(self.screen, (48, 76, 96), meter_back, border_radius=5)
        meter_fill = meter_back.copy()
        meter_fill.width = int(meter_back.width * min(1.0, max(0, energy) / 20))
        if meter_fill.width:
            pygame.draw.rect(self.screen, secondary, meter_fill, border_radius=5)

        action_rect = pygame.Rect(panel_rect.x + 12, panel_rect.y + 49, 200, 34)
        self._fun_mode_action_rect = action_rect
        hovered = action_rect.collidepoint(pygame.mouse.get_pos())
        action_color = tuple(min(255, channel + 18) for channel in accent) if hovered else accent
        pygame.draw.rect(self.screen, action_color, action_rect, border_radius=9)
        action = self.tiny.render(str(gui["action"]), True, (18, 43, 66))
        self.screen.blit(action, action.get_rect(center=action_rect.center))

    def common_events(self, events):
        if getattr(self, "_fun_mode_in_simulation", False):
            action_rect = getattr(self, "_fun_mode_action_rect", None)
            trigger = False
            for event in list(events):
                if event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                    trigger = True
                elif (
                    action_rect is not None
                    and event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and action_rect.collidepoint(event.pos)
                ):
                    # Neutralize this click so it does not also spawn a shape.
                    event.dict["button"] = 0
                    trigger = True
            if trigger:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e}))
                self.play_click()
                self.notify("Fun Mode launched a party event!", 2)
        return original_common_events(self, events)

    def run_simulation(self, *args, **kwargs):
        self._fun_mode_in_simulation = True
        try:
            return original_simulation(self, *args, **kwargs)
        finally:
            self._fun_mode_in_simulation = False

    game_app.draw_background = draw_background
    game_app.draw_toast = draw_toast
    game_app.draw_game_hud = draw_game_hud
    game_app.common_events = common_events
    game_app.run_simulation = run_simulation
    game_app._fun_mode_gui_installed = True


_install_gui_patch()


def register(api):
    api.about(
        name="Fun Mode: Party Pack",
        version="1.1",
        author="Cube Community",
        description=(
            "Adds party shapes, events, animated GUI confetti, "
            "a Fun Meter, and a party-event button."
        ),
    )

    api.shape(
        name="Disco Ball",
        kind="circle",
        size=32,
        color=(150, 110, 255),
        weight=0.8,
    )
    api.shape(
        name="Confetti Star",
        kind="polygon",
        sides=5,
        size=25,
        color=(255, 75, 170),
        weight=0.65,
    )
    api.shape(
        name="Party Sun",
        kind="polygon",
        sides=8,
        size=38,
        color=(255, 205, 55),
        weight=1.1,
    )

    api.event(
        name="Moon Bounce",
        duration=10,
        wind=180,
        gravity_scale=0.16,
        spawn_count=8,
        banner="Moon Bounce! Everything is light, floaty, and ready to party!",
        color=(125, 155, 255),
    )
    api.event(
        name="Confetti Cannon",
        duration=6,
        wind=1200,
        gravity_scale=0.55,
        spawn_count=12,
        banner="Confetti Cannon! A colorful blast races across the beach!",
        color=(255, 80, 175),
    )
