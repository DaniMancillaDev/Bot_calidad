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


import time

# Caché en memoria: {user_id: (timestamp, tiene_acceso)}
_CACHE_ACCESO = {}
TTL_CACHE = 60 # segundos

async def comando_mi_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía el ID de Telegram al usuario para que pueda registrarse."""
    if not update.message:
        return
    user_id = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(
        f"<b>Tu ID de Telegram es:</b> <code>{user_id}</code>\n\n"
        "<i>Copia y pásale este número al Administrador del sistema para que te dé de alta.</i>",
        parse_mode="HTML",
    )


def create_verificar_acceso(api_client):
    """
    Factory: middleware que bloquea usuarios no registrados.

    Args:
        api_client: instancia de BotApiClient
    """
    async def verificar_acceso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_user:
            return

        user_id = update.effective_user.id if update.effective_user else None

        # ── Lógica de Caché ──
        ahora = time.time()
        if user_id in _CACHE_ACCESO:
            ts, cached_val = _CACHE_ACCESO[user_id]
            if ahora - ts < TTL_CACHE:
                if not cached_val:
                    raise ApplicationHandlerStop()
                return

        try:
            resp = await api_client.tiene_acceso(user_id)
            tiene_acceso = resp.get("tiene_acceso", False)
            # Guardar en caché
            _CACHE_ACCESO[user_id] = (ahora, tiene_acceso)
        except Exception as e:
            # En caso de error de red, asumimos sin acceso y mostramos mensaje amigable
            tiene_acceso = False
            if update.message and not update.message.text.startswith("/mi_id"):
                await update.message.reply_text("<b>Conectando con el servidor.</b> Por favor intenta de nuevo.", parse_mode="HTML")
                raise ApplicationHandlerStop()

        if not tiene_acceso:
            # /mi_id siempre permitido para que puedan solicitar acceso
            if (
                update.message
                and update.message.text
                and update.message.text.startswith("/mi_id")
            ):
                return

            if update.message:
                await update.message.reply_text(
                    "<b>Acceso denegado.</b>\n\n"
                    "No tienes permisos para usar este sistema.\n"
                    "Escribe /mi_id para obtener tu ID y compartirlo con el administrador.",
                    parse_mode="HTML"
                )
            raise ApplicationHandlerStop()

    return verificar_acceso
