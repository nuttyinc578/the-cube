import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from dedicated_server.worker import Simulation


class DedicatedTests(unittest.TestCase):
    def test_linux_system_packages_use_noninteractive_sudo(self):
        script = (Path(__file__).parent/'dedicated_server'/'install.sh').read_text(encoding='utf-8')
        self.assertIn('sudo -n dnf install -y', script)
        self.assertIn('sudo -n chmod +x /local/game/cube-server', script)

    def test_real_physics_shared_ownership(self):
        simulation = Simulation()
        simulation.action('guest-1', {'action': 'spawn', 'x': 200, 'y': 100})
        entity = next(iter(simulation.world.entities))
        simulation.action('guest-1', {'action': 'drag_start', 'id': entity, 'x': 200, 'y': 100})
        simulation.action('guest-2', {'action': 'drag_start', 'id': entity, 'x': 200, 'y': 100})
        self.assertIn('guest-1', simulation.world.dragging)
        self.assertNotIn('guest-2', simulation.world.dragging)
        for _ in range(5):
            simulation.step()
        snapshot = simulation.snapshot()
        self.assertEqual(snapshot['type'], 'snapshot')
        self.assertEqual(len(snapshot['entities']), 1)
        self.assertEqual(snapshot['entities'][0]['owner'], 'guest-1')
        simulation.action('guest-1', {'action': 'disconnect'})
        self.assertNotIn('guest-1', simulation.world.dragging)

    def load_handler(self, name):
        aws = Mock()
        config = Mock()
        with patch.dict(sys.modules, {'boto3': aws, 'botocore': Mock(), 'botocore.config': config}):
            path = Path(__file__).parent/'multiplayer_backend'/(name+'.py')
            spec = importlib.util.spec_from_file_location('test_module_'+name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module, aws.client.return_value

    def test_authenticated_reservation_uses_fixed_game(self):
        module, service = self.load_handler('session_api')
        service.describe_player_sessions.return_value = {'PlayerSessions': []}
        service.create_player_session.return_value = {'PlayerSession': {'DnsName': 'test.example.com', 'Port': 27100,
            'PlayerSessionId': 'psess-test'}}
        with patch.dict(os.environ, {'TEST_DEADLINE': '9999999999', 'COGNITO_CLIENT_ID': 'test-client', 'GAME_SESSION_ID': 'test-session'}):
            result = module.handler({'requestContext': {'authorizer': {'jwt': {'claims': {
                'token_use': 'access', 'client_id': 'test-client', 'sub': 'test-player'}}}}}, None)
        self.assertEqual(result['statusCode'], 200)
        self.assertNotIn('PlayerId', service.describe_player_sessions.call_args.kwargs)
        self.assertEqual(service.create_player_session.call_args.kwargs['GameSessionId'], 'test-session')
        self.assertEqual(len(service.create_player_session.call_args.kwargs['PlayerId']), 64)

    def test_shutdown_armed_does_not_delete_early(self):
        module, service = self.load_handler('test_shutdown')
        with patch.dict(os.environ, {'TEST_DEADLINE': '9999999999'}):
            self.assertEqual(module.handler({}, None), {'state': 'armed'})
        service.delete_fleet.assert_not_called()

    def test_shutdown_deletes_only_recorded_fleet(self):
        module, service = self.load_handler('test_shutdown')
        service.describe_fleet_attributes.return_value = {'FleetAttributes': [{'Name': 'Cube-test'}]}
        with patch.dict(os.environ, {'TEST_DEADLINE': '0', 'TEST_FLEET_ID': 'fleet-test', 'TEST_FLEET_NAME': 'Cube-test'}):
            self.assertEqual(module.handler({}, None)['state'], 'delete-requested')
        service.describe_fleet_attributes.assert_called_once_with(FleetIds=['fleet-test'])
        service.delete_fleet.assert_called_once_with(FleetId='fleet-test')

    def test_shutdown_recovers_unrecorded_test_resources(self):
        module, service = self.load_handler('test_shutdown')
        service.describe_fleet_attributes.return_value = {'FleetAttributes': [
            {'Name': 'Other-game', 'FleetId': 'fleet-other'},
            {'Name': 'Cube-test', 'FleetId': 'fleet-test'}]}
        api_page = {'Items': [
            {'Name': 'Other-api', 'ApiId': 'other'}, {'Name': 'Cube-test-Api', 'ApiId': 'test'}]}
        service.get_api.return_value = {'Name': 'Cube-test-Api'}
        # The ID write may be interrupted immediately after resource creation.
        fleet_page = service.describe_fleet_attributes.return_value
        service.get_paginator.return_value.paginate.side_effect = [[fleet_page], [api_page]]
        service.describe_fleet_attributes.return_value = {'FleetAttributes': [{'Name': 'Cube-test', 'FleetId': 'fleet-test'}]}
        with patch.dict(os.environ, {'TEST_DEADLINE': '0', 'TEST_FLEET_ID': '',
                'TEST_FLEET_NAME': 'Cube-test', 'TEST_API_ID': '', 'TEST_API_NAME': 'Cube-test-Api'}):
            self.assertEqual(module.handler({}, None)['state'], 'delete-requested')
        service.delete_fleet.assert_called_once_with(FleetId='fleet-test')
        service.delete_api.assert_called_once_with(ApiId='test')

    def test_shutdown_accepts_already_deleted_fleet(self):
        module, service = self.load_handler('test_shutdown')
        service.describe_fleet_attributes.return_value = {'FleetAttributes': []}
        with patch.dict(os.environ, {'TEST_DEADLINE': '0', 'TEST_FLEET_ID': 'fleet-test',
                'TEST_FLEET_NAME': 'Cube-test', 'TEST_API_ID': '', 'TEST_API_NAME': ''}):
            self.assertEqual(module.handler({}, None)['state'], 'deleted')
        service.delete_fleet.assert_not_called()


if __name__ == '__main__':
    unittest.main()
