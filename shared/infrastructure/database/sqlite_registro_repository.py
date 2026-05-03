from typing import Dict, List, Optional

from database import DatabaseManager


class SqliteRegistroRepository:
    """
    Adaptador: delega a DatabaseManager sin modificarlo.

    Mapeo:
    guardar()                  → db.guardar_registro()
    obtener_todos()            → db.obtener_todos_registros()
    obtener_por_turno_depto()  → db.obtener_registros_por_turno_depto()
    limpiar_por_usuario()      → db.limpiar_registros_usuario()
    obtener_estadisticas()     → db.obtener_estadisticas()
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    def guardar(self, fotos: List[int], modelo: str, linea: str,
                cantidad: int, responsable: str, descripcion: str,
                user_id: int, turno: Optional[str] = None,
                departamento: Optional[str] = None) -> bool:
        return self._db.guardar_registro(
            fotos, modelo, linea, cantidad, responsable, descripcion,
            user_id, turno, departamento
        )

    def obtener_todos(self, user_id: Optional[int] = None,
                      turno: Optional[str] = None,
                      departamento: Optional[str] = None) -> List[Dict]:
        return self._db.obtener_todos_registros(user_id, turno, departamento)

    def obtener_por_turno_depto(self, turno: str, departamento: str,
                                user_id: Optional[int] = None) -> List[Dict]:
        return self._db.obtener_registros_por_turno_depto(turno, departamento, user_id)

    def limpiar_por_usuario(self, user_id: int) -> bool:
        return self._db.limpiar_registros_usuario(user_id)

    def obtener_estadisticas(self, user_id: Optional[int] = None,
                             turno: Optional[str] = None,
                             departamento: Optional[str] = None) -> Dict:
        return self._db.obtener_estadisticas(user_id, turno, departamento)

    def formatear_rango_fotos(self, fotos: List[int]) -> str:
        """Delega a db._formatear_rango_fotos (utilidad de formateo)."""
        return self._db._formatear_rango_fotos(fotos)
