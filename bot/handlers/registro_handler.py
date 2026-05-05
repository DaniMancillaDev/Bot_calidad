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
import asyncio
import logging
import os
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from telegram.constants import ReactionEmoji

logger = logging.getLogger(__name__)

FOTOS_PATH = "fotos"

# Tiempo de debounce POR USUARIO para agrupar fotos.
# Telegram divide álbumes grandes (>10 fotos) en múltiples media_group_ids.
# Ej: 27 fotos → 3 albums con IDs distintos, enviados en ráfaga.
# 2.0s es suficiente para capturar la pausa entre albums consecutivos
# sin añadir latencia excesiva al usuario.
_DEBOUNCE_SECONDS = 2.0


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
            "3. <b>Responde a las preguntas</b> (Modelo, Línea, Responsable, etc.)\n\n"
            "<i>Usa el botón de <b>MENÚ</b> (abajo a la izquierda) para ver comandos útiles o escribe /info.</i>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    return start


# ─────────────────────────────────────────
# Foto recibida
# ─────────────────────────────────────────
def create_guardar_foto(usuario_repo, contador_repo, conversation_repo, foto_storage):
    """
    Factory para el handler de fotos entrantes.

    Debounce a NIVEL DE USUARIO (no por media_group_id).
    Telegram divide álbumes grandes (>10 fotos) en múltiples media_group_ids.
    Este handler agrupa TODAS las fotos de un usuario que lleguen dentro
    de la ventana de debounce, produciendo exactamente:
      - 1 mensaje "Recibiendo..."
      - 1 mensaje "Se han recibido N fotos"
    sin importar cuántos media_group_ids genere Telegram.

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

        # ===== FUNCIÓN INTERNA DE PROCESAMIENTO ATÓMICO =====
        async def _procesar_foto_ordenada(msg):
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
                return True
            except Exception as e:
                logger.error("Error descargando foto %s: %s", msg.message_id, e)
                return False

        # ===== DEBOUNCE A NIVEL DE USUARIO (NO POR MEDIA GROUP) =====
        #
        # Estructura en context.user_data:
        #   "photo_batch": {
        #       "messages": [msg1, msg2, ...],   ← TODAS las fotos pendientes
        #       "timer_task": Task | None,        ← un solo timer por usuario
        #       "wait_msg_id": int | None,        ← un solo mensaje de espera
        #   }
        #   "batch_lock": asyncio.Lock()          ← protege acceso concurrente

        if "batch_lock" not in context.user_data:
            context.user_data["batch_lock"] = asyncio.Lock()

        # ── Sección crítica: un solo lock por usuario ──
        async with context.user_data["batch_lock"]:
            is_first = "photo_batch" not in context.user_data

            if is_first:
                context.user_data["photo_batch"] = {
                    "messages": [],
                    "timer_task": None,
                    "wait_msg_id": None,
                }

            batch = context.user_data["photo_batch"]
            batch["messages"].append(update.message)

            # Solo la primera foto de todo el lote envía "Recibiendo..."
            if is_first:
                wait_msg = await update.message.reply_text(
                    "<i>Recibiendo y ordenando fotos, por favor espera...</i>",
                    parse_mode="HTML",
                )
                batch["wait_msg_id"] = wait_msg.message_id

            # Cancelar timer anterior (cada foto nueva reinicia el debounce)
            if batch["timer_task"] is not None:
                batch["timer_task"].cancel()

            # Nuevo timer: cuando pasen _DEBOUNCE_SECONDS sin fotos nuevas, procesar todo
            batch["timer_task"] = asyncio.create_task(
                _process_user_batch(
                    context, update.effective_chat.id,
                    user_id, _procesar_foto_ordenada, conversation_repo,
                )
            )
        # ── Fin sección crítica ──

    async def _process_user_batch(
        context, chat_id, user_id, procesar_fn, conversation_repo
    ):
        """
        Se ejecuta tras _DEBOUNCE_SECONDS sin fotos nuevas del usuario.
        Procesa TODAS las fotos acumuladas (de todos los media_group_ids)
        como un solo lote.
        """
        try:
            await asyncio.sleep(_DEBOUNCE_SECONDS)

            # Pop atómico del lote completo
            batch = context.user_data.pop("photo_batch", None)
            if not batch:
                return

            mensajes = batch["messages"]
            # Ordenar por message_id → respeta orden de selección del usuario
            mensajes.sort(key=lambda m: m.message_id)

            logger.info(
                "Procesando lote de %d foto(s) para user %s",
                len(mensajes), user_id,
            )

            exitos = 0
            for msg in mensajes:
                if await procesar_fn(msg):
                    exitos += 1

            if exitos == 0:
                await context.bot.send_message(
                    chat_id,
                    "<b>Error interno al guardar las fotos.</b>",
                    parse_mode="HTML",
                )
                return

            # Feedback al usuario
            conv_actual = conversation_repo.obtener(user_id)
            total = len(conv_actual["fotos"]) if conv_actual else exitos

            texto_estado = (
                f"<b>Se han recibido {total} fotos correctamente.</b>\n\n"
                "<i>Sigue enviando o presiona TERMINAR.</i>"
            )
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("TERMINAR", callback_data="terminar_fotos")]]
            )

            # Borrar mensaje temporal de "Recibiendo..."
            wait_msg_id = batch.get("wait_msg_id")
            if wait_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=chat_id, message_id=wait_msg_id,
                    )
                except Exception:
                    pass

            await context.bot.send_message(
                chat_id=chat_id,
                text=texto_estado,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

        except asyncio.CancelledError:
            # Esperado: llegó otra foto antes del debounce
            pass
        except Exception as e:
            logger.error("Error procesando lote de fotos para user %s: %s", user_id, e)

    return guardar_foto


# ─────────────────────────────────────────
# Callback: botón inline TERMINAR
# ─────────────────────────────────────────
def create_terminar_callback(registro_service):
    """
    Factory para el callback del botón inline TERMINAR.
    Procesa la acción como si el usuario hubiera escrito "TERMINAR".

    Args:
        registro_service: implementa .procesar_respuesta(user_id, texto) → Result
    """
    async def terminar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user:
            return

        await query.answer()  # Quitar "relojito" del botón

        user_id = update.effective_user.id
        result = registro_service.procesar_respuesta(user_id, "TERMINAR")

        # Quitar botón inline del mensaje anterior
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        if result.mensaje:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=result.mensaje,
                parse_mode="HTML",
            )

    return terminar_callback


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
            await update.message.reply_text(
                result.mensaje,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )

    return procesar_respuesta
