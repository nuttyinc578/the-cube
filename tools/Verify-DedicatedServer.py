"""Two ordinary TLS players sharing real headless CPE physics, no AWS calls."""
import json
import hashlib
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT/'build'/'dedicated-tls-qa'
    folder.mkdir(parents=True, exist_ok=True)
    certificate, key = folder/'localhost.crt', folder/'localhost.key'
    openssl = shutil.which('openssl')
    if not openssl:
        git_openssl = Path('C:/Program Files/Git/usr/bin/openssl.exe')
        openssl = str(git_openssl) if git_openssl.is_file() else None
    if not openssl:
        raise RuntimeError('OpenSSL is required for the local TLS verification fixture.')
    binary = ROOT/'dedicated_server'/('cube-server.exe' if os.name == 'nt' else 'cube-server')
    subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
        '-keyout', str(key), '-out', str(certificate)], check=True, capture_output=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with (folder/'server.log').open('w', encoding='utf-8') as logfile:
        process = subprocess.Popen([str(binary), '--local', '--port', str(port),
            '--python', sys.executable, '--worker', str(ROOT/'dedicated_server'/'worker.py'), '--cert', str(certificate),
            '--key', str(key), '--log-file', str(folder/'startup.log')], cwd=ROOT, stdout=logfile, stderr=logfile,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        clients = []
        readers = []
        try:
            context = ssl.create_default_context(cafile=str(certificate))
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            deadline = time.monotonic()+60
            while True:
                try:
                    raw = socket.create_connection(('127.0.0.1', port), timeout=3)
                    clients.append(context.wrap_socket(raw, server_hostname='localhost'))
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('Dedicated host did not start; see build/dedicated-tls-qa/server.log')
                    time.sleep(.2)
            clients.append(context.wrap_socket(socket.create_connection(('127.0.0.1', port), timeout=5), server_hostname='localhost'))
            for index, client in enumerate(clients):
                client.settimeout(10)
                client.sendall((json.dumps({'type': 'join', 'protocol': 'cube-json-tls-v1',
                    'player_session_id': 'psess-local-'+str(index)})+'\n').encode())
                readers.append(client.makefile('rb'))
            clients[0].sendall(b'{"type":"action","data":{"action":"spawn","x":250,"y":120}}\n')
            snapshots = []
            for reader in readers:
                for _ in range(60):
                    snapshot = json.loads(reader.readline(1024*1024))
                    if snapshot.get('entities'):
                        snapshots.append(snapshot)
                        break
            assert len(snapshots) == 2, 'Both players must receive the shared world'
            assert snapshots[0]['entities'][0]['id'] == snapshots[1]['entities'][0]['id']
            assert str(snapshots[0]['entities'][0]['owner']).startswith('guest-')
            (folder/'success.json').write_text(json.dumps({'two_tls_players': True,
                'server_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}), encoding='utf-8')
            print('PASS: two certificate-verified TLS clients received authoritative CPE snapshots.')
        finally:
            for reader in readers:
                reader.close()
            for client in clients:
                client.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()
