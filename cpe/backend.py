"""Choose the installed CPE backend at game startup."""
import json
import sys
import importlib
from pathlib import Path

GAME_ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
config = GAME_ROOT / 'cpe-backend.json'
if not config.exists() and getattr(sys, 'frozen', False):
    config = Path(sys._MEIPASS) / 'cpe-backend.json'
configuration = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
BACKEND = configuration.get('backend', 'classic')
if BACKEND not in {'classic', 'rephysics', 'project'}:
    raise RuntimeError('Unknown CPE backend in cpe-backend.json')
if BACKEND == 'rephysics':
    sys.path.insert(0, str(GAME_ROOT))
    from cpe_rephysics import physics as physics_backend
    from cpe_rephysics import CubePhysicsEngine
elif BACKEND == 'project':
    # Custom projects are explicitly trusted by the user in CPE Flasher Tool.
    sys.path.insert(0, str(GAME_ROOT))
    project = importlib.import_module('cpe_project')
    physics_backend = importlib.import_module('cpe_project.physics')
    CubePhysicsEngine = project.CubePhysicsEngine
else:
    import pymunk as physics_backend
    from .engine import CubePhysicsEngine
