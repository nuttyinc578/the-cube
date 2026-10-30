"""Build a separate tested Windows nightly, never an installed game folder."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-tests', action='store_true', help='Use only after the same sources passed tests')
    parser.add_argument('--skip-installer', action='store_true')
    args = parser.parse_args()
    if sys.version_info[:3] != (3, 15, 2):
        raise RuntimeError('This nightly requires Python 3.15.2. Create a dedicated venv and install requirements-nightly.txt.')
    for name, version in (('pygame-ce', '2.5.8'), ('pymunk', '7.3.1'), ('pyinstaller', '6.22.3')):
        if importlib.metadata.version(name) != version:
            raise RuntimeError(f'Install the pinned nightly dependency: {name}=={version}')
    os.environ.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PYGAME_HIDE_SUPPORT_PROMPT='1')
    folder = ROOT/'build'/'nightly-game'
    if folder.exists():
        raise RuntimeError('build/nightly-game already exists. Preserve it or choose a clean checkout before rebuilding.')
    if not args.skip_tests:
        run(sys.executable, '-m', 'unittest', 'test_nightly', 'test_cpeloader', 'test_halloween_music',
            'test_og_recovery', 'test_nuttymod_isolation', 'test_error_update', 'test_summer_game',
            'test_theme_system', 'test_legacy_versions', 'test_cube_launcher', 'test_gamelift',
            'test_dedicated_server', 'cpe.tests.test_cpe', '-v')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', folder,
        '--workpath', ROOT/'build'/'nightly-pyinstaller', ROOT/'nightly_build.spec')
    shutil.copy2(ROOT/'NIGHTLY_6.4.2.md', folder/'NIGHTLY_6.4.2.md')
    licences = folder/'third-party-licenses'
    licences.mkdir()
    for name in ('pygame-ce', 'pymunk', 'pyinstaller'):
        dist = importlib.metadata.distribution(name)
        for item in dist.files or []:
            if 'license' in item.name.lower() or item.name.lower().startswith(('copying', 'lgpl', 'gpl')):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    destination = licences/name/Path(str(item))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    for name in ('LICENSE.txt', 'LICENSE'):
        source = Path(sys.base_prefix)/name
        if source.is_file():
            shutil.copy2(source, licences/'Python-LICENSE.txt')
            break
    # Smoke testing only renders to an explicit build QA folder, never userdata.
    run(folder/'The Cube Beta Nightly.exe', '--nightly-self-test', ROOT/'build'/'nightly-qa'/'report.json', timeout=120)
    report = json.loads((ROOT/'build'/'nightly-qa'/'report.json').read_text(encoding='utf-8'))
    if report['python'] != '3.15.2' or report['version'] != '6.4.2-nightly' or not report['physics_ok']:
        raise RuntimeError('Frozen nightly smoke test did not pass.')
    run(sys.executable, ROOT/'tools'/'Package-BaseHalloween.py', '--build-dir', 'build/nightly-game',
        '--version', '6.4.2-nightly', '--exe-name', 'The Cube Beta Nightly.exe')
    sys.path.insert(0, str(ROOT))
    from cpeloader import CPELoader
    if CPELoader(folder).changes():
        raise RuntimeError('Packaged integrity manifest does not match the nightly.')
    output = ROOT/'build'/'nightly-download'
    output.mkdir(exist_ok=True)
    portable = ROOT/'build'/'The-Cube-Beta-Halloween-6.4.2-nightly-Portable.zip'
    shutil.copy2(portable, output/portable.name)
    shutil.copy2(ROOT/'NIGHTLY_6.4.2.md', output/'NIGHTLY_6.4.2.md')
    if not args.skip_installer:
        candidates = [Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)'))/'Inno Setup 6'/'ISCC.exe',
                      Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Inno Setup 6'/'ISCC.exe']
        compiler = next((p for p in candidates if p.is_file()), None)
        if compiler is None:
            raise RuntimeError('Install Inno Setup 6 to build the nightly installer, or use --skip-installer.')
        run(compiler, f'/DPayloadDir={folder}', f'/DOutputDir={output}', ROOT/'installer'/'TheCubeBetaNightly.iss')
    products = [p for p in output.iterdir() if p.suffix in {'.zip', '.exe'}]
    (output/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(products)), encoding='ascii')
    print(f'Tested nightly downloads: {output}', flush=True)


if __name__ == '__main__':
    main()
