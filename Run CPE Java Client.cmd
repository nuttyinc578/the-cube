@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0cpe\java-client\out\com\nuttyinc\cpe\CpeClient.class" (
  javac -d "%~dp0cpe\java-client\out" "%~dp0cpe\java-client\src\main\java\com\nuttyinc\cpe\CpeClient.java"
  if errorlevel 1 goto failed
)
java -cp "%~dp0cpe\java-client\out" com.nuttyinc.cpe.CpeClient 127.0.0.1 4310 %*
if errorlevel 1 goto failed
endlocal
exit /b 0

:failed
echo.
echo The Java CPE client could not connect. Start Run CPE Aspire.cmd first.
pause
endlocal
exit /b 1
