@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0The Cube Beta Fall.exe" (
  "%~dp0The Cube Beta Fall.exe" %*
) else (
  py -3.10 "%~dp0the_cube_beta_summer.py" %*
)
if errorlevel 1 (
  echo.
  echo The Cube Beta CPE could not start.
  pause
)
endlocal