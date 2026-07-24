"""
DjangoContadorRepository — implementa ContadorRepository usando el ORM de Django.
Usa SELECT FOR UPDATE para garantizar atomicidad sin race conditions.
Reemplaza sqlite_contador_repository.py.
"""
from typing import Optional


class DjangoContadorRepository:
    """Adaptador: ContadorRepository sobre Django ORM con atomic increment global."""

    def obtener_y_avanzar_lote(self, user_id: int, n: int = 1, turno: Optional[str] = None,
                               departamento: Optional[str] = None) -> list[int]:
        """Reserva 'n' contadores en una sola transacción atómica a nivel global."""
        if n <= 0:
            return []
            
        from calidad.models import GlobalCounter
        from django.db import transaction

        with transaction.atomic():
            contador, _ = GlobalCounter.objects.select_for_update().get_or_create(
                nombre='fotos', defaults={'valor_actual': 1}
            )
            valor_actual = contador.valor_actual
            contador.valor_actual += n
            contador.save(update_fields=['valor_actual'])
            return list(range(valor_actual, valor_actual + n))

    def obtener_y_avanzar(self, user_id: int, turno: Optional[str] = None,
                          departamento: Optional[str] = None) -> int:
        """Retorna el contador global actual y lo incrementa en 1, de forma atómica."""
        from calidad.models import GlobalCounter
        from django.db import transaction

        with transaction.atomic():
            contador, _ = GlobalCounter.objects.select_for_update().get_or_create(
                nombre='fotos', defaults={'valor_actual': 1}
            )
            valor_actual = contador.valor_actual
            contador.valor_actual += 1
            contador.save(update_fields=['valor_actual'])
            return valor_actual

    def obtener_actual(self, user_id: int, turno: Optional[str] = None,
                       departamento: Optional[str] = None) -> int:
        from calidad.models import GlobalCounter

        try:
            return GlobalCounter.objects.get(nombre='fotos').valor_actual
        except GlobalCounter.DoesNotExist:
            return 1
