@echo off
setlocal
cd /d "%~dp0"
dotnet run --project "%~dp0cpe\CPE.AppHost\CPE.AppHost.csproj" --launch-profile http %*
if errorlevel 1 (
  echo.
  echo The CPE Aspire host could not start. Make sure .NET 8 and Node.js are installed.
  pause
)
endlocal
