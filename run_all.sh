#!/data/data/com.termux/files/usr/bin/bash

echo "========================================"
echo "   Iniciando Bot y Panel (TERMUX)"
echo "========================================"

# Matar procesos viejos para evitar conflictos
pkill -f "run_bot.py"
pkill -f "manage.py runserver"

# 1. Iniciar el Bot en segundo plano
echo "[1/2] Lanzando Bot..."
python run_bot.py > bot.log 2>&1 &

# 2. Iniciar el Panel Web Django
echo "[2/2] Lanzando Panel Web..."
echo "👉 Accede en tu navegador a: http://127.0.0.1:8000"
echo "----------------------------------------"

cd web
python manage.py runserver
