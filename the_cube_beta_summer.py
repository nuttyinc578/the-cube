"""The Cube Beta 6.2.3 - Fall Edition with GitHub OG installs."""

from __future__ import annotations

import math
import os
import sys
import time
from typing import Any

import pygame

from cube_core import (
    ADDONS_DIR,
    APP_TITLE,
    CORAL,
    FALL_PALETTE,
    DEFAULT_PORT,
    FLOOR_Y,
    FPS,
    HEIGHT,
    INK,
    MINT,
    MUTED,
    NAVY,
    THEMES,
    VERSION,
    WHITE,
    WIDTH,
    YELLOW,
    AddonManager,
    NetworkPeer,
    PhysicsWorld,
    FallEventController,
    bundle_path,
    clamp,
    fall_countdown,
    load_settings,
    local_ip,
    safe_color,
    save_settings,
)


class Button:
    def __init__(
        self,
        rect: tuple[int, int, int, int],
        text: str,
        accent: tuple[int, int, int] = WHITE,
        dark_text: bool = True,
    ):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.accent = accent
        self.dark_text = dark_text

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse: tuple[int, int]) -> None:
        hovered = self.rect.collidepoint(mouse)
        shadow = self.rect.move(0, 5)
        pygame.draw.rect(surface, (10, 45, 70), shadow, border_radius=14)
        color = tuple(min(255, channel + 12) for channel in self.accent) if hovered else self.accent
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        pygame.draw.rect(surface, WHITE, self.rect, 2 if hovered else 1, border_radius=14)
        label_color = INK if self.dark_text else WHITE
        label = font.render(self.text, True, label_color)
        surface.blit(label, label.get_rect(center=self.rect.center))


