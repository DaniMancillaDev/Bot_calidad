import os
from bot.client.api_client import BotApiClient
from shared.infrastructure.storage.foto_storage import LocalFotoStorage


def build_container(db=None):
    """
    Contenedor de dependencias (inyección manual).
    Intercambiar backend de storage = cambiar solo aquí.
    """
    api_url = os.getenv("API_BASE_URL", "http://web:8000")
    api_key = os.getenv("BOT_API_KEY", "default-internal-secret-key-123")
    api_client = BotApiClient(base_url=api_url, api_key=api_key)

    # Etapa 5: Storage abstracto. Cambiar LocalFotoStorage → S3FotoStorage aquí.
    foto_storage = LocalFotoStorage(
        base_path=os.getenv("FOTOS_PATH", "media_files/fotos"),
        thumbs_path=os.getenv("THUMBS_PATH", "media_files/thumbs"),
    )

    return {
        'api_client': api_client,
        'foto_storage': foto_storage,
    }
