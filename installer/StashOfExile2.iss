; StashOfExile2 installer (3.0.6, owner: "an install method ... so people stop getting StashOfExile(1).exe ... and so it
; comes up in the windows search as an installed program. I still want the portable option").
;
; - Per user: installs to %LOCALAPPDATA%\Programs\StashOfExile2 - no admin prompt, and the app can update itself
;   there the same way the portable exe does (it swaps its own exe).
; - Start menu shortcut (Windows search finds it), an optional desktop shortcut, and an uninstaller in
;   Settings > Apps.
; - Your data stays in %APPDATA%\StashOfExile2 (as with the portable exe): uninstalling never deletes it.
; - The file "installed.txt" next to the exe tells the app it was installed (updates then also update the version
;   shown in Settings > Apps).
;
; 3.1.0 (owner: "one installer that first prompts for 'Full Install' or 'Portable'"): the first page asks.
; - Full Install: all of the above.
; - Portable: one folder you pick, Desktop\StashOfExile2 by default. No shortcuts, no uninstaller, nothing in
;   Settings > Apps, no installed.txt, so it updates like the portable exe. A new player's data goes in that
;   folder's "data" folder, through data_location.txt. Someone who already has data in %APPDATA% keeps using it.
; - StashOfExile2.exe stays on every release: older apps' updater looks for that name.
;
; Built by .github/workflows/release.yml (and build_installer.bat on your own PC) with Inno Setup 6:
;   ISCC /DAppVersion=3.0.6 installer\StashOfExile2.iss      (paths in here are from this folder: ..\dist)
; -> dist\Setup-StashOfExile2-<version>.exe  (the name does NOT start with "StashOfExile2": older apps' updater takes
;    the first .exe whose name does, which must stay the portable one.)

; /DTest=1 (build_installer.bat with a test build): "StashOfExile2 Test", its own entry and folder, and the test
; build's data_location.txt (its testdata folder) - it never touches a real install or your real data.
#ifdef Test
  #define Name "StashOfExile2 Test"
  #define Dir "StashOfExile2-Test"
  #define Id "{{9C1D2E7A-5B8F-4C3E-9A61-3F0B7D2E4C15}"
#else
  #define Name "StashOfExile2"
  #define Dir "StashOfExile2"
  #define Id "{{4A06F3CE-701E-4E4F-BA95-0CF8D0630828}"
#endif

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SrcExe
  #define SrcExe "..\dist\StashOfExile2.exe"
#endif
#ifndef OutDir
  #define OutDir "..\dist"
#endif

[Setup]
AppId={#Id}
AppName={#Name}
AppVersion={#AppVersion}
AppVerName={#Name} {#AppVersion}
AppPublisher=StashOfExile
AppPublisherURL=https://github.com/StashOfExile/StashOfExile2
AppSupportURL=https://github.com/StashOfExile/StashOfExile2/issues
AppUpdatesURL=https://github.com/StashOfExile/StashOfExile2/releases
DefaultDirName={localappdata}\Programs\{#Dir}
DisableDirPage=no
DefaultGroupName={#Name}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutDir}
OutputBaseFilename=Setup-{#Dir}-{#AppVersion}
SetupIconFile=..\stashofexile2.ico
UninstallDisplayIcon={app}\StashOfExile2.exe
UninstallDisplayName={#Name}
Uninstallable=not IsPortable
CreateUninstallRegKey=not IsPortable
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Make a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked; Check: not IsPortable

[Files]
Source: "{#SrcExe}"; DestDir: "{app}"; DestName: "StashOfExile2.exe"; Flags: ignoreversion
Source: "installed.txt"; DestDir: "{app}"; Flags: ignoreversion; Check: not IsPortable
#ifdef Test
Source: "{#DataPointer}"; DestDir: "{app}"; DestName: "data_location.txt"; Flags: ignoreversion
#endif

[Icons]
Name: "{autoprograms}\{#Name}"; Filename: "{app}\StashOfExile2.exe"; Check: not IsPortable
Name: "{autodesktop}\{#Name}"; Filename: "{app}\StashOfExile2.exe"; Tasks: desktopicon; Check: not IsPortable

[Run]
Filename: "{app}\StashOfExile2.exe"; Description: "Start {#Name}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; what an update leaves next to the exe (the app deletes it itself; this is in case it couldn't)
Type: files; Name: "{app}\StashOfExile2_update.exe"
Type: files; Name: "{app}\update_log.txt"

[Code]
var
  ModePage: TInputOptionWizardPage;
  FullDir: String;

// The first page: Full Install or Portable. A silent install is a Full Install.
procedure InitializeWizard;
begin
  ModePage := CreateInputOptionPage(wpWelcome, 'How do you want it?',
    'Pick one. Run Setup again any time to change it.',
    'Full Install adds it to your Start menu, Windows search and Settings > Apps, with an uninstaller.' + #13#10 + #13#10 +
    'Portable puts everything in one folder you pick. Nothing else on your PC changes. Move or delete the folder ' +
    'any time.', True, False);
  ModePage.Add('Full Install, recommended');
  ModePage.Add('Portable');
  ModePage.Values[0] := True;
end;

function IsPortable: Boolean;
begin
  Result := (ModePage <> nil) and ModePage.Values[1];
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ModePage.ID then
  begin
    if FullDir = '' then
      FullDir := WizardForm.DirEdit.Text;
    if IsPortable then
      WizardForm.DirEdit.Text := ExpandConstant('{userdesktop}\{#Dir}')
    else
      WizardForm.DirEdit.Text := FullDir;
  end;
end;

// Full Install goes to its usual folder without asking; Portable asks where.
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpSelectDir) and not IsPortable;
end;

// Portable: a new player's data lives next to the app. Someone who already uses the app keeps their data where it
// is, and a portable copy that already has its pointer keeps it.
procedure CurStepChanged(CurStep: TSetupStep);
var
  PointerFile: String;
begin
  if (CurStep = ssPostInstall) and IsPortable then
  begin
    PointerFile := ExpandConstant('{app}\data_location.txt');
    if not FileExists(PointerFile) and not DirExists(ExpandConstant('{userappdata}\StashOfExile2')) then
      SaveStringToFile(PointerFile, ExpandConstant('{app}\data'), False);
  end;
end;
