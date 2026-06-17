"""
bot/handlers/cancelar_handler.py

Responsabilidad única: cancelar un registro en curso y hacer rollback
del contador de fotos al valor previo a la sesión.

Bot hace: borrado físico de fotos del disco (tiene acceso al volumen).
Backend hace: rollback del contador (vía API).
"""
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

import os
FOTOS_PATH   = os.getenv("FOTOS_PATH",   "media_files/fotos")
THUMBS_PATH  = os.getenv("THUMBS_PATH",  "media_files/thumbs")
PROXIES_PATH = os.getenv("PROXIES_PATH", "media_files/proxies")


def create_cancelar(api_client):
    """
    Factory para /cancelar.

    Args:
        api_client:        BotApiClient
    """
    async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        try:
            user_id = update.effective_user.id if update.effective_user else None

            # Cancelar buffers temporales (fotos en debounce)
            batch = context.user_data.pop("photo_batch", None)
            if batch:
                if batch.get("timer_task"):
                    batch["timer_task"].cancel()
                wait_msg_id = batch.get("wait_msg_id")
                if wait_msg_id:
                    try:
                        await context.bot.delete_message(
                            chat_id=update.effective_chat.id, message_id=wait_msg_id
                        )
                    except Exception:
                        pass

            # Rollback de contador + limpieza backend vía API
            try:
                resp = await api_client.cancelar_sesion(user_id)
                contador_revertido = resp.get("contador_revertido")
                fotos = resp.get("fotos", [])
            except Exception as e:
                logger.error("Error llamando API cancelar_sesion: %s", e)
                await update.message.reply_text(
                    "<b>Error de red.</b> No se pudo cancelar la sesion. Intenta de nuevo.",
                    parse_mode="HTML"
                )
                return

            fotos_eliminadas = 0

            # Borrado físico en fotos/, thumbs/ y proxies/ para no dejar huérfanos
            for base_path in [FOTOS_PATH, THUMBS_PATH, PROXIES_PATH]:
                user_folder = os.path.join(base_path, str(user_id))
                if not os.path.exists(user_folder):
                    continue
                archivos = os.listdir(user_folder)

                # 1. Borrar por número de foto de la sesión cancelada
                for numero_foto in fotos:
                    prefijo = f"{int(numero_foto):03d}_"
                    for archivo in archivos:
                        if archivo.startswith(prefijo):
                            ruta = os.path.join(user_folder, archivo)
                            try:
                                os.remove(ruta)
                                fotos_eliminadas += 1
                                logger.info("Foto eliminada: %s", ruta)
                            except OSError as e:
                                logger.warning("No se pudo eliminar %s: %s", ruta, e)

                # 2. Borrar temporales huérfanas (tmp_*.jpg) del debounce
                for archivo in archivos:
                    if archivo.startswith("tmp_") and archivo.endswith(".jpg"):
                        ruta = os.path.join(user_folder, archivo)
                        try:
                            os.remove(ruta)
                            fotos_eliminadas += 1
                            logger.info("Temporal huérfana eliminada: %s", ruta)
                        except OSError as e:
                            logger.warning("No se pudo eliminar temporal %s: %s", ruta, e)

            msg = "<b>Registro cancelado.</b>\n\n"
            msg += f"<b>Fotos eliminadas:</b> {fotos_eliminadas}\n"
            if contador_revertido is not None:
                msg += f"<b>Siguiente foto:</b> {contador_revertido:03d}\n"
            msg += "<i>Los datos del intento no fueron guardados.</i>"
            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error("Error en /cancelar: %s", e)
            await update.message.reply_text(
                "<b>Error interno al cancelar la operación.</b>", parse_mode="HTML"
            )

    return cancelar
