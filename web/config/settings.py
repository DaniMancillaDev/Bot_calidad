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

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'calidad',  # Nuestra app principal
]

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
# BASE DE DATOS: apunta a la del bot
# ====================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        # La misma DB que usa el bot (un nivel arriba de web/)
        'NAME': BOT_DIR / 'bot_calidad.db',
    }
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
STATICFILES_DIRS = [BASE_DIR / 'static']

# Fotos del bot - accesibles desde el panel web
MEDIA_URL = '/media/'
MEDIA_ROOT = BOT_DIR  # Sirve fotos/ desde la raíz del bot

# ====================================
# LOGIN
# ====================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
