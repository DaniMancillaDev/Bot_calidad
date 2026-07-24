import os
import time
import logging
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Garbage collector para archivos temporales y workspaces abandonados"

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        fotos_dir = media_root / 'fotos'
        workspaces_dir = media_root / 'workspaces'

        ahora = time.time()
        horas_48 = 48 * 3600
        horas_24 = 24 * 3600

        # 1. Limpiar fotos temporales (tmp_*.jpg) en media/fotos/
        if fotos_dir.exists():
            for root, dirs, files in os.walk(fotos_dir):
                for file in files:
                    if file.startswith("tmp_") and file.endswith(".jpg"):
                        file_path = Path(root) / file
                        try:
                            # 24 horas para tmp files sueltos
                            if ahora - file_path.stat().st_mtime > horas_24:
                                os.remove(file_path)
                                logger.info(f"Eliminado temporal huérfano: {file_path}")
                        except Exception as e:
                            logger.error(f"Error borrando {file_path}: {e}")

        # 2. Limpiar carpetas de workspaces
        if workspaces_dir.exists():
            try:
                ImportSession = apps.get_model('calidad', 'ImportSession')
                has_model = True
            except LookupError:
                has_model = False

            for ws_dir in workspaces_dir.iterdir():
                if ws_dir.is_dir():
                    uuid_str = ws_dir.name
                    borrar = False
                    
                    if has_model:
                        try:
                            session = ImportSession.objects.get(uuid=uuid_str)
                            if session.status in ('CONFIRMED', 'EXPIRED', 'FAILED'):
                                borrar = True
                        except ImportSession.DoesNotExist:
                            # Si no existe sesión, aplicar regla de 48h
                            if ahora - ws_dir.stat().st_mtime > horas_48:
                                borrar = True
                    else:
                        # Fallback si el modelo aún no fue migrado
                        if ahora - ws_dir.stat().st_mtime > horas_48:
                            borrar = True

                    if borrar:
                        try:
                            shutil.rmtree(ws_dir)
                            logger.info(f"Workspace eliminado: {ws_dir}")
                        except Exception as e:
                            logger.error(f"Error borrando workspace {ws_dir}: {e}")
        
        self.stdout.write(self.style.SUCCESS("Limpieza completada."))
