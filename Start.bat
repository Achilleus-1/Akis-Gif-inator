@echo off
cd /d "%~dp0"
if exist "Akis-Gif-inator.exe" (
    start "" "%~dp0Akis-Gif-inator.exe"
) else if exist ".venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
) else (
    echo Build Akis-Gif-inator.exe first, or install the development requirements.
    pause
)
