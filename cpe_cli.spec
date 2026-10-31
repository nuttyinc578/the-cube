# Standalone console command: portable users do not need to install Python.
a = Analysis(['cpeloader_cli.py'], pathex=[], binaries=[],
             datas=[('build/cpe-recovery/image.zip', 'recovery'), ('build/cpe-recovery/image.json', 'recovery')], hiddenimports=[],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='cpe', console=True,
          debug=False, strip=False, upx=False, icon=['build/christmas-icon.ico'])
