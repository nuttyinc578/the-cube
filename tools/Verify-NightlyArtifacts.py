"""Verify the exact downloadable ZIP, checksums and locked portable payload."""
from pathlib import Path
import hashlib
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cpeloader import CPELoader, COMPONENTS
from cube_launcher.core import unpack


def main():
    folder = ROOT/'build'/'nightly-download'
    expected = {'The-Cube-Beta-6.4.2-nightly-Setup.exe',
                'The-Cube-Beta-Halloween-6.4.2-nightly-Portable.zip'}
    found = set()
    for line in (folder/'SHA256SUMS.txt').read_text(encoding='ascii').splitlines():
        digest, name = line.split('  ', 1)
        assert name in expected and name not in found
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest() == digest
        found.add(name)
    assert found == expected
    with tempfile.TemporaryDirectory(prefix='nightly-portable-qa-', dir=ROOT/'build') as temporary:
        extracted = Path(temporary)
        unpack(folder/'The-Cube-Beta-Halloween-6.4.2-nightly-Portable.zip', extracted)
        assert (extracted/'The Cube Beta Nightly.exe').is_file()
        assert (extracted/'third-party-licenses'/'pygame-ce'/'LGPL.txt').is_file() or list((extracted/'third-party-licenses'/'pygame-ce').rglob('LGPL.txt'))
        loader = CPELoader(extracted)
        assert not loader.unlocked and all(loader.state()['components'].get(n) is False for n in COMPONENTS)
        assert loader.changes() == [], 'Portable payload differs from its original manifest'
        assert not any((extracted/name).exists() for name in ('userdata', 'gamelift.json', 'cpe-flash-profile.json'))
    print('Final downloads verified: both SHA-256 hashes, extracted ZIP, LGPL text, locked loader and full integrity manifest.')


if __name__ == '__main__':
    main()
