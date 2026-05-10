import os
from bot.client.api_client import BotApiClient

def build_container(db=None):
    """
    Construye el contenedor de dependencias (inyección manual).
    Paso 1 del desacoplamiento: inyectamos api_client y lo empezamos a usar.
    """
    api_url = os.getenv("API_BASE_URL", "http://web:8000")
    api_key = os.getenv("BOT_API_KEY", "default-internal-secret-key-123")
    api_client = BotApiClient(base_url=api_url, api_key=api_key)

    return {
        'api_client': api_client,
    }
