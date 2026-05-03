"""
bot/handlers/auth_handler.py

Responsabilidad única: autenticación y control de acceso.
  - /mi_id   → devuelve el ID de Telegram al usuario
  - middleware verificar_acceso → bloquea usuarios no registrados

SRP : solo cambia si cambia la política de acceso.
DIP : recibe usuario_repo (Protocol), no DatabaseManager concreto.
"""
from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes


async def comando_mi_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía el ID de Telegram al usuario para que pueda registrarse."""
    if not update.message:
        return
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"<b>Tu ID de Telegram es:</b> <code>{user_id}</code>\n\n"
        "<i>Copia y pásale este número al Administrador del sistema para que te dé de alta.</i>",
        parse_mode="HTML",
    )


def create_verificar_acceso(usuario_repo):
    """
    Factory: middleware que bloquea usuarios no registrados.

    Args:
        usuario_repo: implementa .tiene_acceso(user_id) → bool
    """
    async def verificar_acceso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user:
            return

        user_id = update.effective_user.id

        if not usuario_repo.tiene_acceso(user_id):
            # /mi_id siempre permitido para que puedan solicitar acceso
            if (
                update.message
                and update.message.text
                and update.message.text.startswith("/mi_id")
            ):
                return

            if update.message:
                await update.message.reply_text(
                    "<b>ACCESO DENEGADO</b>\n\n"
                    "No tienes permisos para usar este bot.\n"
                    "Escribe /mi_id para obtener tu identificador y registrarte.",
                    parse_mode="HTML"
                )
            raise ApplicationHandlerStop()

    return verificar_acceso
