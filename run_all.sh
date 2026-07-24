#!/bin/bash
trap "kill 0" EXIT

export PYTHONPATH=$(pwd)

echo "Iniciando infra Docker (Postgres + Redis)..."
docker-compose up -d postgres redis

echo "Esperando base de datos..."
until docker exec bot_calidad_postgres pg_isready -U postgres -d bot_calidad &>/dev/null; do
    sleep 1
done

echo "Ejecutando migraciones..."
uv run python web/manage.py migrate

echo "Limpiando procesos viejos..."
pkill -9 -f "main.py" || true
pkill -9 -f "celery" || true
pkill -9 -f "manage.py runserver" || true
pkill -9 -f "hupper" || true
sleep 1

echo "Starting Bot..."
uv run python main.py &

echo "Starting Web (Django)..."
uv run python web/manage.py runserver 0.0.0.0:8000 &

echo "Starting Celery Worker..."
(cd web && PYTHONPATH=.. FOTOS_PATH="$(pwd)/../media_files/fotos" THUMBS_PATH="$(pwd)/../media_files/thumbs" PROXIES_PATH="$(pwd)/../media_files/proxies" uv run celery -A calidad.celery_app worker --loglevel=info) &

# Wait for all background processes
wait
