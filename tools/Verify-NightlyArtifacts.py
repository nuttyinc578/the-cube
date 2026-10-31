"""Verify the exact downloadable ZIP, checksums and locked portable payload."""
from pathlib import Path
import hashlib
import tempfile
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from release_info import EXE_NAME, SETUP_NAME, PORTABLE_NAME
from cpeloader import CPELoader, COMPONENTS
from cube_launcher.core import unpack


def main():
    folder = ROOT/'build'/'nightly-download'
    expected = {SETUP_NAME, PORTABLE_NAME}
    found = set()
    for line in (folder/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        digest, name = line.split('  ', 1)
        assert name in expected and name not in found
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == digest
        found.add(name)
    assert found == expected
    with tempfile.TemporaryDirectory(prefix='nightly-portable-qa-', dir=ROOT/'build') as temporary:
        extracted = Path(temporary)
        unpack(folder/PORTABLE_NAME, extracted)
        assert (extracted/EXE_NAME).is_file()
        assert (extracted/'cpe.exe').is_file()
        assert (extracted/'Open CPE Command Prompt.cmd').is_file()
        assert (extracted/'third-party-licenses'/'pygame-ce'/'LGPL.txt').is_file() or list((extracted/'third-party-licenses'/'pygame-ce').rglob('LGPL.txt'))
        loader = CPELoader(extracted)
        assert not loader.unlocked and all(loader.state()['components'].get(n) is False for n in COMPONENTS)
        assert loader.changes() == [], 'Portable payload differs from its original manifest'
        assert not any((extracted/name).exists() for name in ('userdata', 'gamelift.json', 'cpe-flash-profile.json'))
        manifest = (extracted/'cpeloader_manifest.json').read_bytes()
        state = (extracted/'cpeloader_state.json').read_bytes()
        # Only damage the disposable extracted QA copy, never an installed game.
        (extracted/'cpeloader.py').unlink()
        (extracted/EXE_NAME).write_bytes(b'QA damaged game image')
        missing = subprocess.run([str(extracted/'cpe.exe'), '--cpeloader', '-connect', str(extracted)],
                                 capture_output=True, text=True, timeout=180)
        assert missing.returncode == 1 and 'CPELOADER_MISSING: cpeloader.py' in missing.stderr
        # No -connect: prove the executable chooses its own game folder, not cwd.
        restored = subprocess.run([str(extracted/'cpe.exe'), '--cpeloader', '-cpe/repair',
                                   '-cpeloader/repair', '--no-gui', '--yes'], cwd=ROOT,
                                  capture_output=True, text=True, timeout=180)
        assert restored.returncode == 0, restored.stdout+'\n'+restored.stderr
        assert (extracted/'cpeloader_manifest.json').read_bytes() == manifest
        assert (extracted/'cpeloader_state.json').read_bytes() == state
        assert loader.changes() == [], 'Recovery image did not restore the exact original bytes'
        backups = list((extracted/'backup'/'cpe-cli').glob('*/original/'+EXE_NAME))
        assert len(backups) == 1 and backups[0].read_bytes() == b'QA damaged game image'
        version = subprocess.run([str(extracted/'cpe.exe'), '--cpeloader', '--v'],
                                 capture_output=True, text=True, check=True, timeout=180)
        assert version.stdout.strip() == 'CPELoader v2'
        print('Packaged recovery passed: missing-loader error, embedded image, game restoration, backup and unchanged lock state.')
    print('Final downloads verified: both SHA-256 hashes, extracted ZIP, LGPL text, locked loader and full integrity manifest.')


if __name__ == '__main__':
    main()
