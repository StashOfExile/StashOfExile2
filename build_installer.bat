@echo off
rem 3.0.6: builds the installer (Setup-StashOfExile2-<version>.exe) next to the exe in dist\ - the release does the same
rem on GitHub. Needs Inno Setup 6 (free): winget install JRSoftware.InnoSetup
rem With a test build (dist\StashOfExile2-Test.exe from build_soe2.bat) it makes Setup-StashOfExile2-Test-<version>.exe:
rem "StashOfExile2 Test" in Start / Settings > Apps, its own folder, and it keeps using the test build's testdata.
cd /d "%~dp0"
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 isn't installed. Install it once with:  winget install JRSoftware.InnoSetup
  pause
  exit /b 1
)
for /f "usebackq delims=" %%v in (`py -c "import re;print(re.search(r'APP_VERSION = \"([^\"]+)\"', open('stashofexile2.py', encoding='utf-8').read()).group(1))"`) do set "V=%%v"
if exist "dist\StashOfExile2-Test.exe" (
  "%ISCC%" "/DAppVersion=%V%" /DTest=1 "/DSrcExe=..\dist\StashOfExile2-Test.exe" "/DDataPointer=..\dist\data_location.txt" installer\StashOfExile2.iss
) else (
  "%ISCC%" "/DAppVersion=%V%" installer\StashOfExile2.iss
)
if errorlevel 1 (
  echo Something went wrong - scroll up for the error.
  pause
  exit /b 1
)
echo.
echo DONE. The installer is in %~dp0dist
dir /b dist\Setup-*.exe
pause
