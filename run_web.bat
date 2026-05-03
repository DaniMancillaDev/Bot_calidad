@echo off
:: ================================
:: Script para iniciar el Panel Web
:: ================================
cd /d "%~dp0web"
echo Iniciando Panel de Calidad Web en http://127.0.0.1:8000
echo Presiona Ctrl+C para detener.
echo.
..\.venv\Scripts\python.exe manage.py runserver
pause
