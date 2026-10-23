# Estado del proyecto Sonidos Bot (21/10/2026)

## Hecho

### Paso 1: estructura y configuración
- [x] Proyecto en Python (discord.py + FFmpeg), pensado para Windows
- [x] `config.json` en `%APPDATA%\SonidosBot`, con validación (IDs, teclas, botones y palabras repetidas)
- [x] Palabras clave sin distinguir mayúsculas ni tildes
- [x] El token también puede venir de la variable `SONIDOS_BOT_TOKEN`

### Paso 2: núcleo del bot
- [x] Descarga los audios del canal de Discord y los guarda en caché. Si se sube un audio con el mismo nombre, reemplaza al anterior
- [x] Entra solo al canal de voz y vuelve a entrar si lo sacan
- [x] Volumen y tiempo mínimo entre sonidos
- [x] Comandos `/sonidos`, `/tocar` y `/recargar`
- [x] Recarga el config sin reiniciar, para añadir o cambiar palabras y sonidos

### Paso 3: disparadores
- [x] Palabra clave por texto: "Chiqui Tapia", "manda más", "uruguayo"
- [x] Palabra clave por voz con Vosk en español, sin internet y con la misma lista que la de texto
- [x] Atajos de teclado globales
- [x] Botones del mando, que se puede conectar o desconectar con el bot en marcha

### Paso 4: instalador y menú
- [x] Menú de configuración en tema oscuro estilo Discord con acentos naranja
- [x] Secciones Conexión, Modos, Sonidos y Ajustes
- [x] Tarjetas por sonido con botón Probar, y detección de tecla y botón del mando pulsándolos
- [x] Descarga del modelo de voz desde el menú
- [x] Empaquetado con PyInstaller (`SonidosBot.exe` + `ConfigurarSonidosBot.exe` + FFmpeg)
- [x] Instalador Inno Setup: sin pedir administrador, con accesos directos, opción de inicio con Windows y apertura del menú al terminar
- [x] Script `installer\build.ps1` y compilación automática en GitHub Actions
- [x] 39 tests automáticos que pasan

## Pendiente para la próxima sesión

### Lo que tienes que hacer tú
1. **Crear el repositorio en GitHub** y conectarlo, para subir el código. Así GitHub compila el instalador `.exe` solo.
2. **Crear el bot en el portal de Discord**: copiar el token, activar "Message Content Intent" e invitarlo al servidor (los pasos están en el README).
3. **Subir los 3 audios al canal de sonidos**: `chiqui_tapia.mp3`, `manda_mas.mp3` y `uruguayo.mp3`, o ajustar los nombres en el menú.
4. **Pasar los IDs** del servidor, del canal de voz y del canal de audios (o cargarlos directamente en el menú).

### Lo que haremos juntos
5. **Generar el instalador `.exe`** en GitHub Actions y revisar que compile sin errores.
6. **Prueba real en tu PC con Windows**: instalar, configurar y probar cada modo (texto, voz, teclado y mando).
7. **Verificar la palabra por voz**. Es el mayor riesgo: Discord ahora cifra el audio de voz, y la librería que lo recibe podría no soportarlo todavía. Si falla, el plan B es escuchar el micrófono de tu PC, aunque así solo se detectaría tu voz.
8. **Ajustar el reconocimiento** si Vosk entiende mal "Chiqui Tapia" (por ejemplo, añadiendo variantes de la palabra).
9. **Detalles opcionales**: icono propio para el programa, icono en la bandeja del sistema en lugar de la ventana de consola, y firma del `.exe` para evitar el aviso de Windows SmartScreen.
