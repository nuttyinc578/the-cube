"""Offline functional coverage for Christmas, CPE 0.0.3 and CPELoader v2."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('CPE_DISABLE_BRIDGE', '1')

import pygame
from cpe.cache import CacheError, ProtectedSnapshot
from cpe.engine import CubePhysicsEngine
from cpe.performance import fast_enabled, set_fast_mode
from cpe.runtime import CPEBridgeRuntime
from cpeloader import COMPONENTS, CPELoader, snapshot, write_json
from cpeloader_cli import main
from cube_updater import CubeUpdater
from test_nightly import render_app
from christmas_update import fast_warning, toggle_fast, christmas_background, christmas_icon


class ProtectedCacheTests(unittest.TestCase):
    def test_snapshot_owns_nested_data_and_roundtrips(self):
        original = {'bodies': [{'id': 1, 'x': 20.0}], 'particles': []}
        protected = ProtectedSnapshot.capture(original)
        original['bodies'][0]['x'] = 99
        self.assertEqual(protected.restore()['bodies'][0]['x'], 20)
        restored = protected.restore()
        restored['bodies'].clear()
        self.assertEqual(len(protected.restore()['bodies']), 1)

    def test_cache_validation_bounds_and_digest(self):
        with self.assertRaises(CacheError):
            ProtectedSnapshot.capture({'sample': float('nan')})
        with self.assertRaises(CacheError):
            ProtectedSnapshot.capture({'sample': 'x'*(2*1024*1024+1)})
        with self.assertRaises(CacheError):
            ProtectedSnapshot(b'{}', '0'*64).restore()

    def test_bridge_captures_before_background_publication(self):
        bridge = CPEBridgeRuntime(enabled=False)
        bridge.enabled = True  # Exercise queue without creating a network worker.
        original = {'bodies': [{'id': 2}], 'particles': []}
        bridge.publish_cache(original)
        original['bodies'].clear()
        self.assertEqual(bridge._latest_cache[1].restore()['bodies'], [{'id': 2}])
        bridge.publish_cache({'bad': float('nan')})
        self.assertEqual(bridge.status()['cache_rejections'], 1)
        self.assertEqual(bridge._latest_cache[0], 1)


class FastModeTests(unittest.TestCase):
    def tearDown(self):
        set_fast_mode(False)

    def test_live_and_future_engines_restore_quality(self):
        engine = CubePhysicsEngine(particle_limit=1200)
        set_fast_mode(True)
        self.assertEqual(engine.space.iterations, 12)
        self.assertEqual(engine.particles.max_particles, 800)
        self.assertEqual(engine.health_report()['fixed_step_hz'], 120)
        future = CubePhysicsEngine(particle_limit=100)
        self.assertTrue(future.fast_mode)
        self.assertEqual(future.particles.max_particles, 100)
        set_fast_mode(False)
        self.assertEqual(engine.particles.max_particles, 1200)
        self.assertEqual(engine.space.iterations, 20)
        self.assertFalse(future.fast_mode)

    def test_clearing_removes_collision_bookkeeping(self):
        engine = CubePhysicsEngine()
        engine._collision_times[(1, 2)] = 0
        engine.clear()
        self.assertFalse(engine._collision_times)


class ChristmasUITests(unittest.TestCase):
    def setUp(self):
        self.app = render_app()
        self.app.settings.update(theme='christmas', fullscreen=False)
        self.app.notify = lambda *args: None
        set_fast_mode(False)
        self.addCleanup(pygame.quit)
        self.addCleanup(set_fast_mode, False)

    def test_both_confirmation_screens_must_be_accepted(self):
        with patch('christmas_update.confirmation', return_value=False), patch('christmas_update.fast_warning') as warning:
            self.assertTrue(toggle_fast(self.app))
            warning.assert_not_called()
            self.assertFalse(fast_enabled())
        with patch('christmas_update.confirmation', return_value=True), patch('christmas_update.fast_warning', return_value=False):
            toggle_fast(self.app)
            self.assertFalse(fast_enabled())
        with patch('christmas_update.confirmation', return_value=True), patch('christmas_update.fast_warning', return_value=True):
            toggle_fast(self.app)
            self.assertTrue(fast_enabled())
        toggle_fast(self.app)
        self.assertFalse(fast_enabled())

    def test_fullscreen_warning_defaults_cancel_and_restores_window(self):
        enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0)
        with patch('pygame.event.get', return_value=[enter]):
            self.assertFalse(fast_warning(self.app))
        self.assertFalse(self.app.screen.get_flags() & pygame.FULLSCREEN)

    def test_fullscreen_warning_accept_and_quit(self):
        events = [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0),
                  pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0)]
        with patch('pygame.event.get', return_value=events):
            self.assertTrue(fast_warning(self.app))
        with patch('pygame.event.get', return_value=[pygame.event.Event(pygame.QUIT)]):
            self.assertIsNone(fast_warning(self.app))

    def test_christmas_art_renders(self):
        christmas_background(self.app, 1.0)
        self.assertEqual(christmas_icon().get_size(), (64, 64))


class LoaderV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'My Cube Folder'
        self.root.mkdir()
        for name in COMPONENTS:
            (self.root/name).write_text('# component', encoding='utf-8')
        (self.root/'game.py').write_text('# game', encoding='utf-8')
        write_json(self.root/'cpeloader_manifest.json', {'files': snapshot(self.root)})
        self.loader = CPELoader(self.root)
        self.loader.unlock()

    def test_command_locks_all_components_without_resealing(self):
        manifest = (self.root/'cpeloader_manifest.json').read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['-connect', '-'+str(self.root), '-LOCK', '-cpeloader']), 0)
        self.assertFalse(self.loader.unlocked)
        self.assertTrue(all(v is False for v in self.loader.state()['components'].values()))
        self.assertEqual((self.root/'cpeloader_manifest.json').read_bytes(), manifest)
        self.assertEqual(self.loader.changes(), [])
        CubeUpdater(self.root, '6.4.3-nightly').require_update()

    def test_version_flags_do_not_connect_or_change_files(self):
        before = (self.root/'cpeloader_state.json').read_bytes()
        commands = [
            ['-cpeloader', '--v'],
            ['--version', '-cpeloader'],
            ['-connect', str(self.root/'missing'), '-cpeloader', '--v'],
        ]
        for command in commands:
            with self.subTest(command=command), contextlib.redirect_stdout(io.StringIO()) as output:
                with patch('cpeloader_cli.CPELoader') as loader, patch('cpeloader_cli.Path.resolve') as resolve:
                    self.assertEqual(main(command), 0)
                    loader.assert_not_called()
                    resolve.assert_not_called()
                self.assertEqual(output.getvalue().strip(), 'CPELoader v2')
        self.assertEqual((self.root/'cpeloader_state.json').read_bytes(), before)

    def test_version_and_lock_are_rejected_without_changing_state(self):
        before = (self.root/'cpeloader_state.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
            main(['-connect', str(self.root), '-cpeloader', '--v', '-LOCK'])
        self.assertEqual(result.exception.code, 2)
        self.assertEqual((self.root/'cpeloader_state.json').read_bytes(), before)

    def test_status_and_lock_still_require_connection_folder(self):
        for command in (['-cpeloader'], ['-cpeloader', '-LOCK']):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main(command)
                self.assertEqual(result.exception.code, 2)

    def test_modification_warning_survives_relocking(self):
        (self.root/'game.py').write_text('# my custom cube', encoding='utf-8')
        self.assertIn('game.py', self.loader.lock())
        self.assertIn('game.py', self.loader.changes())
        with self.assertRaises(PermissionError):
            CubeUpdater(self.root, '6.4.3-nightly').require_update()

    def test_read_only_status_does_not_lock(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['-connect', str(self.root), '-cpeloader']), 0)
        self.assertTrue(self.loader.unlocked)

    def test_missing_game_folder_is_not_created(self):
        path = self.root/'not a game'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['-connect', str(path), '-LOCK', '-cpeloader']), 1)
        self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
