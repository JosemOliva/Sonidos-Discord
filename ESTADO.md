# Estado del proyecto Sonidos Bot (23/10/2026)

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

## 23/10/2026
- [x] Código subido a GitHub (JosemOliva/Sonidos-Discord) y el instalador compila en Actions
- [x] Bot creado en el portal de Discord, IDs copiados e instalador probado en la PC de Jose
- [x] PR #1: el mando Redragon Harrow Pro (Windows lo ve como Xbox 360) no se detectaba; ahora se lee también por XInput
- [x] PR #2: el bot usa los sonidos del **panel de sonidos** del servidor; el canal de audios pasa a ser opcional

## Pendiente para la próxima sesión
1. **Admin del servidor**: aceptar el bot con el enlace de invitación (Jose no es administrador).
2. **Instalar la compilación #4** (rama `sonidos-soundboard`) y comprobar:
   - que *Detectar* reconoce los botones del mando;
   - que el desplegable de Sonidos muestra los del panel ("El chiqui Ackerman", "El Manda Mas"...), con el canal de audios vacío.
3. Si todo va bien, **fusionar PR #1 y PR #2** en `main`.
4. **Prueba real** con el bot en el canal de voz: texto, teclado, mando y voz.
5. **Verificar la palabra por voz** (riesgo: cifrado de voz de Discord; plan B: micrófono de la PC).
6. **Ajustar el reconocimiento** de Vosk si entiende mal las palabras.
7. **Opcionales**: icono propio, icono en la bandeja del sistema y firma del `.exe`.
