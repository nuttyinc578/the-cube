import unittest
import time
import ssl
from unittest.mock import Mock, patch
from gamelift_client import GameLiftPeer, validate_reservation
from cube_core import NetworkPeer
from multiplayer_backend.gamelift_reservations import Reservations


class GameLiftTests(unittest.TestCase):
    def reservation(self):
        return {'protocol': 'cube-json-tls-v1', 'dns_name': 'test.example.com', 'port': 27100,
            'player_session_id': 'psess-12345678'}

    def test_peer_uses_server_reservation(self):
        peer = GameLiftPeer(self.reservation())
        self.assertEqual((peer.host, peer.port, peer.role), ('test.example.com', 27100, 'client'))
        self.assertFalse(peer.connected)
        peer.close()

    def test_roundtrip_reservation(self):
        value = self.reservation()
        self.assertEqual(validate_reservation(value), value)

    def test_client_requires_tls12_and_preserves_hostname_verification(self):
        peer = GameLiftPeer(self.reservation())
        self.addCleanup(peer.close)
        raw, context = Mock(), Mock()
        with patch('gamelift_client.socket.create_connection', return_value=raw), \
                patch('gamelift_client.ssl.create_default_context', return_value=context):
            connection = peer._connect_client()
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        context.wrap_socket.assert_called_once_with(raw, server_hostname='test.example.com')
        self.assertIs(connection, context.wrap_socket.return_value)
        connection.sendall.assert_called_once()

    def test_lan_snapshot_still_roundtrips(self):
        host = NetworkPeer('host', port=0)
        self.addCleanup(host.close)
        host.start()
        deadline = time.monotonic()+5
        while not host._server or host._server.getsockname()[1] == 0:
            if time.monotonic() > deadline:
                self.fail('LAN listener did not start')
            time.sleep(.01)
        guest = NetworkPeer('client', '127.0.0.1', host._server.getsockname()[1])
        self.addCleanup(guest.close)
        guest.start()
        while not (guest.connected and host.connected):
            if time.monotonic() > deadline:
                self.fail('LAN peers did not connect')
            time.sleep(.01)
        host.send({'type': 'snapshot', 'entities': []})
        messages = []
        while not messages and time.monotonic() < deadline:
            messages = guest.messages()
            time.sleep(.01)
        self.assertEqual(messages, [{'type': 'snapshot', 'entities': []}])

    def test_backend_reserves_authenticated_identity(self):
        client = Mock()
        client.search_game_sessions.return_value = {'GameSessions': [{'GameSessionId': 'test-session'}]}
        client.create_player_session.return_value = {'PlayerSession': {'DnsName': 'test.example.com',
            'Port': 27100, 'PlayerSessionId': 'psess-12345678'}}
        result = Reservations(client, 'fleet-test').reserve_verified_player('test-player')
        self.assertEqual(result, self.reservation())
        player = client.create_player_session.call_args.kwargs['PlayerId']
        self.assertEqual(len(player), 64)
        self.assertNotEqual(player, 'test-player')

    def test_no_games_returns_no_reservation(self):
        client = Mock()
        client.search_game_sessions.return_value = {'GameSessions': []}
        with self.assertRaises(RuntimeError):
            Reservations(client, 'fleet-test').reserve_verified_player('test-player')
        client.create_player_session.assert_not_called()

    def test_base_game_includes_cloud_menu_and_halloween(self):
        import the_cube_beta_summer as game
        self.assertTrue(game.GameApp._halloween_update_installed)
        self.assertIn('gamelift_ui', game.GameApp.multiplayer_menu.__code__.co_names)


if __name__ == '__main__':
    unittest.main()
