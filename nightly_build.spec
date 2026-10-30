# Dedicated nightly build; stable release specs and assets are unchanged.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

addon_datas = [(str(p), str(p.parent)) for p in Path('addons').rglob('*')
    if p.is_file() and '__pycache__' not in p.parts and not p.name.startswith('.')
    and (p.suffix != '.pyc' or p.name == 'nuttymod_runtime_v122.pyc')]
theme_datas = [(str(p), str(p.parent)) for p in Path('themes').rglob('*')
    if p.is_file() and not any(s.startswith('.') or s in ('inbox', 'publish-work', '__pycache__') for s in p.parts)]
a = Analysis(['the_cube_beta_summer.py'], pathex=['addons'], binaries=[],
    datas=[('icon.ico', '.'), ('normal_icon.ico', '.'), ('halloween_cube_icon.png', '.'),
        ('error_update_logo.png', '.'), ('LICENCE.txt', '.'), ('click.mp3', '.'),
        ('fall_music.mp3', '.'), ('THIRD_PARTY_NOTICES.txt', '.'), ('nightly-config.json', '.'),
        ('repair_payload', 'repair_payload'), ('cpe-backend.json', '.'),
        ('cpeloader.py', '.'), ('cpeloader_core_runtime.js', '.'), ('cpeloader_core.rb', '.'),
        *addon_datas, *theme_datas,
        *collect_data_files('pygame', includes=['**/LICENSE*', '**/COPYING*']),
        *collect_data_files('pymunk', includes=['**/LICENSE*'])],
    hiddenimports=['cpe_rephysics.engine', 'cpe_rephysics.physics', 'cpe_rephysics.particles', 'cpe_rephysics.protocol'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='The Cube Beta Nightly',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    runtime_tmpdir=None, console=False, disable_windowed_traceback=False,
    icon=['icon.ico'], version='nightly_version.txt')
