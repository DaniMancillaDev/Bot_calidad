import logging
import os
import json
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from shared.domain.estado_conversacion import EstadoConversacion, parse_estado_conversacion


class JsonConversationStateRepository:
    """
    Adaptador: encapsula el estado de conversaciones que actualmente
    vive como dict global + JSON en main_sqlite.py:103-146.

    Misma lógica, misma estructura de datos, mismo archivo JSON.
    Solo cambia la encapsulación (de módulo → clase).

    Mapeo:
    tiene_conversacion()  → user_id in conversaciones
    obtener()             → conversaciones[user_id]
    iniciar()             → iniciar_conversacion()
    finalizar()           → finalizar_conversacion()
    persistir()           → guardar_estado()
    """

    def __init__(self, db_manager=None):
        if db_manager is None:
            from database import db
            self._db = db
        else:
            self._db = db_manager
        self._conversaciones: Dict[int, Dict] = {}

    def obtener(self, user_id: int) -> Optional[Dict]:
        estado_json = self._db.obtener_estado_conversacion(user_id)
        if estado_json:
            data = json.loads(estado_json)
            estado = parse_estado_conversacion(data.get('estado'))
            if estado is not None:
                data['estado'] = estado.value
            self._conversaciones[user_id] = data
            return self._conversaciones[user_id]
        return None

    def tiene_conversacion(self, user_id: int) -> bool:
        return self.obtener(user_id) is not None

    def iniciar(self, user_id: int) -> Dict:
        estado = {
            'estado': EstadoConversacion.ESPERANDO_FOTOS.value,
            'fotos': [],
            'datos': {},
            'fotos_sin_asignar': []
        }
        self._conversaciones[user_id] = estado
        self.persistir(user_id)
        return estado

    def finalizar(self, user_id: int) -> None:
        if user_id in self._conversaciones:
            del self._conversaciones[user_id]
        self._db.eliminar_estado_conversacion(user_id)

    def persistir(self, user_id: int = None) -> None:
        if user_id is not None:
            if user_id in self._conversaciones:
                self._db.guardar_estado_conversacion(user_id, json.dumps(self._conversaciones[user_id], ensure_ascii=False))
                # Remove from memory to avoid stale cache
                del self._conversaciones[user_id]
        else:
            # Fallback for old calls (should not be used with concurrent_updates)
            for uid, estado in list(self._conversaciones.items()):
                self._db.guardar_estado_conversacion(uid, json.dumps(estado, ensure_ascii=False))
            self._conversaciones.clear()

    @property
    def conversaciones(self) -> Dict[int, Dict]:
        return self._conversaciones
