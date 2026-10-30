"""Consent-driven official downloads; never patch a running game in place."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from cube_launcher.core import request, redirected, update_guard

REPO = 'nuttyinc578/the-cube'
API = f'https://api.github.com/repos/{REPO}/releases?per_page=100'
RELEASES_URL = f'https://github.com/{REPO}/releases'
NIGHTLY_URL = 'https://nightly.link/nuttyinc578/the-cube/workflows/build-nightly/main/The-Cube-Beta-6.4.3-nightly-Windows.zip'
LIMIT = 900 * 1024 * 1024


@dataclass(frozen=True)
class Update:
    version: str
    name: str
    url: str
    sha256: str
    size: int
    installer: bool


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(-nightly)?', value)
    if not match:
        raise ValueError('Unsupported release version.')
    return (*(int(match[i]) for i in (1, 2, 3)), 0 if match[4] else 1)


def parse_updates(payload, current):
    if not isinstance(payload, list):
        raise ValueError('Invalid GitHub release response.')
    found = []
    for release in payload:
        if not isinstance(release, dict) or release.get('draft'):
            continue
        tag = release.get('tag_name', '')
        try:
            if version_key(tag) <= version_key(current):
                continue
        except (ValueError, TypeError):
            continue
        assets = release.get('assets')
        if not isinstance(assets, list):
            continue
        candidates = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name, url, digest, size = (asset.get(k) for k in ('name', 'browser_download_url', 'digest', 'size'))
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._ -]{0,160}', name):
                continue
            lower = name.lower()
            installer = lower.endswith('-setup.exe') and lower.startswith('the-cube-beta-')
            portable = lower.endswith('-portable.zip') and lower.startswith('the-cube-beta-')
            if not (installer or portable) or url != f'https://github.com/{REPO}/releases/download/{tag}/{name}':
                continue
            if not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                continue
            if type(size) is not int or not 0 < size <= LIMIT:
                continue
            candidates.append(Update(tag, name, url, digest[7:], size, installer))
        if candidates:
            found.append(max(candidates, key=lambda a: a.installer))
    return sorted(found, key=lambda a: version_key(a.version), reverse=True)


class CubeUpdater:
    def __init__(self, root, current, opener=request):
        self.root = Path(root).resolve()
        self.current, self.opener = current, opener

    def require_update(self):
        update_guard(self.root)  # No unlocked-update bypass is honored by this updater.
        if (self.root/'cpeloader_manifest.json').exists():
            from cpeloader import CPELoader
            if CPELoader(self.root).changes():
                raise PermissionError('Modified game files: use the external installer in a new folder.')
        profile = self.root/'cpe-flash-profile.json'
        if profile.exists():
            try:
                data = json.loads(profile.read_text(encoding='utf-8'))
                if not isinstance(data, dict) or data.get('custom_portable'):
                    raise ValueError()
            except (OSError, ValueError):
                raise PermissionError('Custom or unreadable build profile: obtain updates from its owner.') from None

    def check(self):
        with self.opener(API) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('Release catalog too large.')
        return parse_updates(json.loads(raw), self.current)

    def download(self, update, progress=lambda message: None, cancelled=None):
        self.require_update()
        # Reject fabricated Update objects before requesting their URLs.
        record = {'tag_name': update.version, 'assets': [{'name': update.name, 'browser_download_url': update.url,
            'digest': 'sha256:'+update.sha256, 'size': update.size}]}
        if update not in parse_updates([record], self.current):
            raise ValueError('Invalid or outdated update.')
        folder = self.root/'userdata'/'updates'
        for path in (self.root/'userdata', folder):
            if redirected(path):
                raise ValueError('Redirected update directory; cancelled.')
            path.mkdir(exist_ok=True)
        destination = folder/(update.sha256[:16]+'-'+update.name)
        temporary = destination.with_suffix(destination.suffix+'.part')
        if redirected(destination) or redirected(temporary):
            raise ValueError('Redirected update file; cancelled.')
        received, digest = 0, hashlib.sha256()
        try:
            with self.opener(update.url) as source, temporary.open('wb') as output:
                while chunk := source.read(256 * 1024):
                    if cancelled is not None and cancelled.is_set():
                        raise InterruptedError('Download cancelled.')
                    received += len(chunk)
                    if received > update.size:
                        raise ValueError('Update exceeded its declared size.')
                    output.write(chunk)
                    digest.update(chunk)
                    progress(f'Downloading {received/1048576:.1f} / {update.size/1048576:.1f} MB')
            if received != update.size or digest.hexdigest() != update.sha256:
                raise ValueError('Checksum or size mismatch. Update was not installed.')
            self.require_update()  # Recheck loader state after network activity.
            os.replace(temporary, destination)
            return destination
        finally:
            temporary.unlink(missing_ok=True)

    def launch_installer(self, update, path):
        self.require_update()
        expected = self.root/'userdata'/'updates'/(update.sha256[:16]+'-'+update.name)
        if Path(path) != expected or not update.installer or redirected(expected):
            raise ValueError('Not a verified installer download.')
        if hashlib.sha256(expected.read_bytes()).hexdigest() != update.sha256:
            raise ValueError('The installer changed after download. Download it again.')
        return subprocess.Popen([str(expected)], cwd=str(expected.parent), shell=False)
