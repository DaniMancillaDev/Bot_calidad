"""
DjangoRegistroRepository — implementa RegistroRepository usando el ORM de Django.
Reemplaza sqlite_registro_repository.py.
"""
import os
import django
from typing import List, Dict, Optional

# Configurar Django ORM si no está inicializado (para el bot)
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'web'))
    django.setup()


class DjangoRegistroRepository:
    """Adaptador: RegistroRepository sobre Django ORM."""

    def guardar(self, fotos: List[int], modelo: str, linea: str,
                cantidad: int, responsable: str, descripcion: str,
                user_id: int, turno: Optional[str] = None,
                departamento: Optional[str] = None,
                numero_parte: Optional[str] = None) -> bool:
        from calidad.models import RegistroDefecto
        import time
        try:
            # Normalizar: asegurar lista de ints
            fotos_list = list(fotos) if isinstance(fotos, list) else []

            # Dual-write: legacy TextField + nuevo ArrayField
            fotos_str = ", ".join(str(f) for f in fotos_list)
            
            # Sanitizar numero_parte
            if numero_parte:
                np_upper = numero_parte.strip().upper()
                if np_upper in ("N/A", "NA", "VACÍO", "VACIO", "*", "_OMITIR_"):
                    numero_parte = None
                else:
                    numero_parte = np_upper

            t0 = time.monotonic()
            RegistroDefecto.objects.create(
                fotos=fotos_str,             # legacy — mantener mientras se migra
                fotos_nums=fotos_list,        # Fase 1 — nuevo campo normalizado
                modelo=modelo.upper() if modelo else "",
                numero_parte=numero_parte,
                linea=linea.upper() if linea else "",
                cantidad=cantidad,
                responsable=responsable.upper() if responsable else "",
                descripcion=descripcion.upper() if descripcion else "",
                user_id=user_id,
                turno=turno,
                departamento=departamento,
            )
            elapsed = (time.monotonic() - t0) * 1000
            import logging
            logging.getLogger(__name__).info(
                "RegistroDefecto guardado | user_id=%s fotos=%s elapsed=%.1fms",
                user_id, fotos_list, elapsed
            )
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Error guardando RegistroDefecto: %s", e)
            return False

    def obtener_todos(self, user_id: Optional[int] = None,
                      turno: Optional[str] = None,
                      departamento: Optional[str] = None) -> List[Dict]:
        from calidad.models import RegistroDefecto
        qs = RegistroDefecto.objects.all()
        if user_id:
            qs = qs.filter(user_id=user_id)
        if turno:
            qs = qs.filter(turno=turno)
        if departamento:
            qs = qs.filter(departamento=departamento)
        return list(qs.values())

    def obtener_por_turno_depto(self, turno: str, departamento: str,
                                user_id: Optional[int] = None) -> List[Dict]:
        from calidad.models import RegistroDefecto
        qs = RegistroDefecto.objects.filter(turno=turno, departamento=departamento)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return list(qs.values())

    def limpiar_por_usuario(self, user_id: int) -> bool:
        from calidad.models import RegistroDefecto
        try:
            RegistroDefecto.objects.filter(user_id=user_id).delete()
            return True
        except Exception:
            return False

    def obtener_estadisticas(self, user_id: Optional[int] = None,
                             turno: Optional[str] = None,
                             departamento: Optional[str] = None) -> Dict:
        from calidad.models import RegistroDefecto
        from django.db.models import Sum, Count
        qs = RegistroDefecto.objects.all()
        if user_id:
            qs = qs.filter(user_id=user_id)
        if turno:
            qs = qs.filter(turno=turno)
        if departamento:
            qs = qs.filter(departamento=departamento)
        agg = qs.aggregate(total=Count('id'), cantidad_total=Sum('cantidad'))
        return {
            'total_registros': agg['total'] or 0,
            'cantidad_total': agg['cantidad_total'] or 0,
        }
