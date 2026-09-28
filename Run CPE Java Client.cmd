@echo off
setlocal
cd /d "%~dp0"
for /f "delims=" %%J in ('where javac 2^>nul') do if not defined JAVAC_EXE set "JAVAC_EXE=%%J"
if not defined JAVAC_EXE goto failed
for %%D in ("%JAVAC_EXE%") do set "JAVA_EXE=%%~dpDjava.exe"
if not exist "%JAVA_EXE%" goto failed
if not exist "%~dp0cpe\java-client\out\com\nuttyinc\cpe\CpeClient.class" (
  "%JAVAC_EXE%" -d "%~dp0cpe\java-client\out" "%~dp0cpe\java-client\src\main\java\com\nuttyinc\cpe\CpeClient.java"
  if errorlevel 1 goto failed
)
"%JAVA_EXE%" -cp "%~dp0cpe\java-client\out" com.nuttyinc.cpe.CpeClient 127.0.0.1 4310 %*
if errorlevel 1 goto failed
endlocal
exit /b 0

:failed
echo.
echo The Java CPE client could not connect. Start Run CPE Aspire.cmd first.
pause
endlocal
exit /b 1
