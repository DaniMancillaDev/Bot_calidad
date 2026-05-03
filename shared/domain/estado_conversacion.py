from __future__ import annotations

from enum import Enum
from typing import Optional


class EstadoConversacion(Enum):
    ESPERANDO_FOTOS = "ESPERANDO_FOTOS"
    ESPERANDO_MODELO = "ESPERANDO_MODELO"
    ESPERANDO_LINEA = "ESPERANDO_LINEA"
    ESPERANDO_CANTIDAD = "ESPERANDO_CANTIDAD"
    ESPERANDO_RESPONSABLE = "ESPERANDO_RESPONSABLE"
    ESPERANDO_DESCRIPCION = "ESPERANDO_DESCRIPCION"


_LEGACY_MAP = {
    # legacy json_conversation_state.py / main_sqlite.py stored lowercase strings
    "esperando_fotos": EstadoConversacion.ESPERANDO_FOTOS,
    "esperando_modelo": EstadoConversacion.ESPERANDO_MODELO,
    "esperando_linea": EstadoConversacion.ESPERANDO_LINEA,
    "esperando_cantidad": EstadoConversacion.ESPERANDO_CANTIDAD,
    "esperando_responsable": EstadoConversacion.ESPERANDO_RESPONSABLE,
    "esperando_descripcion": EstadoConversacion.ESPERANDO_DESCRIPCION,
}


def parse_estado_conversacion(raw: object) -> Optional[EstadoConversacion]:
    """
    Convierte estado raw (persistido o legacy) a Enum.
    Retorna None si valor desconocido.
    """
    if isinstance(raw, EstadoConversacion):
        return raw
    if isinstance(raw, str):
        if raw in _LEGACY_MAP:
            return _LEGACY_MAP[raw]
        try:
            return EstadoConversacion(raw)
        except ValueError:
            return None
    return None

