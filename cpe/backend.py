"""Choose the installed CPE backend at game startup."""
import json
import sys
from pathlib import Path

GAME_ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
config = GAME_ROOT / 'cpe-backend.json'
if not config.exists() and getattr(sys, 'frozen', False):
    config = Path(sys._MEIPASS) / 'cpe-backend.json'
BACKEND = json.loads(config.read_text(encoding='utf-8')).get('backend', 'classic') if config.exists() else 'classic'
if BACKEND not in {'classic', 'rephysics'}:
    raise RuntimeError('Unknown CPE backend in cpe-backend.json')
if BACKEND == 'rephysics':
    sys.path.insert(0, str(GAME_ROOT))
    from cpe_rephysics import physics as physics_backend
    from cpe_rephysics import CubePhysicsEngine
else:
    import pymunk as physics_backend
    from .engine import CubePhysicsEngine
