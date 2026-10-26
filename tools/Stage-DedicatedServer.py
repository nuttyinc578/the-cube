"""Allowlisted Linux game-server build payload; no game credentials or mods."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', default='build/gamelift-linux-server')
    args = parser.parse_args()
    destination = (ROOT/args.destination).resolve()
    if ROOT/'build' not in destination.parents:
        raise ValueError('Server staging must stay under the repository build directory.')
    destination.mkdir(parents=True, exist_ok=False)
    for name in ('worker.py', 'install.sh', 'requirements.txt', 'cube-server'):
        shutil.copy2(ROOT/'dedicated_server'/name, destination/name)
    for name in ('cube_core.py', 'LICENCE.txt'):
        shutil.copy2(ROOT/name, destination/name)
    for name in ('cpe', 'cpe_rephysics'):
        for path in (ROOT/name).rglob('*.py'):
            if any(part in {'__pycache__', 'tests', 'test', 'bin', 'obj', '.venv', 'node_modules'} for part in path.parts):
                continue
            target = destination/path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    print(destination)


if __name__ == '__main__':
    main()
