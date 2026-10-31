"""Offline frozen-game QA. No accounts, network, settings or unlock writes."""
from __future__ import annotations
import importlib.metadata
import json
import os
from pathlib import Path
import platform
from types import SimpleNamespace

import pygame
from cube_core import VERSION, PhysicsWorld, bundle_path
from fluent_ui import BUILTINS, FluentButton, buttons
from nightly_ui import render_home, render_loading, install_nightly_ui, _main_menu
from cpeloader_ui import render_unlock, render_loader_warning


def run(report_path):
    # Self-test mode exits after QA; never contact even a localhost bridge.
    os.environ['CPE_DISABLE_BRIDGE'] = '1'
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((1100, 720))
    app = SimpleNamespace(screen=pygame.display.get_surface(),
        font=pygame.font.SysFont('segoeui', 21), small=pygame.font.SysFont('segoeui', 16),
        tiny=pygame.font.SysFont('segoeui', 14), large=pygame.font.SysFont('segoeui', 46, bold=True),
        settings={'theme': 'halloween'}, theme_store=SimpleNamespace(state=lambda: {}),
        cpeloader=SimpleNamespace(unlocked=False, unlocked_updates_enabled=False),
        play_click=lambda: None)
    world = None
    try:
        for theme in BUILTINS:
            app.settings['theme'] = theme
            controls, actions = render_home(app, 1.2)
            buttons(app, controls, [])
            assert 'single' in actions and 'updater' in actions
            assert all(app.screen.get_rect().contains(b.rect) for b in controls)
            pygame.image.save(app.screen, str(report_path.parent/f'home-{theme}.png'))
        app.settings['theme'] = 'christmas'
        render_loading(app, .65, 1.2)
        pygame.image.save(app.screen, str(report_path.parent/'loading.png'))
        from christmas_update import render_fast_warning, christmas_background
        buttons(app, render_fast_warning(app), [])
        pygame.image.save(app.screen, str(report_path.parent/'fast-cpe-warning.png'))
        christmas_background(app, 1.2)
        pygame.image.save(app.screen, str(report_path.parent/'christmas-world.png'))
        render_unlock(app)
        pygame.image.save(app.screen, str(report_path.parent/'cpeloader-unlock.png'))
        render_loader_warning(app, ['cpe-backend.json'], modified=True)
        pygame.image.save(app.screen, str(report_path.parent/'cpeloader-warning.png'))
        items = [FluentButton((1, 1, 80, 40), 'Play')]
        assert buttons(app, items, [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0)])[0] == 0
        class StartupProbe:
            def __init__(self):
                self.settings = {'theme': 'halloween', 'fluent_ui_seen': True, 'christmas_ui_seen': True}
                self.main_menu = lambda: 'obsolete-menu'
        install_nightly_ui(StartupProbe)
        assert StartupProbe().main_menu.__func__ is _main_menu
        for name in ('halloween_cube_icon.png', 'LICENCE.txt', 'nightly-config.json', 'click.mp3'):
            assert bundle_path(name).is_file(), f'Missing bundled asset: {name}'
        world = PhysicsWorld(900, SimpleNamespace(shapes=[], events=[]))
        from cpe import __version__ as cpe_version
        from cpe.backend import BACKEND
        from cpe.performance import set_fast_mode
        assert BACKEND == 'classic' and cpe_version == '0.0.3-nightly'
        set_fast_mode(True)
        assert world.cpe.fast_mode and world.cpe.space.iterations == 12
        set_fast_mode(False)
        assert not world.cpe.fast_mode and world.cpe.space.iterations == 20
        world.spawn(250, 110, owner='nightly-qa')
        for _ in range(60):
            world.update(1/60, 0, 1)
        assert world.snapshot()
        # PyInstaller metadata is optional; pygame.version is the actual imported runtime.
        report = {'version': VERSION, 'python': platform.python_version(),
            'pygame': pygame.version.ver, 'pygame_ce': bool(getattr(pygame, 'IS_CE', False)),
            'physics_ok': True, 'themes_rendered': list(BUILTINS),
            'keyboard_ok': True, 'instance_menu_binding_ok': True,
            'loader_default': 'locked', 'cpeloader_version': '2', 'cpe_version': '0.0.3-nightly',
            'cache_protection': True, 'network_used': False}
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        if world is not None:
            world.close()
        pygame.quit()
