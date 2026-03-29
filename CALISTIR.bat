@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo REWORLD yerel sunucu: http://127.0.0.1:8080
echo Kapatmak icin Ctrl+C
echo.
py -m http.server 8080 2>nul
if errorlevel 1 python -m http.server 8080
