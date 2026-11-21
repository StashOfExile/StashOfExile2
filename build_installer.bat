@echo off
rem 3.0.6: builds the installer (Setup-StashOfExile2-<version>.exe) next to the exe in dist\ - the release does the same
rem on GitHub. Needs Inno Setup 6 (free, only to BUILD it - players never need it): winget install JRSoftware.InnoSetup
rem With a test build (dist\StashOfExile2-Test.exe from build_soe2.bat) it makes Setup-StashOfExile2-Test-<version>.exe:
rem "StashOfExile2 Test" in Start / Settings > Apps, its own folder, and it keeps using the test build's testdata.
rem (No ( ) blocks around the Inno Setup path: "Program Files (x86)" has a ")" that ends such a block early.)
cd /d "%~dp0"
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto found
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto found
set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto found
echo Inno Setup 6 isn't installed. Install it once with:  winget install JRSoftware.InnoSetup
goto fail

:found
set "V="
for /f "usebackq delims=" %%v in (`py -c "import re;print(re.search('APP_VERSION = .([0-9.]+).', open('stashofexile2.py', encoding='utf-8').read()).group(1))"`) do set "V=%%v"
if "%V%"=="" echo Couldn't read APP_VERSION from stashofexile2.py.& goto fail
echo Version %V%
if exist "dist\StashOfExile2-Test.exe" goto test
echo Building the installer for dist\StashOfExile2.exe ...
"%ISCC%" "/DAppVersion=%V%" installer\StashOfExile2.iss
if errorlevel 1 goto fail
goto done

:test
echo Building the TEST installer for dist\StashOfExile2-Test.exe ...
"%ISCC%" "/DAppVersion=%V%" /DTest=1 "/DSrcExe=..\dist\StashOfExile2-Test.exe" "/DDataPointer=..\dist\data_location.txt" installer\StashOfExile2.iss
if errorlevel 1 goto fail

:done
echo.
echo DONE. The installer is in %~dp0dist
dir /b dist\Setup-*.exe
pause
exit /b 0

:fail
echo.
echo Something went wrong - scroll up for the error.
pause
exit /b 1
