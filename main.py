"""
main.py — Entry Point

Responsabilidad única: arrancar el proceso.
  1. Cargar variables de entorno
  2. Construir el contenedor de dependencias
  3. Construir la aplicación Telegram
  4. Iniciar el polling

No contiene handlers, factories ni lógica de negocio.
Todo el wiring vive en bot/app.py.
Todo el negocio vive en shared/.
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from shared.config.logging_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

from database import db
from shared.config.dependencies import build_container
from bot.app import build_application

# Directorio base de fotos (se crea si no existe)
FOTOS_PATH = "fotos"
os.makedirs(FOTOS_PATH, exist_ok=True)


def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN no está configurado en las variables de entorno.")
        sys.exit(1)

    container = build_container(db)
    application = build_application(token, container)

    logger.info("Bot de Calidad iniciado (Clean Architecture)")
    application.run_polling()


if __name__ == "__main__":
    main()