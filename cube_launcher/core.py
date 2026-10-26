from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import urllib.request
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from .cloud import DEFAULT_CLOUD

REPO = 'nuttyinc578/the-cube'
API = f'https://api.github.com/repos/{REPO}/releases?per_page=100'
LIMIT = 900 * 1024 * 1024


def redirected(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def atomic_json(path, value):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temp, path)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}', value):
        raise ValueError('Instance name: 1–48 letters, numbers, hyphens or underscores.')
    if value.upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))}:
        raise ValueError('Reserved Windows name.')
    return value


class TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.hostname not in {'github.com', 'api.github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}:
            raise ValueError('Unexpected download redirect; cancelled.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def request(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'api.github.com', 'github.com'}:
        raise ValueError('Only official HTTPS GitHub downloads are supported.')
    return urllib.request.build_opener(TrustedRedirect()).open(
        urllib.request.Request(url, headers={'User-Agent': 'Cube-Beta-Launcher/1.0', 'Accept': 'application/vnd.github+json'}), timeout=40)


def catalog_payload(payload):
    if not isinstance(payload, list):
        raise ValueError('Invalid release catalog.')
    result = []
    for release in payload:
        if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
            continue
        tag = release.get('tag_name', '')
        if not isinstance(tag, str) or not re.fullmatch(r'v?\d+(?:\.\d+){0,3}', tag):
            continue
        for asset in release.get('assets', []):
            name, url, digest = asset.get('name', ''), asset.get('browser_download_url', ''), asset.get('digest', '')
            if not isinstance(name, str) or '/' in name or '\\' in name:
                continue
            portable = name.lower().endswith('.zip') and 'portable' in name.lower()
            standalone = name.lower().endswith('.exe') and not any(s in name.lower() for s in ('setup', 'install', 'flasher', 'launcher'))
            if not (portable or standalone) or not isinstance(url, str) or not url.startswith(f'https://github.com/{REPO}/releases/download/{tag}/'):
                continue
            if not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
                continue
            size = asset.get('size', 0)
            if not isinstance(size, int) or not 0 < size <= LIMIT:
                continue
            result.append({'version': tag, 'name': name, 'url': url, 'sha256': digest[7:], 'size': size, 'kind': 'zip' if portable else 'exe'})
            break
    return sorted(result, key=lambda a: tuple(int(v) for v in a['version'].lstrip('v').split('.')), reverse=True)


def update_guard(game):
    """Strict policy, independent of game scripts and update-bypass profiles."""
    path = game / 'cpeloader_state.json'
    if not path.exists():
        if any((game / name).exists() for name in ('cpeloader.py', 'cpeloader_core_runtime.js', 'cpeloader_core.rb')):
            raise PermissionError('CPELoader state is missing. Start the game or repair with the official installer.')
        return  # Historical editions have no CPELoader.
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError()
        state = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or type(state.get('unlocked')) is not bool or not isinstance(state.get('components'), dict):
            raise ValueError()
        components = state['components']
        if any(type(v) is not bool for v in components.values()):
            raise ValueError()
    except (OSError, ValueError, TypeError):
        raise PermissionError('Unreadable CPELoader state. Update blocked; use the official installer.') from None
    if state['unlocked'] or any(components.values()):
        raise PermissionError('CPELoader is unlocked or partially unlocked. Launcher updates are blocked. Use the official installer.')


def unpack(archive, destination):
    """Validate the entire ZIP before extracting any game files."""
    seen, total = set(), 0
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > 20000:
            raise ValueError('Too many package files.')
        for entry in entries:
            name = entry.filename.rstrip('/')
            parts = name.split('/')
            if not name or '\\' in name or any(p in ('', '.', '..') or ':' in p or p.endswith(('.', ' ')) for p in parts):
                raise ValueError('Invalid portable package filename.')
            for p in parts:
                base = p.split('.')[0].upper()
                if base in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))}:
                    raise ValueError('Reserved package filename.')
            key = name.casefold()
            if key in seen or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                raise ValueError('Unsupported portable package entry.')
            seen.add(key)
            total += entry.file_size
            if total > 2 * LIMIT:
                raise ValueError('Expanded portable package too large.')
        bundle.extractall(destination)


