FROM python:3.13-slim

# Dependencias del sistema (Tesseract OCR para generación de Excel con imágenes)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copiar dependencias primero para cache de capas
COPY pyproject.toml uv.lock ./

# Instalar dependencias de producción + gunicorn
RUN uv sync --frozen --no-dev && \
    uv pip install gunicorn

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
CMD ["sh", "-c", "uv run python web/manage.py migrate && uv run gunicorn --pythonpath web config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120"]
