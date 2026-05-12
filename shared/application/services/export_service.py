import os
import zipfile
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from calidad.models import PerfilUsuario, RegistroDefecto

FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")

class ExportService:
    """
    Servicio unificado para exportar evidencias (fotos en ZIP).
    Single Source of Truth para lógicas de RBAC, filtros y generación de ZIP.
    """

    def _get_perfil(self, telegram_id: int) -> PerfilUsuario:
        try:
            return PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_id)
        except PerfilUsuario.DoesNotExist:
            raise PermissionDenied("Usuario no registrado.")

    def obtener_turnos(self, requester_id: int) -> list[str]:
        """Devuelve los turnos disponibles según el rol del usuario."""
        p = self._get_perfil(requester_id)
        if p.rol == 'admin':
            turnos = RegistroDefecto.objects.order_by().values_list('turno', flat=True).distinct()
            return sorted([t for t in turnos if t])
        else:
            return [p.turno]

    def get_evidence_info(self, requester_id: int) -> dict:
        """Devuelve metadata sobre las fotos de un usuario."""
        import re
        p = self._get_perfil(requester_id)
        user_folder = Path(FOTOS_PATH) / str(requester_id)
        
        if not user_folder.exists():
            return {"total": 0, "jpgs": 0, "pngs": 0, "rango_min": 0, "rango_max": 0, "size_mb": 0.0}

        def _extraer_numero(nombre: str) -> int:
            m = re.match(r"^(\d+)", nombre)
            return int(m.group(1)) if m else -1

        imgs = [f for f in user_folder.iterdir() if f.is_file() and f.suffix.lower() in ('.jpg', '.png')]
        jpgs = sum(1 for f in imgs if f.suffix.lower() == '.jpg')
        pngs = sum(1 for f in imgs if f.suffix.lower() == '.png')
        size_mb = sum(f.stat().st_size for f in imgs) / (1024 * 1024)

        numeros = [_extraer_numero(f.name) for f in imgs if _extraer_numero(f.name) != -1]
        rango_min = min(numeros) if numeros else 0
        rango_max = max(numeros) if numeros else 0

        return {
            "total": len(imgs),
            "jpgs": jpgs,
            "pngs": pngs,
            "rango_min": rango_min,
            "rango_max": rango_max,
            "size_mb": size_mb
        }

    def obtener_operadores(self, turno: str, requester_id: int) -> list[dict]:
        """Devuelve los operadores que tienen registros en un turno."""
        p = self._get_perfil(requester_id)
        if p.rol != 'admin' and p.turno != turno:
            raise PermissionDenied("No tienes acceso a este turno.")

        user_ids = RegistroDefecto.objects.filter(turno=turno).order_by().values_list('user_id', flat=True).distinct()
        perfiles = PerfilUsuario.objects.filter(telegram_user_id__in=user_ids).select_related('usuario')
        
        operadores = []
        for perf in perfiles:
            nombre = f"{perf.usuario.first_name} {perf.usuario.last_name}".strip() or perf.usuario.username
            operadores.append({"id": perf.telegram_user_id, "nombre": nombre})
        return operadores

    def _zip_worker(self, user_ids: list[int], zip_path: str, inicio: int = None, fin: int = None):
        """Worker síncrono para generar el ZIP. Se ejecutará en un thread."""
        import re
        def _extraer_numero(nombre: str) -> int:
            m = re.match(r"^(\d+)", nombre)
            return int(m.group(1)) if m else -1

        multiple_users = len(user_ids) > 1
        count = 0
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for uid in user_ids:
                user_folder = Path(FOTOS_PATH) / str(uid)
                if not user_folder.exists():
                    continue
                for f in user_folder.iterdir():
                    if f.is_file() and f.suffix.lower() in ('.jpg', '.png'):
                        num = _extraer_numero(f.name)
                        if inicio is not None and fin is not None:
                            if num == -1 or not (inicio <= num <= fin):
                                continue

                        # Usar nombre original (con timestamp) para evitar colisiones de nombres duplicados
                        nombre_limpio = f.name

                        arcname = f"{uid}_{nombre_limpio}" if multiple_users else nombre_limpio
                        zf.write(f, arcname=arcname)
                        count += 1
        return count

    def generate_evidence_zip(self, requester_id: int, turno: str = None, operador_id: str = None, inicio: int = None, fin: int = None) -> tuple[str, int]:
        """
        Genera un ZIP con las fotos correspondientes a los filtros.
        Retorna la ruta al ZIP temporal generado y la cantidad de fotos incluidas.
        """
        p = self._get_perfil(requester_id)

        user_ids_to_export = []

        if not turno and not operador_id:
            # Caso /descargar simple del operador
            user_ids_to_export = [requester_id]
        else:
            # Caso /descargar_turno del admin/supervisor
            if p.rol != 'admin' and p.turno != turno:
                raise PermissionDenied("No tienes acceso a este turno.")
            
            if operador_id and operador_id.lower() != 'todos':
                user_ids_to_export = [int(operador_id)]
            else:
                user_ids_to_export = list(RegistroDefecto.objects.filter(turno=turno).values_list('user_id', flat=True).distinct())

        if not user_ids_to_export:
            raise ValueError("No se encontraron registros para estos filtros.")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        fd, temp_path = tempfile.mkstemp(suffix=".zip", prefix=f"evidencia_{timestamp}_")
        os.close(fd) # Cerramos el fd porque zipfile lo abrirá por su cuenta

        count = self._zip_worker(user_ids_to_export, temp_path, inicio=inicio, fin=fin)

        # Verificar si el ZIP quedó vacío (un ZIP vacío mide 22 bytes)
        if os.path.getsize(temp_path) <= 22 or count == 0:
            os.remove(temp_path)
            raise ValueError("No se encontraron imágenes guardadas.")

        return temp_path, count
