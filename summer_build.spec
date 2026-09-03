# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["the_cube_beta_summer.py"],
    pathex=["addons"],
    binaries=[],
    datas=[
        ("icon.ico", "."),
        ("LICENCE.txt", "."),
        ("click.mp3", "."),
        ("fall_music.mp3", "."),
        ("THIRD_PARTY_NOTICES.txt", "."),
        ("addons", "addons"),
        ("themes", "themes"),
    ],
    hiddenimports=["_nuttymod_connection", "_nuttymod_v140_patch"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="The Cube Beta Fall",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["icon.ico"],
    version="summer_version.txt",
)
