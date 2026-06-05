"""
web/calidad/celery_app.py

Instancia de Celery para el panel de calidad.
Broker: Redis (CELERY_BROKER_URL en settings/env)
Backend: Redis (para consultar el estado de las tareas)
"""
import os
from celery import Celery
from dotenv import load_dotenv

# Cargar .env.local para que Celery lea variables de entorno
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(base_dir, '.env.local'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('calidad')

# Leer config de Django bajo el namespace CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas en cada app de Django
app.autodiscover_tasks()
