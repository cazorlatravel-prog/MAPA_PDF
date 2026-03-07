; ────────────────────────────────────────────────────────────────────────────
; Inno Setup Script - Generador de Planos Forestales v2.0
;
; Para crear el instalador:
;   1. Descarga Inno Setup: https://jrsoftware.org/isdl.php
;   2. Primero ejecuta: python build_exe.py  (elige opción 1: carpeta)
;   3. Abre este archivo con Inno Setup y pulsa Compilar (Ctrl+F9)
;
; El instalador resultante estará en: Output/InstaladorPlanos_v2.0.exe
; ────────────────────────────────────────────────────────────────────────────

#define MyAppName "Generador de Planos Forestales"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Jose Caballero"
#define MyAppExeName "GeneradorPlanos.exe"
#define MyAppURL "https://github.com/cazorlatravel-prog/MAPA_PDF"

[Setup]
AppId={{A7F3B2E1-5C4D-4E8A-9B6F-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\GeneradorPlanos
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Carpeta donde se genera el instalador
OutputDir=Output
OutputBaseFilename=InstaladorPlanos_v{#MyAppVersion}
; Icono del instalador (descomenta si tienes el .ico)
; SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Estilo visual
WizardSizePercent=120
; Requiere admin para instalar en Program Files
PrivilegesRequired=admin
; Información adicional
VersionInfoVersion={#MyAppVersion}
VersionInfoDescription=Generador de Planos Forestales
VersionInfoCopyright=2024 {#MyAppPublisher}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el &Escritorio"; GroupDescription: "Iconos adicionales:"
Name: "quicklaunchicon"; Description: "Crear icono en la barra de &Inicio rápido"; GroupDescription: "Iconos adicionales:"; Flags: unchecked

[Files]
; Todos los archivos de la carpeta dist/GeneradorPlanos
Source: "dist\GeneradorPlanos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\*.pyc"
