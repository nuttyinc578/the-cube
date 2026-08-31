#define MyAppName "The Cube Beta Fall Edition"
#define MyAppVersion "6.2.1"
#define MyAppPublisher "nutty'inc"
#define MyAppExeName "The Cube Beta Fall.exe"

[Setup]
AppId={{728303EA-A1F8-438C-BEEF-0F164EB35252}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/nuttyinc578
AppSupportURL=https://github.com/nuttyinc578
AppUpdatesURL=https://github.com/nuttyinc578
AppCopyright=Copyright (c) 2026 nutty'inc
AppComments=Interactive physics sandbox powered by CPE and IPE
VersionInfoVersion=6.2.1.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
VersionInfoCopyright=Copyright (c) 2026 nutty'inc
DefaultDirName={localappdata}\Programs\The Cube Beta Fall Edition
DefaultGroupName=The Cube Beta Fall Edition
DisableProgramGroupPage=yes
AllowNoIcons=yes
LicenseFile=..\LICENCE.txt
OutputDir=..\installer-output
OutputBaseFilename=The-Cube-Beta-Fall-6.2.1-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
UsePreviousAppDir=yes
UsePreviousGroup=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addonsshortcut"; Description: "Add an Add-ons Folder shortcut to the Start Menu"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}\addons"
Name: "{app}\addons\mods"

[Files]
; Main Fall Edition game and documentation
Source: "..\dist\The Cube Beta Fall.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENCE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

; CPE launchers
Source: "..\dist\Run The Cube Beta CPE.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\Run CPE Aspire.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\Run CPE Java Client.cmd"; DestDir: "{app}"; Flags: ignoreversion

; Current add-ons. Runtime state, backups, caches, and old terms files are intentionally excluded.
Source: "..\dist\addons\*.py"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\*.pyc"; DestDir: "{app}\addons"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\dist\addons\*.rb"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\*.bat"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\*.batch"; DestDir: "{app}\addons"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\dist\addons\*.cs"; DestDir: "{app}\addons"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\dist\addons\*.c#"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\*.jar"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\README.md"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\NUTTYMOD_README.md"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\nuttymod_update_config.json"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\mods\*"; DestDir: "{app}\addons\mods"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\addons\nuttymod_bootstrap\nuttymod_*"; DestDir: "{app}\addons\nuttymod_bootstrap"; Flags: ignoreversion
Source: "..\dist\addons\nuttymod_bootstrap\package.json"; DestDir: "{app}\addons\nuttymod_bootstrap"; Flags: ignoreversion

; CPE bridge, Go cache, Java client, and Aspire host
Source: "..\dist\cpe\README.md"; DestDir: "{app}\cpe"; Flags: ignoreversion
Source: "..\dist\cpe\node-bridge\*"; DestDir: "{app}\cpe\node-bridge"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\cpe\go-cache\*.go"; DestDir: "{app}\cpe\go-cache"; Flags: ignoreversion
Source: "..\dist\cpe\go-cache\*.mod"; DestDir: "{app}\cpe\go-cache"; Flags: ignoreversion
Source: "..\dist\cpe\go-cache\bin\cpe-go-cache.exe"; DestDir: "{app}\cpe\go-cache\bin"; Flags: ignoreversion
Source: "..\dist\cpe\java-client\*"; DestDir: "{app}\cpe\java-client"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\cpe\CPE.AppHost\CPE.AppHost.csproj"; DestDir: "{app}\cpe\CPE.AppHost"; Flags: ignoreversion
Source: "..\dist\cpe\CPE.AppHost\Program.cs"; DestDir: "{app}\cpe\CPE.AppHost"; Flags: ignoreversion
Source: "..\dist\cpe\CPE.AppHost\Properties\launchSettings.json"; DestDir: "{app}\cpe\CPE.AppHost\Properties"; Flags: ignoreversion

[Icons]
Name: "{group}\The Cube Beta Fall Edition"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Add-ons Folder"; Filename: "{sys}\explorer.exe"; Parameters: """{app}\addons"""; Tasks: addonsshortcut
Name: "{group}\MIT License"; Filename: "{app}\LICENCE.txt"
Name: "{autodesktop}\The Cube Beta Fall Edition"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch The Cube Beta Fall Edition"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel1.Caption := 'Welcome to The Cube Beta Fall Edition 6.2.1 Setup';
  WizardForm.WelcomeLabel2.Caption :=
    'This setup installs the Fall Edition game, CPE physics support, and the current add-ons.' + #13#10 + #13#10 +
    'You must read and accept the MIT License before installation can continue.';
  WizardForm.LicenseAcceptedRadio.Caption := 'I accept the MIT License';
  WizardForm.LicenseNotAcceptedRadio.Caption := 'I do not accept the MIT License';
end;
