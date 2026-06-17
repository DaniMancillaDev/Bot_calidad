#!/bin/bash

# Trap Ctrl+C to kill both processes
trap "kill 0" EXIT

echo "Cleaning up old processes..."
pkill -9 -f "hupper|manage.py|celery|main\.py|-m main" || true
sleep 1

echo "Starting Bot..."
uv run python main.py &

echo "Starting Web (Django)..."
uv run python web/manage.py runserver &

echo "Starting Ngrok tunnel 'otro'..."
ngrok start otro &

echo "Starting Celery Worker..."
(cd web && PYTHONPATH=.. uv run celery -A calidad.celery_app worker --loglevel=info) &


# Wait for all background processes to finish
wait
