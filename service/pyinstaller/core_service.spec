# PyInstaller spec for the headless core service (service/core_service.py).
#
# Onedir build (not onefile): onefile self-extracts to a fresh %TEMP% dir on
# every launch, adding startup latency and being the most common failure
# mode reported for vgamepad+PyInstaller. Onedir avoids extraction entirely;
# shipping a folder is fine since it goes inside the Tauri bundle anyway.
#
# Build with:
#   pyinstaller service/pyinstaller/core_service.spec

import os

from PyInstaller.utils.hooks import collect_all

# SPECPATH is already the absolute directory containing this .spec file
# (service/pyinstaller/), not the file path itself.
SPEC_DIR = os.path.abspath(SPECPATH)
REPO_ROOT = os.path.abspath(os.path.join(SPEC_DIR, "..", ".."))
ENTRY_SCRIPT = os.path.join(REPO_ROOT, "service", "core_service.py")

# vgamepad's ViGEmClient.dll is resolved at runtime via a __file__-relative
# ctypes.CDLL(...) path (vgamepad/win/vigem_client.py), not a normal import,
# so PyInstaller's static analysis can't find it on its own. collect_all
# preserves the package's relative directory layout for its binaries/data,
# which is required for that __file__-relative lookup to keep working.
# NOTE: collect_all() returns (src, dest) 2-tuples in hook-variable format —
# these must be passed into the Analysis() constructor, not concatenated
# onto a.datas/a.binaries after construction (that expects 3-tuple TOC
# entries and raises "not enough values to unpack").
vg_datas, vg_binaries, vg_hiddenimports = collect_all("vgamepad")

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[REPO_ROOT],
    binaries=vg_binaries,
    datas=vg_datas,
    hiddenimports=[
        # usb.core.find() probes backends dynamically via importlib, which
        # PyInstaller's static analysis can miss.
        "usb.backend.libusb1",
        "usb.backend.libusb0",
        "usb.backend.openusb",
        # pynput dispatches to a platform submodule dynamically.
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    ] + vg_hiddenimports,
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
    name="core_service",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Keep a console for now so build/runtime errors (esp. the vgamepad DLL
    # load) are visible during bring-up. Switch to False once packaging is
    # verified working end-to-end.
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="core_service",
)
