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
import os
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from telegram.constants import ReactionEmoji

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
            "<b>¡Hola! Listo para registrar defectos.</b>\n\n"
            "<b>Paso 1: Envía las fotos del defecto</b>\n"
            "Puedes enviar una o varias. Cuando termines, simplemente toca el botón <b>TERMINAR</b>.\n\n"
            "<i>Tip: Para ver otras opciones, usa el menú o escribe /</i>",
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

        photo = update.message.photo[-1]
        file = await photo.get_file()

        contador = contador_repo.obtener_y_avanzar(user_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{contador:03d}_{timestamp}.jpg"

        user_folder = os.path.join(FOTOS_PATH, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        ruta = os.path.join(user_folder, nombre_archivo)

        try:
            await file.download_to_drive(ruta)
        except Exception as e:
            print(f"Error descargando foto: {e}")
            await update.message.reply_text("<b>Error interno al guardar la foto en el servidor.</b>", parse_mode="HTML")
            return

        conv = conversation_repo.obtener(user_id)
        if conv is not None:
            conv["fotos"].append(contador)
            conversation_repo.persistir()

        # Debouncing: Esperar a que lleguen todas las fotos de la ráfaga (álbum) antes de enviar el feedback
        import asyncio

        # Si ya había una tarea de feedback esperando, la cancelamos
        tarea_anterior = context.user_data.get("feedback_task")
        if tarea_anterior:
            tarea_anterior.cancel()

        async def send_feedback():
            try:
                # Esperamos 1.5 segundos para agrupar fotos enviadas en álbum o en ráfaga
                await asyncio.sleep(1.5)
                
                conv_actual = conversation_repo.obtener(user_id)
                total = len(conv_actual["fotos"]) if conv_actual else 1
                
                texto_estado = (
                    f"<b>Se han recibido {total} fotos correctamente.</b>\n\n"
                    "<i>Sigue enviando o presiona el botón <b>TERMINAR</b>.</i>"
                )
                
                reply_markup = ReplyKeyboardMarkup([["TERMINAR"]], resize_keyboard=True)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=texto_estado,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            except asyncio.CancelledError:
                # La tarea fue cancelada porque llegó otra foto muy rápido. Comportamiento esperado.
                pass
            except Exception as e:
                print(f"Error enviando feedback: {e}")

        # Creamos la nueva tarea en background
        nueva_tarea = asyncio.create_task(send_feedback())
        context.user_data["feedback_task"] = nueva_tarea

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
            await update.message.reply_text(
                result.mensaje,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )

    return procesar_respuesta
