# Instalador

- `sonidos_bot.spec`: empaquetado con PyInstaller. Genera `SonidosBot.exe`, una
  sola app sin consola (el menú con el bot dentro), con FFmpeg incluido.
- `installer.iss`: Inno Setup. Crea `SonidosBot-Setup-x.y.z.exe`, que instala sin
  permisos de administrador, crea un acceso directo, ofrece iniciar el bot con
  Windows y abre la app al terminar.
- `build.ps1`: hace todo lo anterior en un paso (venv, FFmpeg, tests,
  PyInstaller e Inno Setup).
- `.github/workflows/build-windows.yml`: lo mismo en GitHub Actions, para
  obtener el `.exe` sin compilar en tu PC.
