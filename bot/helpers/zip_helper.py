"""
bot/helpers/zip_helper.py

Helper puro: crea y envía un ZIP con imágenes al chat de Telegram.
Sin lógica de negocio, sin dependencias de repositorios.

SRP: única razón de cambio = cambiar cómo se empaquetan/envían los ZIPs.
"""
import os
import tempfile
import zipfile
from datetime import datetime

from telegram import Update

# Directorio base de fotos (constante de configuración)
FOTOS_PATH = "fotos"


async def crear_y_enviar_zip(
    update: Update,
    archivos_imagenes: list[str],
    sufijo: str,
    user_id: int,
) -> None:
    """
    Empaqueta una lista de archivos de imagen en un ZIP y lo envía al usuario.

    Args:
        update:            Contexto de Telegram con el mensaje activo.
        archivos_imagenes: Nombres de archivo (solo el basename) a incluir.
        sufijo:            Etiqueta descriptiva para el nombre del ZIP (ej. 'completo', 'lote_01').
        user_id:           ID del usuario dueño de las fotos.
    """
    nombre_zip: str | None = None
    try:
        user_folder = os.path.join(FOTOS_PATH, str(user_id))
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmpzip:
            with zipfile.ZipFile(tmpzip.name, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
                for archivo in archivos_imagenes:
                    ruta = os.path.join(user_folder, archivo)
                    
                    # Limpiar nombre para el ZIP (001_20231201_153022.jpg -> 001.jpg)
                    partes = archivo.split('_', 1)
                    if len(partes) > 1:
                        ext = os.path.splitext(archivo)[1]
                        nombre_limpio = f"{partes[0]}{ext}"
                    else:
                        nombre_limpio = archivo
                        
                    zipf.write(ruta, arcname=nombre_limpio)
            nombre_zip = tmpzip.name

        tamanio_mb = os.path.getsize(nombre_zip) / (1024 * 1024)

        with open(nombre_zip, "rb") as fzip:
            await update.message.reply_document(
                document=fzip,
                filename=f"fotos_defectos_{sufijo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                caption=f"ZIP con {len(archivos_imagenes)} imágenes ({tamanio_mb:.1f} MB)",
            )

    except Exception as e:
        await update.message.reply_text(f"Error al enviar el archivo ZIP {sufijo}: {e}")
    finally:
        if nombre_zip:
            try:
                os.remove(nombre_zip)
            except OSError as e:
                print(f"[WARN] No se pudo borrar ZIP temporal: {e}")
