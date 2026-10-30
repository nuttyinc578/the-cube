"""Exercise consent, collision refusal and uninstall in a fresh build-only folder."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import winreg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cpeloader import CPELoader
from release_info import EXE_NAME, SETUP_NAME, INSTALLER_ID

REGISTRY = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{'+INSTALLER_ID+'}_is1'


def registered():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY):
            return True
    except FileNotFoundError:
        return False


def main():
    if registered():
        raise RuntimeError('An existing nightly installation is registered. Refusing to alter it for QA.')
    folder = Path(tempfile.mkdtemp(prefix='nightly-installer-qa-', dir=ROOT/'build')).resolve()
    if not folder.is_relative_to((ROOT/'build').resolve()):
        raise RuntimeError('A repository build-only folder is required.')
    installer = ROOT/'build'/'nightly-download'/SETUP_NAME
    def setup(destination, accept=False):
        args = [str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
                '/NOICONS', '/TASKS=', f'/DIR={destination}', f'/LOG={folder/(destination.name+".log")}']
        if accept:
            args.append('/ACCEPTMIT=yes')
        return subprocess.run(args, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW).returncode
    declined = folder/'declined'
    assert setup(declined) != 0 and not declined.exists(), 'MIT consent was not enforced'
    occupied = folder/'occupied'
    occupied.mkdir()
    (occupied/'keep.txt').write_text('original game backup', encoding='utf-8')
    assert setup(occupied, True) != 0, 'The installer accepted a nonempty game folder'
    assert (occupied/'keep.txt').read_text(encoding='utf-8') == 'original game backup'
    assert len(list(occupied.iterdir())) == 1, 'An existing folder was changed'
    installed = folder/'installed'
    try:
        assert setup(installed, True) == 0, 'Nightly installer failed'
        assert (installed/'LICENCE.txt').read_bytes() == (ROOT/'LICENCE.txt').read_bytes()
        assert not CPELoader(installed).unlocked
        assert CPELoader(installed).changes() == [], 'Installed payload hashes differ'
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        report = folder/'smoke'/'report.json'
        subprocess.run([str(installed/EXE_NAME), '--nightly-self-test', str(report)],
                       env=env, timeout=180, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        data = json.loads(report.read_text(encoding='utf-8'))
        assert data['python'] == '3.15.2' and data['instance_menu_binding_ok'] and data['physics_ok']
        assert CPELoader(installed).changes() == []
    finally:
        uninstaller = installed/'unins000.exe'
        if uninstaller.is_file():
            subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                           timeout=180, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    assert not registered(), 'The QA uninstall registration remains'
    print('Nightly installer passed: MIT consent, overwrite refusal, locked payload, frozen game and uninstall.')


if __name__ == '__main__':
    main()
