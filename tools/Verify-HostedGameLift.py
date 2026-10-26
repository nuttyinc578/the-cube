"""Two ordinary operator-reserved players; never prints reservation credentials."""
import argparse
import json
from pathlib import Path
import runpy
import socket
import ssl
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', default='build/gamelift-test-deployment')
    args = parser.parse_args()
    state_folder = (ROOT/args.state_dir).resolve()
    if ROOT/'build' not in state_folder.parents:
        raise ValueError('Deployment state must be under the repository build directory.')
    state = json.loads((state_folder/'resources.json').read_text(encoding='utf-8'))
    if state.get('status') != 'hosting' or time.time() >= float(state['deadline_epoch']):
        raise RuntimeError('An active, unexpired deployment is required.')
    aws = runpy.run_path(str(ROOT/'tools'/'Deploy-GameLiftTest.py'))['aws']
    for _ in range(30):
        session = aws('gamelift', 'describe-game-sessions', GameSessionId=state['game_session_id'])['GameSessions'][0]
        if session['Status'] == 'ACTIVE':
            break
        time.sleep(2)
    else:
        raise RuntimeError('Game session did not activate.')
    # One API round trip keeps both reservations within AWS's 60-second join window.
    reservations = aws('gamelift', 'create-player-sessions',
        GameSessionId=state['game_session_id'],
        PlayerIds=['cube-qa-'+uuid.uuid4().hex for _ in range(2)])['PlayerSessions']
    if len(reservations) != 2:
        raise RuntimeError('AWS did not reserve both test players.')
    clients, readers = [], []
    try:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        for reservation in reservations:
            hostname = reservation['DnsName']
            raw = socket.create_connection((hostname, reservation['Port']), timeout=15)
            client = context.wrap_socket(raw, server_hostname=hostname)
            client.settimeout(15)
            clients.append(client)
            client.sendall((json.dumps({'type': 'join', 'protocol': 'cube-json-tls-v1',
                'player_session_id': reservation['PlayerSessionId']})+'\n').encode())
            readers.append(client.makefile('rb'))
        clients[0].sendall(b'{"type":"action","data":{"action":"spawn","x":250,"y":120}}\n')
        snapshots = []
        for reader in readers:
            for _ in range(100):
                line = reader.readline(1024*1024)
                if not line:
                    raise RuntimeError('Hosted server closed the player connection.')
                snapshot = json.loads(line)
                if snapshot.get('entities'):
                    snapshots.append(snapshot)
                    break
        if len(snapshots) != 2 or snapshots[0]['entities'][0]['id'] != snapshots[1]['entities'][0]['id']:
            raise RuntimeError('Players did not receive the same authoritative world.')
        request = urllib.request.Request(state['backend_url']+'/sessions/reserve', data=b'{}',
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=15):
                raise RuntimeError('Reservation API unexpectedly allowed an unsigned request.')
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise RuntimeError('Unexpected reservation API status: '+str(error.code)) from None
        proof = {'two_public_tls_players': True, 'unsigned_api_status': 401,
            'fleet_id': state['fleet_id'], 'backend_url': state['backend_url'],
            'verified_at_epoch': time.time(), 'cognito_browser_login_verified': False}
        (state_folder/'hosted-verification.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
        print('PASS: two public TLS players shared authoritative CPE physics; reservation API requires sign-in.')
    finally:
        for reader in readers:
            reader.close()
        for client in clients:
            client.close()


if __name__ == '__main__':
    main()
