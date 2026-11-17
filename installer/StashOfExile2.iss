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
DisableDirPage=auto
DefaultGroupName={#Name}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutDir}
OutputBaseFilename=Setup-{#Dir}-{#AppVersion}
SetupIconFile=..\stashofexile2.ico
UninstallDisplayIcon={app}\StashOfExile2.exe
UninstallDisplayName={#Name}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Make a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#SrcExe}"; DestDir: "{app}"; DestName: "StashOfExile2.exe"; Flags: ignoreversion
Source: "installed.txt"; DestDir: "{app}"; Flags: ignoreversion
#ifdef Test
Source: "{#DataPointer}"; DestDir: "{app}"; DestName: "data_location.txt"; Flags: ignoreversion
#endif

[Icons]
Name: "{autoprograms}\{#Name}"; Filename: "{app}\StashOfExile2.exe"
Name: "{autodesktop}\{#Name}"; Filename: "{app}\StashOfExile2.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StashOfExile2.exe"; Description: "Start {#Name}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; what an update leaves next to the exe (the app deletes it itself; this is in case it couldn't)
Type: files; Name: "{app}\StashOfExile2_update.exe"
Type: files; Name: "{app}\update_log.txt"
