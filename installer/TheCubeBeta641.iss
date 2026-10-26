#ifndef PayloadDir
  #define PayloadDir "..\build\installer-6.4.1-payload"
#endif
#ifndef OutputDir
  #define OutputDir "..\build\installer-6.4.1-output"
#endif
#define GameExe "The Cube Beta Halloween Update.exe"

[Setup]
AppId=TheCubeBeta641
AppName=The Cube Beta Halloween Update
AppVersion=6.4.1
AppVerName=The Cube Beta Halloween Update 6.4.1
AppPublisher=nutty'inc
AppPublisherURL=https://github.com/nuttyinc578
AppSupportURL=https://github.com/nuttyinc578/the-cube/issues
AppUpdatesURL=https://github.com/nuttyinc578/the-cube/releases
AppCopyright=Copyright (c) 2026 nutty'inc
VersionInfoVersion=6.4.1.0
VersionInfoDescription=The Cube Beta Halloween Update 6.4.1 Setup
DefaultDirName={localappdata}\Programs\The Cube Beta 6.4.1
DefaultGroupName=The Cube Beta 6.4.1
UsePreviousAppDir=no
UsePreviousGroup=no
DisableProgramGroupPage=yes
AllowNoIcons=yes
LicenseFile={#PayloadDir}\LICENCE.txt
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#GameExe}
OutputDir={#OutputDir}
OutputBaseFilename=The-Cube-Beta-Halloween-Update-6.4.1-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}\addons"
Name: "{app}\themes\inbox"
Name: "{app}\backup"

[Files]
; All game files come from the checksum-verified, published 6.4.1 portable ZIP.
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\The Cube Beta 6.4.1"; Filename: "{app}\{#GameExe}"; WorkingDir: "{app}"
Name: "{group}\Add-ons Folder"; Filename: "{sys}\explorer.exe"; Parameters: """{app}\addons"""
Name: "{group}\MIT License"; Filename: "{app}\LICENCE.txt"
Name: "{autodesktop}\The Cube Beta 6.4.1"; Filename: "{app}\{#GameExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#GameExe}"; Description: "Launch The Cube Beta 6.4.1"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
function FolderHasContents(const Folder: String): Boolean;
var
  Entry: TFindRec;
begin
  Result := False;
  if FindFirst(AddBackslash(Folder) + '*', Entry) then
  begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then
        begin
          Result := True;
          Break;
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if WizardSilent and (ExpandConstant('{param:ACCEPTMIT|no}') <> 'yes') then
  begin
    SuppressibleMsgBox('Silent setup requires /ACCEPTMIT=yes after reviewing the MIT License.', mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

procedure InitializeWizard;
begin
  WizardForm.LicenseAcceptedRadio.Caption := 'I accept the MIT License';
  WizardForm.LicenseNotAcceptedRadio.Caption := 'I do not accept the MIT License';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if FolderHasContents(ExpandConstant('{app}')) then
    Result := 'Choose an empty installation folder. This installer will not overwrite an existing or modified game. Keep your previous version and backups separately.';
end;
