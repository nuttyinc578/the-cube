#ifndef PayloadDir
  #define PayloadDir "..\build\nightly-game"
#endif
#ifndef OutputDir
  #define OutputDir "..\build\nightly-download"
#endif

[Setup]
AppId={{{#InstallerId}}
AppName={#GameName}
AppVersion={#ReleaseVersion}
AppPublisher=nutty'inc
AppPublisherURL=https://github.com/nuttyinc578/the-cube
DefaultDirName={localappdata}\Programs\{#GameName} {#ReleaseVersion}
DefaultGroupName={#GameName} {#ReleaseVersion}
PrivilegesRequired=lowest
LicenseFile={#PayloadDir}\LICENCE.txt
SetupIconFile={#ReleaseIcon}
OutputDir={#OutputDir}
OutputBaseFilename={#SetupName}
VersionInfoVersion={#WindowsVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UsePreviousAppDir=no
UsePreviousGroup=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\{#GameExe}

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#GameName}"; Filename: "{app}\{#GameExe}"
Name: "{group}\CPE Command Prompt"; Filename: "{cmd}"; Parameters: "/K cd /d ""{app}"""; WorkingDir: "{app}"
Name: "{autodesktop}\{#GameName}"; Filename: "{app}\{#GameExe}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\{#GameExe}"; Description: "Play {#GameName}"; Flags: nowait postinstall skipifsilent

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
    Result := 'Choose a new empty folder. This release will not overwrite an existing game or backup.';
end;
