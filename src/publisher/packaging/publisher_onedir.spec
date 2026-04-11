# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/publisher/main.py'],
    pathex=['src/publisher'],
    binaries=[],
    datas=[],
    hiddenimports=['sounddevice', 'numpy', 'websockets', 'livekit', 'PySide6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BYODPublisher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BYODPublisher',
)
