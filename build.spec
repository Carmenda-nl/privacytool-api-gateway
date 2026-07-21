# -*- mode: python ; coding: utf-8 -*-

import os
import site
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

sys.path.insert(0, str(Path(SPECPATH) / 'app'))
from main._version import __version__

print(f'\nAPI-Gateway build: {__version__}\n')

# Check build OS
windows = sys.platform == 'win32'
site_packages = site.getsitepackages()[1] if windows else site.getsitepackages()[0]

rest_framework_path = Path(site_packages) / 'rest_framework'

# Update paths to match current project structure
app_path = Path(SPECPATH) / 'app'

datas = []
datas += copy_metadata('polars')

datas += collect_data_files('rest_framework')
datas += collect_data_files('polars')

# Add the app directory selectively
excluded_items = {
    '.vscode',
    'uv.lock',
    '.mypy_cache',
    '__pycache__',
    'data',
    'tests',
    'pytest',
    'core.py',
    'Makefile',
    'pyproject.toml',
}

for root, dirs, files in os.walk(app_path):
    dirs[:] = [directory for directory in dirs if directory not in excluded_items and not directory.startswith('.')]

    for filename in files:
        if isinstance(filename, str) and filename not in excluded_items and not filename.startswith('.'):
            source_path = str(Path(root) / filename)
            rel_path = os.path.relpath(root, app_path)

            dest_path = str(Path('app') / rel_path) if rel_path != '.' else 'app'
            datas.append((source_path, dest_path))

# Filter out files and folders not needed for production
datas = [
    (source, dest)
    for source, dest in datas
    if not (isinstance(source, str) and ('__pycache__' in source or '.pyc' in source))
]

rest_framework_imports = collect_submodules('rest_framework')

datas.append((str(rest_framework_path), 'rest_framework'))

binaries = []
hiddenimports = []
hiddenimports += collect_submodules('polars')
hiddenimports += collect_submodules('whitenoise')

tmp_ret = collect_all('rest_framework')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('polars')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('uvicorn')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


# Drop test suites dragged in by collect_submodules/collect_all
def _has_test_segment(path, sep):
    parts = path.replace('\\', '/').split('/') if sep is None else path.split(sep)
    return 'test' in parts or 'tests' in parts


hiddenimports = [imp for imp in hiddenimports if not _has_test_segment(imp, '.')]
datas = [
    (source, dest)
    for source, dest in datas
    if not (isinstance(dest, str) and _has_test_segment(dest, None))
]

a = Analysis(
    [str(app_path / 'frozen.py')],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'test',
        'tests',
        'hypothesis',
        'IPython',
        'jupyter',
        'notebook',
        'tkinter',
        'Tkinter',
        'pdb',
        'matplotlib',
        'pylab',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='api-gateway',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
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

coll = COLLECT(exe, a.binaries, a.datas, a.scripts, strip=False, upx=True, upx_exclude=[], name='api-gateway')