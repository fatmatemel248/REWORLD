@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo REWORLD Flask sunucu: http://127.0.0.1:5000
echo Kapatmak icin Ctrl+C
echo.
py app.py 2>nul
if errorlevel 1 python app.py
