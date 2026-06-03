from typing import Dict, Any, Callable, Tuple
from .entities import EstadoConversacion, FSMContext, FSMResult
from .validators import validar_cantidad, validar_modelo, validar_linea

import os

class RegistroFSM:
    """
    Máquina de estados finita declarativa para el registro de defectos.
    Regla: La FSM pura NO realiza I/O (no BD, no Redis). Solo evalúa estados,
    valida inputs y muta el FSMContext.
    """
    
    def __init__(self):
        self.enable_part_number = os.getenv("ENABLE_PART_NUMBER", "false").lower() in ("true", "1", "yes")
        
        # Mapeo: EstadoActual -> (FunciónValidadora, ClaveDato, SiguienteEstado, MensajeExito, MensajeError)
        self.transitions = {
            EstadoConversacion.ESPERANDO_MODELO: (
                validar_modelo,
                "modelo",
                EstadoConversacion.ESPERANDO_NUMERO_PARTE if self.enable_part_number else EstadoConversacion.ESPERANDO_LINEA,
                "<b>[2/6] Número de Parte (Opcional)</b>\n"
                "Ingresa el número de parte.\n\n"
                "Si no aplica, presiona OMITIR." if self.enable_part_number else 
                "<b>[2/5] Línea de Producción</b>\n"
                "Anotado. ¿En qué línea ocurrió?\n"
                "<code>Ej: T03</code>",
                "Modelo inválido."
            ),
            EstadoConversacion.ESPERANDO_NUMERO_PARTE: (
                lambda x: True, # Todo válido, incluso omitir
                "numero_parte",
                EstadoConversacion.ESPERANDO_LINEA,
                "<b>[3/6] Línea de Producción</b>\n"
                "Anotado. ¿En qué línea ocurrió?\n"
                "<code>Ej: T03</code>",
                "Número de parte inválido."
            ),
            EstadoConversacion.ESPERANDO_LINEA: (
                validar_linea,
                "linea",
                EstadoConversacion.ESPERANDO_CANTIDAD,
                f"<b>[{'4/6' if self.enable_part_number else '3/5'}] Cantidad</b>\n"
                "Perfecto. ¿Cuántos defectos encontraste?\n"
                "<i>Solo ingresa el número.</i>",
                "Línea inválida."
            ),
            EstadoConversacion.ESPERANDO_CANTIDAD: (
                validar_cantidad,
                "cantidad",
                EstadoConversacion.ESPERANDO_RESPONSABLE,
                f"<b>[{'5/6' if self.enable_part_number else '4/5'}] Responsable</b>\n"
                "Bien. ¿Quién es el responsable?\n"
                "<code>Ej: XM</code>",
                "⚠️ Por favor, ingresa solo números para la cantidad."
            ),
            EstadoConversacion.ESPERANDO_RESPONSABLE: (
                lambda x: True,  # Todo es válido por ahora
                "responsable",
                EstadoConversacion.ESPERANDO_DESCRIPCION,
                f"<b>[{'6/6' if self.enable_part_number else '5/5'}] Descripción</b>\n"
                "Casi terminamos. Por último, descríbeme brevemente el defecto:",
                "Responsable inválido."
            ),
            EstadoConversacion.ESPERANDO_DESCRIPCION: (
                lambda x: True,
                "descripcion",
                None, # Significa que termina el flujo
                "", # Se ignora, se generará el mensaje de resumen al guardar
                "Descripción inválida."
            )
        }

    def procesar_evento(self, context: FSMContext, texto: str) -> FSMResult:
        """
        Avanza la máquina de estados en base al input del usuario.
        Muta el objeto context si la transición es exitosa.
        """
        estado_actual = context.estado
        
        if estado_actual not in self.transitions:
            return FSMResult(
                exito=False,
                mensaje="Estado actual desconocido o no procesable.",
                nuevo_estado=estado_actual
            )
            
        validador, clave, sig_estado, msg_exito, msg_error = self.transitions[estado_actual]
        
        if not validador(texto):
            return FSMResult(
                exito=False,
                mensaje=msg_error,
                nuevo_estado=estado_actual
            )
            
        # Parse especial para cantidad
        valor = int(texto) if clave == "cantidad" else texto
        
        # Muta el contexto
        context.update_dato(clave, valor)
        context.estado = sig_estado or estado_actual # Si es None, mantengo el actual pero finalizado
        
        finalizado = (sig_estado is None)
        
        return FSMResult(
            exito=True,
            mensaje=msg_exito,
            nuevo_estado=sig_estado,
            finalizado=finalizado
        )
