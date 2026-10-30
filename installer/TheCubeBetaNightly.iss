#ifndef PayloadDir
  #define PayloadDir "..\build\nightly-game"
#endif
#ifndef OutputDir
  #define OutputDir "..\build\nightly-download"
#endif

[Setup]
AppId={{4EF5D2BD-C720-4355-92A6-3349EA2A9942}
AppName=The Cube Beta Nightly
AppVersion=6.4.2-nightly
AppPublisher=nutty'inc
AppPublisherURL=https://github.com/nuttyinc578/the-cube
DefaultDirName={localappdata}\Programs\The Cube Beta Nightly 6.4.2
DefaultGroupName=The Cube Beta Nightly
PrivilegesRequired=lowest
LicenseFile={#PayloadDir}\LICENCE.txt
SetupIconFile=..\icon.ico
OutputDir={#OutputDir}
OutputBaseFilename=The-Cube-Beta-6.4.2-nightly-Setup
VersionInfoVersion=6.4.2.0
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
UninstallDisplayIcon={app}\The Cube Beta Nightly.exe

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\The Cube Beta Nightly"; Filename: "{app}\The Cube Beta Nightly.exe"
Name: "{autodesktop}\The Cube Beta Nightly"; Filename: "{app}\The Cube Beta Nightly.exe"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\The Cube Beta Nightly.exe"; Description: "Play The Cube Beta Nightly"; Flags: nowait postinstall skipifsilent

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
    Result := 'Choose a new empty folder. This nightly will not overwrite an existing game or backup.';
end;
