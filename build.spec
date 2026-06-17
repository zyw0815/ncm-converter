# build.spec — PyInstaller 打包配置
# 在 macOS 上构建 .app，在 Windows 上构建 .exe：
#   pyinstaller build.spec
import sys

block_cipher = None

# 单一版本号来源：version.py
_ver = {}
with open("version.py", encoding="utf-8") as _f:
    exec(_f.read(), _ver)
APP_VERSION = _ver["__version__"]

# 各平台图标
_icon = "assets/icon.ico" if sys.platform.startswith("win") else "assets/icon.icns"

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt6'],
    hookspath=[],
    runtime_hooks=[],
    # 本应用不使用 setuptools/pkg_resources；排除它们以避免 PyInstaller 自动
    # 注入的 pkg_resources 运行时钩子在启动时因缺少 jaraco 而崩溃。
    excludes=['pkg_resources', 'setuptools', 'pip'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NCM-Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='NCM-Converter',
)

app = BUNDLE(
    coll,
    name='NCM-Converter.app',
    bundle_identifier='com.ncmconverter.app',
    icon='assets/icon.icns',
    version=APP_VERSION,
    info_plist={
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'NSHighResolutionCapable': True,
    },
)
