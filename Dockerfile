FROM python:3.13-slim@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285

ARG SOURCE_COMMIT=unknown
LABEL org.opencontainers.image.title="Bot de Calidad web/celery" \
      org.opencontainers.image.revision="$SOURCE_COMMIT"

# Dependencias del sistema (Tesseract OCR para generación de Excel con imágenes)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /uvx /bin/

# Copiar dependencias primero para cache de capas
COPY pyproject.toml uv.lock ./

# Instalar dependencias de producción
RUN uv sync --frozen --no-dev

# Copiar código fuente de la web
COPY web/ web/
COPY shared/ shared/
COPY plantilla_reporte.xlsx ./

# Usuario no-root para seguridad
RUN useradd -m -r -u 1001 webuser && \
    mkdir -p /app/media_files/fotos /app/data /app/static_collected && \
    chown -R webuser:webuser /app

USER webuser

EXPOSE 8000

# Volúmenes: DB y media compartidos con el bot
VOLUME ["/app/media_files", "/app/data"]

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/login/')" || exit 1

# Migrate + arrancar Gunicorn (producción real)
CMD ["sh", "-c", "uv run python web/manage.py migrate && uv run python web/manage.py collectstatic --noinput && uv run gunicorn --pythonpath web config.asgi:application --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 2 --timeout 120"]
