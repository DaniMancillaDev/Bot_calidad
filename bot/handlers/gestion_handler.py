"""
bot/handlers/gestion_handler.py

Responsabilidad única: operaciones destructivas de limpieza.
  - /limpiar       → elimina los registros de BD del usuario (no afecta contador)
  - /limpiar_fotos → elimina las imágenes en disco del usuario (no afecta contador)

Bot hace: borrado físico de fotos del volumen (solo limpiar_fotos).
Backend hace: borrado BD (vía API).
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


def _borrar_archivos_usuario(user_id: int) -> int:
    """Borra fotos, thumbs y proxies de un usuario. Retorna total de archivos borrados."""
    total = 0
    for base in [FOTOS_PATH, THUMBS_PATH, PROXIES_PATH]:
        folder = os.path.join(base, str(user_id))
        if not os.path.exists(folder):
            continue
        for nombre_archivo in os.listdir(folder):
            ruta = os.path.join(folder, nombre_archivo)
            if os.path.isfile(ruta):
                try:
                    os.remove(ruta)
                    total += 1
                except OSError as e:
                    logger.warning("No se pudo borrar %s: %s", ruta, e)
    return total


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
            user_id = update.effective_user.id if update.effective_user else None if update.effective_user else None

            # Borrar archivos físicos ANTES de limpiar BD
            # (si el API falla, al menos el disco queda limpio)
            _borrar_archivos_usuario(user_id)
            resp = await api_client.limpiar_sesion(user_id)

            if resp.get('status') == 'cleaned':
                await update.message.reply_text(
                    "<b>Registros eliminados.</b>\n\n"
                    f"<b>Usuario:</b> {resp.get('nombre', user_id)}\n"
                    f"<b>Turno:</b> {resp.get('turno', '-')}\n"
                    f"<b>Departamento:</b> {resp.get('departamento', '-')}\n\n"
                    "<i>Solo se eliminaron tus registros del turno actual.</i>",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("<b>Error al eliminar registros.</b>", parse_mode="HTML")

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
            user_id = update.effective_user.id if update.effective_user else None if update.effective_user else None

            # Obtener perfil para mostrar nombre en respuesta
            perfil = await api_client.obtener_perfil(user_id)
            nombre = perfil.get('nombre', str(user_id)) if perfil else str(user_id)

            # Borrar fotos, thumbs y proxies — sin dejar huérfanos en ningún directorio
            fotos_eliminadas = _borrar_archivos_usuario(user_id)

            # Ahora sí reinicia el contador porque el usuario lo pidió
            await api_client.limpiar_fotos_sesion(user_id)

            await update.message.reply_text(
                "<b>Fotos eliminadas.</b>\n\n"
                f"<b>Usuario:</b> {nombre}\n"
                f"<b>Fotos eliminadas:</b> {fotos_eliminadas}\n"
                "<b>Contador:</b> Reiniciado a 1\n\n"
                "<i>Solo se eliminaron tus fotos del turno actual.</i>",
                parse_mode="HTML"
            )

        except Exception as e:
            logger.error("Error en /limpiar_fotos: %s", e)
            await update.message.reply_text(
                "<b>Error interno al eliminar fotos.</b>", parse_mode="HTML"
            )

    return limpiar_fotos
