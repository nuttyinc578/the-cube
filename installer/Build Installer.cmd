@echo off
setlocal
cd /d "%~dp0"

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
  echo Inno Setup 6 was not found.
  echo Install it from https://jrsoftware.org/isdl.php and run this file again.
  pause
  exit /b 1
)

"%ISCC%" "%~dp0TheCubeBetaFall.iss"
if errorlevel 1 (
  echo.
  echo Installer build failed.
  pause
  exit /b 1
)

echo.
echo Installer created in: %~dp0..\installer-output
endlocal
