@echo off
rem Abre o app em modo desenvolvimento (sem console).
rem Para distribuir aos analistas, use o executavel: dist\ImportadorCameras.exe
cd /d "%~dp0"
start "" pythonw run_app.py
