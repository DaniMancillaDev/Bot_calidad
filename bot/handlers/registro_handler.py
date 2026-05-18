"""
bot/handlers/registro_handler.py

Responsabilidad única: flujo principal de registro de defectos.
  - /start              → reinicia/inicia sesión
  - foto recibida       → guarda la imagen y actualiza el contador
  - texto libre         → delega en RegistroService (FSM)

SRP : solo cambia si cambia el flujo de captura de defectos en Telegram.
DIP : recibe api_client. No tiene dependencias locales de base de datos ni FSM.
ISP : usa solo metodos de api_client.
"""
import asyncio
import logging
import os
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from telegram.constants import ReactionEmoji

logger = logging.getLogger(__name__)

import os
FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")

# Tiempo de debounce POR USUARIO para agrupar fotos.
# Telegram divide álbumes grandes (>10 fotos) en múltiples media_group_ids.
# Ej: 27 fotos → 3 albums con IDs distintos, enviados en ráfaga.
# 2.0s es suficiente para capturar la pausa entre albums consecutivos
# sin añadir latencia excesiva al usuario.
_DEBOUNCE_SECONDS = 2.0


# ─────────────────────────────────────────
# /start
# ─────────────────────────────────────────
def create_start(api_client):
    """
    Factory para /start.

    Args:
        api_client: BotApiClient
    """
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id if update.effective_user else None
        
        try:
            # Cancelamos la sesión anterior (FSM) sin borrar registros de BD
            await api_client.cancelar_sesion(user_id)
            await api_client.iniciar_defecto(user_id)

            await update.message.reply_text(
                "<b>Agente IQA</b>\n"
                "<i>Sistema de captura de defectos en linea de produccion.</i>\n\n"
                "<b>Flujo de registro:</b>\n"
                "1. <b>Envia las fotos</b> del defecto detectado (una o varias).\n"
                "2. Presiona <b>TERMINAR</b> para cerrar el album.\n"
                "3. <b>Responde el formulario:</b> Modelo, Linea, Responsable y descripcion.\n\n"
                "<i>Usa el menu inferior para ver los comandos disponibles, o escribe /info.</i>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception as e:
            logger.error("Error iniciando /start: %s", e)
            await update.message.reply_text(
                "<b>Error de conexion.</b> No se pudo iniciar la sesion. Intenta de nuevo.",
                parse_mode="HTML"
            )

    return start


# ─────────────────────────────────────────
# Foto recibida
# ─────────────────────────────────────────
def create_guardar_foto(api_client):
    """
    Factory para el handler de fotos entrantes.

    Debounce a NIVEL DE USUARIO (no por media_group_id).
    Agrupa TODAS las fotos en una ventana y las descarga temporalmente.
    Luego delega al backend la transición de FSM y renombrado.

    Args:
        api_client: BotApiClient
    """
    async def guardar_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id if update.effective_user else None
        
        try:
            perfil = await api_client.obtener_perfil(user_id)
            if not perfil:
                await update.message.reply_text(
                    "<b>Usuario no registrado.</b>\n"
                    "Contacta al administrador con tu ID de Telegram.\n"
                    f"Tu ID es: <code>{user_id}</code>",
                    parse_mode="HTML",
                )
                return
        except Exception as e:
            logger.error("Error verificando usuario para fotos: %s", e)
            return

        # ===== FUNCIÓN INTERNA DE DESCARGA TEMPORAL =====
        async def _descargar_foto_temporal(msg) -> int:
            try:
                photo = msg.photo[-1]
                file = await photo.get_file(read_timeout=30)

                nombre_archivo = f"tmp_{msg.message_id}.jpg"

                user_folder = os.path.join(FOTOS_PATH, str(user_id))
                os.makedirs(user_folder, exist_ok=True)
                ruta = os.path.join(user_folder, nombre_archivo)

                await file.download_to_drive(ruta)
                return msg.message_id
            except Exception as e:
                logger.error("Error descargando foto %s: %s", msg.message_id, e)
                return -1

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
                    user_id, _descargar_foto_temporal, api_client
                )
            )
        # ── Fin sección crítica ──

    async def _process_user_batch(
        context, chat_id, user_id, descargar_fn, api_client
    ):
        """
        Se ejecuta tras _DEBOUNCE_SECONDS sin fotos nuevas del usuario.
        """
        try:
            await asyncio.sleep(_DEBOUNCE_SECONDS)

            batch = context.user_data.pop("photo_batch", None)
            if not batch:
                return

            mensajes = batch["messages"]
            mensajes.sort(key=lambda m: m.message_id)

            logger.info("Descargando lote de %d foto(s) temporalmente para user %s", len(mensajes), user_id)

            fotos_ids = []
            for msg in mensajes:
                msg_id = await descargar_fn(msg)
                if msg_id != -1:
                    fotos_ids.append(msg_id)

            if not fotos_ids:
                await context.bot.send_message(
                    chat_id,
                    "<b>Error interno al descargar las fotos.</b>",
                    parse_mode="HTML",
                )
                return

            # Delegar FSM al backend
            try:
                result = await api_client.adjuntar_evidencia_lote(user_id, fotos_ids)
                
                texto_estado = result.get('mensaje', f"Se agregaron {len(fotos_ids)} foto(s).")
                
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("TERMINAR", callback_data="terminar_fotos")]]
                )
            except Exception as e:
                logger.error("Error enviando lote al backend para user %s: %s", user_id, e)
                texto_estado = "<b>Error al procesar lote en el servidor.</b>"
                reply_markup = None

            # Borrar mensaje temporal de "Recibiendo..."
            wait_msg_id = batch.get("wait_msg_id")
            if wait_msg_id:
                try:
                    await context.bot.delete_message(
                        chat_id=chat_id, message_id=wait_msg_id,
                    )
                except Exception:
                    pass

            # Quitar botones TERMINAR de mensajes anteriores (si hay)
            terminar_msg_ids = context.user_data.get("terminar_msg_ids", [])
            for old_msg_id in terminar_msg_ids:
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=chat_id, message_id=old_msg_id, reply_markup=None
                    )
                except Exception:
                    pass

            sent_msg = await context.bot.send_message(
                chat_id=chat_id,
                text=texto_estado,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

            # Rastrear ID del mensaje con botón TERMINAR para limpiarlo después
            if reply_markup:
                if "terminar_msg_ids" not in context.user_data:
                    context.user_data["terminar_msg_ids"] = []
                context.user_data["terminar_msg_ids"].append(sent_msg.message_id)

        except asyncio.CancelledError:
            # Esperado: llegó otra foto antes del debounce
            pass
        except Exception as e:
            logger.error("Error procesando lote de fotos para user %s: %s", user_id, e)

    return guardar_foto


# ─────────────────────────────────────────
# Callback: botón inline TERMINAR
# ─────────────────────────────────────────
def create_terminar_callback(api_client):
    """
    Factory para el callback del botón inline TERMINAR.
    """
    async def terminar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user:
            return

        await query.answer()

        user_id = update.effective_user.id if update.effective_user else None
        
        try:
            result = await api_client.responder_defecto(user_id, "TERMINAR")
            exito = result.get('exito', False)
            mensaje = result.get('mensaje')
        except Exception as e:
            logger.error("Error terminando fotos para %s: %s", user_id, e)
            exito = False
            mensaje = "Error al procesar la terminación del álbum."

        # Quitar TODOS los botones inline TERMINAR de mensajes previos
        terminar_msg_ids = context.user_data.pop("terminar_msg_ids", [])
        for msg_id in terminar_msg_ids:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=update.effective_chat.id, message_id=msg_id, reply_markup=None
                )
            except Exception:
                pass

        # Solo enviar mensaje si TERMINAR fue exitoso (álbum cerrado)
        if exito and mensaje:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=mensaje,
                parse_mode="HTML",
            )
        elif not exito and mensaje:
            # TERMINAR rechazado (ya no en ESPERANDO_FOTOS) — feedback breve
            await query.answer(text=mensaje, show_alert=True)

    return terminar_callback


# ─────────────────────────────────────────
# Texto libre → FSM
# ─────────────────────────────────────────
def create_procesar_respuesta(api_client):
    """
    Factory: adaptador delgado Telegram → API.
    """
    async def procesar_respuesta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or not update.message.text:
            return

        user_id = update.effective_user.id if update.effective_user else None
        
        try:
            result = await api_client.responder_defecto(user_id, update.message.text)
            mensaje = result.get('mensaje')
        except Exception as e:
            logger.error("Error procesando texto libre para %s: %s", user_id, e)
            mensaje = "Error al procesar tu respuesta."

        if mensaje:
            await update.message.reply_text(
                mensaje,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )

    return procesar_respuesta
