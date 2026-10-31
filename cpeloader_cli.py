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
    option_names = {'-LOCK', '-cpeloader', '-cpe/repair', '-cpeloader/repair', '-fullgame/repair'}
    for option in ('-connect', '--connect'):
        if option in values:
            i = values.index(option) + 1
            if (i < len(values) and values[i].startswith('-') and not values[i].startswith('--')
                    and values[i] not in option_names):
                values[i] = values[i][1:]
    parser = argparse.ArgumentParser(prog='cpe', description='CPELoader v2: inspect or lock an installed Cube Beta.')
    game_folder = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).parent
    parser.add_argument('-connect', '--connect', type=Path, metavar='GAME_FOLDER', nargs='?', const=game_folder,
                        help='Select a game folder; omit the path to select the folder containing cpe.exe')
    parser.add_argument('-LOCK', '--lock', action='store_true')
    parser.add_argument('-cpeloader', '--cpeloader', action='store_true', required=True)
    parser.add_argument('-cpe/repair', dest='repair_cpe', action='store_true',
                        help='Restore CPE and the compiled game from the bundled recovery image')
    parser.add_argument('-cpeloader/repair', dest='repair_loader', action='store_true',
                        help='Restore missing or changed CPELoader components')
    parser.add_argument('-fullgame/repair', dest='repair_game', action='store_true',
                        help='Restore all bundled game files, CPE and CPELoader; preserve player data and lock state')
    parser.add_argument('--no-gui', action='store_true', help='Use console repair instead of the visual recovery screen')
    parser.add_argument('--yes', action='store_true', help='Explicitly accept backup and replacement for repair')
    parser.add_argument('--v', '--version', dest='show_version', action='store_true',
                        help='Show the bundled CPELoader version without connecting or changing files')
    args = parser.parse_args(values)
    repairing = args.repair_cpe or args.repair_loader or args.repair_game
    if args.show_version:
        if args.lock or repairing or args.no_gui or args.yes:
            parser.error('--v/--version cannot be combined with locking or repair options')
        print(f'CPELoader v{LOADER_VERSION}')
        return 0
    if repairing and args.lock:
        parser.error('Repair preserves lock state; run -LOCK separately after repair')
    if not repairing and (args.no_gui or args.yes):
        parser.error('--no-gui and --yes require a repair operation')
    if args.connect is None and not repairing:
        parser.error('-connect GAME_FOLDER is required for status or locking')
    try:
        if repairing:
            from cpe_repair import prepare_repair, execute_repair
            selected = args.connect or game_folder
            groups = ({'cpe', 'cpeloader', 'game'} if args.repair_game else
                      ({'cpe'} if args.repair_cpe else set()) | ({'cpeloader'} if args.repair_loader else set()))
            print('CPE IMAGE REPAIR: this may take up to 3 minutes; slow disks can take longer.', flush=True)
            print('Close the game and CPE services. Changed files are backed up before replacement.', flush=True)
            print('Game folder: '+str(selected.absolute()), flush=True)
            if args.repair_game:
                print('Full-game repair restores bundled themes and add-ons too. Saves, settings, extra custom files, '
                      'lock state and the running cpe.exe are preserved.', flush=True)
            plan = prepare_repair(selected, groups)
            if plan.missing_loader:
                print('CPELOADER_MISSING: '+', '.join(plan.missing_loader)+' (selected for restoration)', flush=True)
            if not args.no_gui:
                from cpe_repair_ui import repair_window
                return repair_window(plan, accepted=args.yes)
            if not args.yes:
                try:
                    answer = input('Restore official files from the recovery image? [y/N] ')
                except EOFError:
                    answer = ''
                if answer.strip().lower() != 'y':
                    print('Repair cancelled. No files changed.')
                    return 2
            result = execute_repair(plan, lambda n, text: print(f'{n:3d}%  {text}', flush=True))
            print(json.dumps(result, indent=2))
            return 0
        root = args.connect.resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Select the extracted Cube Beta game folder, not a ZIP or a parent directory.')
        missing = [name for name in COMPONENTS if not (root/name).is_file()]
        if missing:
            raise RuntimeError('CPELOADER_MISSING: '+', '.join(missing)+
                               '. Use --cpeloader -cpeloader/repair with this game folder, or reinstall.')
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
