"""
bot/handlers/registro_handler.py

Responsabilidad única: flujo principal de registro de defectos.
  - /start              → reinicia/inicia sesión
  - foto recibida       → guarda la imagen y actualiza el contador
  - texto libre         → delega en RegistroService (FSM)

SRP : solo cambia si cambia el flujo de captura de defectos.
DIP : recibe repos e interfaces, no concretos ni `db`.
ISP : cada factory recibe SOLO las dependencias que necesita.
"""
import logging
import os
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from telegram.constants import ReactionEmoji

logger = logging.getLogger(__name__)

FOTOS_PATH = "fotos"


# ─────────────────────────────────────────
# /start
# ─────────────────────────────────────────
def create_start(conversation_repo):
    """
    Factory para /start.

    Args:
        conversation_repo: implementa .finalizar(), .iniciar()
    """
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        conversation_repo.finalizar(user_id)   # idempotente
        conversation_repo.iniciar(user_id)

        await update.message.reply_text(
            "<b>Agente IQA</b>\n\n"
            "Bienvenido al asistente de captura de defectos. Este bot está diseñado "
            "para agilizar el reporte de incidencias en línea de producción.\n\n"
            "<b>Flujo de Trabajo:</b>\n"
            "1. <b>Envía las fotos</b> del defecto detectado (una o varias).\n"
            "2. Presiona el botón <b>TERMINAR</b> para cerrar el álbum.\n"
            "3. <b>Responde a las preguntas</b> (Modelo, Línea, Responsable, etc.).\n\n"
            "<i>Usa el botón de <b>MENÚ</b> (abajo a la izquierda) para ver comandos útiles o escribe /info.</i>",
            parse_mode="HTML",
        )

    return start


