import os
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime

from django.core.exceptions import PermissionDenied

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

    def _zip_worker(self, ordered_fotos: list[tuple[int, int]], zip_path: str, inicio: int = None, fin: int = None):
        """Worker síncrono para generar el ZIP. Se ejecutará en un thread."""
        import re
        
        archivos_validos = []
        user_dirs_cache = {}
        
        for uid, num in ordered_fotos:
            if inicio is not None and fin is not None:
                if not (inicio <= num <= fin):
                    continue
                    
            if uid not in user_dirs_cache:
                user_folder = Path(FOTOS_PATH) / str(uid)
                files = {}
                if user_folder.exists():
                    for f in user_folder.iterdir():
                        if f.is_file() and f.suffix.lower() in ('.jpg', '.png'):
                            m = re.match(r"^(\d+)", f.name)
                            if m:
                                # Guardamos el más reciente en caso de repetidos (por la fecha en nombre)
                                f_num = int(m.group(1))
                                if f_num not in files or f.name > files[f_num].name:
                                    files[f_num] = f
                user_dirs_cache[uid] = files
                
            if num in user_dirs_cache[uid]:
                archivos_validos.append(user_dirs_cache[uid][num])

        # 3. Escribir al ZIP con numeración secuencial
        # Mantenemos el orden exacto de `ordered_fotos` (orden de registros de BD)
        count = (inicio - 1) if inicio is not None else 0
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
                for f in archivos_validos:
                    count += 1
                    arcname = f"{count:02d}{f.suffix}"
                    zf.write(f, arcname=arcname)
                    
            return count
        except Exception:
            try:
                os.unlink(zip_path)
            except OSError:
                pass
            raise

    def generate_evidence_zip(self, requester_id: int, turno: str = None, operador_id: str = None, inicio: int = None, fin: int = None) -> tuple[str, int]:
        """
        Genera un ZIP con las fotos correspondientes a los filtros.
        Retorna la ruta al ZIP temporal generado y la cantidad de fotos incluidas.
        """
        p = self._get_perfil(requester_id)

        from django.utils import timezone
        from datetime import timedelta
        # Obtener solo la evidencia del turno/sesión actual o recientes (últimas 72 horas)
        # Esto evita descargar historial viejo y permite descargar fotos recién "revisadas"
        limite = timezone.now() - timedelta(hours=72)

        if not turno and not operador_id:
            # Caso /descargar simple del operador
            qs = RegistroDefecto.objects.filter(user_id=requester_id, fecha_registro__gte=limite)
        else:
            # Caso /descargar_turno del admin/supervisor
            if p.rol != 'admin' and p.turno != turno:
                raise PermissionDenied("No tienes acceso a este turno.")
            
            qs = RegistroDefecto.objects.filter(turno=turno, fecha_registro__gte=limite)
            if operador_id and operador_id.lower() != 'todos':
                qs = qs.filter(user_id=int(operador_id))

        qs = qs.order_by('fecha_registro')
        
        ordered_fotos = []
        for r in qs:
            uid = r.user_id
            nums = []
            if r.fotos_nums:
                nums = r.fotos_nums
            else:
                from shared.utils.photo_parser import parse_photo_numbers
                nums = parse_photo_numbers(r.fotos)
            
            for n in sorted(list(set(nums))):
                ordered_fotos.append((uid, n))

        if not ordered_fotos:
            raise ValueError("No se encontraron registros con fotos para estos filtros.")

        timestamp = datetime.now().strftime('%H%M')
        fd, temp_path = tempfile.mkstemp(suffix=".zip", prefix=f"evidencia_{timestamp}_")
        os.close(fd) # Cerramos el fd porque zipfile lo abrirá por su cuenta

        count = self._zip_worker(ordered_fotos, temp_path, inicio=inicio, fin=fin)

        # Verificar si el ZIP quedó vacío (un ZIP vacío mide 22 bytes)
        if os.path.getsize(temp_path) <= 22 or count == 0:
            os.remove(temp_path)
            raise ValueError("No se encontraron imágenes guardadas.")

        return temp_path, count
