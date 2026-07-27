"""
DjangoUsuarioRepository — implementa UsuarioRepository usando el ORM de Django.
Reemplaza sqlite_usuario_repository.py.
"""
import os
from typing import Dict, List, Optional


class DjangoUsuarioRepository:
    """Adaptador: UsuarioRepository sobre Django ORM."""

    def obtener(self, telegram_user_id: int) -> Optional[Dict]:
        from calidad.models import PerfilUsuario
        try:
            p = PerfilUsuario.objects.select_related('usuario').get(telegram_user_id=telegram_user_id)
            nombre_completo = f"{p.usuario.first_name} {p.usuario.last_name}".strip()
            return {
                'telegram_user_id': p.telegram_user_id,
                'turno': p.turno,
                'departamento': p.departamento,
                'rol': p.rol,
                'username': p.usuario.username,
                'nombre': nombre_completo or p.usuario.username,
            }
        except PerfilUsuario.DoesNotExist:
            return None
