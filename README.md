# Sonidos Bot para Discord

Bot que reproduce sonidos en un canal de voz de Discord. Cada sonido se puede
disparar de cuatro formas:

| Modo | Cómo se dispara |
|---|---|
| `keyboard` | Atajo de teclado global en la PC (ej. `<ctrl>+<alt>+1`) |
| `gamepad` | Botón de un mando conectado a la PC |
| `text_keyword` | Alguien escribe la palabra clave en el chat (ej. "Chiqui Tapia") |
| `voice_keyword` | Alguien dice la palabra clave en el canal de voz (Vosk, offline) |

Los audios se toman del panel de sonidos (soundboard) del servidor y,
opcionalmente, de los adjuntos de un canal de texto. El bot los descarga y
los guarda en caché local.

## Estructura

```
bot-sonido-discord/
├── run.py                   # lanzador del bot (SonidosBot.exe)
├── configurar.py            # lanzador del menú (ConfigurarSonidosBot.exe)
├── config.example.json      # ejemplo de configuración
├── requirements.txt
├── sonidos_bot/
│   ├── __main__.py          # CLI: python -m sonidos_bot [--config] [--check]
│   ├── wizard.py            # menú de configuración (tema oscuro)       [paso 4 ✔]
│   ├── wizard_helpers.py    # lógica del menú sin ventanas              [paso 4 ✔]
│   ├── config.py            # carga, validación y guardado del config   [paso 1 ✔]
│   ├── bot.py               # cliente de Discord, comandos y recarga    [paso 2 ✔]
│   ├── sound_library.py     # descarga y caché de sonidos del canal     [paso 2 ✔]
│   ├── player.py            # reproducción en voz con FFmpeg            [paso 2 ✔]
│   └── triggers/
│       ├── base.py          # contrato común de los disparadores        [paso 1 ✔]
│       ├── keywords.py      # búsqueda de palabras (texto y voz)        [paso 3 ✔]
│       ├── keyboard.py      # pynput                                    [paso 3 ✔]
│       ├── gamepad.py       # pygame                                    [paso 3 ✔]
│       ├── text_keyword.py  # mensajes del chat                         [paso 3 ✔]
│       └── voice_keyword.py # audio del canal + Vosk                    [paso 3 ✔]
├── installer/
│   ├── sonidos_bot.spec     # PyInstaller: bot + menú + FFmpeg          [paso 4 ✔]
│   ├── installer.iss        # Inno Setup: SonidosBot-Setup.exe          [paso 4 ✔]
│   └── build.ps1            # compila todo en Windows                   [paso 4 ✔]
├── .github/workflows/       # compila el instalador en GitHub Actions   [paso 4 ✔]
└── tests/
```

## Instalación en una PC

1. Ejecuta `SonidosBot-Setup-x.y.z.exe` (no pide permisos de administrador).
2. Al terminar se abre **Configurar Sonidos Bot**: pega el token y los IDs,
   marca los modos (teclado, mando, palabra por texto, palabra por voz), revisa
   los sonidos y, si usas la voz, pulsa *Descargar modelo en español*.
3. Pulsa **Guardar e iniciar bot**.

Para añadir o cambiar sonidos y palabras clave más adelante, vuelve a abrir
*Configurar Sonidos Bot* desde el menú Inicio. Si el bot está abierto, aplica
los cambios solo. La configuración se conserva al desinstalar o actualizar.

## Generar el instalador

- **En GitHub:** al subir el proyecto a un repositorio, la acción
  *Instalador Windows* compila el `.exe` y lo deja para descargar en la
  pestaña *Actions*.
- **En tu PC Windows:** instala Python 3.12 e Inno Setup 6 y ejecuta
  `powershell -ExecutionPolicy Bypass -File installer\build.ps1`. El
  instalador queda en `dist\`.

## Preparar el bot en Discord (una sola vez)

1. En <https://discord.com/developers/applications> crea una aplicación y,
   en **Bot**, copia el token y activa **Message Content Intent**.
2. En **OAuth2 > URL Generator** marca `bot` y `applications.commands`, y los
   permisos *View Channels*, *Send Messages*, *Read Message History*,
   *Connect* y *Speak*. Abre la URL e invita el bot a tu servidor.
3. Los sonidos del panel de sonidos del servidor se usan tal cual, con el
   nombre que tienen en Discord (por ejemplo `El Manda Mas`).
4. Opcional: para usar además archivos propios, pon el ID de un canal de
   texto en *ID del canal con los audios* y sube ahí los audios. El nombre
   del archivo es el nombre del sonido; si coincide con uno del panel, gana
   el archivo. Para cambiarlo, súbelo de nuevo con el mismo nombre.

## Uso

- El bot entra solo al canal de voz configurado y vuelve a entrar si lo sacan.
- Los sonidos nuevos del panel, o los audios que se suban al canal de sonidos,
  se descargan al momento.
- Si se edita el `config.json` (a mano o con el menú del instalador), el bot
  lo recarga en unos segundos sin reiniciar: así se añaden o cambian palabras
  clave, teclas y sonidos.
- Comandos en Discord: `/sonidos` (lista), `/tocar nombre` (reproduce, con
  autocompletado) y `/recargar` (relee config y canal).

## Disparadores

- **Palabras clave (texto y voz):** cada sonido tiene una sola lista
  `keywords`, que usan los dos modos. Da igual si se escribe con mayúsculas o
  tildes, pero tiene que ser la palabra completa ("uruguayo" no salta con
  "uruguayos").
- **Voz:** descarga el modelo `vosk-model-small-es-0.42` de
  <https://alphacephei.com/vosk/models>, descomprímelo y pon su carpeta en
  `voice_model_path`. Funciona sin internet y solo escucha a personas, no a
  otros bots.
- **Teclado:** atajos globales en formato pynput: `<ctrl>+<alt>+1`, `<f9>`,
  `<shift>+a`. Funcionan aunque Discord u otro juego tenga el foco.
- **Mando:** número de botón empezando en 0. Se puede conectar o
  desconectar el mando con el bot en marcha.

## Configuración

El config se guarda en `%APPDATA%\SonidosBot\config.json` (Windows) o
`~/.config/sonidosbot/config.json`. El token también puede venir de la
variable `SONIDOS_BOT_TOKEN` para no guardarlo en disco.

- `discord`: token y los IDs del servidor, del canal de voz y del canal donde
  están los audios (en Discord: Ajustes > Avanzado > Modo desarrollador, luego
  clic derecho > Copiar ID).
- `modes`: qué disparadores están activos.
- `bindings`: por cada sonido, su `hotkey`, `gamepad_button` y `keywords`. El
  nombre del sonido es el del archivo en Discord; mayúsculas, tildes y
  `_`/espacios dan igual (`Chiqui Tapia.mp3` = `chiqui_tapia.mp3`).
- `volume` (0 a 2), `cooldown_seconds` y `voice_model_path` (carpeta del modelo
  Vosk en español, solo para `voice_keyword`).

## Desarrollo

```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest
python -m sonidos_bot --config config.example.json --check
```
