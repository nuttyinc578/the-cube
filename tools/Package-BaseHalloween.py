"""Package the actual Halloween base game without adding CPE Flasher."""
import argparse
import re
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
    parser.add_argument('--version', help='Optional release version for the portable filename')
    parser.add_argument('--exe-name', default='The Cube Beta Halloween Update.exe')
    args = parser.parse_args()
    if args.version and not re.fullmatch(r'\d+\.\d+\.\d+(-nightly)?', args.version):
        raise ValueError('Release version must have three numeric components.')
    folder = (ROOT/args.build_dir).resolve()
    if Path(args.exe_name).name != args.exe_name or ROOT not in folder.parents or not (folder/args.exe_name).is_file():
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
    # This preserved optional add-on runtime is a distributable asset, not a
    # generated __pycache__ file. Modern Python uses its readable compatibility API.
    legacy_runtime = ROOT/'addons'/'nuttymod'/'nuttymod_runtime_v122.pyc'
    if legacy_runtime.is_file():
        shutil.copy2(legacy_runtime, folder/'addons'/'nuttymod'/legacy_runtime.name)
    # No local unlock state, cloud credentials, flasher binary or userdata copied.
    write_json(folder/'cpeloader_state.json', {'unlocked': False, 'components': {
        'cpeloader.py': False, 'cpeloader_core_runtime.js': False, 'cpeloader_core.rb': False}})
    write_json(folder/'cpeloader_manifest.json', {'files': snapshot(folder)})
    archive = folder.parent/(f'The-Cube-Beta-Halloween-{args.version}-Portable.zip' if args.version
        else 'Cube-Beta-Halloween-GameLift-Prepared-Portable.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                output.write(path, path.relative_to(folder).as_posix())
    print(archive)


if __name__ == '__main__':
    main()
