"""
DjangoContadorRepository — implementa ContadorRepository usando el ORM de Django.
Usa SELECT FOR UPDATE para garantizar atomicidad sin race conditions.
Reemplaza sqlite_contador_repository.py.
"""
from typing import Optional


class DjangoContadorRepository:
    """Adaptador: ContadorRepository sobre Django ORM con atomic increment."""

    def obtener_y_avanzar_lote(self, user_id: int, n: int = 1, turno: Optional[str] = None,
                               departamento: Optional[str] = None) -> list[int]:
        """Reserva 'n' contadores en una sola transacción atómica."""
        if n <= 0:
            return []
            
        from calidad.models import ContadorUsuario
        from django.db import transaction

        with transaction.atomic():
            contador, _ = ContadorUsuario.objects.select_for_update().get_or_create(
                telegram_user_id=user_id, defaults={'contador_actual': 1}
            )
            valor_actual = contador.contador_actual
            contador.contador_actual += n
            contador.save(update_fields=['contador_actual'])
            return list(range(valor_actual, valor_actual + n))

    def obtener_y_avanzar(self, user_id: int, turno: Optional[str] = None,
                          departamento: Optional[str] = None) -> int:
        """Retorna el contador actual y lo incrementa en 1, de forma atómica."""
        from calidad.models import ContadorUsuario
        from django.db import transaction

        with transaction.atomic():
            contador, _ = ContadorUsuario.objects.select_for_update().get_or_create(
                telegram_user_id=user_id,
                defaults={'contador_actual': 1}
            )
            valor_actual = contador.contador_actual
            contador.contador_actual += 1
            contador.save(update_fields=['contador_actual'])
            return valor_actual

    def obtener_actual(self, user_id: int, turno: Optional[str] = None,
                       departamento: Optional[str] = None) -> int:
        from calidad.models import ContadorUsuario

        try:
            return ContadorUsuario.objects.get(telegram_user_id=user_id).contador_actual
        except ContadorUsuario.DoesNotExist:
            return 1
