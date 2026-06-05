#!/bin/bash

# Trap Ctrl+C to kill both processes
trap "kill 0" EXIT

echo "Starting Bot..."
uv run python main.py &

echo "Starting Web (Django)..."
uv run python web/manage.py runserver &

echo "Starting Ngrok..."
ngrok http 8000 &

echo "Starting Celery Worker..."
(cd web && PYTHONPATH=.. uv run celery -A calidad.celery_app worker --loglevel=info) &


# Wait for all background processes to finish
wait
