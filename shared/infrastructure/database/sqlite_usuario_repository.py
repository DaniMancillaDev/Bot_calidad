from typing import Dict, List, Optional

from database import DatabaseManager


class SqliteUsuarioRepository:
    """
    Adaptador: delega a DatabaseManager sin modificarlo.

    Mapeo:
    tiene_acceso()    → db.usuario_tiene_acceso()
    obtener()         → db.obtener_usuario()
    crear()           → db.crear_usuario()
    actualizar()      → db.actualizar_usuario()
    listar()          → db.listar_usuarios()
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    def tiene_acceso(self, telegram_user_id: int) -> bool:
        return self._db.usuario_tiene_acceso(telegram_user_id)

    def obtener(self, telegram_user_id: int) -> Optional[Dict]:
        return self._db.obtener_usuario(telegram_user_id)

    def crear(self, telegram_user_id: int, turno: str, departamento: str,
              username: Optional[str] = None) -> bool:
        return self._db.crear_usuario(telegram_user_id, turno, departamento, username)

    def actualizar(self, telegram_user_id: int,
                   turno: Optional[str] = None,
                   departamento: Optional[str] = None,
                   username: Optional[str] = None) -> bool:
        return self._db.actualizar_usuario(telegram_user_id, turno, departamento, username)

    def listar(self) -> List[Dict]:
        return self._db.listar_usuarios()
