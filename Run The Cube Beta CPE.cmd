@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0The Cube Beta Nightly.exe" (
  "%~dp0The Cube Beta Nightly.exe" %*
) else if exist "%~dp0The Cube Beta Halloween Update.exe" (
  "%~dp0The Cube Beta Halloween Update.exe" %*
) else (
  python "%~dp0the_cube_beta_summer.py" %*
)
if errorlevel 1 (
  echo.
  echo The Cube Beta CPE could not start.
  pause
)
endlocal
