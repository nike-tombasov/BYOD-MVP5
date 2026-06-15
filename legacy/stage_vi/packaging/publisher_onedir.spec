# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

hidden_imports = collect_submodules('livekit.rtc') + [
    'sounddevice',
    'numpy',
    'websockets',
    'PySide6',
]

datas = collect_data_files('livekit.rtc')
binaries = collect_dynamic_libs('livekit.rtc')


a = Analysis(
    ['src/publisher/main.py'],
    pathex=['src/publisher'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
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
