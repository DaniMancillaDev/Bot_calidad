from celery import shared_task
from django.db import transaction
from workspace.services.processing import process_upload_logic
import shutil
import os
from django.conf import settings

@shared_task
def process_workspace_upload(session_uuid):
    """
    Tarea Celery para procesar el ZIP y el Excel de forma asíncrona.
    """
    # Usar transaction.atomic para select_for_update dentro del servicio
    with transaction.atomic():
        process_upload_logic(session_uuid)

@shared_task
def cleanup_workspace_folder(zip_extract_path):
    """
    Limpia la carpeta extraida en background después de confirmar.
    """
    if zip_extract_path:
        full_path = os.path.join(settings.MEDIA_ROOT, zip_extract_path)
        if os.path.exists(full_path):
            shutil.rmtree(full_path, ignore_errors=True)
