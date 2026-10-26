"""GameLift client transport. No AWS credentials or SDK on players' machines."""
from __future__ import annotations
import json
import re
import socket
import ssl
import urllib.request
from urllib.parse import urlsplit
from cube_core import NetworkPeer


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Multiplayer backend redirects are not allowed.')


def reserve(endpoint, access_token):
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Configure an HTTPS multiplayer backend URL in gamelift.json.')
    request = urllib.request.Request(endpoint.rstrip('/')+'/sessions/reserve', data=b'{}',
        headers={'Authorization': 'Bearer '+access_token, 'Content-Type': 'application/json'}, method='POST')
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
        payload = response.read(16385)
    if len(payload) > 16384:
        raise ValueError('Multiplayer reservation response too large.')
    return validate_reservation(json.loads(payload))


def validate_reservation(value):
    if not isinstance(value, dict) or value.get('protocol') != 'cube-json-tls-v1':
        raise ValueError('This server does not support the Cube multiplayer protocol.')
    host, port, session = value.get('dns_name'), value.get('port'), value.get('player_session_id')
    if not isinstance(host, str) or not re.fullmatch(r'[a-zA-Z0-9.-]{1,253}', host):
        raise ValueError('A TLS game-server DNS name is required.')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid multiplayer server port.')
    if not isinstance(session, str) or not re.fullmatch(r'psess-[A-Za-z0-9-]{1,128}', session):
        raise ValueError('Invalid GameLift player reservation.')
    return {'dns_name': host, 'port': port, 'player_session_id': session, 'protocol': value['protocol']}


class GameLiftPeer(NetworkPeer):
    def __init__(self, reservation):
        self.reservation = validate_reservation(reservation)
        super().__init__('client', self.reservation['dns_name'], self.reservation['port'])

    def _connect_client(self):
        raw = socket.create_connection((self.host, self.port), timeout=8)
        try:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            connection = context.wrap_socket(raw, server_hostname=self.host)
            connection.sendall((json.dumps({'type': 'join', 'protocol': 'cube-json-tls-v1',
                'player_session_id': self.reservation['player_session_id']})+'\n').encode())
            return connection
        except Exception:
            raw.close()
            raise
