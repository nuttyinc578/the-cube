"""Offline tests for the nightly UI, countdown and consent-driven updater."""
import hashlib
import io
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from contextlib import ExitStack

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame
from cpeloader import COMPONENTS, CPELoader, write_json
from cube_updater import CubeUpdater, parse_updates, version_key, REPO
from fluent_ui import BUILTINS, FluentButton, buttons, confirmation
from nightly_ui import power_countdown, render_home, render_loading, set_theme, install_nightly_ui
from theme_system import ThemeStore


def release(payload=b'official test download', version='6.5.0', setup=True):
    name = f'The-Cube-Beta-Halloween-{version}-'+('Setup.exe' if setup else 'Portable.zip')
    return {'tag_name': version, 'assets': [{'name': name, 'browser_download_url':
        f'https://github.com/{REPO}/releases/download/{version}/{name}',
        'digest': 'sha256:'+hashlib.sha256(payload).hexdigest(), 'size': len(payload)}]}


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in COMPONENTS:
            (self.root/name).write_text('# loader component', encoding='utf-8')
        write_json(self.root/'cpeloader_state.json', {'unlocked': False, 'components': {n: False for n in COMPONENTS}})
        self.data = b'official test download'
        self.record = release(self.data)
        self.update = parse_updates([self.record], '6.4.2-nightly')[0]

    def manager(self, data=None):
        return CubeUpdater(self.root, '6.4.2-nightly', lambda url: io.BytesIO(self.data if data is None else data))

    def test_catalog_never_downgrades_or_repeats_current_nightly(self):
        self.assertEqual(parse_updates([release(version='6.4.1'), release(version='6.4.2-nightly')], '6.4.2-nightly'), [])
        self.assertGreater(version_key('6.4.2'), version_key('6.4.2-nightly'))

    def test_prefers_installer_and_sorts_newer_versions(self):
        record = release(setup=False)
        record['assets'] += release()['assets']
        result = parse_updates([release(version='6.4.3'), record], '6.4.2-nightly')
        self.assertEqual(result[0].version, '6.5.0')
        self.assertTrue(result[0].installer)

    def test_draft_and_missing_checksum_are_not_updates(self):
        draft = release(); draft['draft'] = True
        missing = release(); missing['assets'][0]['digest'] = None
        self.assertEqual(parse_updates([draft, missing], '6.4.2-nightly'), [])

    def test_catalog_read_is_bounded(self):
        manager = self.manager(b' '*(4*1024*1024+1))
        with self.assertRaisesRegex(ValueError, 'too large'):
            manager.check()

    def test_download_checks_size_and_hash_without_replacing_game(self):
        (self.root/'game.exe').write_bytes(b'installed')
        result = self.manager().download(self.update)
        self.assertEqual(result.read_bytes(), self.data)
        self.assertEqual((self.root/'game.exe').read_bytes(), b'installed')
        self.assertTrue(result.is_relative_to(self.root/'userdata'/'updates'))
        self.assertFalse(list(result.parent.glob('*.part')))

    def test_bad_checksum_leaves_no_download(self):
        with self.assertRaisesRegex(ValueError, 'Checksum'):
            self.manager(b'wrong content').download(self.update)
        self.assertEqual(list((self.root/'userdata'/'updates').iterdir()), [])

    def test_cancelled_download_is_removed(self):
        event = threading.Event(); event.set()
        with self.assertRaises(InterruptedError):
            self.manager().download(self.update, cancelled=event)
        self.assertEqual(list((self.root/'userdata'/'updates').iterdir()), [])

    def test_unlocked_and_partial_loader_block_before_network(self):
        manager = self.manager()
        manager.opener = Mock(side_effect=AssertionError('Network must not be called'))
        CPELoader(self.root).unlock()
        with self.assertRaises(PermissionError):
            manager.download(self.update)
        write_json(self.root/'cpeloader_state.json', {'unlocked': False, 'components': {COMPONENTS[0]: True}})
        with self.assertRaises(PermissionError):
            manager.download(self.update)
        manager.opener.assert_not_called()

    def test_custom_build_is_not_officially_updatable(self):
        write_json(self.root/'cpe-flash-profile.json', {'schema': 1, 'custom_portable': True})
        with self.assertRaisesRegex(PermissionError, 'owner'):
            self.manager().require_update()

    def test_loader_is_rechecked_after_download(self):
        def progress(message): CPELoader(self.root).unlock()
        with self.assertRaises(PermissionError):
            self.manager().download(self.update, progress)
        self.assertEqual(list((self.root/'userdata'/'updates').iterdir()), [])

    def test_installer_requires_explicit_launch_and_rechecks_hash(self):
        manager = self.manager()
        with patch('cube_updater.subprocess.Popen') as launch:
            path = manager.download(self.update)
            launch.assert_not_called()
            manager.launch_installer(self.update, path)
            self.assertFalse(launch.call_args.kwargs['shell'])
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                manager.launch_installer(self.update, path)
            self.assertEqual(launch.call_count, 1)


