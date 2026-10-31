"""Offline, backup-first repair from the recovery image bundled in cpe.exe.

Never imports code from the selected game or replaces its integrity manifest,
loader state, saves, add-ons, or the running cpe.exe itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import zipfile

from cpeloader import COMPONENTS
from release_info import VERSION, EXE_NAME

MAX_IMAGE_BYTES = 256 * 1024 * 1024
MAX_FILES = 256
BRIDGE_FILES = (
    'node-bridge/package.json', 'node-bridge/server.js', 'go-cache/go.mod', 'go-cache/main.go',
    'java-client/README.md', 'java-client/src/main/java/com/nuttyinc/cpe/CpeClient.java',
    'CPE.AppHost/CPE.AppHost.csproj', 'CPE.AppHost/Program.cs',
    'CPE.AppHost/Properties/launchSettings.json',
)


class RepairError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_name(relative):
    name = PurePosixPath(relative)
    if not relative or name.is_absolute() or str(name) != relative or any(
            part in ('', '.', '..') or ':' in part or '\\' in part for part in name.parts):
        raise RepairError('REPAIR_PATH: invalid recovery path.')
    return name


def checked_path(root, relative):
    """Reject traversal, symlinks and Windows junctions before reading/writing."""
    name = validate_name(relative)
    target = root.joinpath(*name.parts)
    if root.is_symlink() or root.is_junction():
        raise RepairError('REPAIR_PATH: redirected game folder is not supported.')
    current = root
    for part in name.parts:
        current /= part
        if current.is_symlink() or current.is_junction():
            raise RepairError(f'REPAIR_PATH: redirected path: {relative}')
        if current.exists() and current != target and not current.is_dir():
            raise RepairError(f'REPAIR_PATH: parent is not a directory: {relative}')
    return target


def image_paths():
    if getattr(sys, 'frozen', False):
        folder = Path(sys._MEIPASS)/'recovery'
    else:
        folder = Path(__file__).resolve().parent/'build'/'cpe-recovery'
    return folder/'image.zip', folder/'image.json'


def build_image(root, game_folder, output):
    """Build-time only: freeze original release bytes, before cpe.exe is compiled."""
    sources = {EXE_NAME: (game_folder/EXE_NAME, 'cpe'),
               'cpe-backend.json': (root/'cpe-backend.json', 'cpe')}
    sources.update({name: (root/name, 'cpeloader') for name in COMPONENTS})
    sources.update({'cpe/'+name: (root/'cpe'/name, 'cpe') for name in BRIDGE_FILES})
    sources.update({'cpe/'+p.name: (p, 'cpe') for p in sorted((root/'cpe').glob('*.py'))})
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    with zipfile.ZipFile(output/'image.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, (path, group) in sorted(sources.items()):
            data = path.read_bytes()
            records[name] = {'sha256': digest(data), 'size': len(data), 'group': group}
            archive.writestr(name, data)
    metadata = {'schema': 1, 'version': VERSION, 'files': records,
                'image_sha256': digest((output/'image.zip').read_bytes())}
    (output/'image.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')


def load_image(paths=None):
    image, metadata = paths or image_paths()
    try:
        if metadata.stat().st_size > 128*1024 or image.stat().st_size > MAX_IMAGE_BYTES:
            raise RepairError('REPAIR_IMAGE: recovery image is too large.')
        record = json.loads(metadata.read_text(encoding='utf-8'))
        raw = image.read_bytes()
        if record.get('schema') != 1 or record.get('version') != VERSION:
            raise RepairError('REPAIR_IMAGE: unsupported recovery image version.')
        if digest(raw) != record.get('image_sha256'):
            raise RepairError('REPAIR_IMAGE: checksum mismatch; download a fresh official installer.')
        files = record['files']
        if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
            raise RepairError('REPAIR_IMAGE: invalid file table.')
        import io
        data = {}
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) != len(files) or {e.filename for e in entries} != set(files):
                raise RepairError('REPAIR_IMAGE: unexpected or duplicate archive members.')
            if sum(e.file_size for e in entries) > MAX_IMAGE_BYTES:
                raise RepairError('REPAIR_IMAGE: expanded recovery image is too large.')
            folded = set()
            for entry in entries:
                name, info = entry.filename, files[entry.filename]
                validate_name(name)  # Never extract arbitrary archive members.
                group = info['group']
                allowed = (name in COMPONENTS if group == 'cpeloader' else
                           group == 'cpe' and (name in (EXE_NAME, 'cpe-backend.json') or
                                              name.startswith('cpe/')))
                if not allowed or name.casefold() in folded or entry.is_dir():
                    raise RepairError('REPAIR_IMAGE: unsupported or duplicate recovery target.')
                folded.add(name.casefold())
                payload = archive.read(entry)
                if len(payload) != info['size'] or digest(payload) != info['sha256']:
                    raise RepairError(f'REPAIR_IMAGE: file checksum mismatch: {name}')
                data[name] = payload
        if not all(name in files for name in (*COMPONENTS, EXE_NAME)):
            raise RepairError('REPAIR_IMAGE: recovery image is incomplete.')
        return files, data
    except RepairError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile) as exc:
        raise RepairError('REPAIR_IMAGE_MISSING: bundled recovery image is missing or invalid; '
                          'download the complete official installer or portable ZIP.') from exc


@dataclass
class RepairPlan:
    root: Path
    payloads: dict[str, bytes]
    original: dict[str, str | None]
    missing_loader: tuple[str, ...]
    manifest_bytes: bytes


def prepare_repair(root, groups, paths=None):
    root = Path(root).absolute()
    checked_path(root, 'cpeloader_manifest.json')
    if not root.is_dir():
        raise RepairError('GAME_FOLDER_MISSING: select an existing extracted game folder.')
    root = root.resolve(strict=True)
    files, payloads = load_image(paths)
    manifest = checked_path(root, 'cpeloader_manifest.json')
    try:
        if manifest.stat().st_size > 4*1024*1024:
            raise ValueError('oversized manifest')
        manifest_bytes = manifest.read_bytes()
        original_files = json.loads(manifest_bytes)['files']
        if not isinstance(original_files, dict) or any(
                original_files.get(name) != info['sha256'] for name, info in files.items()):
            raise ValueError('release mismatch')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RepairError('REPAIR_VERSION_MISMATCH: original game manifest is missing or does not '
                          'match this recovery image. Use the matching official installer in a new folder.') from exc
    missing = tuple(name for name in COMPONENTS if not checked_path(root, name).is_file())
    if missing and 'cpeloader' not in groups:
        raise RepairError('CPELOADER_MISSING: '+', '.join(missing)+
                          '. Include -cpeloader/repair to restore these files.')
    selected, original = {}, {}
    for name, info in files.items():
        if info['group'] not in groups:
            continue
        target = checked_path(root, name)
        if target.exists() and not target.is_file():
            raise RepairError(f'REPAIR_PATH: expected a regular file: {name}')
        before = digest(target.read_bytes()) if target.exists() else None
        if before != info['sha256']:
            selected[name], original[name] = payloads[name], before
    # Check backup redirection even before confirmation.
    checked_path(root, 'backup/cpe-cli')
    return RepairPlan(root, selected, original, missing, manifest_bytes)


def execute_repair(plan, progress=lambda percent, message: None):
    """Stage and verify all originals first; roll back replacements on failure."""
    root = plan.root
    if checked_path(root, 'cpeloader_manifest.json').read_bytes() != plan.manifest_bytes:
        raise RepairError('REPAIR_CHANGED: game manifest changed; repair cancelled.')
    if not plan.payloads:
        progress(100, 'Files already match the recovery image. No changes needed.')
        return {'restored': [], 'backup': None}
    for name, before in plan.original.items():
        target = checked_path(root, name)
        current = digest(target.read_bytes()) if target.exists() else None
        if current != before:
            raise RepairError('REPAIR_CHANGED: game files changed after confirmation; close the game and retry.')
    backup_root = checked_path(root, 'backup/cpe-cli')
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-'), dir=backup_root))
    staged, replaced = {}, []
    report = {'version': VERSION, 'status': 'preparing', 'original': plan.original}
    try:
        total = len(plan.payloads)
        for index, (name, payload) in enumerate(plan.payloads.items()):
            target = checked_path(root, name)
            if plan.original[name] is not None:
                saved = backup/'original'/name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                if digest(saved.read_bytes()) != plan.original[name]:
                    raise RepairError('REPAIR_CHANGED: file changed during backup; repair cancelled.')
            stage = backup/'staged'/name
            stage.parent.mkdir(parents=True, exist_ok=True)
            stage.write_bytes(payload)
            if digest(stage.read_bytes()) != digest(payload):
                raise RepairError('REPAIR_IO: recovery staging verification failed.')
            staged[name] = stage
            progress(int((index+1)*40/total), 'Backing up and staging: '+name)
        report['status'] = 'replacing'
        (backup/'repair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        for index, (name, stage) in enumerate(staged.items()):
            target = checked_path(root, name)
            current = digest(target.read_bytes()) if target.exists() else None
            if current != plan.original[name]:
                raise RepairError('REPAIR_CHANGED: file changed before replacement; repair stopped.')
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage, target)
            replaced.append(name)
            if digest(target.read_bytes()) != digest(plan.payloads[name]):
                raise RepairError('REPAIR_IO: restored file failed verification.')
            progress(40+int((index+1)*60/total), 'Verified: '+name)
        report['status'] = 'complete'
        (backup/'repair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return {'restored': replaced, 'backup': str(backup)}
    except Exception as exc:
        failed = []
        for name in reversed(replaced):
            try:
                target = checked_path(root, name)
                if plan.original[name] is None:
                    target.unlink()
                else:
                    rollback = backup/'rollback'/name
                    rollback.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup/'original'/name, rollback)
                    os.replace(rollback, target)
            except (OSError, RepairError):
                failed.append(name)
        report.update(status='rollback-incomplete' if failed else 'rolled-back', error=str(exc), rollback_failed=failed)
        (backup/'repair.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        detail = 'Some originals could not be restored; close the game and restore the backup.' if failed else 'Replaced files were rolled back.'
        raise RepairError(f'REPAIR_FAILED: {exc} {detail} Backup: {backup}') from exc
