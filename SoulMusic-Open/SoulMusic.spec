# -*- mode: python ; coding: utf-8 -*-
# SoulMusic.spec  —  PyInstaller build descriptor
# Output:  dist\SoulMusic\SoulMusic.exe  (onedir, faster startup)
# Build:   pyinstaller SoulMusic.spec --noconfirm

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
        'sounddevice', '_sounddevice', 'cffi', '_cffi_backend',
        'serial', 'serial.tools', 'serial.tools.list_ports',
        'matplotlib', 'matplotlib.pyplot', 'matplotlib.backends.backend_agg',
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
