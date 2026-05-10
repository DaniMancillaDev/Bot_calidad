"""
bot/helpers/zip_helper.py

Helper puro: crea y envía un ZIP con imágenes al chat de Telegram.
Sin lógica de negocio, sin dependencias de repositorios.

SRP: única razón de cambio = cambiar cómo se empaquetan/envían los ZIPs.
Etapa 4 (Fase 1): ZIP creación movida a thread executor (no bloquea asyncio).
"""
import asyncio
import logging
import os
import tempfile
import time
import zipfile
from datetime import datetime

from telegram import Update

logger = logging.getLogger(__name__)

# Directorio base de fotos (constante de configuración)
FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")


def _crear_zip_sync(archivos_imagenes: list, user_folder: str, tmp_path: str) -> int:
    """
    Función SÍNCRONA que crea el ZIP en disco.
    Se ejecuta en un thread pool, fuera del event loop de asyncio.
    Returns: número de archivos incluidos.
    """
    count = 0
    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for archivo in archivos_imagenes:
            if isinstance(archivo, tuple):
                ruta, nombre_limpio = archivo
            else:
                ruta = os.path.join(user_folder, archivo)
                partes = archivo.split('_', 1)
                if len(partes) > 1:
                    ext = os.path.splitext(archivo)[1]
                    nombre_limpio = f"{partes[0]}{ext}"
                else:
                    nombre_limpio = archivo

            if os.path.exists(ruta):
                zipf.write(ruta, arcname=nombre_limpio)
                count += 1
    return count


async def crear_y_enviar_zip(
    update: Update,
    archivos_imagenes: list[str],
    sufijo: str,
    user_id: int,
) -> None:
    """
    Empaqueta una lista de archivos de imagen en un ZIP y lo envía al usuario.
    La creación del ZIP se ejecuta en un thread pool (no bloquea asyncio).

    Args:
        update:            Contexto de Telegram con el mensaje activo.
        archivos_imagenes: Nombres de archivo (solo el basename) a incluir.
        sufijo:            Etiqueta descriptiva para el nombre del ZIP.
        user_id:           ID del usuario dueño de las fotos.
    """
    nombre_zip: str | None = None
    t0 = time.monotonic()
    try:
        user_folder = os.path.join(FOTOS_PATH, str(user_id))

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmpzip:
            nombre_zip = tmpzip.name

        # Etapa 4: Ejecutar en thread pool para NO bloquear asyncio
        loop = asyncio.get_event_loop()
        count = await loop.run_in_executor(
            None,
            _crear_zip_sync,
            archivos_imagenes,
            user_folder,
            nombre_zip,
        )

        elapsed_zip = (time.monotonic() - t0) * 1000
        tamanio_mb = os.path.getsize(nombre_zip) / (1024 * 1024)
        logger.info(
            "ZIP creado | user_id=%s archivos=%d size=%.1fMB elapsed_zip=%.1fms",
            user_id, count, tamanio_mb, elapsed_zip,
        )

        msg = update.message or update.callback_query.message
        t1 = time.monotonic()
        with open(nombre_zip, "rb") as fzip:
            await msg.reply_document(
                document=fzip,
                filename=f"fotos_defectos_{sufijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                caption=f"ZIP con {count} imágenes ({tamanio_mb:.1f} MB)",
                read_timeout=300,
                write_timeout=300,
            )
        elapsed_upload = (time.monotonic() - t1) * 1000
        logger.info(
            "ZIP enviado | user_id=%s elapsed_upload=%.1fms",
            user_id, elapsed_upload,
        )

    except Exception as e:
        msg = update.message or update.callback_query.message
        logger.error("Error al enviar ZIP %s: %s", sufijo, e)
        await msg.reply_text(f"Error al enviar el archivo ZIP {sufijo}: {e}")
    finally:
        if nombre_zip:
            try:
                os.remove(nombre_zip)
            except OSError as e:
                logger.warning("No se pudo borrar ZIP temporal: %s", e)
