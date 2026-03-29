# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for lantern-city-tui standalone executable.

Build:
    uv run pyinstaller lantern-city-tui.spec

Output: dist/lantern-city-tui.exe (Windows) or dist/lantern-city-tui (Linux/macOS)
"""

block_cipher = None

a = Analysis(
    ["src/lantern_city/tui.py"],
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
        # Textual core
        "textual",
        "textual.app",
        "textual.screen",
        "textual.widgets",
        "textual.widgets._input",
        "textual.widgets._button",
        "textual.widgets._label",
        "textual.widgets._static",
        "textual.widgets._rich_log",
        "textual.containers",
        "textual.binding",
        "textual.worker",
        "textual.css.query",
        "textual.css.scalar",
        # Textual drivers
        "textual.drivers.win32",
        "textual.drivers.linux",
        "textual.drivers.headless",
        # Rich (Textual dependency)
        "rich",
        "rich.text",
        "rich.markup",
        "rich.console",
        "rich.segment",
        # asyncio Windows support
        "asyncio.proactor_events",
        "asyncio.windows_events",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["fastapi", "uvicorn", "starlette"],
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
    name="lantern-city-tui",
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
