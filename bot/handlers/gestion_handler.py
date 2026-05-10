"""
bot/handlers/gestion_handler.py

Responsabilidad única: operaciones destructivas de limpieza.
  - /limpiar       → elimina los registros de BD del usuario y reinicia contador
  - /limpiar_fotos → elimina las imágenes en disco del usuario y reinicia contador

Bot hace: borrado físico de fotos del volumen (solo limpiar_fotos).
Backend hace: borrado BD + reinicio de contador (vía API).
"""
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

import os
FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")


def create_limpiar(api_client):
    """
    Factory para /limpiar.

    Args:
        api_client:        BotApiClient
    """
    async def limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None

            resp = await api_client.limpiar_sesion(user_id)

            if resp.get('status') == 'cleaned':
                await update.message.reply_text(
                    "<b>Registros limpiados:</b>\n\n"
                    f"• <b>Usuario:</b> {resp.get('nombre', user_id)}\n"
                    f"• <b>Turno:</b> {resp.get('turno', '-')}\n"
                    f"• <b>Depto:</b> {resp.get('departamento', '-')}\n\n"
                    "<i>Solo se eliminaron TUS registros.</i>",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("<b>Error al limpiar registros.</b>", parse_mode="HTML")

        except Exception as e:
            logger.error("Error en /limpiar: %s", e)
            await update.message.reply_text(
                "<b>Error interno al limpiar registros.</b>", parse_mode="HTML"
            )

    return limpiar


def create_limpiar_fotos(api_client):
    """
    Factory para /limpiar_fotos.

    Args:
        api_client:        BotApiClient
    """
    async def limpiar_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None

            # Obtener perfil para mostrar nombre en respuesta
            perfil = await api_client.obtener_perfil(user_id)
            nombre = perfil.get('nombre', str(user_id)) if perfil else str(user_id)

            # Borrado físico del volumen local (el bot tiene acceso al volumen)
            user_folder = os.path.join(FOTOS_PATH, str(user_id))
            fotos_eliminadas = 0
            if os.path.exists(user_folder):
                for nombre_archivo in os.listdir(user_folder):
                    ruta = os.path.join(user_folder, nombre_archivo)
                    if os.path.isfile(ruta):
                        os.remove(ruta)
                        fotos_eliminadas += 1

            # Reiniciar contador en backend
            await api_client.limpiar_fotos_sesion(user_id)

            await update.message.reply_text(
                "<b>Fotos eliminadas:</b>\n\n"
                f"• <b>Usuario:</b> {nombre}\n"
                f"• <b>Fotos eliminadas:</b> {fotos_eliminadas}\n"
                "• <b>Contador reiniciado a:</b> 001\n\n"
                "<i>Solo se eliminaron TUS fotos.</i>",
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error("Error en /limpiar_fotos: %s", e)
            await update.message.reply_text(
                "<b>Error interno al eliminar fotos.</b>", parse_mode="HTML"
            )

    return limpiar_fotos
