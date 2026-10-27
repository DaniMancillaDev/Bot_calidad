"""
Configuración de Django - Panel de Calidad
"""
import os
from pathlib import Path
from urllib.parse import urlparse
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# La base de datos del bot está un nivel arriba
BOT_DIR = BASE_DIR.parent

SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-calidad-bot-SOLO-PARA-DESARROLLO-LOCAL'
)

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0,web,*').split(',')
if '.trycloudflare.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.trycloudflare.com')

USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'django.contrib.postgres',  # ArrayField, SearchVector, etc.
    'calidad',  # Nuestra app principal
    'workspace', # Workspace de Importación (Fase 2)
]

# ====================================
# REST FRAMEWORK API
# ====================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ====================================
# BASE DE DATOS: PostgreSQL obligatorio
# ====================================
_database_url = os.getenv('DATABASE_URL', '')
if not _database_url:
    raise ImproperlyConfigured('DATABASE_URL es obligatorio; este proyecto usa PostgreSQL.')
if urlparse(_database_url).scheme not in ('postgres', 'postgresql'):
    raise ImproperlyConfigured('DATABASE_URL debe apuntar a PostgreSQL; SQLite no esta soportado.')

import dj_database_url

_default_db = dj_database_url.config(
    env='DATABASE_URL',
    # ASGI creates request-scoped threads; persistent connections exhaust PostgreSQL.
    conn_max_age=0,
)

DATABASES = {
    'default': _default_db
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ====================================
# INTERNACIONALIZACIÓN
# ====================================
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Tijuana'  # Ajusta a tu zona horaria
USE_I18N = True
USE_TZ = True

# ====================================
# ARCHIVOS ESTÁTICOS Y DE MEDIA
# ====================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR.parent / 'static_collected'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Fotos del bot - accesibles desde el panel web
MEDIA_URL = '/media/'
MEDIA_ROOT = BOT_DIR / 'media_files'  # Aislar archivos media

# Thumbnails (generados por Celery, servidos vía proxy Django → Nginx internal)
THUMBS_ROOT = MEDIA_ROOT / 'thumbs'
THUMBS_URL  = '/media-protegida/thumbs/'
FOTOS_ROOT  = MEDIA_ROOT / 'fotos'
FOTOS_URL   = '/media-protegida/fotos/'

# WhatsApp ingestion is disabled until an explicit key and group allow-list exist.
WHATSAPP_INGEST_API_KEY = os.getenv('WHATSAPP_INGEST_API_KEY')
WHATSAPP_ALLOWED_GROUP_IDS = frozenset(
    item.strip() for item in os.getenv('WHATSAPP_ALLOWED_GROUP_IDS', '').split(',') if item.strip()
)
WHATSAPP_PENDING_ROOT = Path(os.getenv(
    'WHATSAPP_PENDING_ROOT',
    str(BOT_DIR / 'data' / 'whatsapp_pending'),
))
WHATSAPP_MAX_IMAGE_BYTES = int(os.getenv('WHATSAPP_MAX_IMAGE_BYTES', str(25 * 1024 * 1024)))
WHATSAPP_ALLOW_HISTORICAL = False
WHATSAPP_PROCESSING_LEASE_SECONDS = max(1, int(os.getenv('WHATSAPP_PROCESSING_LEASE_SECONDS', '300')))

# ====================================
# LOGIN
# ====================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ====================================
# SEGURIDAD (activo solo en producción)
# ====================================
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ====================================
# CELERY + REDIS
# En local: Redis debe correr en localhost:6379
# En Docker: usar redis://redis:6379/0
# ====================================
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TASK_TRACK_STARTED = True
# Limpiar resultados de Redis después de 1 hora (evitar memory leak)
CELERY_RESULT_EXPIRES = 3600

# Cloudflare support
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [
    'https://*.trycloudflare.com',
    'https://*.danimancilladev.dev',
    'https://iqa.danimancilladev.dev',
]
