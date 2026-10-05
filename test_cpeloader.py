import os
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
from cpeloader import CPELoader, COMPONENTS, snapshot, write_json
from cpeloader_ui import unlock_screen, unlocked_warning, loader_loading, LoaderReset
from cpe_rephysics.flash import install


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in COMPONENTS: (self.root/name).write_text('# component')
        self.loader = CPELoader(self.root)
    def tearDown(self): self.temp.cleanup()

    def test_default_lock_and_partial_unlock_deny_flash_before_writes(self):
        self.assertFalse(self.loader.unlocked)
        with self.assertRaises(PermissionError): install(self.root)
        self.assertFalse((self.root/'backup').exists())
        write_json(self.loader.path, {'unlocked': True, 'components': {COMPONENTS[0]: True}})
        with self.assertRaises(PermissionError): self.loader.require_flash()

    def test_unlock_detects_added_changed_removed_files_and_blocks_updates(self):
        (self.root/'base.py').write_text('old')
        self.loader.unlock(); self.loader.require_flash()
        (self.root/'base.py').write_text('new')
        (self.root/'addon.rb').write_text('new')
        (self.root/COMPONENTS[2]).unlink()
        self.assertEqual(self.loader.changes(), sorted(['base.py', 'addon.rb', COMPONENTS[2]]))
        with self.assertRaises(PermissionError): self.loader.require_flash()
        with self.assertRaises(PermissionError): self.loader.require_in_game_update()

    def test_locked_manifest_and_corrupt_state(self):
        write_json(self.root/'cpeloader_manifest.json', {'files': snapshot(self.root)})
        (self.root/COMPONENTS[0]).write_text('modified')
        self.assertIn(COMPONENTS[0], self.loader.changes())
        self.loader.path.write_text('{broken')
        self.assertFalse(self.loader.unlocked)
        self.assertIn('unreadable', self.loader.changes()[0])

    def test_installer_and_runtime_files_do_not_trigger_integrity_warning(self):
        write_json(self.root/'cpeloader_manifest.json', {'files': snapshot(self.root)})
        for name in ['unins000.exe', 'unins000.dat', 'settings.json']:
            (self.root/name).write_text('runtime')
        self.assertEqual(self.loader.changes(), [])

    def test_unlocked_version_and_experience_rewrites_are_blocked(self):
        from og_recovery import OGRecoveryManager, OGRecoveryError
        from theme_system import ThemeStore, ThemeError
        self.loader.unlock()
        manager = OGRecoveryManager(self.root)
        with self.assertRaisesRegex(OGRecoveryError, 'external installer'):
            manager.prepare('6.3.0')
        store = ThemeStore(self.root)
        with self.assertRaisesRegex(ThemeError, 'external installer'):
            store.activate_experience('developer-beta')
        with self.assertRaisesRegex(ThemeError, 'external installer'):
            store.activate_legacy('christmas')

    def test_node_and_ruby_share_fail_closed_flash_policy(self):
        source = Path(__file__).resolve().parent
        for runtime, script in [('node', COMPONENTS[1]), ('ruby', COMPONENTS[2])]:
            executable = shutil.which(runtime)
            if not executable: continue  # Ruby is optional on Windows CI.
            def status():
                result = subprocess.run([executable, str(source/script), str(self.root), 'flash'], capture_output=True, text=True, timeout=15)
                return result
            self.loader.path.unlink(missing_ok=True)
            self.assertNotEqual(status().returncode, 0)
            self.loader.unlock()
            result = status()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['unlocked'])
            (self.root/COMPONENTS[2]).unlink()
            self.assertNotEqual(status().returncode, 0)
            (self.root/COMPONENTS[2]).write_text('# component')
            self.loader.path.write_text('null')
            self.assertNotEqual(status().returncode, 0)

    def test_y_unlocks_and_resets_shift_n_cancels(self):
        app = SimpleNamespace(cpeloader=self.loader)
        cancel = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, mod=pygame.KMOD_SHIFT)
        with patch('pygame.event.get', return_value=[cancel]): self.assertTrue(unlock_screen(app))
        self.assertFalse(self.loader.unlocked)
        yes = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y, mod=0)
        with patch('pygame.event.get', return_value=[yes]), patch('cpeloader_ui.time.monotonic', side_effect=[0, 2]):
            with self.assertRaises(LoaderReset): unlock_screen(app)
        self.assertTrue(self.loader.unlocked)

    def test_warning_at_halfway_requires_enter(self):
        pygame.init()
        self.loader.unlock()
        app = SimpleNamespace(cpeloader=self.loader, screen=pygame.Surface((1100, 720)), large=pygame.font.Font(None, 46), small=pygame.font.Font(None, 21), clock=SimpleNamespace(tick=lambda fps: None), common_events=lambda events: True)
        times = iter([0, .3, 1.5, 1.5, 1.5, 2, 3.1])
        with patch('pygame.event.get', return_value=[]), patch('pygame.display.flip'), patch('cpeloader_ui.time.monotonic', side_effect=lambda: next(times)), patch('cpeloader_ui.unlocked_warning', return_value=True) as warning:
            self.assertTrue(loader_loading(app)); warning.assert_called_once()
        enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0)
        other = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0)
        with patch('pygame.event.get', side_effect=[[other], [enter]]), patch('pygame.display.flip'):
            self.assertTrue(unlocked_warning(app, ['base.py']))
        pygame.quit()

if __name__ == '__main__': unittest.main()
