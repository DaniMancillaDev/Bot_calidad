import functools
from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

def prevent_double_tap(func):
    """
    Decorador para prevenir la ejecución concurrente de callbacks (double-tap)
    por parte del mismo usuario. Usa context.user_data como un Lock en memoria.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # Usamos un flag global por usuario
        lock_key = "is_processing_callback"
        
        if context.user_data.get(lock_key):
            # Si el usuario hace doble tap rápido, ignoramos silenciosamente.
            # Opcional: await update.callback_query.answer("Procesando...", show_alert=False)
            logger.debug("Doble tap bloqueado para usuario %s", update.effective_user.id)
            return
            
        context.user_data[lock_key] = True
        try:
            return await func(update, context, *args, **kwargs)
        finally:
            # Siempre liberamos el lock, incluso si hay error
            context.user_data[lock_key] = False
            
    return wrapper