class GameApp:
    def __init__(self):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass
        self.settings = load_settings()
        self.screen: pygame.Surface
        self.apply_display()
        try:
            pygame.display.set_icon(pygame.image.load(str(bundle_path("icon.ico"))))
        except (pygame.error, OSError):
            pass
        pygame.display.set_caption(f"{APP_TITLE} v{VERSION}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("segoeui", 21)
        self.small = pygame.font.SysFont("segoeui", 16)
        self.tiny = pygame.font.SysFont("segoeui", 14)
        self.large = pygame.font.SysFont("segoeui", 46, bold=True)
        self.hero = pygame.font.SysFont("segoeui", 64, bold=True)
        self.click_sound: pygame.mixer.Sound | None = None
        self.addons = AddonManager()
        self.background_cache: dict[str, pygame.Surface] = {}
        self.toast = ""
        self.toast_until = 0.0
        self._load_audio()

    def apply_display(self) -> None:
        flags = pygame.FULLSCREEN if self.settings.get("fullscreen") else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

    def _load_audio(self) -> None:
        if not pygame.mixer.get_init():
            return
        try:
            self.click_sound = pygame.mixer.Sound(str(bundle_path("click.mp3")))
            self.click_sound.set_volume(0.55)
        except (pygame.error, OSError):
            self.click_sound = None
        try:
            pygame.mixer.music.load(str(bundle_path("fall_music.mp3")))
            pygame.mixer.music.set_volume(0.32)

        except (pygame.error, OSError):
            pass

    def start_music(self) -> None:
        if not self.settings["music"] or not pygame.mixer.get_init():
            return
        try:
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.play(-1)
            else:
                pygame.mixer.music.unpause()
        except pygame.error:
            pass

    def play_click(self) -> None:
        if self.settings["sound"] and self.click_sound:
            self.click_sound.play()

    def notify(self, message: str, seconds: float = 3) -> None:
        self.toast = message
        self.toast_until = time.monotonic() + seconds

    def draw_toast(self) -> None:
        if not self.toast or time.monotonic() >= self.toast_until:
            return
        label = self.small.render(self.toast, True, WHITE)
        rect = label.get_rect(center=(WIDTH // 2, HEIGHT - 26)).inflate(28, 14)
        pygame.draw.rect(self.screen, (14, 54, 76), rect, border_radius=12)
        self.screen.blit(label, label.get_rect(center=rect.center))

    def background_surface(self) -> pygame.Surface:
        theme_name = self.settings["theme"]
        if theme_name in self.background_cache:
            return self.background_cache[theme_name]
        theme = THEMES[theme_name]
        surface = pygame.Surface((WIDTH, HEIGHT))
        horizon = 430
        for y in range(horizon):
            ratio = y / horizon
            color = tuple(
                int(theme["sky_top"][i] * (1 - ratio) + theme["sky_bottom"][i] * ratio)
                for i in range(3)
            )
            pygame.draw.line(surface, color, (0, y), (WIDTH, y))
        pygame.draw.polygon(
            surface,
            theme["water"],
            [(0, 515), (0, 445), (145, 380), (300, 455), (455, 365),
             (625, 448), (790, 372), (940, 440), (WIDTH, 390), (WIDTH, 615), (0, 615)],
        )
        pygame.draw.rect(surface, theme["sand"], (0, 575, WIDTH, HEIGHT - 575))
        for index, x in enumerate(range(45, WIDTH, 105)):
            trunk_y = 475 + (index % 3) * 24
            pygame.draw.rect(surface, (82, 52, 35), (x, trunk_y, 12, 118))
            foliage = FALL_PALETTE[index % len(FALL_PALETTE)]
            pygame.draw.circle(surface, foliage, (x + 6, trunk_y - 4), 32)
            pygame.draw.circle(surface, tuple(max(0, value - 25) for value in foliage), (x - 17, trunk_y + 12), 23)
            pygame.draw.circle(surface, tuple(min(255, value + 22) for value in foliage), (x + 27, trunk_y + 12), 24)
        self.background_cache[theme_name] = surface
        return surface

    def draw_background(self, ticks: float, simple: bool = False) -> None:
        self.screen.blit(self.background_surface(), (0, 0))
        theme = THEMES[self.settings["theme"]]
        sun_x = 820 if self.settings["theme"] == "harvest" else 875
        sun_y = 215 if self.settings["theme"] == "harvest" else 105
        pygame.draw.circle(self.screen, theme["sun"], (sun_x, sun_y), 54)
        if not simple:
            for index in range(4):
                x = int((80 + index * 290 + ticks * (9 + index)) % (WIDTH + 180)) - 90
                y = 105 + (index % 2) * 75
                self.draw_cloud(x, y)
        if not simple:
            for index in range(24):
                speed = 22 + (index % 5) * 7
                x = int((index * 83 + ticks * (13 + index % 4)) % (WIDTH + 90)) - 45
                y = int((index * 71 + ticks * speed) % 610) + 35
                color = FALL_PALETTE[index % len(FALL_PALETTE)]
                self.draw_leaf((x, y), color, ticks * 1.8 + index, 0.7 + (index % 3) * 0.18)

    def draw_leaf(
        self,
        center: tuple[int, int],
        color: tuple[int, int, int],
        angle: float,
        scale: float = 1.0,
    ) -> None:
        base_points = [(-11, 0), (-3, -7), (7, -5), (12, 0), (5, 7), (-4, 6)]
        cosine, sine = math.cos(angle), math.sin(angle)
        points = [
            (
                int(center[0] + (x * cosine - y * sine) * scale),
                int(center[1] + (x * sine + y * cosine) * scale),
            )
            for x, y in base_points
        ]
        pygame.draw.polygon(self.screen, color, points)
        stem_end = (
            int(center[0] + cosine * 15 * scale),
            int(center[1] + sine * 15 * scale),
        )
        pygame.draw.line(self.screen, (92, 55, 35), center, stem_end, max(1, int(scale * 2)))

    def draw_cloud(self, x: int, y: int) -> None:
        color = (245, 252, 255)
        pygame.draw.circle(self.screen, color, (x + 35, y + 13), 24)
        pygame.draw.circle(self.screen, color, (x + 66, y), 34)
        pygame.draw.circle(self.screen, color, (x + 100, y + 15), 26)
        pygame.draw.rect(self.screen, color, (x + 32, y + 12, 72, 30), border_radius=15)

    def draw_panel(self, rect: pygame.Rect, alpha: int = 235) -> None:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((246, 252, 255, alpha))
        pygame.draw.rect(panel, (255, 255, 255, 245), panel.get_rect(), 2, border_radius=22)
        self.screen.blit(panel, rect)

    def title_block(self, kicker: str, title: str, subtitle: str, y: int = 100) -> None:
        kicker_label = self.small.render(kicker.upper(), True, NAVY)
        self.screen.blit(kicker_label, kicker_label.get_rect(center=(WIDTH // 2, y)))
        title_label = self.large.render(title, True, WHITE)
        self.screen.blit(title_label, title_label.get_rect(center=(WIDTH // 2, y + 48)))
        sub_label = self.font.render(subtitle, True, WHITE)
        self.screen.blit(sub_label, sub_label.get_rect(center=(WIDTH // 2, y + 92)))

    def wait_click(self, buttons: list[Button], events: list[pygame.event.Event]) -> int | None:
        mouse = pygame.mouse.get_pos()
        for event in events:
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                for index, button in enumerate(buttons):
                    if button.rect.collidepoint(event.pos):
                        self.play_click()
                        return index
        for button in buttons:
            button.draw(self.screen, self.font, mouse)
        return None

    def common_events(self, events: list[pygame.event.Event]) -> bool:
        for event in events:
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.settings["fullscreen"] = not self.settings["fullscreen"]
                save_settings(self.settings)
                self.apply_display()
        return True

    def licence_dialog(self) -> bool:
        """Show the packaged MIT Licence before allowing access to the main menu."""
        licence_path = bundle_path("LICENCE.txt")
        try:
            licence_text = licence_path.read_text(encoding="utf-8")
            licence_loaded = True
        except OSError:
            licence_text = (
                "The MIT Licence could not be loaded.\n\n"
                "Please reinstall The Cube Beta Fall Edition."
            )
            licence_loaded = False

        panel_rect = pygame.Rect(65, 32, WIDTH - 130, HEIGHT - 64)
        text_rect = pygame.Rect(115, 145, WIDTH - 250, 385)
        accept_rect = pygame.Rect(WIDTH - 355, 590, 240, 52)
        decline_rect = pygame.Rect(115, 590, 240, 52)
        legal_font = pygame.font.SysFont("segoeui", 16)
        legal_bold = pygame.font.SysFont("segoeui", 16, bold=True)

        rendered_lines: list[tuple[pygame.Surface | None, int, int]] = []
        content_height = 0
        for raw_line in licence_text.splitlines():
            line = raw_line.strip()
            if not line:
                rendered_lines.append((None, 12, 0))
                content_height += 12
                continue

            heading = line.upper() == line and any(character.isalpha() for character in line)
            font = legal_bold if heading else legal_font
            indent = 18 if line.startswith("* ") else 0
            if line.startswith("* "):
                line = "\u2022 " + line[2:]

            words = line.split()
            current = ""
            wrapped: list[str] = []
            maximum_width = text_rect.width - 28 - indent
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if current and font.size(candidate)[0] > maximum_width:
                    wrapped.append(current)
                    current = word
                else:
                    current = candidate
            if current:
                wrapped.append(current)

            for wrapped_line in wrapped:
                surface = font.render(wrapped_line, True, INK)
                rendered_lines.append((surface, surface.get_height() + 4, indent))
                content_height += surface.get_height() + 4

        max_scroll = max(0, content_height - text_rect.height + 10)
        scroll = 0

        while True:
            ticks = pygame.time.get_ticks() / 1000
            events = pygame.event.get()
            mouse = pygame.mouse.get_pos()

            for event in events:
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
                    if event.key == pygame.K_F11:
                        self.settings["fullscreen"] = not self.settings["fullscreen"]
                        save_settings(self.settings)
                        self.apply_display()
                    elif event.key == pygame.K_UP:
                        scroll -= 32
                    elif event.key == pygame.K_DOWN:
                        scroll += 32
                    elif event.key == pygame.K_PAGEUP:
                        scroll -= text_rect.height - 30
                    elif event.key == pygame.K_PAGEDOWN:
                        scroll += text_rect.height - 30
                    elif event.key == pygame.K_HOME:
                        scroll = 0
                    elif event.key == pygame.K_END:
                        scroll = max_scroll
                    elif (
                        event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
                        and licence_loaded
                        and scroll >= max_scroll - 4
                    ):
                        self.play_click()
                        return True
                elif event.type == pygame.MOUSEWHEEL:
                    scroll -= event.y * 42
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    if decline_rect.collidepoint(event.pos):
                        self.play_click()
                        return False
                    if (
                        accept_rect.collidepoint(event.pos)
                        and licence_loaded
                        and scroll >= max_scroll - 4
                    ):
                        self.play_click()
                        return True

            scroll = int(clamp(scroll, 0, max_scroll))
            accepted_enabled = licence_loaded and scroll >= max_scroll - 4

            self.draw_background(ticks)
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((7, 31, 48, 145))
            self.screen.blit(shade, (0, 0))
            self.draw_panel(panel_rect, 252)

            title = self.large.render("MIT Licence", True, NAVY)
            self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 75)))
            subtitle = self.small.render(
                "Copyright (c) 2026 nutty'inc - read before continuing.",
                True,
                MUTED,
            )
            self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 112)))

            pygame.draw.rect(self.screen, (255, 255, 255), text_rect, border_radius=10)
            pygame.draw.rect(self.screen, (172, 201, 213), text_rect, 2, border_radius=10)
            old_clip = self.screen.get_clip()
            self.screen.set_clip(text_rect.inflate(-12, -10))
            line_y = text_rect.y + 8 - scroll
            for surface, line_height, indent in rendered_lines:
                if surface is not None and line_y + line_height >= text_rect.y and line_y <= text_rect.bottom:
                    self.screen.blit(surface, (text_rect.x + 14 + indent, line_y))
                line_y += line_height
            self.screen.set_clip(old_clip)

            track = pygame.Rect(text_rect.right + 12, text_rect.y, 10, text_rect.height)
            pygame.draw.rect(self.screen, (210, 224, 230), track, border_radius=5)
            if max_scroll:
                thumb_height = max(42, int(track.height * text_rect.height / content_height))
                thumb_y = track.y + int((track.height - thumb_height) * scroll / max_scroll)
            else:
                thumb_height = track.height
                thumb_y = track.y
            pygame.draw.rect(
                self.screen,
                (59, 142, 165),
                (track.x, thumb_y, track.width, thumb_height),
                border_radius=5,
            )

            status_text = (
                "MIT Licence displayed. Choose Continue."
                if accepted_enabled
                else "Scroll to the end to continue."
            )
            if not licence_loaded:
                status_text = "Licence unavailable. Reinstall the game to continue."
            status = self.small.render(status_text, True, NAVY if accepted_enabled else MUTED)
            self.screen.blit(status, status.get_rect(center=(WIDTH // 2, 557)))

            decline_color = (255, 177, 158) if decline_rect.collidepoint(mouse) else (246, 154, 136)
            pygame.draw.rect(self.screen, decline_color, decline_rect, border_radius=14)
            decline_label = self.font.render("DECLINE & EXIT", True, NAVY)
            self.screen.blit(decline_label, decline_label.get_rect(center=decline_rect.center))

            if accepted_enabled:
                accept_color = (93, 220, 177) if accept_rect.collidepoint(mouse) else MINT
                accept_text_color = NAVY
            else:
                accept_color = (198, 208, 212)
                accept_text_color = (112, 127, 134)
            pygame.draw.rect(self.screen, accept_color, accept_rect, border_radius=14)
            accept_label = self.font.render("CONTINUE", True, accept_text_color)
            self.screen.blit(accept_label, accept_label.get_rect(center=accept_rect.center))

            pygame.display.flip()
            self.clock.tick(FPS)
    def fall_update_screen(self, duration: float = 4.2) -> bool:
        """Present the v6.2 download screen while the fall soundtrack begins."""
        self.start_music()
        started = time.monotonic()
        duration = max(0.01, duration)
        while True:
            elapsed = time.monotonic() - started
            progress = min(1.0, elapsed / duration)
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
                    if event.key == pygame.K_F11:
                        self.settings["fullscreen"] = not self.settings["fullscreen"]
                        save_settings(self.settings)
                        self.apply_display()
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and progress >= 0.25:
                        progress = 1.0

            ticks = pygame.time.get_ticks() / 1000
            self.draw_background(ticks)
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((48, 26, 18, 128))
            self.screen.blit(shade, (0, 0))
            panel = pygame.Rect(160, 105, 780, 500)
            self.draw_panel(panel, 248)

            badge = self.small.render(f"THE CUBE BETA  |  v{VERSION}", True, (128, 52, 39))
            self.screen.blit(badge, badge.get_rect(center=(WIDTH // 2, 155)))
            title = self.large.render("DOWNLOADING FALL UPDATE", True, (91, 57, 35))
            self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 215)))
            stage_names = [
                "Unpacking autumn colors...",
                "Planting fall physics events...",
                "Preparing multiplayer and add-ons...",
                "Starting Autumn Leaves...",
            ]
            stage = stage_names[min(len(stage_names) - 1, int(progress * len(stage_names)))]
            stage_label = self.font.render(stage, True, MUTED)
            self.screen.blit(stage_label, stage_label.get_rect(center=(WIDTH // 2, 270)))

            track = self.small.render(
                'NOW PLAYING  |  "Autumn Leaves" by LofCosmos via Pixabay',
                True,
                (128, 52, 39),
            )
            self.screen.blit(track, track.get_rect(center=(WIDTH // 2, 318)))

            track_rect = pygame.Rect(235, 365, 630, 34)
            pygame.draw.rect(self.screen, (222, 207, 184), track_rect, border_radius=17)
            fill_rect = pygame.Rect(track_rect.x, track_rect.y, int(track_rect.width * progress), track_rect.height)
            if fill_rect.width:
                pygame.draw.rect(self.screen, (222, 108, 39), fill_rect, border_radius=17)
            percent = self.small.render(f"{int(progress * 100):d}%", True, INK)
            self.screen.blit(percent, percent.get_rect(center=track_rect.center))

            countdown_text, remaining = fall_countdown()
            countdown_title = "FALL BEGINS IN" if remaining else "THE FALL UPDATE HAS ARRIVED"
            countdown_heading = self.tiny.render(countdown_title, True, MUTED)
            self.screen.blit(countdown_heading, countdown_heading.get_rect(center=(WIDTH // 2, 452)))
            countdown = self.large.render(countdown_text, True, (145, 92, 48))
            self.screen.blit(countdown, countdown.get_rect(center=(WIDTH // 2, 492)))
            hint = self.tiny.render("Press Enter or Space to finish early after 25%.", True, MUTED)
            self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 557)))

            pygame.display.flip()
            self.clock.tick(FPS)
            if progress >= 1.0:
                return True

    def run(self) -> None:
        if not self.licence_dialog():
            save_settings(self.settings)
            pygame.quit()
            return
        if not self.fall_update_screen():
            save_settings(self.settings)
            pygame.quit()
            return
        action = "menu"
        while action != "quit":
            if action == "menu":
                action = self.main_menu()
            elif action == "single":
                self.run_simulation()
                action = "menu"
            elif action == "multiplayer":
                action = self.multiplayer_menu()
            elif action == "addons":
                self.addons_menu()
                action = "menu"
            elif action == "settings":
                self.settings_menu()
                action = "menu"
            else:
                action = "menu"
        save_settings(self.settings)
        pygame.quit()

    def main_menu(self) -> str:
        buttons = [
            Button((385, 285, 330, 54), "PLAY SOLO", YELLOW),
            Button((385, 350, 330, 54), "PLAY MULTIPLAYER", MINT),
            Button((385, 415, 330, 54), "ADD-ONS", WHITE),
            Button((385, 480, 330, 54), "SETTINGS", WHITE),
            Button((385, 555, 330, 48), "QUIT", (255, 181, 165)),
        ]
        actions = ["single", "multiplayer", "addons", "settings", "quit"]
        while True:
            ticks = pygame.time.get_ticks() / 1000
            events = pygame.event.get()
            if not self.common_events(events):
                return "quit"
            self.draw_background(ticks)
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((8, 55, 83, 38))
            self.screen.blit(shade, (0, 0))
            badge = self.small.render(f"FALL EDITION  |  v{VERSION}", True, NAVY)
            badge_rect = badge.get_rect(center=(WIDTH // 2, 78)).inflate(28, 13)
            pygame.draw.rect(self.screen, (255, 238, 162), badge_rect, border_radius=14)
            self.screen.blit(badge, badge.get_rect(center=badge_rect.center))
            title = self.hero.render("THE CUBE BETA", True, WHITE)
            self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 150)))
            subtitle = self.font.render("Drop it. Grab it. Launch it. Make fall chaos together.", True, WHITE)
            self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 205)))
            countdown_text, remaining = fall_countdown()
            countdown_rect = pygame.Rect(360, 229, 380, 42)
            countdown_color = (250, 198, 72) if remaining else (222, 108, 39)
            pygame.draw.rect(self.screen, countdown_color, countdown_rect, border_radius=14)
            countdown_label = self.small.render(
                f"FALL COUNTDOWN  |  {countdown_text}",
                True,
                INK,
            )
            self.screen.blit(countdown_label, countdown_label.get_rect(center=countdown_rect.center))
            selected = self.wait_click(buttons, events)
            self.draw_toast()
            pygame.display.flip()
            self.clock.tick(FPS)
            if selected is not None:
                return actions[selected]

    def settings_menu(self) -> None:
        buttons = [
            Button((350, 260, 400, 48), "THEME", WHITE),
            Button((350, 318, 195, 48), "GRAVITY âˆ’", WHITE),
            Button((555, 318, 195, 48), "GRAVITY +", WHITE),
            Button((350, 376, 400, 48), "MUSIC", WHITE),
            Button((350, 434, 400, 48), "CLICK SOUND", WHITE),
            Button((350, 492, 400, 48), "FALL EVENTS", WHITE),
            Button((350, 565, 400, 50), "BACK", YELLOW),
        ]
        while True:
            ticks = pygame.time.get_ticks() / 1000
            events = pygame.event.get()
            if not self.common_events(events):
                raise SystemExit
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    save_settings(self.settings)
                    return
            self.draw_background(ticks)
            self.title_block("Tune your sandbox", "Settings", "Your choices are saved automatically.", 82)
            self.draw_panel(pygame.Rect(310, 230, 480, 410))
            labels = [
                f"THEME  â€¢  {self.settings['theme'].upper()}",
                f"GRAVITY âˆ’   {self.settings['gravity']}",
                f"GRAVITY +   {self.settings['gravity']}",
                f"MUSIC  â€¢  {'ON' if self.settings['music'] else 'OFF'}",
                f"CLICK SOUND  â€¢  {'ON' if self.settings['sound'] else 'OFF'}",
                f"FALL EVENTS  â€¢  EVERY {self.settings['event_interval']}s",
                "BACK",
            ]
            for button, label in zip(buttons, labels):
                button.text = label
            selected = self.wait_click(buttons, events)
            pygame.display.flip()
            self.clock.tick(FPS)
            if selected is None:
                continue
            if selected == 0:
                names = list(THEMES)
                current = names.index(self.settings["theme"])
                self.settings["theme"] = names[(current + 1) % len(names)]
            elif selected == 1:
                self.settings["gravity"] = max(150, self.settings["gravity"] - 150)
            elif selected == 2:
                self.settings["gravity"] = min(2200, self.settings["gravity"] + 150)
            elif selected == 3:
                self.settings["music"] = not self.settings["music"]
                if pygame.mixer.get_init():
                    if self.settings["music"]:
                        if not pygame.mixer.music.get_busy():
                            try:
                                pygame.mixer.music.play(-1)
                            except pygame.error:
                                pass
                        else:
                            pygame.mixer.music.unpause()
                    else:
                        pygame.mixer.music.pause()
            elif selected == 4:
                self.settings["sound"] = not self.settings["sound"]
            elif selected == 5:
                values = [10, 14, 18, 24, 30]
                current = min(range(len(values)), key=lambda i: abs(values[i] - self.settings["event_interval"]))
                self.settings["event_interval"] = values[(current + 1) % len(values)]
            elif selected == 6:
                save_settings(self.settings)
                return
            save_settings(self.settings)

    def addons_menu(self) -> None:
        buttons = [
            Button((272, 612, 180, 48), "RELOAD", MINT),
            Button((462, 612, 250, 48), "OPEN ADD-ONS FOLDER", YELLOW),
            Button((722, 612, 120, 48), "BACK", WHITE),
        ]
        while True:
            ticks = pygame.time.get_ticks() / 1000
            events = pygame.event.get()
            if not self.common_events(events):
                raise SystemExit
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.DROPFILE:
                    _, message = self.addons.install(event.file)
                    self.notify(message, 5)
            self.draw_background(ticks)
            self.title_block(
                "Make it yours",
                "Add-on Dock",
                "Drag a Python (.py) or Ruby (.rb) add-on anywhere onto this window.",
                66,
            )
            self.draw_panel(pygame.Rect(145, 205, 810, 385))
            if not self.addons.records:
                text = self.font.render("No add-ons found yet. Drop one here to begin.", True, MUTED)
                self.screen.blit(text, text.get_rect(center=(WIDTH // 2, 365)))
            else:
                y = 232
                for record in self.addons.records[:6]:
                    status_color = MINT if record.ok else CORAL
                    pygame.draw.circle(self.screen, status_color, (177, y + 20), 7)
                    name = self.font.render(f"{record.name}  v{record.version}", True, INK)
                    self.screen.blit(name, (195, y + 3))
                    language = self.tiny.render(f"{record.language}  â€¢  {record.author}", True, MUTED)
                    self.screen.blit(language, (720, y + 8))
                    detail = record.description if record.ok else record.detail
                    detail_label = self.small.render(detail[:92], True, MUTED)
                    self.screen.blit(detail_label, (195, y + 31))
                    pygame.draw.line(self.screen, (211, 226, 232), (175, y + 62), (925, y + 62))
                    y += 66
            footer = self.tiny.render(
                "Add-ons run code on your computer. Only use files from creators you trust.",
                True,
                NAVY,
            )
            self.screen.blit(footer, footer.get_rect(center=(WIDTH // 2, 583)))
            selected = self.wait_click(buttons, events)
            self.draw_toast()
            pygame.display.flip()
            self.clock.tick(FPS)
            if selected == 0:
                self.addons.reload()
                self.notify(self.addons.last_message)
            elif selected == 1:
                try:
                    os.startfile(str(ADDONS_DIR))  # type: ignore[attr-defined]
                except OSError:
                    self.notify(f"Add-ons folder: {ADDONS_DIR}", 6)
            elif selected == 2:
                return

    def multiplayer_menu(self) -> str:
        buttons = [
            Button((375, 292, 350, 58), "HOST A LAN GAME", YELLOW),
            Button((375, 365, 350, 58), "JOIN A LAN GAME", MINT),
            Button((375, 450, 350, 52), "BACK", WHITE),
        ]
        while True:
            ticks = pygame.time.get_ticks() / 1000
            events = pygame.event.get()
            if not self.common_events(events):
                return "quit"
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return "menu"
            self.draw_background(ticks)
            self.title_block(
                "Two-player LAN",
                "Share the Sandbox",
                "Host and guest can spawn, grab, throw, burst, and trigger events together.",
                82,
            )
            self.draw_panel(pygame.Rect(325, 252, 450, 285))
            selected = self.wait_click(buttons, events)
            hint = self.small.render("Both computers must be on the same local network.", True, NAVY)
            self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, 530)))
            pygame.display.flip()
            self.clock.tick(FPS)
            if selected == 0:
                peer = NetworkPeer("host")
                peer.start()
                self.run_simulation(peer, is_host=True)
                return "multiplayer"
            if selected == 1:
                address = self.join_address_menu()
                if address:
                    peer = NetworkPeer("client", address[0], address[1])
                    peer.start()
                    self.run_simulation(peer, is_host=False)
                return "multiplayer"
            if selected == 2:
                return "menu"

    def join_address_menu(self) -> tuple[str, int] | None:
        value = "127.0.0.1"
        input_rect = pygame.Rect(310, 330, 480, 62)
        buttons = [
            Button((355, 435, 190, 52), "CONNECT", MINT),
            Button((555, 435, 190, 52), "BACK", WHITE),
        ]
        pygame.key.start_text_input()
        try:
            while True:
                ticks = pygame.time.get_ticks() / 1000
                events = pygame.event.get()
                if not self.common_events(events):
                    return None
                submit = False
                for event in events:
                    if event.type == pygame.TEXTINPUT:
                        value = (value + event.text)[:80]
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_BACKSPACE:
                            value = value[:-1]
                        elif event.key == pygame.K_RETURN:
                            submit = True
                        elif event.key == pygame.K_ESCAPE:
                            return None
                self.draw_background(ticks)
                self.title_block(
                    "Join a friend",
                    "Host Address",
                    "Enter the host's local IP. You may add :port if they changed it.",
                    92,
                )
                self.draw_panel(pygame.Rect(260, 280, 580, 245))
                pygame.draw.rect(self.screen, WHITE, input_rect, border_radius=14)
                pygame.draw.rect(self.screen, MINT, input_rect, 3, border_radius=14)
                shown = self.font.render(value or "192.168.1.20", True, INK if value else MUTED)
                self.screen.blit(shown, (input_rect.x + 18, input_rect.y + 18))
                if (pygame.time.get_ticks() // 500) % 2:
                    cursor_x = input_rect.x + 18 + self.font.size(value)[0]
                    pygame.draw.line(self.screen, INK, (cursor_x, input_rect.y + 16), (cursor_x, input_rect.bottom - 16), 2)
                selected = self.wait_click(buttons, events)
                self.draw_toast()
                pygame.display.flip()
                self.clock.tick(FPS)
                if selected == 1:
                    return None
                if selected == 0 or submit:
                    parsed = self.parse_address(value)
                    if parsed:
                        self.play_click()
                        return parsed
                    self.notify("Enter an address such as 192.168.1.20", 4)
        finally:
            pygame.key.stop_text_input()

    @staticmethod
    def parse_address(value: str) -> tuple[str, int] | None:
        value = value.strip()
        if not value:
            return None
        host, separator, port_text = value.rpartition(":")
        if separator and port_text.isdigit():
            port = int(port_text)
            if 1 <= port <= 65535:
                return host or "127.0.0.1", port
        return value, DEFAULT_PORT

    def run_simulation(self, peer: NetworkPeer | None = None, is_host: bool = True) -> None:
        authoritative = peer is None or is_host
        world = PhysicsWorld(self.settings["gravity"], self.addons) if authoritative else None
        fall_events = FallEventController(self.settings["event_interval"], self.addons) if authoritative else None
        snapshot: list[dict[str, Any]] = []
        particle_snapshot: list[dict[str, Any]] = []
        event_state = {"name": "", "banner": "", "color": list(YELLOW), "remaining": 0, "next": 0}
        client_drag: int | None = None
        paused = False
        send_accumulator = 0.0
        energy = 0
        last_connected = False
        clear_rect = pygame.Rect(WIDTH - 174, 14, 76, 36)
        menu_rect = pygame.Rect(WIDTH - 90, 14, 76, 36)
        try:
            while True:
                dt = min(self.clock.tick(FPS) / 1000, 1 / 30)
                ticks = pygame.time.get_ticks() / 1000
                raw_events = pygame.event.get()
                if not self.common_events(raw_events):
                    raise SystemExit
                mouse = pygame.mouse.get_pos()
                for event in raw_events:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            return
                        if event.key == pygame.K_c:
                            self.dispatch_action({"action": "clear"}, peer, is_host, world, fall_events)
                        elif event.key == pygame.K_e:
                            self.dispatch_action({"action": "event"}, peer, is_host, world, fall_events)
                        elif event.key == pygame.K_SPACE:
                            self.dispatch_action(
                                {"action": "spawn_rain", "count": 8},
                                peer,
                                is_host,
                                world,
                                fall_events,
                            )
                        elif event.key == pygame.K_p and authoritative:
                            paused = not paused
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if clear_rect.collidepoint(event.pos):
                            self.play_click()
                            self.dispatch_action({"action": "clear"}, peer, is_host, world, fall_events)
                            continue
                        if menu_rect.collidepoint(event.pos):
                            self.play_click()
                            return
                        if event.button == 1:
                            if authoritative and world:
                                found = world.entity_at(event.pos)
                                selected_id = found.entity_id if found else None
                            else:
                                selected_id = self.snapshot_entity_at(snapshot, event.pos)
                            if selected_id:
                                client_drag = selected_id
                                self.dispatch_action(
                                    {"action": "drag_start", "id": selected_id, "x": event.pos[0], "y": event.pos[1]},
                                    peer,
                                    is_host,
                                    world,
                                    fall_events,
                                )
                            else:
                                self.play_click()
                                self.dispatch_action(
                                    {"action": "spawn", "x": event.pos[0], "y": event.pos[1]},
                                    peer,
                                    is_host,
                                    world,
                                    fall_events,
                                )
                                energy += 1
                        elif event.button == 3:
                            self.play_click()
                            self.dispatch_action(
                                {"action": "burst", "x": event.pos[0], "y": event.pos[1]},
                                peer,
                                is_host,
                                world,
                                fall_events,
                            )
                    elif event.type == pygame.MOUSEMOTION and client_drag and event.buttons[0]:
                        self.dispatch_action(
                            {"action": "drag_move", "id": client_drag, "x": event.pos[0], "y": event.pos[1]},
                            peer,
                            is_host,
                            world,
                            fall_events,
                        )
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and client_drag:
                        self.dispatch_action(
                            {"action": "drag_end", "id": client_drag},
                            peer,
                            is_host,
                            world,
                            fall_events,
                        )
                        client_drag = None

                if authoritative and world and fall_events:
                    if peer:
                        for message in peer.messages():
                            if message.get("type") == "action" and isinstance(message.get("data"), dict):
                                self.apply_world_action(world, fall_events, message["data"], "guest")
                    if not paused:
                        wind, gravity_scale = fall_events.update(dt, world)
                        world.update(dt, wind, gravity_scale)
                    snapshot = world.snapshot()
                    particle_snapshot = world.particle_snapshot()
                    event_state = fall_events.state()
                    if peer:
                        send_accumulator += dt
                        if send_accumulator >= 0.05:
                            peer.send(
                                {
                                    "type": "snapshot",
                                    "entities": snapshot,
                                    "particles": particle_snapshot,
                                    "event": event_state,
                                    "paused": paused,
                                }
                            )
                            send_accumulator = 0
                elif peer:
                    for message in peer.messages():
                        if message.get("type") == "snapshot":
                            if isinstance(message.get("entities"), list):
                                snapshot = message["entities"][:200]
                            if isinstance(message.get("particles"), list):
                                particle_snapshot = message["particles"][:400]
                            if isinstance(message.get("event"), dict):
                                event_state = message["event"]
                            paused = bool(message.get("paused", False))

                if peer and peer.connected and not last_connected:
                    self.notify("Your friend is connected!", 3)
                last_connected = bool(peer and peer.connected)

                self.draw_background(ticks, simple=True)
                self.draw_cpe_particles(particle_snapshot)
                self.draw_world(snapshot, mouse, client_drag)
                self.draw_game_hud(
                    len(snapshot),
                    energy,
                    event_state,
                    peer,
                    is_host,
                    paused,
                    clear_rect,
                    menu_rect,
                )
                self.draw_toast()
                pygame.display.flip()
        finally:
            if world:
                world.close()
            if peer:
                peer.close()

    def dispatch_action(
        self,
        action: dict[str, Any],
        peer: NetworkPeer | None,
        is_host: bool,
        world: PhysicsWorld | None,
        events: FallEventController | None,
    ) -> None:
        if peer and not is_host:
            peer.send({"type": "action", "data": action})
        elif world and events:
            self.apply_world_action(world, events, action, "host")

    def apply_world_action(
        self,
        world: PhysicsWorld,
        events: FallEventController,
        action: dict[str, Any],
        player: str,
    ) -> None:
        kind = action.get("action")
        try:
            x = clamp(float(action.get("x", WIDTH / 2)), 0, WIDTH)
            y = clamp(float(action.get("y", HEIGHT / 2)), 0, FLOOR_Y)
        except (TypeError, ValueError):
            return
        if kind == "spawn":
            world.spawn(x, y, player)
        elif kind == "burst":
            world.burst((x, y))
        elif kind == "clear":
            world.clear()
        elif kind == "event":
            events.trigger(world)
        elif kind == "spawn_rain":
            count = int(clamp(float(action.get("count", 8)), 1, 16))
            for index in range(count):
                px = 70 + index * ((WIDTH - 140) / max(1, count - 1))
                world.spawn(px, 90 + (index % 3) * 18, player)
        elif kind == "drag_start":
            entity_id = int(action.get("id", 0))
            world.begin_drag(player, (x, y), entity_id)
        elif kind == "drag_move":
            world.move_drag(player, (x, y))
        elif kind == "drag_end":
            world.end_drag(player)

    @staticmethod
    def snapshot_entity_at(snapshot: list[dict[str, Any]], point: tuple[int, int]) -> int | None:
        for item in reversed(snapshot):
            try:
                if math.dist((float(item["x"]), float(item["y"])), point) <= float(item["size"]) + 7:
                    return int(item["id"])
            except (KeyError, TypeError, ValueError):
                continue
        return None

    def draw_cpe_particles(self, particles: list[dict[str, Any]]) -> None:
        for particle in particles:
            try:
                x = int(float(particle["x"]))
                y = int(float(particle["y"]))
                size = max(1, int(float(particle.get("size", 3))))
                color = tuple(int(clamp(float(channel), 0, 255)) for channel in particle.get("color", YELLOW))
                pygame.draw.circle(self.screen, color, (x, y), size)
            except (KeyError, TypeError, ValueError):
                continue

    def draw_world(
        self,
        snapshot: list[dict[str, Any]],
        mouse: tuple[int, int],
        dragging_id: int | None,
    ) -> None:
        for item in snapshot:
            try:
                self.draw_entity(item, mouse, dragging_id)
            except (KeyError, TypeError, ValueError):
                continue
        pygame.draw.line(self.screen, (255, 240, 191), (0, FLOOR_Y), (WIDTH, FLOOR_Y), 4)

    def draw_entity(self, item: dict[str, Any], mouse: tuple[int, int], dragging_id: int | None) -> None:
        center = (int(item["x"]), int(item["y"]))
        size = int(float(item["size"]))
        angle = float(item["a"])
        color = safe_color(item["color"], CORAL)
        owner = str(item.get("owner", "host"))
        outline = (64, 82, 255) if owner == "guest" else WHITE
        hovered = math.dist(center, mouse) <= size + 5
        width = 5 if item.get("id") == dragging_id else 3 if hovered else 2
        if item["kind"] == "circle":
            pygame.draw.circle(self.screen, color, center, size)
            pygame.draw.circle(self.screen, outline, center, size, width)
            spoke = (
                int(center[0] + math.cos(angle) * size * 0.72),
                int(center[1] + math.sin(angle) * size * 0.72),
            )
            pygame.draw.line(self.screen, WHITE, center, spoke, max(3, size // 5))
            pygame.draw.circle(
                self.screen,
                tuple(min(255, channel + 55) for channel in color),
                (center[0] - size // 3, center[1] - size // 3),
                max(3, size // 7),
            )
        else:
            sides = int(clamp(float(item.get("sides", 4)), 3, 8))
            points = [
                (
                    int(center[0] + math.cos(angle - math.pi / 2 + index * math.tau / sides) * size),
                    int(center[1] + math.sin(angle - math.pi / 2 + index * math.tau / sides) * size),
                )
                for index in range(sides)
            ]
            pygame.draw.polygon(self.screen, color, points)
            pygame.draw.polygon(self.screen, outline, points, width)
            highlight = [
                (
                    int(center[0] + math.cos(angle - math.pi / 2 + index * math.tau / sides) * size * 0.58),
                    int(center[1] + math.sin(angle - math.pi / 2 + index * math.tau / sides) * size * 0.58),
                )
                for index in range(sides)
            ]
            pygame.draw.lines(self.screen, tuple(min(255, c + 40) for c in color), True, highlight, 2)

    def draw_game_hud(
        self,
        shape_count: int,
        energy: int,
        event: dict[str, Any],
        peer: NetworkPeer | None,
        is_host: bool,
        paused: bool,
        clear_rect: pygame.Rect,
        menu_rect: pygame.Rect,
    ) -> None:
        bar = pygame.Surface((WIDTH, 64), pygame.SRCALPHA)
        bar.fill((8, 45, 68, 218))
        self.screen.blit(bar, (0, 0))
        title = self.font.render("THE CUBE BETA  /  FALL LAB", True, WHITE)
        self.screen.blit(title, (16, 18))
        stats = self.small.render(f"{shape_count} SHAPES   â€¢   {energy} ENERGY", True, (184, 232, 240))
        self.screen.blit(stats, (325, 22))
        for rect, label, color in ((clear_rect, "CLEAR", CORAL), (menu_rect, "MENU", WHITE)):
            pygame.draw.rect(self.screen, color, rect, border_radius=9)
            text = self.small.render(label, True, INK)
            self.screen.blit(text, text.get_rect(center=rect.center))

        if event.get("name"):
            event_color = safe_color(event.get("color"), YELLOW)
            banner = pygame.Rect(260, 78, 580, 70)
            pygame.draw.rect(self.screen, event_color, banner, border_radius=16)
            name = self.font.render(
                f"{event['name']}  â€¢  {float(event.get('remaining', 0)):.0f}s",
                True,
                INK,
            )
            detail = self.small.render(str(event.get("banner", ""))[:72], True, INK)
            self.screen.blit(name, name.get_rect(center=(WIDTH // 2, 100)))
            self.screen.blit(detail, detail.get_rect(center=(WIDTH // 2, 128)))
        else:
            next_label = self.tiny.render(f"NEXT FALL EVENT  {float(event.get('next', 0)):.0f}s", True, WHITE)
            self.screen.blit(next_label, next_label.get_rect(center=(WIDTH // 2, 84)))

        if peer:
            role = "HOST" if is_host else "GUEST"
            badge_color = MINT if peer.connected else YELLOW
            badge = pygame.Rect(14, 78, 245, 52)
            pygame.draw.rect(self.screen, badge_color, badge, border_radius=13)
            role_label = self.tiny.render(f"{role}  â€¢  {peer.status}"[:38], True, INK)
            self.screen.blit(role_label, role_label.get_rect(center=badge.center))
            if is_host and not peer.connected:
                ip_label = self.small.render(f"Friend enters: {local_ip()}:{peer.port}", True, WHITE)
                ip_rect = ip_label.get_rect(topleft=(17, 139)).inflate(12, 8)
                pygame.draw.rect(self.screen, (9, 49, 73), ip_rect, border_radius=8)
                self.screen.blit(ip_label, (23, 143))
        if paused:
            paused_label = self.large.render("PAUSED", True, WHITE)
            self.screen.blit(paused_label, paused_label.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

        help_bar = pygame.Surface((WIDTH, 38), pygame.SRCALPHA)
        help_bar.fill((8, 45, 68, 225))
        self.screen.blit(help_bar, (0, HEIGHT - 38))
        help_text = self.tiny.render(
            "CLICK empty space: spawn random shape   â€¢   DRAG: grab & throw   â€¢   RIGHT CLICK: burst   â€¢   "
            "SPACE: shape shower   â€¢   E: event   â€¢   C: clear   â€¢   ESC: menu",
            True,
            WHITE,
        )
        self.screen.blit(help_text, help_text.get_rect(center=(WIDTH // 2, HEIGHT - 19)))


from experience_ui import install_experience_ui


install_experience_ui(GameApp, Button)


def main() -> None:
    GameApp().run()


if __name__ == "__main__":
    main()