def alive(pid):
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
        kernel.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # Access denied is conservatively running.
        try:
            code = ctypes.c_ulong()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class Launcher:
    def __init__(self, root=None):
        self.root = Path(root or Path(os.getenv('LOCALAPPDATA', Path.home())) / 'Nuttyinc' / 'CubeLauncher').resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ('instances', 'downloads', 'staging', 'backups'):
            folder = self.root / name
            folder.mkdir(exist_ok=True)
            if redirected(folder) or folder.resolve().parent != self.root:
                raise ValueError('Launcher storage folder is redirected.')
        self.settings_path = self.root / 'settings.json'

    @contextlib.contextmanager
    def lock(self):
        path = self.root / 'operation.lock'
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise RuntimeError('Another launcher operation is active. If it crashed, close all launchers before removing operation.lock.') from None
        try:
            os.close(fd)
            yield
        finally:
            path.unlink()

    def settings(self):
        if not self.settings_path.exists():
            return dict(DEFAULT_CLOUD)
        value = json.loads(self.settings_path.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('Invalid launcher settings.')
        if not value.get('cognito_domain') and not value.get('cognito_client_id'):
            value.update(DEFAULT_CLOUD)
        return value

    def releases(self):
        with request(API) as response:
            data = response.read(4_000_001)
        if len(data) > 4_000_000:
            raise ValueError('Release catalog too large.')
        result = catalog_payload(json.loads(data))
        if not result:
            raise ValueError('No verified portable releases available.')
        atomic_json(self.root / 'catalog.json', result)
        return result

    def cached(self):
        path = self.root / 'catalog.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []

    def instance(self, name):
        base = self.root / 'instances' / identifier(name)
        if redirected(base) or (base.exists() and base.resolve().parent != (self.root/'instances').resolve()):
            raise ValueError('Instance folder is redirected. Refusing operation.')
        if base.exists() and ((base/'game').exists() and (redirected(base/'game') or (base/'game').resolve().parent != base.resolve())):
            raise ValueError('Game folder is redirected. Refusing operation.')
        return base

    def instances(self):
        return sorted(p.name for p in (self.root/'instances').iterdir() if p.is_dir() and (p/'instance.json').is_file())

    def info(self, name):
        return json.loads((self.instance(name)/'instance.json').read_text(encoding='utf-8'))

    def download(self, release, progress=lambda message: None):
        target = self.root/'downloads'/(release['sha256'] + '.' + release['kind'])
        def valid():
            if not target.exists() or redirected(target):
                return False
            with target.open('rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest() == release['sha256']
        if valid():
            return target
        partial = target.with_suffix('.' + uuid.uuid4().hex + '.part')
        digest, count = hashlib.sha256(), 0
        try:
            with request(release['url']) as response, partial.open('xb') as output:
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > LIMIT or count > release['size']:
                        raise ValueError('Download exceeds expected size.')
                    output.write(chunk)
                    digest.update(chunk)
                    progress(f"Downloading {release['version']}: {count * 100 // release['size']}%")
            if count != release['size'] or digest.hexdigest() != release['sha256']:
                raise ValueError('Download verification failed. Nothing installed.')
            os.replace(partial, target)
            return target
        finally:
            partial.unlink(missing_ok=True)

    def ensure_stopped(self, base):
        info = json.loads((base/'instance.json').read_text(encoding='utf-8'))
        pid = info.get('pid')
        if pid and alive(pid):
            raise PermissionError('Close this game instance before updating or playing again.')
        return info

    def install(self, name, release, update=False, progress=lambda message: None):
        with self.lock():
            base = self.instance(name)
            if base.exists():
                if not update:
                    raise ValueError('Instance already exists. Choose Update or a new name.')
                self.ensure_stopped(base)
                update_guard(base/'game')
            elif update:
                raise ValueError('Install this instance first using Download.')
            archive = self.download(release, progress)
            stage = self.root/'staging'/uuid.uuid4().hex
            game = stage/'game'
            game.mkdir(parents=True)
            if release['kind'] == 'zip':
                unpack(archive, game)
                children = list(game.iterdir())
                if len(children) == 1 and children[0].is_dir():
                    wrapper = children[0]
                    moved = stage/'flattened'
                    wrapper.rename(moved)
                    game.rmdir()
                    moved.rename(game)
            else:
                shutil.copy2(archive, game/release['name'])
            executables = [p for p in game.glob('*.exe') if not any(t in p.name.lower() for t in ('setup', 'unins', 'flasher', 'launcher'))]
            if len(executables) != 1:
                raise ValueError('Package must contain exactly one top-level game EXE. Staging retained for inspection.')
            components = ('cpeloader.py', 'cpeloader_core_runtime.js', 'cpeloader_core.rb')
            # Official fresh ZIPs omit mutable state. Initialize ONLY in verified staging;
            # never reset or infer the lock state of an installed instance.
            if any((game/file).exists() for file in components) and not (game/'cpeloader_state.json').exists():
                atomic_json(game/'cpeloader_state.json', {'unlocked': False, 'components': {file: False for file in components}})
            atomic_json(stage/'instance.json', {'version': release['version'], 'exe': executables[0].name, 'asset_sha256': release['sha256'], 'pid': None})
            backup = None
            if base.exists():
                self.ensure_stopped(base)
                update_guard(base/'game')  # Recheck after download/staging.
                for save in ('settings.json', 'userdata'):
                    source, destination = base/'game'/save, game/save
                    if source.exists():
                        if redirected(source):
                            raise ValueError('Redirected userdata; update cancelled.')
                        if destination.exists() and source.is_dir() != destination.is_dir():
                            raise ValueError('Userdata file/directory conflict; update cancelled.')
                        if source.is_dir():
                            if any(redirected(p) for p in source.rglob('*')):
                                raise ValueError('Redirected userdata; update cancelled.')
                            shutil.copytree(source, destination, dirs_exist_ok=True)
                        else:
                            shutil.copy2(source, destination)
                backup = self.root/'backups'/(name + '-' + uuid.uuid4().hex)
                base.rename(backup)
            try:
                stage.rename(base)
            except OSError:
                if backup:
                    backup.rename(base)
                raise
            progress(f"Installed {release['version']} in {name}." + (f' Backup: {backup.name}' if backup else ''))
            return base

    def play(self, name):
        with self.lock():
            base = self.instance(name)
            info = self.ensure_stopped(base)
            exe = info.get('exe', '')
            if not isinstance(exe, str) or Path(exe).name != exe or not exe.lower().endswith('.exe'):
                raise ValueError('Invalid game executable.')
            game = base/'game'
            path = game/exe
            if not path.is_file() or redirected(path) or path.resolve().parent != game.resolve():
                raise ValueError('Game executable missing or redirected.')
            process = subprocess.Popen([str(path)], cwd=game, shell=False)
            info['pid'] = process.pid
            atomic_json(base/'instance.json', info)
            return process.pid
