# -*- mode: python ; coding: utf-8 -*-
# Build (sur l'OS ciblé, PyInstaller ne cross-compile pas) :
#   pyinstaller YouTool.spec --noconfirm
#
# ffmpeg et ffprobe sont pris dans ./ffmpeg/ (sinon dans le PATH) et embarqués dans l'app.
import os
import sys
import shutil
from PyInstaller.utils.hooks import collect_data_files

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
EXT = ".exe" if IS_WIN else ""


def find_tool(name):
    local = os.path.join(SPECPATH, "ffmpeg", name + EXT)
    if os.path.isfile(local):
        return local
    found = shutil.which(name)
    if found:
        return os.path.realpath(found)
    raise SystemExit(f"\n[YouTool] {name}{EXT} introuvable : place-le dans ./ffmpeg/ ou installe ffmpeg.\n")


binaries = [(find_tool("ffmpeg"), "bin"), (find_tool("ffprobe"), "bin")]
if IS_MAC and any("/homebrew/" in s or "/Cellar/" in s for s, _ in binaries):
    print("[YouTool] ATTENTION : ffmpeg de Homebrew détecté, l'app ne marchera pas sur un Mac sans brew."
          " Utilise un build statique dans ./ffmpeg/.")

datas = [("icon.ico", ".")]
datas += collect_data_files("customtkinter")
datas += collect_data_files("certifi")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if IS_WIN:
    # Un seul YouTool.exe
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="YouTool",
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
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="YouTool",
        debug=False,
        strip=False,
        upx=True,
        console=False,
        argv_emulation=False,
        icon=["icon.ico"],  # converti en .icns automatiquement (Pillow requis)
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        name="YouTool",
    )
    if IS_MAC:
        app = BUNDLE(
            coll,
            name="YouTool.app",
            icon="icon.ico",
            bundle_identifier="com.youtool.app",
            info_plist={
                "NSHighResolutionCapable": True,
                "CFBundleShortVersionString": "2.5.0",
            },
        )
