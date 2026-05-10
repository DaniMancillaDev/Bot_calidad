"""
DjangoUsuarioRepository — implementa UsuarioRepository usando el ORM de Django.
Reemplaza sqlite_usuario_repository.py.
"""
import os
from typing import Dict, List, Optional


class DjangoUsuarioRepository:
    """Adaptador: UsuarioRepository sobre Django ORM."""

    def tiene_acceso(self, telegram_user_id: int) -> bool:
        from calidad.models import PerfilUsuario
        return PerfilUsuario.objects.filter(telegram_user_id=telegram_user_id).exists()

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

    def crear(self, telegram_user_id: int, turno: str, departamento: str,
              username: Optional[str] = None) -> bool:
        from calidad.models import PerfilUsuario
        from django.contrib.auth.models import User
        try:
            uname = username or f"tg_{telegram_user_id}"
            user, _ = User.objects.get_or_create(username=uname)
            PerfilUsuario.objects.update_or_create(
                telegram_user_id=telegram_user_id,
                defaults={'usuario': user, 'turno': turno, 'departamento': departamento}
            )
            return True
        except Exception:
            return False

    def actualizar(self, telegram_user_id: int,
                   turno: Optional[str] = None,
                   departamento: Optional[str] = None,
                   username: Optional[str] = None) -> bool:
        from calidad.models import PerfilUsuario
        try:
            updates = {}
            if turno:
                updates['turno'] = turno
            if departamento:
                updates['departamento'] = departamento
            if updates:
                PerfilUsuario.objects.filter(telegram_user_id=telegram_user_id).update(**updates)
            return True
        except Exception:
            return False

    def listar(self) -> List[Dict]:
        from calidad.models import PerfilUsuario
        qs = PerfilUsuario.objects.select_related('usuario').values(
            'telegram_user_id', 'turno', 'departamento', 'rol',
            'usuario__username', 'usuario__first_name', 'usuario__last_name'
        )
        result = []
        for row in qs:
            nombre_completo = f"{row.get('usuario__first_name', '')} {row.get('usuario__last_name', '')}".strip()
            row['nombre'] = nombre_completo or row.get('usuario__username', '')
            result.append(row)
        return result
