; 美剧信息聚合器 — Inno Setup 6 安装脚本

#define AppName      "美剧信息聚合器"
#define AppVersion   "1.0.0"
#define AppPublisher "TV Aggregator"
#define AppExeName   "TVAggregator.exe"
#define AppURL       "https://www.themoviedb.org/"

[Setup]
AppId={{F7A3C2E1-B894-4D6F-9E52-3A1C8B0D7F24}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\TVAggregator
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Output
OutputDir=Output
OutputBaseFilename=TVAggregator_Setup_v{#AppVersion}
SetupIconFile=icon.ico
; Compression
Compression=lzma2/ultra64
SolidCompression=yes
; UI
WizardStyle=modern
WizardSizePercent=120
; Privileges — install for current user only, no UAC prompt needed
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Uninstall
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english";           MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "在桌面创建快捷方式";        GroupDescription: "附加选项:"; Flags: unchecked
Name: "startmenuicon"; Description: "在开始菜单创建快捷方式"; GroupDescription: "附加选项:"; Flags: checkedonce

[Files]
; Main executable (onefile PyInstaller output)
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start menu
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{group}\卸载 {#AppName}";   Filename: "{uninstallexe}";      Tasks: startmenuicon
; Desktop
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "立即启动 {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up config file left by the app
Type: files; Name: "{userappdata}\.tv_aggregator_config.json"
