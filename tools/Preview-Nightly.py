"""Render real UI frames, including interactive controls, without installing."""
from pathlib import Path
import os
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PYGAME_HIDE_SUPPORT_PROMPT='1')
import pygame
from cube_core import DEFAULT_SETTINGS
from cpeloader_ui import unlock_screen, unlocked_warning
from nightly_ui import _main_menu, _themes_menu, _settings_menu, _updater_menu


def main():
    pygame.init()
    pygame.display.set_mode((1100, 720))
    app = SimpleNamespace(screen=pygame.display.get_surface(),
        font=pygame.font.SysFont('segoeui', 21), small=pygame.font.SysFont('segoeui', 16),
        tiny=pygame.font.SysFont('segoeui', 14), large=pygame.font.SysFont('segoeui', 46, bold=True),
        settings=dict(DEFAULT_SETTINGS), theme_store=SimpleNamespace(state=lambda: {}),
        cpeloader=SimpleNamespace(unlocked=False, unlocked_updates_enabled=False),
        clock=pygame.time.Clock(), common_events=lambda events: not any(e.type == pygame.QUIT for e in events),
        play_click=lambda: None, draw_toast=lambda: None)
    folder = ROOT/'build'/'nightly-preview'
    folder.mkdir(exist_ok=True)
    original_get, original_flip = pygame.event.get, pygame.display.flip
    for name, action in [('home', _main_menu), ('themes', _themes_menu), ('settings', _settings_menu),
                         ('updater', _updater_menu), ('unlock', unlock_screen),
                         ('warning', lambda a: unlocked_warning(a, ['cpe-backend.json']))]:
        frames = iter([[], [pygame.event.Event(pygame.QUIT)]])
        pygame.event.get = lambda: next(frames)
        pygame.display.flip = lambda: pygame.image.save(app.screen, str(folder/f'{name}.png'))
        try:
            action(app)
        except SystemExit:
            pass
        finally:
            pygame.event.get, pygame.display.flip = original_get, original_flip
    pygame.quit()
    print(folder)


if __name__ == '__main__':
    main()
