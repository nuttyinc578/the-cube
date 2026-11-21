import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from microsoft_login import AUTHORITY, CLIENT_ID, GRAPH_APP_ID, api_application_id, sign_in_online


API_APP_ID = '11111111-2222-4333-8444-555555555555'


class MicrosoftLoginTests(unittest.TestCase):
    def test_requests_only_the_online_api_with_public_client(self):
        factory = Mock()
        interactive = factory.return_value.acquire_token_interactive
        interactive.return_value = {'access_token': 'online-test-token', 'id_token': 'not-used'}
        with patch.dict(sys.modules, {'msal': SimpleNamespace(PublicClientApplication=factory)}):
            self.assertEqual(sign_in_online(API_APP_ID), 'online-test-token')
        factory.assert_called_once_with(CLIENT_ID, authority=AUTHORITY, exclude_scopes=['offline_access'])
        interactive.assert_called_once_with(scopes=[f'api://{API_APP_ID}/Cube.Online'],
                                            prompt='select_account', timeout=120)

    def test_wrong_resource_cannot_start_sign_in(self):
        for identifier in (None, '', GRAPH_APP_ID, CLIENT_ID):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                api_application_id(identifier)

    def test_id_token_alone_is_never_used_for_online_access(self):
        factory = Mock()
        factory.return_value.acquire_token_interactive.return_value = {'id_token': 'mock-membership-token'}
        with patch.dict(sys.modules, {'msal': SimpleNamespace(PublicClientApplication=factory)}):
            with self.assertRaisesRegex(RuntimeError, 'online-play access token'):
                sign_in_online(API_APP_ID)
