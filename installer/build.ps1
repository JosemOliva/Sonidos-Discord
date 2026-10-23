# Genera el instalador de Windows desde cero.
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1
# Requisitos: Python 3.12 y Inno Setup 6 (https://jrsoftware.org/isdl.php).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-dev.txt

# FFmpeg (build "essentials" de gyan.dev): solo hace falta ffmpeg.exe.
$Vendor = "installer\vendor"
if (-not (Test-Path "$Vendor\ffmpeg.exe")) {
    New-Item -ItemType Directory -Force $Vendor | Out-Null
    $Zip = "$env:TEMP\ffmpeg.zip"
    Invoke-WebRequest "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $Zip
    $Tmp = "$env:TEMP\ffmpeg-extract"
    if (Test-Path $Tmp) { Remove-Item -Recurse -Force $Tmp }
    Expand-Archive $Zip -DestinationPath $Tmp
    Copy-Item (Get-ChildItem $Tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName "$Vendor\ffmpeg.exe"
}

.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\pyinstaller --noconfirm --clean installer\sonidos_bot.spec

$Version = (.\.venv\Scripts\python -c "import sonidos_bot; print(sonidos_bot.__version__)").Trim()
$Iscc = @("iscc", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
    Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
if (-not $Iscc) { throw "No encuentro Inno Setup 6 (ISCC.exe). Instálalo y vuelve a ejecutar." }
& $Iscc "/DAppVersion=$Version" installer\installer.iss
Write-Host "Listo: dist\SonidosBot-Setup-$Version.exe"
