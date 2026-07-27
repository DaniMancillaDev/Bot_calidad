"""
bot/handlers/consulta_handler.py

Responsabilidad única: comandos de solo lectura / consulta.
  - /estado      → muestra contador y estadísticas del grupo
  - /info        → muestra la información del sistema y créditos

SRP : solo cambia si cambia la forma de presentar información al usuario.
DIP : recibe repos e interfaces, sin acceso a `db` ni filesystem directo.
ISP : cada factory recibe SOLO las dependencias que necesita.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# /estado
# ─────────────────────────────────────────
def create_estado(api_client):
    """
    Factory para /estado.

    Args:
        api_client: BotApiClient
    """
    async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None
            
            try:
                stats = await api_client.obtener_estadisticas(user_id)
            except Exception as e:
                if "404" in str(e):
                    await update.message.reply_text("<b>Usuario no registrado.</b>", parse_mode="HTML")
                else:
                    raise e
                return

            if stats.get("rol") == "admin":
                titulo = "Estado del grupo"
                lbl_registros = "Registros del grupo"
            else:
                titulo = "Estado personal"
                lbl_registros = "Registros propios"

            msg = (
                f"<b>{titulo}</b>\n"
                f"<i>Turno {stats['turno']} — {stats['departamento']}</i>\n\n"
                f"<b>Usuario:</b> {stats['nombre']}\n"
                f"<b>{lbl_registros} hoy:</b> {stats['total_registros']}\n"
            )

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error("Error en /estado: %s", e)
            await update.message.reply_text("<b>Error interno al obtener el estado.</b>", parse_mode="HTML")

    return estado


# ─────────────────────────────────────────
# /info
# ─────────────────────────────────────────
def create_info():
    """
    Factory para el comando /info (sin dependencias externas).
    Muestra la información del sistema y créditos del desarrollador.
    """
    async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
            
        texto = (
            "<b>Agente IQA</b>\n"
            "<i>Version 3.1</i>\n\n"
            "<b>Desarrollado por:</b> Daniel Hernandez\n\n"
            "Bot especializado en el registro y gestion de reportes de calidad en linea de produccion."
        )
        await update.message.reply_text(texto, parse_mode="HTML")
        
    return info
