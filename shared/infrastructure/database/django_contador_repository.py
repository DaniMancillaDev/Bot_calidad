"""
DjangoContadorRepository — implementa ContadorRepository usando el ORM de Django.
Usa F() expressions para incrementos atómicos en BD sin bloquear filas en memoria.
Reemplaza sqlite_contador_repository.py.
"""
from typing import Optional


class DjangoContadorRepository:
    """Adaptador: ContadorRepository sobre Django ORM con atomic increment global."""

    def obtener_y_avanzar_lote(self, user_id: int, n: int = 1, turno: Optional[str] = None,
                               departamento: Optional[str] = None) -> list[int]:
        """Reserva 'n' contadores, intentando reutilizar huecos cancelados primero."""
        if n <= 0:
            return []
            
        from calidad.models import GlobalCounter, NumeroReutilizable
        from django.db import transaction
        from django.db.models import F

        with transaction.atomic():
            # 1. Intentar tomar números liberados (huecos)
            huecos = list(NumeroReutilizable.objects.select_for_update().order_by('numero')[:n])
            numeros = [h.numero for h in huecos]

            if huecos:
                NumeroReutilizable.objects.filter(id__in=[h.id for h in huecos]).delete()

            # 2. Completar con el contador global si faltan números
            faltantes = n - len(numeros)
            if faltantes > 0:
                # UPDATE atómico: una sola query, lock de fila mínimo, sin traer valor a Python
                updated = GlobalCounter.objects.filter(nombre='fotos').update(
                    valor_actual=F('valor_actual') + faltantes
                )
                if not updated:
                    # Primera vez: crear e incrementar en una sola operación
                    GlobalCounter.objects.get_or_create(
                        nombre='fotos', defaults={'valor_actual': 1 + faltantes}
                    )
                # Leer el valor DESPUÉS del UPDATE (no bloquea a nadie)
                valor_post = GlobalCounter.objects.values_list('valor_actual', flat=True).get(nombre='fotos')
                valor_pre = valor_post - faltantes
                numeros.extend(range(valor_pre, valor_post))

            return sorted(numeros)

    def obtener_y_avanzar(self, user_id: int, turno: Optional[str] = None,
                          departamento: Optional[str] = None) -> int:
        """Retorna el contador global actual y lo incrementa en 1, de forma atómica."""
        from calidad.models import GlobalCounter
        from django.db import transaction
        from django.db.models import F

        with transaction.atomic():
            updated = GlobalCounter.objects.filter(nombre='fotos').update(
                valor_actual=F('valor_actual') + 1
            )
            if not updated:
                GlobalCounter.objects.get_or_create(
                    nombre='fotos', defaults={'valor_actual': 2}
                )
            valor_post = GlobalCounter.objects.values_list('valor_actual', flat=True).get(nombre='fotos')
            return valor_post - 1

    def obtener_actual(self, user_id: int, turno: Optional[str] = None,
                       departamento: Optional[str] = None) -> int:
        from calidad.models import GlobalCounter

        try:
            return GlobalCounter.objects.get(nombre='fotos').valor_actual
        except GlobalCounter.DoesNotExist:
            return 1
