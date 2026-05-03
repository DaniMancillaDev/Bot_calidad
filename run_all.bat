@echo off
title Bot + Panel de Calidad
echo ========================================
echo   Iniciando Bot y Panel de Calidad
echo ========================================

:: Iniciar Bot en ventana separada
echo [1/2] Lanzando Bot...
start "BOT - Calidad" cmd /c ".venv\Scripts\python.exe main.py || pause"

:: Iniciar Web en ventana actual
echo [2/2] Lanzando Panel Web...
echo Accede en: http://127.0.0.1:8000
echo.
cd web
..\.venv\Scripts\python.exe manage.py runserver

pause
