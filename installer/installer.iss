; Instalador de Windows (Inno Setup 6). Se compila con:
;   iscc installer\installer.iss
; después de generar dist\SonidosBot con PyInstaller.
; Instala para el usuario actual, sin pedir permisos de administrador.

#define AppName "Sonidos Bot"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{8C1E5A52-6F0B-4C7E-9B7B-2C4C2F5D9A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Jose
DefaultDirName={localappdata}\Programs\SonidosBot
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SonidosBot-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\SonidosBot.exe
SetupIconFile=..\sonidos_bot\assets\icono.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
Name: "startup"; Description: "Iniciar el bot al encender Windows"; GroupDescription: "Inicio automático:"; Flags: unchecked

[InstallDelete]
; Versiones anteriores tenían un segundo programa (el menú aparte) y su acceso
; directo; el de inicio con Windows se vuelve a crear solo si se marca.
Type: files; Name: "{app}\ConfigurarSonidosBot.exe"
Type: files; Name: "{group}\Configurar Sonidos Bot.lnk"
Type: files; Name: "{autodesktop}\Configurar Sonidos Bot.lnk"
Type: files; Name: "{userstartup}\Sonidos Bot.lnk"

[Files]
Source: "..\dist\SonidosBot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Sonidos Bot"; Filename: "{app}\SonidosBot.exe"
Name: "{group}\Desinstalar Sonidos Bot"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Sonidos Bot"; Filename: "{app}\SonidosBot.exe"; Tasks: desktopicon
Name: "{userstartup}\Sonidos Bot"; Filename: "{app}\SonidosBot.exe"; Parameters: "--iniciar --minimizado"; Tasks: startup

[Run]
; Al terminar, abre la app para elegir modos, sonidos y palabras clave.
Filename: "{app}\SonidosBot.exe"; Description: "Abrir Sonidos Bot ahora"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; La configuración y los sonidos en %APPDATA%\SonidosBot se conservan a propósito.
Type: filesandordirs; Name: "{app}"
