"""
Configuración de Django - Panel de Calidad
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# La base de datos del bot está un nivel arriba
BOT_DIR = BASE_DIR.parent

SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-calidad-bot-SOLO-PARA-DESARROLLO-LOCAL'
)

DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0,web').split(',')

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
# BASE DE DATOS: PostgreSQL (producción) / SQLite (fallback local)
# ====================================
import dj_database_url

_default_db = dj_database_url.config(
    env='DATABASE_URL',
    default=f'sqlite:///{BOT_DIR / "bot_calidad.db"}',
    conn_max_age=60,  # Connection pooling: reusar conexiones por 60s
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
