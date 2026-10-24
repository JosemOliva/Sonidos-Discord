# Estado del proyecto Sonidos Bot (24/10/2026)

## Hecho

### Paso 1: estructura y configuración
- [x] Proyecto en Python (discord.py + FFmpeg), pensado para Windows
- [x] `config.json` en `%APPDATA%\SonidosBot`, con validación (IDs, teclas y botones repetidos)
- [x] Nombres de sonidos sin distinguir mayúsculas ni tildes
- [x] El token también puede venir de la variable `SONIDOS_BOT_TOKEN`

### Paso 2: núcleo del bot
- [x] Descarga los audios del canal de Discord y los guarda en caché. Si se sube un audio con el mismo nombre, reemplaza al anterior
- [x] Entra solo al canal de voz y vuelve a entrar si lo sacan
- [x] Volumen y tiempo mínimo entre sonidos
- [x] Comandos `/sonidos`, `/tocar` y `/recargar`
- [x] Recarga el config sin reiniciar, para añadir o cambiar teclas, botones y sonidos

### Paso 3: disparadores
- [x] Atajos de teclado globales
- [x] Botones del mando, que se puede conectar o desconectar con el bot en marcha

### Paso 4: instalador y menú
- [x] Menú de configuración en tema oscuro estilo Discord con acentos naranja
- [x] Secciones Conexión, Modos, Sonidos, Ajustes y Registro
- [x] Tarjetas por sonido con botón Probar, y detección de tecla y botón del mando pulsándolos
- [x] Empaquetado con PyInstaller: un solo `SonidosBot.exe` sin consola, con FFmpeg
- [x] Instalador Inno Setup: sin pedir administrador, con accesos directos, opción de inicio con Windows y apertura del menú al terminar
- [x] Script `installer\build.ps1` y compilación automática en GitHub Actions
- [x] 39 tests automáticos que pasan

## 23/10/2026
- [x] Código subido a GitHub (JosemOliva/Sonidos-Discord) y el instalador compila en Actions
- [x] Bot creado en el portal de Discord, IDs copiados e instalador probado en la PC de Jose
- [x] PR #1: el mando Redragon Harrow Pro (Windows lo ve como Xbox 360) no se detectaba; ahora se lee también por XInput
- [x] PR #2: el bot usa los sonidos del **panel de sonidos** del servidor; el canal de audios pasa a ser opcional

## 24/10/2026 (versión 0.3.1, probada por Jose y fusionada en `main`)
- [x] Teclado y mando probados en el canal de voz con los sonidos del panel
- [x] PR #3: **una sola app**. El bot corre dentro del menú, sin consola; al cerrar la ventana sale del canal de voz. Sección *Registro* con lo que hace el bot
- [x] PR #4: se **eliminan para siempre** las palabras clave por voz y por texto (la de voz no puede funcionar: Discord cifra el audio de cada persona). Solo quedan teclado y mando
- [x] Icono propio "Botón" (play naranja) en el programa, los accesos directos, el instalador y la ventana
- [x] Fuente Montserrat incluida en la app

## Pendiente (opcional)
1. Icono en la bandeja del sistema para minimizar la app ahí.
2. Firmar el `.exe` para que Windows no muestre el aviso azul al instalar.
