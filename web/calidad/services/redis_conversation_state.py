"""
RedisConversationState — implementa ConversationStateRepository usando Redis.
Ultra-rápido: lecturas/escrituras en microsegundos vs milisegundos de DB.
Reemplaza json_conversation_state.py (SQLite).
"""
import json
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_TTL = 3600 * 8  # 8 horas — un turno completo


class RedisConversationState:
    """Estado de conversaciones en Redis. Thread-safe, O(1) read/write."""

    def __init__(self, redis_url: str = None):
        import redis
        url = redis_url or os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        self._r = redis.from_url(url, decode_responses=True)
        self._prefix = 'conv:'

    def _key(self, user_id: int) -> str:
        return f"{self._prefix}{user_id}"

    def tiene_conversacion(self, user_id: int) -> bool:
        return self._r.exists(self._key(user_id)) == 1

    def obtener(self, user_id: int) -> Optional[Dict]:
        raw = self._r.get(self._key(user_id))
        if raw is None:
            return None
        return json.loads(raw)

    def iniciar(self, user_id: int) -> Dict:
        estado = {
            'estado': 'ESPERANDO_FOTOS',
            'fotos': [],
            'datos': {},
            'fotos_sin_asignar': [],
        }
        self._r.setex(self._key(user_id), _TTL, json.dumps(estado))
        return estado

    def guardar(self, user_id: int, estado: Dict) -> None:
        self._r.setex(self._key(user_id), _TTL, json.dumps(estado))

    def finalizar(self, user_id: int) -> None:
        self._r.delete(self._key(user_id))
