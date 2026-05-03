import os
import json
from typing import Dict, List, Optional

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

    def __init__(self, estado_file: str = "estado_conversaciones.json"):
        self._estado_file = estado_file
        self._conversaciones: Dict[int, Dict] = {}
        self._cargar()

    def _cargar(self):
        """Idéntico a main_sqlite.py:cargar_estado()"""
        if os.path.exists(self._estado_file):
            try:
                with open(self._estado_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._conversaciones = {int(k): v for k, v in data.items()}
                    for conv in self._conversaciones.values():
                        estado = parse_estado_conversacion(conv.get('estado'))
                        if estado is not None:
                            conv['estado'] = estado.value
            except Exception as e:
                print(f"Error al cargar estado: {e}")
                self._conversaciones = {}

    def _guardar(self):
        """Idéntico a main_sqlite.py:guardar_estado()"""
        try:
            with open(self._estado_file, 'w', encoding='utf-8') as f:
                json.dump(self._conversaciones, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error al guardar estado: {e}")

    def tiene_conversacion(self, user_id: int) -> bool:
        return user_id in self._conversaciones

    def obtener(self, user_id: int) -> Optional[Dict]:
        return self._conversaciones.get(user_id)

    def iniciar(self, user_id: int) -> Dict:
        """Idéntico a main_sqlite.py:iniciar_conversacion()"""
        self._conversaciones[user_id] = {
            'estado': EstadoConversacion.ESPERANDO_FOTOS.value,
            'fotos': [],
            'datos': {},
            'fotos_sin_asignar': []
        }
        self._guardar()
        return self._conversaciones[user_id]

    def finalizar(self, user_id: int) -> None:
        """Idéntico a main_sqlite.py:finalizar_conversacion()"""
        if user_id in self._conversaciones:
            del self._conversaciones[user_id]
            self._guardar()

    def persistir(self) -> None:
        """Expuesto para compatibilidad con la interfaz."""
        self._guardar()

    @property
    def conversaciones(self) -> Dict[int, Dict]:
        """Acceso directo al dict interno (para transición gradual)."""
        return self._conversaciones
