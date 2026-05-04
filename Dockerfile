FROM python:3.13-slim

# Dependencias del sistema (Tesseract OCR)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copiar archivos de dependencias primero (cache de Docker)
COPY pyproject.toml uv.lock ./

# Instalar dependencias Python
RUN uv sync --frozen --no-dev

# Copiar código fuente
COPY bot/ bot/
COPY web/ web/
COPY shared/ shared/
COPY database.py main.py ./
COPY plantilla_reporte.xlsx ./

# Crear directorios para datos en runtime
RUN mkdir -p fotos media

# Instalar gunicorn para produccion
RUN uv pip install gunicorn

# Exponer puerto de Django
EXPOSE 8000

# Healthcheck: verificar que Django responde
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/login/')" || exit 1

# Arrancar bot + web
CMD ["sh", "-c", "uv run python web/manage.py migrate --run-syncdb && uv run python main.py"]
