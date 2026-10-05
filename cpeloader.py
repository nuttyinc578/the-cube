"""CPELoader file integrity and flashing policy for The Cube Beta."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

COMPONENTS = ('cpeloader.py', 'cpeloader_core_runtime.js', 'cpeloader_core.rb')
EXCLUDED_DIRS = {'.git', '.venv', '__pycache__', 'build', 'dist', 'backup', 'backups', 'installer-output', 'package-staging', 'release-download', 'legacy-versions', 'og-recovery', 'node_modules', 'bin', 'obj', 'inbox', 'publish-work'}
MUTABLE = {'settings.json', 'halloween_update_state.json', 'error_update_state.json', 'og-current-version.json', 'cpeloader_state.json', 'cpeloader_manifest.json', 'halloween_music.mp3', 'fall_music.mp3'}


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    for folder, directories, files in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS and not name.startswith('.') and not (Path(folder)/name).is_symlink())
        for name in sorted(files):
            path = Path(folder)/name
            if name.startswith('.') or name in MUTABLE or path.is_symlink(): continue
            if re.fullmatch(r'unins\d+\.(exe|dat|msg)', name, re.IGNORECASE): continue
            if path.suffix in {'.pyc', '.log', '.writing', '.tmp'}: continue
            try: digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError: digest = 'unreadable'
            result[path.relative_to(root).as_posix()] = digest
    return result


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name+'.writing')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class CPELoader:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.path = self.root/'cpeloader_state.json'

    def state(self) -> dict:
        if not self.path.exists(): return {'unlocked': False, 'components': {name: False for name in COMPONENTS}}
        try:
            state = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(state, dict) or not isinstance(state.get('components', {}), dict): raise ValueError('invalid state')
            return state
        except (ValueError, OSError):
            return {'unlocked': False, 'components': {}, 'state_error': True}

    @property
    def unlocked(self) -> bool:
        state = self.state()
        return state.get('unlocked') is True and all(state.get('components', {}).get(name) is True and (self.root/name).is_file() for name in COMPONENTS)

    def unlock(self) -> None:
        if not all((self.root/name).is_file() for name in COMPONENTS):
            raise RuntimeError('Reinstall the game: a CPELoader component is missing.')
        write_json(self.path, {'unlocked': True, 'components': {name: True for name in COMPONENTS}, 'baseline': snapshot(self.root)})

    def changes(self) -> list[str]:
        state = self.state()
        if state.get('state_error'): return ['cpeloader_state.json (unreadable)']
        baseline = state.get('baseline') if state.get('unlocked') is True else None
        manifest = self.root/'cpeloader_manifest.json'
        if baseline is None and manifest.exists():
            try: baseline = json.loads(manifest.read_text(encoding='utf-8'))['files']
            except (ValueError, KeyError, OSError): return ['cpeloader_manifest.json (unreadable)']
        if baseline is None: return []
        if not isinstance(baseline, dict): return ['cpeloader_state.json (invalid baseline)']
        current = snapshot(self.root)
        return sorted(name for name in set(baseline)|set(current) if baseline.get(name) != current.get(name))

    def require_flash(self) -> None:
        if not self.unlocked:
            raise PermissionError('CPELoader is locked. Open the game, press Ctrl+A, then Y to unlock all three loader components before flashing.')

    def require_in_game_update(self) -> None:
        if self.state().get('unlocked') is True or self.state().get('state_error'):
            raise PermissionError('CPELoader is unlocked. Game updates are disabled; use the external installer.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).parent)
    parser.add_argument('--seal', action='store_true', help='Create the trusted baseline while packaging the installer')
    args = parser.parse_args()
    if args.seal:
        write_json(args.root/'cpeloader_manifest.json', {'files': snapshot(args.root)})
    else:
        loader = CPELoader(args.root)
        print(json.dumps({'unlocked': loader.unlocked, 'changes': loader.changes()}))

if __name__ == '__main__': main()
