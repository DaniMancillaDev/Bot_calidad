from database import DatabaseManager


class SqliteContadorRepository:
    """
    Adaptador: delega a DatabaseManager sin modificarlo.

    Mapeo:
    obtener_y_avanzar()  → db.obtener_y_avanzar_contador()
    obtener_actual()     → db.obtener_contador_usuario()

    NOTA: Los métodos legacy vacíos NO se incluyen porque no tienen
    comportamiento real (actualizar_contador_usuario → pass, etc.).
    """

    def __init__(self, db: DatabaseManager):
        self._db = db

    def obtener_y_avanzar(self, user_id: int) -> int:
        return self._db.obtener_y_avanzar_contador(user_id)

    def obtener_actual(self, user_id: int) -> int:
        return self._db.obtener_contador_usuario(user_id)

    def reiniciar(self, user_id: int) -> None:
        """Reinicia el contador del grupo turno/depto del usuario a 1."""
        self._db.reiniciar_contador_usuario(user_id)

    def establecer(self, user_id: int, valor: int) -> None:
        """
        Establece el contador del grupo a un valor específico.
        Usado en /cancelar para rollback al número previo a la sesión.
        """
        self._db.establecer_contador_usuario(user_id, valor)
