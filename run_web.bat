@echo off
:: ================================
:: Script para iniciar el Panel Web
:: ================================
cd /d "%~dp0web"
echo Iniciando Panel de Calidad Web en http://127.0.0.1:8000
echo Presiona Ctrl+C para detener.
echo.
uv run python manage.py runserver
pause
