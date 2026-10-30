"""Explicitly trusted game-level customization, never operating-system rooting."""
from __future__ import annotations

import json
import logging
import runpy
from pathlib import Path


def initialize_profile(app, root: Path) -> None:
    profile_path = root / 'cpe-flash-profile.json'
    if not profile_path.is_file(): return
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    if not isinstance(profile, dict) or profile.get('schema') != 1:
        raise RuntimeError('Invalid flash profile. Restore the backup or reinstall.')
    # Never run custom startup code with a locked loader.
    app.cpeloader.require_flash()
    data = root / 'userdata'
    data.mkdir(exist_ok=True)
    app.userdata = json.loads((data / 'userdata.json').read_text(encoding='utf-8'))
    if not isinstance(app.userdata, dict) or app.userdata.get('schema') != 1:
        raise RuntimeError('Required userdata is invalid. Restore userdata.json.')
    app.game_root_enabled = True
    app.verbose_python = profile.get('verbose_python') is True
    # Cosmetic custom-loader alerts only: integrity/update policy is untouched.
    app.safety_cube_alerts = profile.get('safety_cube_alerts', True) is not False
    logger = logging.getLogger('cpe.flash')
    logger.setLevel(logging.DEBUG if app.verbose_python else logging.INFO)
    log_path = data / 'verbose-python.log'
    if app.verbose_python and not any(getattr(h, 'baseFilename', None) == str(log_path.resolve()) for h in logger.handlers):
        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    logger.info('Flashed game startup: loader unlocked, userdata loaded')
    context = {'app': app, 'userdata': app.userdata, 'game_root': root, 'logger': logger}
    if profile.get('nuttymod_root'):
        from nuttymod_root_support import initialize_nuttymod
        try: initialize_nuttymod(app, root, profile['nuttymod_root'], logger)
        except (RuntimeError, OSError, ValueError, TypeError, KeyError) as exc:
            app.root_mode_enabled = False
            app.nuttymod_root_enabled = False
            app.nuttymod_root_error = str(exc)
            logger.error('NuttyMod Root disabled: %s', exc)
    hooks = profile.get('scripts', [])
    loader = profile.get('loader')
    if loader: hooks = [loader] + list(hooks)
    for relative in hooks:
        path = (root / relative).resolve()
        if not path.is_relative_to((root / 'flash_scripts').resolve()) or path.suffix != '.py':
            raise RuntimeError('Invalid startup script path in flash profile.')
        logger.info('Running trusted startup hook: %s', relative)
        try:
            namespace = runpy.run_path(str(path), init_globals=context)
            if callable(namespace.get('on_load')): namespace['on_load'](app, app.userdata)
        except Exception:
            logger.exception('Custom startup hook failed: %s', relative)
            raise