def render_app():
    pygame.init()
    pygame.display.set_mode((1100, 720))
    return SimpleNamespace(screen=pygame.Surface((1100, 720)),
        font=pygame.font.SysFont('segoeui', 21), small=pygame.font.SysFont('segoeui', 16),
        tiny=pygame.font.SysFont('segoeui', 14), large=pygame.font.SysFont('segoeui', 46, bold=True),
        settings={'theme': 'halloween'}, theme_store=SimpleNamespace(state=lambda: {}),
        cpeloader=SimpleNamespace(unlocked=False, unlocked_updates_enabled=False),
        play_click=Mock(), clock=SimpleNamespace(tick=lambda fps: None))


class NightlyUITests(unittest.TestCase):
    def setUp(self):
        self.app = render_app()
        self.addCleanup(pygame.quit)

    def test_countdown_is_honest_without_a_date(self):
        for value in (None, '', 'invalid', '2026-11-05T00:00:00'):
            self.assertIn('TO BE ANNOUNCED', power_countdown(value))

    def test_countdown_live_future_and_complete(self):
        now = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.assertEqual(power_countdown('2026-11-02T00:00:00Z', now), '01D   00H   00M   00S')
        self.assertIn('COMPLETE', power_countdown('2026-10-31T00:00:00Z', now))

    def test_all_builtins_render_home_loading_and_loader_panels(self):
        from cpeloader_ui import render_unlock, render_loader_warning
        for theme in BUILTINS:
            self.app.settings['theme'] = theme
            controls, actions = render_home(self.app, 1.5)
            self.assertEqual(len(controls), len(actions))
            self.assertIn('single', actions)
            self.assertIn('updater', actions)
            for control in controls:
                self.assertTrue(self.app.screen.get_rect().contains(control.rect))
            render_loading(self.app, .5)
            render_unlock(self.app)
            render_loader_warning(self.app, ['engine.py'])

    def test_keyboard_navigation_plays_original_click(self):
        items = [FluentButton((10, 10, 100, 40), 'One'), FluentButton((10, 60, 100, 40), 'Two')]
        incoming = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0),
                    pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0)]
        self.assertEqual(buttons(self.app, items, incoming), (1, 1))
        self.app.play_click.assert_called_once()

    def test_generic_confirmation_defaults_to_cancel(self):
        enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0)
        with patch('pygame.event.get', return_value=[enter]):
            self.assertFalse(confirmation(self.app, 'Confirm', 'Do something'))

    def test_builtin_themes_are_valid_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ThemeStore(folder)
            self.assertEqual(store.state()['active_theme'], 'halloween')
            self.app.theme_store, self.app.background_cache = store, {}
            with patch('nightly_ui.save_settings'):
                for theme in BUILTINS:
                    set_theme(self.app, theme)
                    self.assertEqual(store.state()['active_theme'], theme)

    def test_first_christmas_defaults_then_remembers_choice(self):
        app = self.app
        app.settings['christmas_ui_seen'] = False
        app.settings['theme'] = 'maple'
        app.background_cache = {}
        app.theme_store.set_active_theme = Mock()
        class FakeGame:
            def __init__(self): self.__dict__.update(app.__dict__)
        install_nightly_ui(FakeGame)
        with patch('nightly_ui.save_settings'):
            first = FakeGame()
            self.assertEqual(first.settings['theme'], 'christmas')
            first.settings['theme'] = 'aurora'
            second = FakeGame()
            self.assertEqual(second.settings['theme'], 'aurora')

    def test_actual_game_binds_nightly_menu_after_error_and_loader_initializers(self):
        import the_cube_beta_summer as game
        from nightly_ui import _main_menu
        with tempfile.TemporaryDirectory() as folder, ExitStack() as patches:
            root = Path(folder)
            for module in ('experience_ui', 'error_update', 'halloween_update', 'cpeloader_ui'):
                patches.enter_context(patch(module+'.app_path', return_value=root))
            patches.enter_context(patch('cube_core.SETTINGS_FILE', root/'settings.json'))
            patches.enter_context(patch.object(game, 'AddonManager', return_value=SimpleNamespace(shapes=[], events=[], records=[])))
            instance = game.GameApp()
            self.assertIs(instance.main_menu.__func__, _main_menu)
            self.assertEqual(instance.settings['theme'], 'christmas')
            self.assertEqual(instance.fall_update_screen.__func__.__name__, 'startup')
            self.assertFalse(instance.cpeloader.unlocked)


if __name__ == '__main__':
    unittest.main()
