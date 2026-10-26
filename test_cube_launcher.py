"""Ordinary launcher behavior tests; no game code or downloads are executed."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from cube_launcher.cloud import DEFAULT_CLOUD, CALLBACK, WEBSITE_SIGNUP_URL, authorization_url, validate_config, open_website_signup
from cube_launcher.core import Launcher, atomic_json, catalog_payload, update_guard


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = Launcher(Path(self.temp.name)/'launcher')

    def release(self, version='6.4.0', wrapped=False):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            prefix = 'The Cube/' if wrapped else ''
            archive.writestr(prefix+'The Cube Beta.exe', b'ordinary test placeholder, never executed')
            archive.writestr(prefix+'settings.json', json.dumps({'volume': 70}))
            archive.writestr(prefix+'cpeloader.py', '"""Ordinary test loader component, never executed."""')
        data = buffer.getvalue()
        result = {'version': version, 'kind': 'zip', 'name': 'Cube-Portable.zip', 'size': len(data),
            'sha256': hashlib.sha256(data).hexdigest(), 'url': 'https://github.com/nuttyinc578/the-cube/releases/download/'+version+'/Cube-Portable.zip'}
        return result, data

    def install(self, version='6.4.0', update=False, wrapped=False):
        release, data = self.release(version, wrapped)
        with patch('cube_launcher.core.request', return_value=io.BytesIO(data)):
            return self.manager.install('default', release, update)

    def test_install_and_wrapper_layout(self):
        base = self.install(wrapped=True)
        self.assertTrue((base/'game'/'The Cube Beta.exe').is_file())
        self.assertEqual(self.manager.instances(), ['default'])
        self.assertEqual(self.manager.info('default')['version'], '6.4.0')
        self.assertFalse(json.loads((base/'game'/'cpeloader_state.json').read_text())['unlocked'])
        update_guard(base/'game')

    def test_update_preserves_settings_and_userdata_and_backup(self):
        base = self.install('6.3.0')
        (base/'game'/'settings.json').write_text('{"volume": 15}')
        (base/'game'/'userdata').mkdir()
        (base/'game'/'userdata'/'save.txt').write_text('player save')
        self.install(update=True)
        self.assertEqual(json.loads((base/'game'/'settings.json').read_text())['volume'], 15)
        self.assertEqual((base/'game'/'userdata'/'save.txt').read_text(), 'player save')
        backup = next((self.manager.root/'backups').iterdir())
        self.assertEqual(json.loads((backup/'instance.json').read_text())['version'], '6.3.0')

    def test_unlocked_update_blocked_even_with_bypass(self):
        base = self.install()
        atomic_json(base/'game'/'cpeloader_state.json', {'unlocked': True, 'components': {}})
        atomic_json(base/'game'/'cpe-flash-profile.json', {'allow_unlocked_updates': True})
        with patch('cube_launcher.core.request') as network:
            with self.assertRaises(PermissionError):
                self.manager.install('default', self.release()[0], True)
            network.assert_not_called()

    def test_partial_unlock_blocks(self):
        game = self.manager.root
        atomic_json(game/'cpeloader_state.json', {'unlocked': False, 'components': {'cpeloader.py': True}})
        with self.assertRaises(PermissionError):
            update_guard(game)

    def test_corrupt_state_blocks(self):
        (self.manager.root/'cpeloader_state.json').write_text('broken JSON')
        with self.assertRaises(PermissionError):
            update_guard(self.manager.root)

    def test_locked_state_allows_update(self):
        atomic_json(self.manager.root/'cpeloader_state.json', {'unlocked': False, 'components': {'cpeloader.py': False}})
        update_guard(self.manager.root)

    def test_duplicate_instance_does_not_download(self):
        self.install()
        with patch('cube_launcher.core.request') as network:
            with self.assertRaises(ValueError):
                self.install()
            network.assert_not_called()

    def test_running_game_blocks_update(self):
        self.install()
        info = self.manager.info('default')
        info['pid'] = 123
        atomic_json(self.manager.instance('default')/'instance.json', info)
        with patch('cube_launcher.core.alive', return_value=True), patch('cube_launcher.core.request') as network:
            with self.assertRaises(PermissionError):
                self.manager.install('default', self.release()[0], True)
            network.assert_not_called()

    def test_failed_promotion_restores_original(self):
        base = self.install('6.3.0')
        original = Path.rename
        def rename(path, destination):
            if path.parent.name == 'staging':
                raise OSError('simulated disk unavailable')
            return original(path, destination)
        with patch.object(Path, 'rename', rename):
            with self.assertRaises(OSError):
                self.install(update=True)
        self.assertEqual(self.manager.info('default')['version'], '6.3.0')

    def test_catalog_numeric_order(self):
        payload = []
        for version in ('6.3.0', '6.4.0'):
            release, _ = self.release(version)
            payload.append({'tag_name': version, 'assets': [{'name': release['name'], 'browser_download_url': release['url'],
                'digest': 'sha256:'+release['sha256'], 'size': release['size']}]})
        self.assertEqual([r['version'] for r in catalog_payload(payload)], ['6.4.0', '6.3.0'])

    def test_cognito_configuration(self):
        self.assertEqual(validate_config({'cognito_domain': 'https://nuttyinc.auth.ca-central-1.amazoncognito.com', 'cognito_client_id': 'abc123'})[1], 'abc123')
        with self.assertRaises(ValueError):
            validate_config({})

    def test_operation_lock(self):
        with self.manager.lock():
            with self.assertRaises(RuntimeError):
                with self.manager.lock():
                    pass
        self.assertFalse((self.manager.root/'operation.lock').exists())

    def test_cloud_defaults_and_existing_settings(self):
        self.assertEqual(self.manager.settings(), DEFAULT_CLOUD)
        custom = {'cognito_domain': 'https://custom.auth.ca-central-1.amazoncognito.com', 'cognito_client_id': 'custom123'}
        atomic_json(self.manager.settings_path, custom)
        self.assertEqual(self.manager.settings(), custom)
        atomic_json(self.manager.settings_path, {'cognito_domain': '', 'cognito_client_id': ''})
        self.assertEqual(self.manager.settings(), DEFAULT_CLOUD)

    def test_cloud_login_uses_launcher_callback_and_pkce(self):
        url = urlsplit(authorization_url(DEFAULT_CLOUD, 'test-login-state', 'test-pkce-challenge'))
        query = parse_qs(url.query)
        self.assertEqual(url.netloc, 'ca-central-1kqtmazcpv.auth.ca-central-1.amazoncognito.com')
        self.assertEqual(query['client_id'], ['q2u1oorqn5lt2v89abisrg7rv'])
        self.assertEqual(query['redirect_uri'], [CALLBACK])
        self.assertEqual(query['scope'], ['openid email'])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['state'], ['test-login-state'])

    def test_signup_opens_exact_website_link(self):
        with patch('cube_launcher.cloud.webbrowser.open', return_value=True) as browser:
            open_website_signup()
            browser.assert_called_once_with(WEBSITE_SIGNUP_URL)
        query = parse_qs(urlsplit(WEBSITE_SIGNUP_URL).query)
        self.assertEqual(query['redirect_uri'], ['https://d84l1y8p4kdic.cloudfront.net'])
        self.assertEqual(query['scope'], ['email openid phone'])

    def test_play_uses_instance_cwd_without_shell(self):
        base = self.install()
        with patch('cube_launcher.core.subprocess.Popen') as launch:
            launch.return_value.pid = 123
            self.assertEqual(self.manager.play('default'), 123)
            launch.assert_called_once_with([str(base/'game'/'The Cube Beta.exe')], cwd=base/'game', shell=False)

    def test_missing_state_on_existing_loader_blocks(self):
        (self.manager.root/'cpeloader.py').write_text('"""Test component."""')
        with self.assertRaises(PermissionError):
            update_guard(self.manager.root)


if __name__ == '__main__':
    unittest.main()
