#!/usr/bin/env bash
# dev.sh — Entorno de desarrollo local
#
# USO:
#   ./dev.sh         → levanta todo (infra + web + bot + celery)
#   ./dev.sh infra   → solo postgres + redis (sin web ni bot)
#   ./dev.sh web     → solo Django
#   ./dev.sh bot     → solo bot Telegram
#   ./dev.sh celery  → solo worker Celery
#   ./dev.sh migrate → corre migraciones
#   ./dev.sh stop    → baja la infra Docker

set -euo pipefail

# ── Cargar variables de entorno local ─────────────────────────────────────────
ENV_FILE=".env.local"
if [[ ! -f "$ENV_FILE" ]]; then
    ENV_FILE=".env"
fi
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: Ni .env ni .env.local existen."
    exit 1
fi
set -a
source "$ENV_FILE"
export PYTHONPATH=$(pwd)
set +a

# ── Colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[dev]${NC} $*"; }
warn()  { echo -e "${YELLOW}[dev]${NC} $*"; }
error() { echo -e "${RED}[dev]${NC} $*"; }

# ── Levantar infra Docker (solo postgres + redis) ─────────────────────────────
infra_up() {
    info "Levantando postgres + redis..."
    docker-compose up -d postgres redis
    info "Esperando postgres..."
    until docker exec bot_calidad_postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" &>/dev/null && \
          docker exec bot_calidad_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" &>/dev/null; do
        sleep 1
    done
    info "Postgres listo ✓"
    until docker exec bot_calidad_redis redis-cli ping &>/dev/null; do
        sleep 1
    done
    info "Redis listo ✓"
}

infra_down() {
    warn "Bajando infra Docker..."
    docker-compose stop postgres redis
    warn "Aniquilando procesos locales (bot, web, celery, hupper)..."
    pkill -9 -f "main.py" || true
    pkill -9 -f "celery" || true
    pkill -9 -f "manage.py runserver" || true
    pkill -9 -f "hupper" || true
    
    # Aniquilar cualquier otro dev.sh en background (excepto este mismo)
    # para evitar que su trap de EXIT detenga los contenedores asincrónicamente
    for pid in $(pgrep -f "dev.sh" || true); do
        if [ "$pid" != "$$" ] && [ "$pid" != "$PPID" ]; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    info "Limpieza completada ✓"
}

migrate() {
    info "Corriendo migraciones..."
    uv run python web/manage.py migrate
    info "Migraciones listas ✓"
}

run_web() {
    info "Iniciando Django en localhost:8000..."
    uv run python web/manage.py runserver 0.0.0.0:8000
}

run_bot() {
    info "Iniciando bot Telegram (con hupper)..."
    uv run hupper -m main
}

run_celery() {
    info "Iniciando worker Celery..."
    cd web && uv run celery -A calidad.celery_app worker --loglevel=info --concurrency=2
}

run_all() {
    infra_down # Limpiar zombis antes de empezar
    infra_up
    migrate

    trap "warn 'Deteniendo procesos...'; kill 0; infra_down" EXIT INT TERM

    info "Iniciando web + bot (hupper) + celery en paralelo..."
    uv run python web/manage.py runserver 0.0.0.0:8000 &
    uv run hupper -m main &
    (cd web && uv run celery -A calidad.celery_app worker --loglevel=info --concurrency=2) &

    wait
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
CMD="${1:-all}"

case "$CMD" in
    infra)   infra_up ;;
    stop)    infra_down ;;
    migrate) infra_up && migrate ;;
    web)     infra_up && migrate && run_web ;;
    bot)     infra_up && run_bot ;;
    celery)  infra_up && run_celery ;;
    all)     run_all ;;
    *)
        echo "Uso: $0 [all|infra|web|bot|celery|migrate|stop]"
        exit 1
        ;;
esac
