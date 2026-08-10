import os
import logging
import time
from typing import Dict, List

from calidad.domain.defectos.entities import EstadoConversacion, FSMContext, FSMResult
from calidad.domain.defectos.state_machine import RegistroFSM
from calidad.services.redis_conversation_state import RedisConversationState
from shared.infrastructure.database.django_registro_repository import DjangoRegistroRepository
from shared.infrastructure.database.django_usuario_repository import DjangoUsuarioRepository
from shared.infrastructure.database.django_contador_repository import DjangoContadorRepository
from shared.infrastructure.storage.foto_storage import LocalFotoStorage

logger = logging.getLogger(__name__)

class DefectoWorkflow:
    """
    Orquestador de la máquina de estados de registro de defectos.
    Integra Redis, la FSM pura y la Base de Datos.
    """
    
    def __init__(self, foto_storage=None):
        # En el entorno de Django, REDIS_URL o CELERY_BROKER_URL está configurado.
        self._state_repo = RedisConversationState()
        self._fsm = RegistroFSM()
        self._registro_repo = DjangoRegistroRepository()
        self._usuario_repo = DjangoUsuarioRepository()
        self._contador_repo = DjangoContadorRepository()
        # Etapa 5: storage inyectado — default LocalFotoStorage para backward compat
        self._storage = foto_storage or LocalFotoStorage()

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
        """Añade lote de fotos al estado actual. Renombra tmp_{id} → {contador}. Avanza FSM si primer lote."""
        import os
        from datetime import datetime
        t0 = time.monotonic()

        if not self._state_repo.tiene_conversacion(user_id):
            self._state_repo.iniciar(user_id)

        estado_dict = self._state_repo.obtener(user_id)
        user_folder = self._storage.get_user_folder(user_id)  # Etapa 5: storage

        nuevos_contadores = []
        rutas_para_thumbnail = []
        archivos_existentes = [msg_id for msg_id in fotos_ids if (user_folder / f"tmp_{msg_id}.jpg").exists()]
        
        if archivos_existentes:
            contadores_lote = self._contador_repo.obtener_y_avanzar_lote(user_id, len(archivos_existentes))

            t_move = time.monotonic()
            
            for msg_id, contador in zip(archivos_existentes, contadores_lote):
                tmp_path = user_folder / f"tmp_{msg_id}.jpg"
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nuevo_nombre = f"{contador:03d}_{timestamp}.jpg"
                nueva_ruta = user_folder / nuevo_nombre

                try:
                    os.rename(tmp_path, nueva_ruta)
                    nuevos_contadores.append(contador)
                    rutas_para_thumbnail.append(str(nueva_ruta))
                except Exception as e:
                    logger.error("rename failed %s → %s: %s", tmp_path, nueva_ruta, e)
            
            elapsed_move = (time.monotonic() - t_move) * 1000
            logger.info("Movimiento de archivos | user_id=%s cantidad=%d elapsed=%.1fms", user_id, len(archivos_existentes), elapsed_move)

        # Lanzar procesamiento de thumbnails por lote (más eficiente)
        if rutas_para_thumbnail:
            try:
                from calidad.tasks import generar_thumbnails_lote_task
                generar_thumbnails_lote_task.delay(user_id, rutas_para_thumbnail)
            except Exception as thumb_exc:
                logger.warning("batch thumbnail dispatch failed: %s", thumb_exc)

        estado_dict['fotos'] = list(set(estado_dict.get('fotos', []) + nuevos_contadores))
        estado_dict['fotos_sin_asignar'] = list(set(estado_dict.get('fotos_sin_asignar', []) + nuevos_contadores))

        total_fotos = len(estado_dict['fotos'])
        mensaje = f"<b>Fotos recibidas: {total_fotos}</b>\n\nPresiona <b>TERMINAR</b> para continuar con el registro."

        self._state_repo.guardar(user_id, estado_dict)

        # Etapa 6: structured log con timing
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "adjuntar_fotos | user_id=%s lote=%d total_fotos=%d elapsed=%.1fms",
            user_id, len(nuevos_contadores), len(estado_dict['fotos']), elapsed
        )

        return FSMResult(
            exito=True,
            mensaje=mensaje,
            nuevo_estado=EstadoConversacion.parse(estado_dict['estado']),
            finalizado=False
        )

    def responder(self, user_id: int, texto: str) -> FSMResult:
        """Procesa respuesta de texto según estado de la FSM."""
        t0 = time.monotonic()
        if not self._state_repo.tiene_conversacion(user_id):
            return FSMResult(exito=False, mensaje="No tienes un reporte en curso. Envía una foto primero.")

        estado_dict = self._state_repo.obtener(user_id)
        estado_actual = EstadoConversacion.parse(estado_dict.get('estado', 'ESPERANDO_FOTOS'))

        # Caso especial: TERMINAR en fase de fotos
        if estado_actual == EstadoConversacion.ESPERANDO_FOTOS:
            if texto.upper() == "TERMINAR":
                if not estado_dict.get('fotos'):
                    return FSMResult(exito=False, mensaje="No has enviado fotos aún.")

                estado_dict['estado'] = EstadoConversacion.ESPERANDO_MODELO.value
                self._state_repo.guardar(user_id, estado_dict)

                enable_part_number = os.getenv("ENABLE_PART_NUMBER", "false").lower() in ("true", "1", "yes")
                total_steps = 6 if enable_part_number else 5
                
                return FSMResult(
                    exito=True,
                    mensaje=(
                        "<b>¡Perfecto! Álbum cerrado.</b>\n\n"
                        f"Para completar el reporte, responde estas {total_steps} preguntas:\n\n"
                        f"<b>[1/{total_steps}] Modelo</b>\n"
                        "¿De qué modelo es el producto?\n"
                        "<code>Ej: ONN 32\" 100012589 AUO</code>"
                    ),
                    nuevo_estado=EstadoConversacion.ESPERANDO_MODELO
                )
            return FSMResult(exito=False, mensaje="Por favor envíame primero las <b>fotos</b> del defecto o presiona TERMINAR.")

        # Rechazar TERMINAR si ya no estamos en fase fotos
        if texto.upper() == "TERMINAR":
            return FSMResult(exito=False, mensaje="El álbum ya fue cerrado. Responde la pregunta actual para continuar.")

        datos = estado_dict.get('datos', {})

        context = FSMContext(
            telegram_id=user_id,
            estado=estado_actual,
            datos=datos
        )

        result = self._fsm.procesar_evento(context, texto.upper())

        if result.exito:
            estado_dict['datos'] = context.datos
            estado_dict['estado'] = context.estado.value if context.estado else None

            if result.finalizado:
                guardado = self._guardar_registro(user_id, estado_dict)
                if guardado:
                    resumen = self._generar_resumen(estado_dict)
                    result.mensaje = f"<b>¡Reporte guardado con éxito!</b>\n\n{resumen}\n\n<i>Para reportar otro defecto, simplemente envíame fotos nuevas.</i>"
                    try:
                        self._state_repo.finalizar(user_id)
                    except Exception as redis_exc:
                        # DB guardado OK; Redis falló → estado huérfano en Redis.
                        # Se requiere reconciliación manual o tarea de limpieza.
                        logger.error(
                            "RECONCILE_NEEDED | user_id=%s DB=OK Redis.finalizar FAILED: %s",
                            user_id, redis_exc
                        )
                else:
                    result.exito = False
                    result.mensaje = "Error al guardar en base de datos."
            else:
                self._state_repo.guardar(user_id, estado_dict)

        # Etapa 6: structured timing log
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "responder | user_id=%s estado=%s exito=%s finalizado=%s elapsed=%.1fms",
            user_id, estado_actual.value if estado_actual else None,
            result.exito, result.finalizado, elapsed
        )
        return result


    def _guardar_registro(self, user_id: int, conv: Dict) -> bool:
        """Guarda físicamente en DjangoRegistroRepository."""
        t0 = time.monotonic()
        try:
            t_usr = time.monotonic()
            usuario = self._usuario_repo.obtener(user_id)
            elapsed_usr = (time.monotonic() - t_usr) * 1000
            
            if not usuario:
                logger.error("_guardar_registro: user_id=%s no encontrado en repositorio", user_id)
                return False

            datos = conv.get('datos', {})
            
            t_db = time.monotonic()
            exito = self._registro_repo.guardar(
                user_id=user_id,
                turno=usuario['turno'],
                departamento=usuario['departamento'],
                modelo=datos.get('modelo', ''),
                numero_parte=datos.get('numero_parte'),
                linea=datos.get('linea', ''),
                cantidad=datos.get('cantidad', 1),
                responsable=datos.get('responsable', ''),
                descripcion=datos.get('descripcion', ''),
                fotos=conv.get('fotos', [])
            )
            elapsed_db = (time.monotonic() - t_db) * 1000
            elapsed_total = (time.monotonic() - t0) * 1000
            logger.info(
                "_guardar_registro | user_id=%s exito=%s fotos=%s usr_time=%.1fms db_time=%.1fms total=%.1fms",
                user_id, exito, conv.get('fotos', []), elapsed_usr, elapsed_db, elapsed_total
            )
            return exito
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.exception(
                "_guardar_registro | user_id=%s DB_ERROR elapsed=%.1fms error=%s",
                user_id, elapsed, exc
            )
            return False
        
    def _generar_resumen(self, conv: Dict) -> str:
        """Genera el texto de resumen para el usuario."""
        datos = conv.get('datos', {})
        num_parte = datos.get('numero_parte')
        part_str = f"<b>Num Parte:</b> {num_parte}\n" if num_parte and num_parte != "_OMITIR_" else ""
        
        return (
            f"<b>Modelo:</b> {datos.get('modelo')}\n"
            f"{part_str}"
            f"<b>Línea:</b> {datos.get('linea')}\n"
            f"<b>Cantidad:</b> {datos.get('cantidad')}\n"
            f"<b>Responsable:</b> {datos.get('responsable')}\n"
            f"<b>Descripción:</b> {datos.get('descripcion')}"
        )
