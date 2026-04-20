# -*- mode: python ; coding: utf-8 -*-
# SoulMusic-linux.spec  —  PyInstaller build descriptor for Linux
#
# Output:  dist/SoulMusic/SoulMusic  (onedir ELF binary, faster startup)
# Build:   pyinstaller SoulMusic-linux.spec --noconfirm
#
# Prerequisites on Linux:
#   pip install pyinstaller PySide6 numpy
#   sudo apt-get install libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
#        libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xkb1 \
#        libxkbcommon-x11-0 libegl1 libgl1  (Ubuntu/Debian)
#
# Notes:
#   - This spec uses the PySide6 xcb Qt platform plugin for X11/Wayland.
#   - For headless/server builds set QT_QPA_PLATFORM=offscreen.
#   - The 'sounddevice' binaries reference ALSA/PulseAudio — these must be
#     present on the target system (standard Linux audio stack).

block_cipher = None

a = Analysis(
    ['soul_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('acoustic',  'acoustic'),
        ('detection', 'detection'),
        ('flight',    'flight'),
    ],
    hiddenimports=[
        'numpy',
        'PySide6.QtSvg',
        'PySide6.QtXml',
        'PySide6.QtDBus',        # needed on Linux for system tray / dbus
        'sounddevice', '_sounddevice', 'cffi', '_cffi_backend',
        'serial', 'serial.tools', 'serial.tools.list_ports',
        'acoustic', 'acoustic.beam', 'acoustic.probe',
        'acoustic.resonance', 'acoustic.emitter',
        'detection', 'detection.acoustic_detect',
        'flight', 'flight.telemetry',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'torchaudio',
        'tensorflow', 'keras',
        'transformers', 'tokenizers', 'datasets',
        'sklearn', 'scikit_learn',
        'scipy',
        'cv2', 'opencv',
        'IPython', 'ipykernel', 'ipywidgets',
        'pandas',
        'PIL', 'Pillow',
        'onnxruntime', 'onnx',
        'numba', 'llvmlite',
        'librosa',
        'imageio',
        'nbformat', 'nbconvert', 'jupyter',
        'jedi',
        'timm',
        # Windows-only packages that may have been pip-installed
        'win32api', 'win32con', 'winreg', 'winnt',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SoulMusic',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX can break PySide6 Qt plugins on Linux — leave off
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # No icon arg here — .ico is Windows only.  Use a .png on Linux:
    # icon='assets/icon.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SoulMusic',
)
