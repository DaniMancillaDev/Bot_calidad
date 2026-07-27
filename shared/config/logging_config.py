"""
Configuración centralizada de logging para el bot de calidad.

Uso en cualquier módulo:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("mensaje")
    logger.error("error: %s", e)

Niveles:
    DEBUG   → detalles de desarrollo
    INFO    → eventos normales (inicio, registros guardados)
    WARNING → situaciones recuperables (orientación fallida, fotos no encontradas)
    ERROR   → fallos que afectan funcionalidad
"""

import logging
import os



def setup_logging() -> None:
    """Configura logging global con salida a consola y archivo rotativo."""

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "bot.log")

    # Formato legible con timestamp, módulo y nivel
    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),  # Consola (stdout)
    ]

    # Archivo rotativo (solo si hay path configurado)
    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )

    # Silenciar loggers ruidosos de terceros
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("onnxruntime").setLevel(logging.WARNING)
