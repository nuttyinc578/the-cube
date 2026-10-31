"""Isolated recovery-image, consent, rollback and missing-loader regressions."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cpe_repair as repair
from cpeloader import COMPONENTS, snapshot
from cpeloader_cli import main
from release_info import EXE_NAME

ROOT = Path(__file__).resolve().parent


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.game = self.base/'game'
        self.game.mkdir()
        (self.game/EXE_NAME).write_bytes(b'compiled game fixture')
        image = self.base/'recovery'
        repair.build_image(ROOT, self.game, image)
        self.paths = (image/'image.zip', image/'image.json')
        self.files, self.payloads = repair.load_image(self.paths)
        for name, data in self.payloads.items():
            target = self.game/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (self.game/'settings.json').write_bytes(b'player settings')
        (self.game/'cpeloader_state.json').write_text(json.dumps({'unlocked': True, 'components': {n: True for n in COMPONENTS}}))
        (self.game/'cpeloader_manifest.json').write_text(json.dumps({'files': snapshot(self.game)}))
        self.manifest = (self.game/'cpeloader_manifest.json').read_bytes()
        self.state = (self.game/'cpeloader_state.json').read_bytes()

    def plan(self, groups=None):
        return repair.prepare_repair(self.game, groups or {'cpe', 'cpeloader'}, self.paths)

    def test_complete_image_is_noop_and_does_not_make_backup(self):
        result = repair.execute_repair(self.plan())
        self.assertEqual(result, {'restored': [], 'backup': None})
        self.assertFalse((self.game/'backup').exists())

    def test_missing_loader_is_named_and_can_be_restored(self):
        (self.game/COMPONENTS[0]).unlink()
        with self.assertRaisesRegex(repair.RepairError, 'CPELOADER_MISSING.*cpeloader.py'):
            self.plan({'cpe'})
        result = repair.execute_repair(self.plan({'cpeloader'}))
        self.assertEqual(result['restored'], [COMPONENTS[0]])
        self.assertEqual((self.game/COMPONENTS[0]).read_bytes(), self.payloads[COMPONENTS[0]])
        self.assertEqual((self.game/'cpeloader_state.json').read_bytes(), self.state)
        self.assertEqual((self.game/'cpeloader_manifest.json').read_bytes(), self.manifest)

    def test_cpe_repair_preserves_backup_state_settings_and_unrelated_mods(self):
        (self.game/EXE_NAME).write_bytes(b'modified engine')
        (self.game/'custom-mod.py').write_bytes(b'user mod')
        events = []
        result = repair.execute_repair(self.plan({'cpe'}), lambda n, msg: events.append(n))
        self.assertEqual((Path(result['backup'])/'original'/EXE_NAME).read_bytes(), b'modified engine')
        self.assertEqual((self.game/EXE_NAME).read_bytes(), self.payloads[EXE_NAME])
        self.assertEqual((self.game/'custom-mod.py').read_bytes(), b'user mod')
        self.assertEqual((self.game/'settings.json').read_bytes(), b'player settings')
        self.assertEqual((self.game/'cpeloader_state.json').read_bytes(), self.state)
        self.assertEqual((self.game/'cpeloader_manifest.json').read_bytes(), self.manifest)
        self.assertEqual(events, sorted(events))
        self.assertEqual(events[-1], 100)

    def test_bad_image_hash_does_not_touch_game(self):
        self.paths[0].write_bytes(b'not a recovery image')
        before = snapshot(self.game)
        with self.assertRaisesRegex(repair.RepairError, 'checksum mismatch'):
            self.plan()
        self.assertEqual(snapshot(self.game), before)
        self.assertFalse((self.game/'backup').exists())

    def test_wrong_or_missing_release_manifest_is_rejected(self):
        for content in ('{}', '{"files": {}}', 'not json'):
            with self.subTest(content=content):
                (self.game/'cpeloader_manifest.json').write_text(content)
                with self.assertRaisesRegex(repair.RepairError, 'REPAIR_VERSION_MISMATCH'):
                    self.plan()
        self.assertFalse((self.game/'backup').exists())

    def test_confirmation_stale_files_cancel_before_backup(self):
        (self.game/EXE_NAME).write_bytes(b'changed once')
        plan = self.plan()
        (self.game/EXE_NAME).write_bytes(b'changed again')
        with self.assertRaisesRegex(repair.RepairError, 'REPAIR_CHANGED'):
            repair.execute_repair(plan)
        self.assertEqual((self.game/EXE_NAME).read_bytes(), b'changed again')
        self.assertFalse((self.game/'backup').exists())

    def test_failed_replacement_rolls_back_and_retains_originals(self):
        first, second = COMPONENTS[:2]
        for name in (first, second):
            (self.game/name).write_bytes(b'original modification')
        plan = self.plan({'cpeloader'})
        real_replace = os.replace
        calls = []
        def replace(source, target):
            calls.append(str(source))
            if 'staged' in Path(source).parts and Path(target).name == second:
                raise PermissionError('file busy')
            return real_replace(source, target)
        with patch('cpe_repair.os.replace', side_effect=replace):
            with self.assertRaisesRegex(repair.RepairError, 'rolled back'):
                repair.execute_repair(plan)
        for name in (first, second):
            self.assertEqual((self.game/name).read_bytes(), b'original modification')
        reports = list((self.game/'backup'/'cpe-cli').glob('*/repair.json'))
        self.assertEqual(json.loads(reports[0].read_text())['status'], 'rolled-back')

    def test_redirected_targets_are_refused_before_backup(self):
        target = self.game/COMPONENTS[0]
        original = Path.is_junction
        with patch.object(Path, 'is_junction', lambda p: p == target or original(p)):
            with self.assertRaisesRegex(repair.RepairError, 'REPAIR_PATH'):
                self.plan()
        self.assertFalse((self.game/'backup').exists())

    def test_cli_alias_version_and_missing_loader_error(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--cpeloader', '--v']), 0)
        self.assertEqual(output.getvalue().strip(), 'CPELoader v2')
        (self.game/COMPONENTS[1]).unlink()
        with contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(['--cpeloader', '-connect', str(self.game)]), 1)
        self.assertIn('CPELOADER_MISSING: '+COMPONENTS[1], error.getvalue())

    def test_console_repair_defaults_to_cancel_then_explicit_consent_repairs(self):
        (self.game/COMPONENTS[0]).unlink()
        command = ['--cpeloader', '-connect', str(self.game), '-cpe/repair', '-cpeloader/repair', '--no-gui']
        with patch('cpe_repair.image_paths', return_value=self.paths), contextlib.redirect_stdout(io.StringIO()) as output:
            with patch('builtins.input', return_value=''):
                self.assertEqual(main(command), 2)
            self.assertFalse((self.game/COMPONENTS[0]).exists())
            self.assertFalse((self.game/'backup').exists())
            self.assertEqual(main(command+['--yes']), 0)
            self.assertIn('3 minutes', output.getvalue())
        self.assertEqual((self.game/COMPONENTS[0]).read_bytes(), self.payloads[COMPONENTS[0]])

    def test_version_lock_and_repair_options_do_not_mix(self):
        commands = [ ['--cpeloader', '--v', '-cpe/repair'],
                     ['--cpeloader', '-LOCK', '-cpeloader/repair'], ['--cpeloader', '--yes'] ]
        for command in commands:
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main(command)
                self.assertEqual(result.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
