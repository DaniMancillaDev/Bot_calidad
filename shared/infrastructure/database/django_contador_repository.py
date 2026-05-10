"""
DjangoContadorRepository — implementa ContadorRepository usando el ORM de Django.
Usa SELECT FOR UPDATE para garantizar atomicidad sin race conditions.
Reemplaza sqlite_contador_repository.py.
"""
from typing import Optional


class DjangoContadorRepository:
    """Adaptador: ContadorRepository sobre Django ORM con atomic increment."""

    def obtener_y_avanzar(self, user_id: int, turno: Optional[str] = None,
                          departamento: Optional[str] = None) -> int:
        """Retorna el contador actual y lo incrementa en 1, de forma atómica."""
        from calidad.models import ContadorGrupo, PerfilUsuario
        from django.db import transaction

        # Obtener turno/depto del usuario si no se pasan
        if not turno or not departamento:
            try:
                perfil = PerfilUsuario.objects.get(telegram_user_id=user_id)
                turno = turno or perfil.turno
                departamento = departamento or perfil.departamento
            except PerfilUsuario.DoesNotExist:
                turno = turno or 'A'
                departamento = departamento or 'IQA'

        with transaction.atomic():
            contador, _ = ContadorGrupo.objects.select_for_update().get_or_create(
                turno=turno,
                departamento=departamento,
                defaults={'contador_actual': 1}
            )
            valor_actual = contador.contador_actual
            contador.contador_actual += 1
            contador.save(update_fields=['contador_actual'])
            return valor_actual

    def obtener_actual(self, user_id: int, turno: Optional[str] = None,
                       departamento: Optional[str] = None) -> int:
        from calidad.models import ContadorGrupo, PerfilUsuario

        if not turno or not departamento:
            try:
                perfil = PerfilUsuario.objects.get(telegram_user_id=user_id)
                turno = turno or perfil.turno
                departamento = departamento or perfil.departamento
            except PerfilUsuario.DoesNotExist:
                turno = turno or 'A'
                departamento = departamento or 'IQA'

        try:
            return ContadorGrupo.objects.get(turno=turno, departamento=departamento).contador_actual
        except ContadorGrupo.DoesNotExist:
            return 1
