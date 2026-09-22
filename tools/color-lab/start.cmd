@echo off
cd /d "%~dp0\..\.."
start "" "http://127.0.0.1:13229/"
python tools/color-lab/server.py
if errorlevel 1 pause
