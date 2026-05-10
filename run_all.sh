#!/bin/bash

# Trap Ctrl+C to kill both processes
trap "kill 0" EXIT

echo "Starting Bot..."
uv run python main.py &

echo "Starting Web (Django)..."
uv run python web/manage.py runserver &

# Wait for all background processes to finish
wait
