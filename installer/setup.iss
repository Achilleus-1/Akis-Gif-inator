#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#ifndef PayloadDir
  #define PayloadDir "..\build\installer-payload"
#endif

[Setup]
AppId={{F10C8C96-254E-4B96-94D1-5723C765DA3B}
AppName=Aki's Gif-inator
AppVersion={#AppVersion}
AppPublisher=Achilleus
AppPublisherURL=https://linktr.ee/achilleus_
AppSupportURL=https://github.com/Achilleus-1/Akis-Gif-inator/issues
AppUpdatesURL=https://github.com/Achilleus-1/Akis-Gif-inator/releases
DefaultDirName={localappdata}\Programs\Akis-Gif-inator
DefaultGroupName=Aki's Gif-inator
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=Akis-Gif-inator-{#AppVersion}-windows-x64-setup
SetupIconFile=..\assets\gif-inator.ico
UninstallDisplayIcon={app}\assets\gif-inator.ico
LicenseFile=..\LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
UninstallDisplayName=Aki's Gif-inator

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "ffmpeg"; Description: "Download FFmpeg from Gyan if it isn't already on PATH"; GroupDescription: "Dependencies (internet required; publisher SHA-256 checked):"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Install-Runtime.ps1"; Flags: dontcopy
Source: "dependencies.json"; Flags: dontcopy
Source: "{tmp}\dependency-stage\runtime\*"; DestDir: "{app}\runtime"; Flags: external ignoreversion recursesubdirs createallsubdirs
Source: "{tmp}\dependency-stage\bin\*"; DestDir: "{app}\bin"; Flags: external ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{tmp}\dependency-stage\dependency-notices\*"; DestDir: "{app}\dependency-notices"; Flags: external ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{tmp}\dependency-stage\runtime-installed.json"; DestDir: "{app}"; Flags: external ignoreversion

[Icons]
Name: "{group}\Aki's Gif-inator"; Filename: "{app}\Akis-Gif-inator.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\gif-inator.ico"
Name: "{autodesktop}\Aki's Gif-inator"; Filename: "{app}\Akis-Gif-inator.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\gif-inator.ico"; Tasks: desktopicon
Name: "{group}\Uninstall Aki's Gif-inator"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Akis-Gif-inator.exe"; WorkingDir: "{app}"; Description: "Launch Aki's Gif-inator"; Flags: nowait postinstall skipifsilent

[Code]
var
  DownloadPage: TDownloadWizardPage;
  DependencyCache: String;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage('Download dependencies', 'Publisher files are checked with SHA-256 before installation.', nil);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpReady then begin
    DownloadPage.Clear;
    DependencyCache := ExpandConstant('{param:DependencyCache|}');
    #include "..\build\installer-dependencies.iss"
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        if not DownloadPage.AbortedByUser then
          SuppressibleMsgBox(GetExceptionMessage, mbCriticalError, MB_OK, IDOK);
        Result := False;
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Params: String;
  ExitCode: Integer;
begin
  Result := '';
  ExtractTemporaryFile('Install-Runtime.ps1');
  ExtractTemporaryFile('dependencies.json');
  WizardForm.StatusLabel.Caption := 'Extracting and verifying the private app runtime...';
  Params := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\Install-Runtime.ps1') +
    '" -Destination "' + ExpandConstant('{tmp}\dependency-stage') + '" -Manifest "' + ExpandConstant('{tmp}\dependencies.json') + '" -Cache "' + ExpandConstant('{tmp}') + '"';
  if not WizardIsTaskSelected('ffmpeg') then Params := Params + ' -SkipFFmpeg';
  if ExpandConstant('{param:ForceFFmpeg|0}') = '1' then Params := Params + ' -ForceFFmpeg';
  if not ExecAndLogOutput(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Params, '', SW_SHOWNORMAL, ewWaitUntilTerminated, ExitCode, nil) then
    Result := 'Unable to start dependency setup. Nothing has been installed.'
  else if ExitCode <> 0 then
    Result := 'Dependency download or verification failed. Check your internet connection and try again. Nothing has been installed.';
end;
