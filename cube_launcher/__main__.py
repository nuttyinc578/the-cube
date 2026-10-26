import argparse
import json
import sys
from .core import Launcher, update_guard


def main(argv=None):
    parser = argparse.ArgumentParser(description='The Cube Beta launcher — official verified downloads and separate instances.')
    parser.add_argument('--data-dir', help='Separate launcher storage directory')
    parser.add_argument('--self-test', action='store_true', help='Check GUI construction without networking')
    commands = parser.add_subparsers(dest='command')
    commands.add_parser('versions', help='Fetch verified official portable releases')
    commands.add_parser('instances')
    for name in ('play', 'status', 'install', 'update'):
        command = commands.add_parser(name)
        command.add_argument('instance')
        if name in ('install', 'update'):
            command.add_argument('version')
    commands.add_parser('sign-in', help='Browser sign-in with configured AWS Cognito')
    args = parser.parse_args(argv)
    try:
        manager = Launcher(args.data_dir)
        if args.self_test:
            import tkinter as tk
            from .gui import LauncherWindow
            window = tk.Tk()
            window.withdraw()
            LauncherWindow(window, manager)
            window.update_idletasks()
            window.destroy()
            print('GUI self-test passed.')
        elif args.command == 'versions':
            print(json.dumps(manager.releases(), indent=2))
        elif args.command == 'instances':
            print(json.dumps(manager.instances()))
        elif args.command == 'status':
            info = manager.info(args.instance)
            try:
                update_guard(manager.instance(args.instance)/'game')
                info['updates'] = 'allowed'
            except PermissionError as exc:
                info['updates'] = str(exc)
            print(json.dumps(info, indent=2))
        elif args.command == 'play':
            print('Started PID', manager.play(args.instance))
        elif args.command in ('install', 'update'):
            release = next((r for r in manager.releases() if r['version'] == args.version), None)
            if not release:
                raise ValueError('No verified portable binary for this version.')
            manager.install(args.instance, release, args.command == 'update', print)
        elif args.command == 'sign-in':
            from .cloud import sign_in
            print('Signed in:', sign_in(manager.settings()))
        else:
            from .gui import show
            show(manager)
        return 0
    except Exception as exc:
        print('Launcher:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
