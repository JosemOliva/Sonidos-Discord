# Empaquetado con PyInstaller: genera dist/SonidosBot/ con dos programas que
# comparten librerías:
#   SonidosBot.exe          el bot (ventana de consola con el log)
#   ConfigurarSonidosBot.exe  el menú de configuración
# Uso (desde la raíz del proyecto):  pyinstaller installer/sonidos_bot.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas, binaries, hiddenimports = [], [], []
for package in ("discord", "davey", "vosk", "pygame"):
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

bot_a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
# El menú usa customtkinter, que trae temas y fuentes como archivos de datos.
cfg_datas, cfg_binaries, cfg_hidden = collect_all("customtkinter")
cfg_a = Analysis(
    [str(ROOT / "configurar.py")],
    pathex=[str(ROOT)],
    binaries=cfg_binaries,
    datas=cfg_datas,
    hiddenimports=cfg_hidden + collect_submodules("pygame"),
)

bot_exe = EXE(
    PYZ(bot_a.pure),
    bot_a.scripts,
    exclude_binaries=True,
    name="SonidosBot",
    console=True,
    icon=icon,
)
cfg_exe = EXE(
    PYZ(cfg_a.pure),
    cfg_a.scripts,
    exclude_binaries=True,
    name="ConfigurarSonidosBot",
    console=False,
    icon=icon,
)

COLLECT(
    bot_exe, bot_a.binaries, bot_a.datas,
    cfg_exe, cfg_a.binaries, cfg_a.datas,
    name="SonidosBot",
)
