"""Package the actual Halloween base game without adding CPE Flasher."""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cpeloader import snapshot, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', default='build/halloween-gamelift-game')
    args = parser.parse_args()
    folder = (ROOT/args.build_dir).resolve()
    if ROOT not in folder.parents or not (folder/'The Cube Beta Halloween Update.exe').is_file():
        raise ValueError('A compiled base game in a repository build subdirectory is required.')
    for name in ('cpeloader.py', 'cpeloader_core_runtime.js', 'cpeloader_core.rb', 'LICENCE.txt',
                 'THIRD_PARTY_NOTICES.txt', 'GAMELIFT_SETUP.md', 'cpe-backend.json'):
        shutil.copy2(ROOT/name, folder/name)
    for name in ('addons', 'themes', 'cpe', 'cpe_rephysics'):
        source = ROOT/name
        if source.exists():
            shutil.copytree(source, folder/name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc',
                '.git', 'node_modules', 'bin', 'obj', 'out', 'tests', 'test', 'inbox', 'publish-work',
                '.env', '.env.*', '.aws', 'credentials', '.theme_state.json', '.cpe_channel.json', '*account*state*', '*connection*state*'))
    # No local unlock state, cloud credentials, flasher binary or userdata copied.
    write_json(folder/'cpeloader_state.json', {'unlocked': False, 'components': {
        'cpeloader.py': False, 'cpeloader_core_runtime.js': False, 'cpeloader_core.rb': False}})
    write_json(folder/'cpeloader_manifest.json', {'files': snapshot(folder)})
    archive = folder.parent/'Cube-Beta-Halloween-GameLift-Prepared-Portable.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                output.write(path, path.relative_to(folder).as_posix())
    print(archive)


if __name__ == '__main__':
    main()
