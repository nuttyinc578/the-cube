"""CPELoader v2 command for Windows Command Prompt; no shell execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from cpeloader import CPELoader, COMPONENTS, LOADER_VERSION


def main(argv=None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    # Support the originally requested -(game folder) spelling as well as a
    # conventional quoted folder argument. No shell expansion or eval is used.
    for option in ('-connect', '--connect'):
        if option in values:
            i = values.index(option) + 1
            if i < len(values) and values[i].startswith('-') and not values[i].startswith('--'):
                values[i] = values[i][1:]
    parser = argparse.ArgumentParser(prog='cpe', description='CPELoader v2: inspect or lock an installed Cube Beta.')
    parser.add_argument('-connect', '--connect', type=Path, metavar='GAME_FOLDER')
    parser.add_argument('-LOCK', '--lock', action='store_true')
    parser.add_argument('-cpeloader', action='store_true', required=True)
    parser.add_argument('--v', '--version', dest='show_version', action='store_true',
                        help='Show the bundled CPELoader version without connecting or changing files')
    args = parser.parse_args(values)
    if args.show_version:
        if args.lock:
            parser.error('--v/--version cannot be combined with -LOCK')
        print(f'CPELoader v{LOADER_VERSION}')
        return 0
    if args.connect is None:
        parser.error('-connect GAME_FOLDER is required for status or locking')
    try:
        root = args.connect.resolve(strict=True)
        if not root.is_dir() or not all((root/name).is_file() for name in COMPONENTS):
            raise ValueError('Select the extracted Cube Beta game folder, not a ZIP or a parent directory.')
        loader = CPELoader(root)
        if args.lock:
            loader.lock()
        warnings = loader.changes()
        print(json.dumps({'cpeloader': LOADER_VERSION, 'folder': str(root),
                          'unlocked': loader.unlocked, 'integrity_warnings': warnings,
                          'message': ('All three components locked. Restart the game. Existing modifications are still untrusted.'
                                      if args.lock else 'Read-only loader status.')}, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'CPE: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
