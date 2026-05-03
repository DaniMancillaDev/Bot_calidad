# Bot de Calidad - Sistema de Reportes

Sistema integral para la gestión de reportes de calidad mediante un bot de Telegram y un panel administrativo web.

## 🚀 Características
- **Bot de Telegram:** Registro de reportes con fotos, validación de usuarios y flujo conversacional.
- **Panel Web (Django):** Visualización de reportes, gestión de usuarios, galería de fotos y descarga de reportes Excel.
- **Inteligencia Artificial:** Detección automática de la orientación de imágenes mediante ONNX.
- **OCR:** Extracción de texto de imágenes usando Tesseract.
- **Reportes:** Generación automática de archivos Excel con fotos incrustadas.

## 🛠️ Tecnologías
- **Core:** Python 3.12+
- **Web:** Django 6.0
- **Bot:** python-telegram-bot
- **IA/Procesamiento:**
  - ONNX Runtime (Detección de ángulo)
  - Pillow (Manipulación de imagen)
  - Pytesseract (OCR)
- **Base de datos:** SQLite
- **Gestión de paquetes:** uv

## 📁 Estructura del Proyecto
- `bot/`: Lógica del bot de Telegram, handlers y servicios.
- `web/`: Aplicación Django, plantillas y vistas del panel.
- `shared/`: Código compartido entre el bot y la web (servicios de IA, base de datos).
- `media/`: Almacenamiento local de reportes y fotos (ignorado en Git).

## 🔧 Instalación (Local)
1. Instalar dependencias con `uv`:
   ```bash
   uv sync
   ```
2. Configurar variables de entorno en `.env`:
   ```bash
   TELEGRAM_TOKEN=tu_token
   DJANGO_SECRET_KEY=tu_secret_key
   ```
3. Ejecutar migraciones:
   ```bash
   python web/manage.py migrate
   ```
4. Iniciar:
   ```bash
   # Iniciar Web
   python web/manage.py runserver
   
   # Iniciar Bot
   python bot/app.py
   ```

## ☁️ Despliegue en VPS (Recomendado)
- **SO:** Ubuntu 22.04+
- **RAM Min:** 2GB (necesario para modelos de IA).
- **Dependencias:** Requiere `tesseract-ocr` instalado en el sistema.
