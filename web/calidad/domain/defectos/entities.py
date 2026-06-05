from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

class EstadoConversacion(str, Enum):
    ESPERANDO_FOTOS = "ESPERANDO_FOTOS"
    ESPERANDO_MODELO = "ESPERANDO_MODELO"
    ESPERANDO_NUMERO_PARTE = "ESPERANDO_NUMERO_PARTE"
    ESPERANDO_LINEA = "ESPERANDO_LINEA"
    ESPERANDO_CANTIDAD = "ESPERANDO_CANTIDAD"
    ESPERANDO_RESPONSABLE = "ESPERANDO_RESPONSABLE"
    ESPERANDO_DESCRIPCION = "ESPERANDO_DESCRIPCION"
    
    @classmethod
    def parse(cls, value: str) -> Optional['EstadoConversacion']:
        try:
            return cls(value.upper())
        except ValueError:
            return None

@dataclass
class FSMContext:
    """Representa el estado actual y datos recolectados de una sesión de registro."""
    telegram_id: int
    estado: EstadoConversacion = EstadoConversacion.ESPERANDO_FOTOS
    datos: Dict[str, Any] = field(default_factory=dict)
    
    def update_dato(self, key: str, value: Any):
        self.datos[key] = value

@dataclass
class FSMResult:
    """Resultado de procesar un evento en la FSM."""
    exito: bool
    mensaje: str
    nuevo_estado: Optional[EstadoConversacion] = None
    finalizado: bool = False
