import logging
from typing import Dict, Any, List

from calidad.domain.defectos.entities import EstadoConversacion, FSMContext, FSMResult
from calidad.domain.defectos.state_machine import RegistroFSM
from calidad.services.redis_conversation_state import RedisConversationState
from shared.infrastructure.database.django_registro_repository import DjangoRegistroRepository
from shared.infrastructure.database.django_usuario_repository import DjangoUsuarioRepository
from shared.infrastructure.database.django_contador_repository import DjangoContadorRepository

logger = logging.getLogger(__name__)

class DefectoWorkflow:
    """
    Orquestador de la máquina de estados de registro de defectos.
    Integra Redis, la FSM pura y la Base de Datos.
    """
    
    def __init__(self):
        # En el entorno de Django, REDIS_URL o CELERY_BROKER_URL está configurado.
        self._state_repo = RedisConversationState()
        self._fsm = RegistroFSM()
        self._registro_repo = DjangoRegistroRepository()
        self._usuario_repo = DjangoUsuarioRepository()
        self._contador_repo = DjangoContadorRepository()

    def iniciar(self, user_id: int) -> FSMResult:
        """Inicia una nueva sesión de reporte."""
        if not self._state_repo.tiene_conversacion(user_id):
            self._state_repo.iniciar(user_id)
            return FSMResult(exito=True, mensaje="Envíame las <b>fotos</b> del defecto.")
        
        estado = self._state_repo.obtener(user_id)
        return FSMResult(
            exito=True, 
            mensaje=f"Ya tienes un reporte en curso (Estado: {estado.get('estado')}). Si deseas cancelar, usa /cancelar."
        )

    def adjuntar_fotos(self, user_id: int, fotos_ids: List[int]) -> FSMResult:
        """Añade un lote de fotos al estado actual. Las renombra desde tmp_{id} a {contador}. Avanza FSM si es primer lote."""
        import os
        from datetime import datetime
        
        if not self._state_repo.tiene_conversacion(user_id):
            self._state_repo.iniciar(user_id)
            
        estado_dict = self._state_repo.obtener(user_id)
        
        import os
        FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")
        user_folder = os.path.join(FOTOS_PATH, str(user_id))
        
        nuevos_contadores = []
        for msg_id in fotos_ids:
            tmp_path = os.path.join(user_folder, f"tmp_{msg_id}.jpg")
            if os.path.exists(tmp_path):
                # Obtener siguiente contador
                contador = self._contador_repo.obtener_y_avanzar(user_id)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nuevo_nombre = f"{contador:03d}_{timestamp}.jpg"
                nueva_ruta = os.path.join(user_folder, nuevo_nombre)
                
                try:
                    os.rename(tmp_path, nueva_ruta)
                    nuevos_contadores.append(contador)
                except Exception as e:
                    logger.error(f"Error renombrando {tmp_path}: {e}")
        
        estado_dict['fotos'] = list(set(estado_dict.get('fotos', []) + nuevos_contadores))
        estado_dict['fotos_sin_asignar'] = list(set(estado_dict.get('fotos_sin_asignar', []) + nuevos_contadores))
        
        estado_actual = EstadoConversacion.parse(estado_dict.get('estado'))
        
        mensaje = f"<b>¡{len(nuevos_contadores)} foto(s) recibidas!</b>\n\n¿Deseas enviar más fotos o prefieres continuar con el registro?"

            
        self._state_repo.guardar(user_id, estado_dict)
        
        return FSMResult(
            exito=True, 
            mensaje=mensaje, 
            nuevo_estado=EstadoConversacion.parse(estado_dict['estado']),
            finalizado=False
        )

    def responder(self, user_id: int, texto: str) -> FSMResult:
        """Procesa una respuesta de texto según el estado de la FSM."""
        if not self._state_repo.tiene_conversacion(user_id):
            return FSMResult(exito=False, mensaje="No tienes un reporte en curso. Envía una foto primero.")
            
        estado_dict = self._state_repo.obtener(user_id)
        estado_actual = EstadoConversacion.parse(estado_dict.get('estado', 'ESPERANDO_FOTOS'))
        
        # Caso especial: El usuario presiona TERMINAR en el álbum de fotos
        if estado_actual == EstadoConversacion.ESPERANDO_FOTOS:
            if texto.upper() == "TERMINAR":
                if not estado_dict.get('fotos'):
                    return FSMResult(exito=False, mensaje="No has enviado fotos aún.")
                
                estado_dict['estado'] = EstadoConversacion.ESPERANDO_MODELO.value
                self._state_repo.guardar(user_id, estado_dict)
                
                return FSMResult(
                    exito=True,
                    mensaje=(
                        "<b>¡Perfecto! Álbum cerrado.</b>\n\n"
                        "Para completar el reporte, responde estas 5 preguntas:\n\n"
                        "<b>[1/5] Modelo</b>\n"
                        "¿De qué modelo es el producto?\n"
                        "<code>Ej: ONN 32\" 100012589 AUO</code>"
                    ),
                    nuevo_estado=EstadoConversacion.ESPERANDO_MODELO
                )
            return FSMResult(exito=False, mensaje="Por favor envíame primero las <b>fotos</b> del defecto o presiona TERMINAR.")
            
        # Rechazar TERMINAR si ya no estamos en fase de fotos
        if texto.upper() == "TERMINAR":
            return FSMResult(exito=False, mensaje="El álbum ya fue cerrado. Responde la pregunta actual para continuar.")

        context = FSMContext(
            telegram_id=user_id,
            estado=estado_actual,
            datos=estado_dict.get('datos', {})
        )
        
        result = self._fsm.procesar_evento(context, texto.upper())
        
        if result.exito:
            estado_dict['datos'] = context.datos
            estado_dict['estado'] = context.estado.value if context.estado else None
            
            if result.finalizado:
                # Termina FSM, guardar en base de datos
                guardado = self._guardar_registro(user_id, estado_dict)
                if guardado:
                    resumen = self._generar_resumen(estado_dict)
                    result.mensaje = f"<b>¡Reporte guardado con éxito!</b>\n\n{resumen}\n\n<i>Para reportar otro defecto, simplemente envíame fotos nuevas.</i>"
                    self._state_repo.finalizar(user_id)
                else:
                    result.exito = False
                    result.mensaje = "Error al guardar en base de datos."
            else:
                self._state_repo.guardar(user_id, estado_dict)
                
        return result

    def _guardar_registro(self, user_id: int, conv: Dict) -> bool:
        """Guarda físicamente en DjangoRegistroRepository."""
        usuario = self._usuario_repo.obtener(user_id)
        if not usuario:
            return False
            
        datos = conv.get('datos', {})
        exito = self._registro_repo.guardar(
            user_id=user_id,
            turno=usuario['turno'],
            departamento=usuario['departamento'],
            modelo=datos.get('modelo', ''),
            linea=datos.get('linea', ''),
            cantidad=datos.get('cantidad', 1),
            responsable=datos.get('responsable', ''),
            descripcion=datos.get('descripcion', ''),
            fotos=conv.get('fotos', [])
        )
        return exito
        
    def _generar_resumen(self, conv: Dict) -> str:
        """Genera el texto de resumen para el usuario."""
        datos = conv.get('datos', {})
        fotos_str = self._formatear_rango_fotos(conv.get('fotos', []))
        return (
            f"📸 <b>Fotos:</b> {fotos_str}\n"
            f"📱 <b>Modelo:</b> {datos.get('modelo')}\n"
            f"🏭 <b>Línea:</b> {datos.get('linea')}\n"
            f"⚠️ <b>Cantidad:</b> {datos.get('cantidad')}\n"
            f"👤 <b>Responsable:</b> {datos.get('responsable')}\n"
            f"📝 <b>Descripción:</b> {datos.get('descripcion')}"
        )

    def _formatear_rango_fotos(self, fotos: list[int]) -> str:
        if not fotos:
            return ""
        
        fotos_unicas = sorted(list(set(fotos)))
        rangos = []
        rango_actual = [fotos_unicas[0]]
        
        for i in range(1, len(fotos_unicas)):
            if fotos_unicas[i] == fotos_unicas[i-1] + 1:
                rango_actual.append(fotos_unicas[i])
            else:
                if len(rango_actual) > 1:
                    rangos.append(f"{rango_actual[0]}-{rango_actual[-1]}")
                else:
                    rangos.append(str(rango_actual[0]))
                rango_actual = [fotos_unicas[i]]
                
        if len(rango_actual) > 1:
            rangos.append(f"{rango_actual[0]}-{rango_actual[-1]}")
        else:
            rangos.append(str(rango_actual[0]))
            
        return ", ".join(rangos)
