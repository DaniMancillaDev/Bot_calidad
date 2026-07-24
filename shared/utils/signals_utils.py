import contextlib
from django.db.models.signals import post_save
from calidad.models import RegistroDefecto

@contextlib.contextmanager
def disable_telegram_signals():
    """
    Deshabilita temporalmente los receptores de post_save en RegistroDefecto
    para evitar el spam de Telegram durante operaciones masivas o bulk.
    """
    original_receivers = post_save.receivers[:]
    post_save.receivers = []
    
    try:
        yield
    finally:
        post_save.receivers = original_receivers
