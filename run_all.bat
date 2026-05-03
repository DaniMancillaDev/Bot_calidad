@echo off
title Bot + Panel de Calidad
echo ========================================
echo   Iniciando Bot y Panel de Calidad
echo ========================================

:: Iniciar Bot en ventana separada con auto-reload (hupper)
echo [1/2] Lanzando Bot (con Hupper)...
start "BOT - Calidad" cmd /c "uv run hupper -m main || pause"

:: Iniciar Web en ventana actual
echo [2/2] Lanzando Panel Web...
echo Accede en: http://127.0.0.1:8000
echo.
cd web
uv run python manage.py runserver

pause
