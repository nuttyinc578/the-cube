#define MyAppName "The Cube Beta Halloween Update"
#define MyAppVersion "6.4.0"
#define MyAppPublisher "nutty'inc"
#define MyAppExeName "The Cube Beta Halloween Update.exe"

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
AppComments=Halloween Broken Lands physics sandbox powered by CPE and IPE
VersionInfoVersion=6.4.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
VersionInfoCopyright=Copyright (c) 2026 nutty'inc
DefaultDirName={localappdata}\Programs\The Cube Beta Halloween Update
DefaultGroupName=The Cube Beta Halloween Update
DisableProgramGroupPage=yes
AllowNoIcons=yes
LicenseFile=..\LICENCE.txt
OutputDir=..\installer-output
OutputBaseFilename=The-Cube-Beta-Halloween-Update-6.4.0-Setup
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
Name: "{app}\addons\nuttymod"
Name: "{app}\themes\inbox"
Name: "{app}\backup\themes"
Name: "{app}\legacy-versions"
Name: "{app}\backup\og"
Name: "{app}\og-recovery"

[Files]
; Main Halloween Edition game and documentation
Source: "..\dist\The Cube Beta Halloween Update.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENCE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\dist\cpe-backend.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\dist\cpe_rephysics\*"; DestDir: "{app}\cpe_rephysics"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "..\dist\cpeloader.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\cpeloader_core_runtime.js"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\cpeloader_core.rb"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\cpeloader_manifest.json"; DestDir: "{app}"; Flags: ignoreversion

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
Source: "..\dist\addons\*.jar"; DestDir: "{app}\addons"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\dist\addons\README.md"; DestDir: "{app}\addons"; Flags: ignoreversion
Source: "..\dist\addons\mods\*"; DestDir: "{app}\addons\mods"; Flags: ignoreversion recursesubdirs createallsubdirs
; NuttyMod is deliberately isolated so the normal add-on scan cannot execute it.
Source: "..\dist\addons\nuttymod\*"; DestDir: "{app}\addons\nuttymod"; Flags: ignoreversion recursesubdirs createallsubdirs

; Verified Theme Store. Runtime inbox and backups start empty.
Source: "..\dist\themes\*"; DestDir: "{app}\themes"; Flags: ignoreversion recursesubdirs createallsubdirs

; CPE bridge, Go cache, Java client, and Aspire host
Source: "..\dist\cpe\*"; DestDir: "{app}\cpe"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Installer updates restore the default loader lock and replace the trusted baseline.
Type: files; Name: "{app}\cpeloader_state.json"
; Move optional gameplay extensions out of the normal scan path during upgrade.
Type: files; Name: "{app}\addons\fun_mode.py"
Type: files; Name: "{app}\addons\fun_mode.rb"
Type: files; Name: "{app}\addons\physics_3d.py"
Type: files; Name: "{app}\addons\physics_3d.rb"
; Remove NuttyMod's old auto-scanned layout during upgrade.
Type: files; Name: "{app}\addons\_nuttymod_connection.py"
Type: files; Name: "{app}\addons\_nuttymod_v140_patch.py"
Type: files; Name: "{app}\addons\nuttymod_loader.py"
Type: files; Name: "{app}\addons\nuttymod_loader.rb"
Type: files; Name: "{app}\addons\nuttymod_service.py"
Type: files; Name: "{app}\addons\nuttymod_loader_patch.jar"
Type: files; Name: "{app}\addons\nuttymod_root_mode_profile.jar"
Type: files; Name: "{app}\addons\nuttymod_update_config.json"
Type: files; Name: "{app}\addons\nuttymod_runtime_v122.pyc"
Type: filesandordirs; Name: "{app}\addons\nuttymod_bootstrap"
Type: files; Name: "{app}\nuttymod_core.py"
Type: files; Name: "{app}\nuttymod_cube_core.py"
Type: files; Name: "{app}\nuttymod_service.py"
Type: files; Name: "{app}\nuttymod_loader_patch.jar"
Type: files; Name: "{app}\nuttymod_root_mode_profile.jar"

[Icons]
Name: "{group}\The Cube Beta Halloween Update"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Add-ons Folder"; Filename: "{sys}\explorer.exe"; Parameters: """{app}\addons"""; Tasks: addonsshortcut
Name: "{group}\Theme Store Folder"; Filename: "{sys}\explorer.exe"; Parameters: """{app}\themes"""
Name: "{group}\MIT License"; Filename: "{app}\LICENCE.txt"
Name: "{autodesktop}\The Cube Beta Halloween Update"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch The Cube Beta Halloween Update"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel1.Caption := 'Welcome to The Cube Beta Halloween Update 6.4.0 Setup';
  WizardForm.WelcomeLabel2.Caption :=
    'This setup installs the Halloween Broken Lands update, CPE physics support, OG.exe backup-first recovery, the Theme Store, and the current add-ons.' + #13#10 + #13#10 +
    'You must read and accept the MIT License before installation can continue.';
  WizardForm.LicenseAcceptedRadio.Caption := 'I accept the MIT License';
  WizardForm.LicenseNotAcceptedRadio.Caption := 'I do not accept the MIT License';
end;
