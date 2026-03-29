# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for lantern-city standalone executable.

Build:
    uv run pyinstaller lantern-city.spec

Output: dist/lantern-city.exe (Windows) or dist/lantern-city (Linux/macOS)
"""

block_cipher = None

a = Analysis(
    ["src/lantern_city/cli.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        # SQLAlchemy SQLite dialect is loaded by string at runtime
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.sql.default_comparator",
        # Pydantic v2 internals resolved dynamically
        "pydantic",
        "pydantic.v1",
        "pydantic_core",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy server-side packages declared as deps but unused in CLI
    excludes=["fastapi", "uvicorn", "starlette", "anyio", "h11"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lantern-city",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
