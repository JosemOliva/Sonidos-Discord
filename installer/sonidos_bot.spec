# Empaquetado con PyInstaller: genera dist/SonidosBot/SonidosBot.exe, una sola
# app sin consola (el menú de configuración con el bot dentro).
# Uso (desde la raíz del proyecto):  pyinstaller installer/sonidos_bot.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent

datas, binaries, hiddenimports = [], [], []
# customtkinter trae temas y fuentes como archivos de datos.
for package in ("discord", "davey", "pygame", "customtkinter"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("pynput")

ffmpeg = ROOT / "installer" / "vendor" / "ffmpeg.exe"
if ffmpeg.exists():
    binaries.append((str(ffmpeg), "."))
else:
    print("AVISO: falta installer/vendor/ffmpeg.exe, el bot necesitará ffmpeg en el PATH")

# Icono del programa; el mismo archivo va dentro para la ventana (wizard.py).
icon = ROOT / "sonidos_bot" / "assets" / "icono.ico"
datas += [(str(icon), "sonidos_bot/assets"), (str(icon.with_suffix(".png")), "sonidos_bot/assets")]
# Fuente de la app (Montserrat), se carga al abrir la ventana.
datas += [(str(f), "sonidos_bot/assets/fuentes") for f in (ROOT / "sonidos_bot" / "assets" / "fuentes").iterdir()]

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
    icon=str(icon),
)
COLLECT(exe, a.binaries, a.datas, name="SonidosBot")
