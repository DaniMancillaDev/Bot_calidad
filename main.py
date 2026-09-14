"""
main.py — Entry Point

Responsabilidad única: arrancar el proceso.
  1. Cargar variables de entorno
  2. Construir el contenedor de dependencias
  3. Construir la aplicación Telegram
  4. Iniciar webhook (producción) o polling (fallback local)

No contiene handlers, factories ni lógica de negocio.
Todo el wiring vive en bot/app.py.
Todo el negocio vive en shared/.
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv('.env.local')

from shared.config.logging_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

from shared.config.dependencies import build_container
from bot.app import build_application

# Directorio base de fotos: Docker monta media_files en /app/media_files,
# local usa media_files/ relativo al proyecto.
FOTOS_PATH = os.getenv('FOTOS_PATH', 'media_files/fotos')
os.makedirs(FOTOS_PATH, exist_ok=True)


def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN no está configurado en las variables de entorno.")
        sys.exit(1)

    container = build_container()
    application = build_application(token, container)

    logger.info("Bot de Calidad iniciado (Clean Architecture)")

    webhook_url = os.getenv("WEBHOOK_URL")  # ej: https://iqa.danimancilladev.dev/webhook
    if webhook_url:
        logger.info("Modo WEBHOOK → %s", webhook_url)
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("WEBHOOK_PORT", "8001")),
            url_path="/webhook",
            webhook_url=webhook_url,
            secret_token=os.getenv("WEBHOOK_SECRET", ""),
            drop_pending_updates=True,
        )
    else:
        logger.info("Modo POLLING (WEBHOOK_URL no definida)")
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()