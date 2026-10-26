"""Configure only the owned base-game build after hosted verification succeeds."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cpeloader import snapshot, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', default='build/gamelift-test-deployment')
    args = parser.parse_args()
    deployment = (ROOT/args.state_dir).resolve()
    if ROOT/'build' not in deployment.parents:
        raise ValueError('Deployment state must be under the repository build directory.')
    state = json.loads((deployment/'resources.json').read_text(encoding='utf-8'))
    proof = json.loads((deployment/'hosted-verification.json').read_text(encoding='utf-8'))
    if state.get('status') != 'hosting' or time.time() >= float(state['deadline_epoch']):
        raise RuntimeError('The hosted test must still be running.')
    if not proof.get('two_public_tls_players') or proof['fleet_id'] != state['fleet_id']:
        raise RuntimeError('This fleet must pass the public two-player check first.')
    folder = ROOT/'build'/'halloween-gamelift-game'
    if not (folder/'The Cube Beta Halloween Update.exe').is_file():
        raise RuntimeError('The compiled base game is missing; do not alter an installed game.')
    archive = ROOT/'build'/('Cube-Beta-Halloween-GameLift-Test-'+state['prefix'].removeprefix('CubeBetaTest-')+'.zip')
    if archive.exists():
        raise RuntimeError('This test archive already exists; inspect it instead of overwriting it.')
    write_json(folder/'gamelift.json', {'backend_url': state['backend_url'], 'test_expires_at': state['deadline']})
    shutil.copy2(ROOT/'GAMELIFT_SETUP.md', folder/'GAMELIFT_SETUP.md')
    (folder/'HOSTED_TEST.txt').write_text('Cube Beta Halloween: temporary GameLift test.\n'
        'Open Multiplayer > Amazon GameLift Online and sign in to Nuttyinc Cloud.\n'
        'The game server and reservation API are scheduled for deletion at '+state['deadline']+' UTC.\n'
        'LAN and single-player remain available after shutdown. Browser sign-in still needs user verification.\n', encoding='utf-8')
    write_json(folder/'cpeloader_manifest.json', {'files': snapshot(folder)})
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(folder).as_posix())
    print(archive)


if __name__ == '__main__':
    main()
