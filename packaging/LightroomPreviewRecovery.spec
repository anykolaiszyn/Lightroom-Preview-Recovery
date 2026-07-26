from pathlib import Path


root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "PyQt5", "PyQt6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LightroomPreviewRecovery",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    version=str(root / "packaging" / "version_info.txt"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LightroomPreviewRecovery",
)