# ─────────────────────────────────────────
# Foto recibida
# ─────────────────────────────────────────
def create_guardar_foto(usuario_repo, contador_repo, conversation_repo, foto_storage):
    """
    Factory para el handler de fotos entrantes.

    Args:
        usuario_repo:      implementa .obtener(user_id)
        contador_repo:     implementa .obtener_y_avanzar(user_id)
        conversation_repo: implementa .tiene_conversacion(), .iniciar(), .obtener(), .persistir()
        foto_storage:      (reservado para futura abstracción de almacenamiento)
    """
    async def guardar_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id
        usuario = usuario_repo.obtener(user_id)

        if not usuario:
            await update.message.reply_text(
                "<b>Usuario no registrado.</b>\n"
                "Contacta al administrador con tu ID de Telegram.\n"
                f"Tu ID es: <code>{user_id}</code>",
                parse_mode="HTML",
            )
            return

        if not conversation_repo.tiene_conversacion(user_id):
            conversation_repo.iniciar(user_id)
            context.user_data["status_message_id"] = None

        # ===== FUNCIÓN INTERNA DE PROCESAMIENTO ATÓMICO =====
        async def _procesar_foto_ordenada(msg):
            if not msg.photo:
                return "INVALID"
            try:
                photo = msg.photo[-1]
                file = await photo.get_file(read_timeout=30)

                contador = contador_repo.obtener_y_avanzar(user_id)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nombre_archivo = f"{contador:03d}_{timestamp}.jpg"

                user_folder = os.path.join(FOTOS_PATH, str(user_id))
                os.makedirs(user_folder, exist_ok=True)
                ruta = os.path.join(user_folder, nombre_archivo)

                await file.download_to_drive(ruta)

                conv = conversation_repo.obtener(user_id)
                if conv is not None:
                    conv["fotos"].append(contador)
                    conversation_repo.persistir()
                return "OK"
            except Exception as e:
                logger.error("Error descargando foto %s: %s", msg.message_id, e)
                return "ERROR"

        # ===== SISTEMA DE BUFFERING Y DEBOUNCING =====
        import asyncio

        if "photo_batch" not in context.user_data:
            context.user_data["photo_batch"] = {
                "messages": [],
                "timer_task": None,
                "wait_msg_id": None,
                "sending_wait_msg": False
            }
        if "processing_lock" not in context.user_data:
            context.user_data["processing_lock"] = asyncio.Lock()
        if "is_processing" not in context.user_data:
            context.user_data["is_processing"] = False

        grupo = context.user_data["photo_batch"]
        
        # is_first = no hay mensaje de espera ya visible en el chat
        # Usamos sending_wait_msg como un lock síncrono para evitar race conditions
        is_first = False
        if grupo["wait_msg_id"] is None and not grupo.get("sending_wait_msg"):
            is_first = True
            grupo["sending_wait_msg"] = True

        grupo["messages"].append(update.message)

        # Mandamos el mensaje de espera solo si no hay uno visible ya
        if is_first:
            try:
                wait_msg = await update.message.reply_text("<i>Recibiendo y ordenando fotos, por favor espera...</i>", parse_mode="HTML")
                grupo["wait_msg_id"] = wait_msg.message_id
            finally:
                grupo["sending_wait_msg"] = False

        # Cancelar timer anterior si existe
        if grupo["timer_task"]:
            grupo["timer_task"].cancel()

        # Función que se ejecutará tras 3.5s de inactividad
        async def process_batch(chat_id):
            try:
                await asyncio.sleep(3.5)
            except asyncio.CancelledError:
                return  # Nueva foto canceló el timer
                
            grupo["timer_task"] = None
            
            # Si ya hay un lote procesándose, dejamos que el bucle activo consuma los mensajes
            if context.user_data["is_processing"]:
                return

            context.user_data["is_processing"] = True
            lock = context.user_data["processing_lock"]
            
            async with lock:
                try:
                    exitos = 0
                    invalidos = 0
                    
                    # Consumir mensajes continuamente mientras sigan llegando
                    while grupo["messages"]:
                        mensajes = list(grupo["messages"])
                        grupo["messages"].clear()
                        
                        # Ordenar por message_id para asegurar el orden de selección
                        mensajes.sort(key=lambda m: m.message_id)
                        
                        for msg in mensajes:
                            res = await _procesar_foto_ordenada(msg)
                            if res == "OK":
                                exitos += 1
                            elif res == "INVALID":
                                invalidos += 1
                    
                    wait_msg_id = grupo["wait_msg_id"]
                    reply_markup = ReplyKeyboardMarkup([["TERMINAR"]], resize_keyboard=True)

                    if exitos == 0 and invalidos > 0:
                        mensaje_invalido = (
                            " <b>Archivo no válido.</b>\n"
                            "El sistema solo acepta <b>fotos comprimidas</b>.\n"
                            "Los videos o documentos son ignorados."
                        )
                        if conversation_repo.tiene_conversacion(user_id):
                            conv_act = conversation_repo.obtener(user_id)
                            fotos_c = len(conv_act.get("fotos", []))
                            mensaje_invalido += f"\n\nTienes <b>{fotos_c} fotos</b> en el registro actual.\n¿Qué deseas hacer?"
                        # Editar el mensaje de espera con el aviso de archivo inválido
                        if wait_msg_id:
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=chat_id, message_id=wait_msg_id,
                                    text=mensaje_invalido, parse_mode="HTML"
                                )
                            except Exception:
                                await context.bot.send_message(chat_id, mensaje_invalido, parse_mode="HTML")
                        else:
                            await context.bot.send_message(chat_id, mensaje_invalido, parse_mode="HTML")
                        if conversation_repo.tiene_conversacion(user_id):
                            await context.bot.send_message(chat_id, "Elige una opción:", reply_markup=reply_markup)
                        grupo["wait_msg_id"] = None
                        return

                    if exitos == 0:
                        if wait_msg_id:
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=chat_id, message_id=wait_msg_id,
                                    text="<b>Error interno al guardar las fotos.</b>", parse_mode="HTML"
                                )
                            except Exception:
                                await context.bot.send_message(chat_id, "<b>Error interno al guardar las fotos.</b>", parse_mode="HTML")
                        grupo["wait_msg_id"] = None
                        return

                    # Feedback final: editar el mensaje de espera con el resultado acumulado
                    total_exitos = exitos
                    if conversation_repo.tiene_conversacion(user_id):
                        conv_act = conversation_repo.obtener(user_id)
                        total_exitos = len(conv_act.get("fotos", []))

                    texto_estado = f"<b>Se han recibido {total_exitos} fotos correctamente.</b>\n"
                    if invalidos > 0:
                        texto_estado += f" <i>{invalidos} archivo(s) ignorados (no eran fotos).</i>\n"
                    texto_estado += "\n<i>Sigue enviando o presiona el botón <b>TERMINAR</b>.</i>"
                    
                    if wait_msg_id:
                        try:
                            await context.bot.edit_message_text(
                                chat_id=chat_id, message_id=wait_msg_id,
                                text=texto_estado, parse_mode="HTML"
                            )
                        except Exception:
                            await context.bot.send_message(
                                chat_id=chat_id, text=texto_estado,
                                parse_mode="HTML", reply_markup=reply_markup
                            )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id, text=texto_estado,
                            parse_mode="HTML", reply_markup=reply_markup
                        )
                    grupo["wait_msg_id"] = None
                except Exception as e:
                    logger.error("Error procesando lote de fotos: %s", e)
                finally:
                    context.user_data["is_processing"] = False

        # Iniciar el nuevo timer
        grupo["timer_task"] = asyncio.create_task(process_batch(update.effective_chat.id))

    return guardar_foto


# ─────────────────────────────────────────
# Texto libre → FSM
# ─────────────────────────────────────────
def create_procesar_respuesta(registro_service):
    """
    Factory: adaptador delgado Telegram → RegistroService.

    Args:
        registro_service: implementa .procesar_respuesta(user_id, texto) → Result
    """
    async def procesar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not update.message.text:
            return

        user_id = update.effective_user.id
        result = registro_service.procesar_respuesta(user_id, update.message.text)

        if result.mensaje:
            # Limpiar el mensaje de espera de fotos si el usuario interactúa (por ejemplo, con TERMINAR)
            if "photo_batch" in context.user_data:
                context.user_data["photo_batch"]["wait_msg_id"] = None
                
            await update.message.reply_text(
                result.mensaje,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )

    return procesar_respuesta
