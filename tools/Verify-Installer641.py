"""Prepare the exact public payload and test installation only on a CI runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import runpy
import stat
import subprocess
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT/'build'/'installer-6.4.1-download'/'The-Cube-Beta-Halloween-6.4.1-Portable.zip'
PAYLOAD = ROOT/'build'/'installer-6.4.1-payload'
SETUP = ROOT/'build'/'installer-6.4.1-output'/'The-Cube-Beta-Halloween-Update-6.4.1-Setup.exe'
PORTABLE_SHA256 = 'f8ae9222b0e0daaa25a914ad50a7c78b399cc702bf1de4f5035c5a27513cf8c7'
GAME_EXE = 'The Cube Beta Halloween Update.exe'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    if digest(ARCHIVE) != PORTABLE_SHA256:
        raise RuntimeError('The public portable ZIP does not match release 6.4.1.')
    with zipfile.ZipFile(ARCHIVE) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or sum(entry.file_size for entry in entries) > 500*1024*1024:
            raise RuntimeError('Unexpected portable archive layout or size.')
        for entry in entries:
            name = entry.filename
            parts = PurePosixPath(name).parts
            if name.startswith('/') or '\\' in name or ':' in name or '..' in parts or stat.S_ISLNK(entry.external_attr >> 16):
                raise RuntimeError('Unsafe portable archive path.')
            if any(part in {'.aws', 'userdata', '.venv', 'cpe_flasher'} for part in parts):
                raise RuntimeError('Unexpected private or unrelated payload.')
        if 'CPE Flasher Tool.exe' in names or 'gamelift.json' in names:
            raise RuntimeError('Unexpected flasher or online endpoint.')
        manifest = json.loads(archive.read('cpeloader_manifest.json'))['files']
        for name, expected in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise RuntimeError('Portable manifest mismatch: '+name)
        if not archive.read('LICENCE.txt').startswith(b'MIT License'):
            raise RuntimeError('The MIT copyright licence is missing.')
        PAYLOAD.mkdir(parents=True, exist_ok=False)
        archive.extractall(PAYLOAD)
    print('Verified and staged the exact published 6.4.1 portable payload.')


def run_setup(destination, log, *, accept=True, group='The Cube Beta 6.4.1 CI'):
    command = [str(SETUP), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-', '/NORESTART',
               '/TASKS=!desktopicon', '/DIR='+str(destination), '/GROUP='+group, '/LOG='+str(log)]
    if accept:
        command.append('/ACCEPTMIT=yes')
    return subprocess.run(command, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW).returncode


def verify_install():
    # Never install or uninstall on the developer/player's computer.
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise RuntimeError('Installation checks may run only on the disposable Windows Actions runner.')
    runner_temp = Path(os.environ['RUNNER_TEMP']).resolve()
    work = Path(tempfile.mkdtemp(prefix='cube-installer-641-', dir=runner_temp)).resolve()
    if not work.is_relative_to(runner_temp):
        raise RuntimeError('The installation fixture must remain within runner temporary storage.')
    installed = work/'installed-game'
    refused = work/'licence-not-accepted'
    if run_setup(refused, work/'no-consent.log', accept=False) == 0 or (refused/GAME_EXE).exists():
        raise RuntimeError('Silent setup did not require explicit MIT acceptance.')
    occupied = work/'existing-player-folder'
    occupied.mkdir()
    sentinel = occupied/'player-save.txt'
    sentinel.write_text('Keep this player file.', encoding='utf-8')
    sentinel_digest = digest(sentinel)
    if run_setup(occupied, work/'occupied.log') == 0:
        raise RuntimeError('Setup overwrote a non-empty target.')
    if digest(sentinel) != sentinel_digest or sorted(path.name for path in occupied.iterdir()) != ['player-save.txt']:
        raise RuntimeError('Refused setup modified the player folder.')
    group = 'Cube Beta 6.4.1 CI '+work.name
    if run_setup(installed, work/'install.log', group=group) != 0:
        raise RuntimeError('Installation failed; see '+str(work/'install.log'))
    uninstall = installed/'unins000.exe'
    try:
        for path in PAYLOAD.rglob('*'):
            if path.is_file() and digest(installed/path.relative_to(PAYLOAD)) != digest(path):
                raise RuntimeError('Installed file differs from published portable: '+str(path))
        loader_module = runpy.run_path(str(installed/'cpeloader.py'), run_name='cube_installer_qa')
        loader = loader_module['CPELoader'](installed)
        if loader.changes() or loader.unlocked:
            raise RuntimeError('The installed game has an integrity warning or unlocked loader.')
        subprocess.run([str(installed/GAME_EXE), '--release-smoke-test'], cwd=installed,
                       timeout=120, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if loader.changes():
            raise RuntimeError('Smoke verification altered the installed game.')
        shortcut = Path(os.environ['APPDATA'])/'Microsoft'/'Windows'/'Start Menu'/'Programs'/group/'The Cube Beta 6.4.1.lnk'
        if not shortcut.is_file() or not uninstall.is_file():
            raise RuntimeError('Missing Start Menu shortcut or uninstaller.')
        user_file = installed/'backup'/'player-save.txt'
        user_file.parent.mkdir(exist_ok=True)
        user_file.write_text('Preserve this player-created backup.', encoding='utf-8')
        user_digest = digest(user_file)
    finally:
        if uninstall.is_file():
            subprocess.run([str(uninstall), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                           timeout=120, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(40):
        if not (installed/GAME_EXE).exists():
            break
        time.sleep(.25)
    if (installed/GAME_EXE).exists() or shortcut.exists() or digest(user_file) != user_digest:
        raise RuntimeError('Uninstall did not remove the game/shortcut or preserve the player backup.')
    print(json.dumps({'version': '6.4.1', 'published_payload_unchanged': True,
        'mit_consent_required': True, 'nonempty_folder_protected': True,
        'installed_game_smoke_passed': True, 'loader_integrity_passed': True,
        'shortcut_and_uninstall_passed': True, 'player_backup_preserved': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'test'))
    options = parser.parse_args()
    (prepare if options.mode == 'prepare' else verify_install)()
