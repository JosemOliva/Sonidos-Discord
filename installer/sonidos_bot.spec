# Empaquetado con PyInstaller: genera dist/SonidosBot/SonidosBot.exe, una sola
# app sin consola (el menú de configuración con el bot dentro).
# Uso (desde la raíz del proyecto):  pyinstaller installer/sonidos_bot.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas, binaries, hiddenimports = [], [], []
# customtkinter trae temas y fuentes como archivos de datos.
for package in ("discord", "davey", "vosk", "pygame", "customtkinter"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("discord.ext.voice_recv")
hiddenimports += collect_submodules("pynput")

ffmpeg = ROOT / "installer" / "vendor" / "ffmpeg.exe"
if ffmpeg.exists():
    binaries.append((str(ffmpeg), "."))
else:
    print("AVISO: falta installer/vendor/ffmpeg.exe, el bot necesitará ffmpeg en el PATH")

icon = ROOT / "installer" / "icono.ico"
icon = str(icon) if icon.exists() else None

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
exe = EXE(
    PYZ(a.pure),
    a.scripts,
    exclude_binaries=True,
    name="SonidosBot",
    console=False,
    icon=icon,
)
COLLECT(exe, a.binaries, a.datas, name="SonidosBot")
