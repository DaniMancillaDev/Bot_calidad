"""
web/calidad/tasks.py

Tareas Celery para generación de reportes Excel y thumbnails en background.

- generar_thumbnail_task: genera miniaturas de fotos async sin bloquear el flujo.
- generar_excel_task: genera reportes Excel en background.

Estado se guarda en Redis. Compatible con múltiples workers y Gunicorn.
"""
import logging
import os
import zipfile
import tempfile
import re
import time
from pathlib import Path
from datetime import datetime

from celery import shared_task

logger = logging.getLogger(__name__)

# ── Configuración de thumbnails ────────────────────────────────────────────────
THUMB_SIZE = (300, 300)
THUMB_QUALITY = 75
FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")
THUMBS_PATH = os.getenv("THUMBS_PATH", "media_files/thumbs")


@shared_task(
    bind=True,
    name='calidad.tasks.generar_thumbnail_task',
    max_retries=2,
    default_retry_delay=10,
    ignore_result=True,     # No necesitamos el resultado en Redis
)
def generar_thumbnail_task(self, user_id: int, foto_path: str) -> None:
    """
    Genera thumbnail JPEG (300×300) de la imagen original.

    Reglas:
    - Original NUNCA se modifica.
    - EXIF de orientación se aplica antes de hacer thumbnail.
    - Si falla: solo log. No propaga excepción al bot.
    - Thumbnail en: media_files/thumbs/{user_id}/{nombre_original}
    """
    t0 = time.monotonic()
    try:
        from PIL import Image, ImageOps

        foto_path_obj = Path(foto_path)
        if not foto_path_obj.exists():
            # Si aún hay reintentos, reintentar en silencio
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=2)
            
            # Solo loguear si fallaron todos los reintentos
            logger.error("generar_thumbnail_task: archivo NO ENCONTRADO tras reintentos: %s", foto_path)
            return

        # Crear carpeta de thumbnails para este usuario
        thumb_dir = Path(THUMBS_PATH) / str(user_id)
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / foto_path_obj.name

        with Image.open(foto_path_obj) as img:
            # Aplicar orientación EXIF sin modificar el original
            img = ImageOps.exif_transpose(img)

            # Convertir a RGB si es necesario (RGBA, P, etc.)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Thumbnail preservando aspect ratio
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            img.save(thumb_path, format='JPEG', quality=THUMB_QUALITY, optimize=True)

        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "Thumbnail generado | user_id=%s archivo=%s size=%s elapsed=%.1fms",
            user_id, foto_path_obj.name,
            f"{thumb_path.stat().st_size // 1024}KB",
            elapsed,
        )

    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        logger.error(
            "Error generando thumbnail | user_id=%s foto=%s elapsed=%.1fms error=%s",
            user_id, foto_path, elapsed, exc,
        )
        # NO relanzar — el upload original no debe fallar por un thumbnail

@shared_task(
    bind=True,
    name='calidad.tasks.generar_thumbnails_lote_task',
    max_retries=3,
    default_retry_delay=5,
    ignore_result=True,
)
def generar_thumbnails_lote_task(self, user_id: int, fotos_paths: list[str]) -> None:
    """
    Versión optimizada: procesa un lote completo de fotos en una sola tarea.
    Reduce overhead de Redis y worker.
    """
    from PIL import Image, ImageOps
    t_start = time.monotonic()
    procesadas = 0
    errores = 0

    thumb_dir = Path(THUMBS_PATH) / str(user_id)
    thumb_dir.mkdir(parents=True, exist_ok=True)

    for foto_path in fotos_paths:
        try:
            foto_path_obj = Path(foto_path)
            # Reintento inteligente por archivo
            intentos = 0
            while not foto_path_obj.exists() and intentos < 3:
                time.sleep(1)
                intentos += 1

            if not foto_path_obj.exists():
                logger.error("Lote Thumbnail: archivo NO ENCONTRADO: %s", foto_path)
                errores += 1
                continue

            thumb_path = thumb_dir / foto_path_obj.name
            with Image.open(foto_path_obj) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                img.save(thumb_path, format='JPEG', quality=THUMB_QUALITY, optimize=True)
            procesadas += 1

        except Exception as e:
            logger.error("Error en lote thumbnail para %s: %s", foto_path, e)
            errores += 1

    elapsed = (time.monotonic() - t_start) * 1000
    logger.info(
        "Lote de thumbnails completado | user_id=%s total=%d ok=%d errores=%d elapsed=%.1fms",
        user_id, len(fotos_paths), procesadas, errores, elapsed
    )


# ── Alias de proveedores ────────────────────────────────────────────────────
ALIAS = {
    'WH': 'TSCEM',
}


def _consolidar_registros(regs):
    """
    Fusiona registros con mismo (modelo, descripcion).
    Fotos se unen, cantidades se suman.
    """
    agrupados = {}
    for reg in regs:
        clave = (
            (reg.get('modelo') or '').strip().upper(),
            (reg.get('descripcion') or '').strip().upper(),
        )
        if clave in agrupados:
            existente = agrupados[clave]
            fotos_existentes = set(existente['fotos_nums'])
            for n in reg.get('fotos_nums', []):
                if n not in fotos_existentes:
                    existente['fotos_nums'].append(n)
                    fotos_existentes.add(n)
            existente['cantidad'] = (existente.get('cantidad') or 1) + (reg.get('cantidad') or 1)
        else:
            agrupados[clave] = dict(reg)
    return list(agrupados.values())


@shared_task(bind=True, name='calidad.tasks.generar_excel_task')
def generar_excel_task(self, registros_data, rotaciones, fotos_dir_str, fecha_str):
    """
    Tarea Celery: genera reportes Excel en background.

    Args:
        registros_data: Lista de dicts de registros.
        rotaciones:     Dict {clave: angulo}.
        fotos_dir_str:  Ruta al directorio de fotos como string.
        fecha_str:      Timestamp string para el nombre del archivo.

    Returns:
        Dict con 'file_path' y 'filename' del resultado.
    """
    from calidad.services.reporte_excel import generate_excel

    fotos_dir = Path(fotos_dir_str)

    # Agrupar registros por responsable
    grupos = {}
    for reg in registros_data:
        resp = (reg.get('responsable') or 'SIN_PROVEEDOR').strip().upper()
        resp = ALIAS.get(resp, resp)
        grupos.setdefault(resp, []).append(reg)

    # Crear directorio temporal compartido si no existe
    temp_dir = Path(fotos_dir_str).parent / "temp_reports"
    temp_dir.mkdir(parents=True, exist_ok=True)

    archivos_generados = []
    total_grupos = len(grupos)

    from shared.infrastructure.ai.defect_translator import build_translator
    translator = build_translator()

    for i, (proveedor, regs) in enumerate(grupos.items(), 1):
        # Actualizar progreso visible via Celery state
        self.update_state(
            state='PROGRESS',
            meta={'progress': f'Procesando {proveedor} ({i}/{total_grupos})'}
        )

        # Usar el directorio compartido en lugar de /tmp del contenedor
        output_path = temp_dir / f"tmp_{proveedor}_{datetime.now().timestamp()}.xlsx"

        generate_excel(
            registros=regs,
            rotaciones=rotaciones,
            fotos_dir=fotos_dir,
            output_path=output_path,
            translator=translator,
        )
        nombre = f"reporte_{proveedor}_{fecha_str}.xlsx"
        archivos_generados.append((nombre, str(output_path)))

    self.update_state(state='PROGRESS', meta={'progress': 'Preparando archivo final...'})

    # ── Actualización Automática de Estado ────────────────────────────────────
    # El usuario aprobó que al exportar correctamente, los registros pasen a "revisado"
    from calidad.models import RegistroDefecto, EstadoRevision
    
    registro_ids = [r.get('id') for r in registros_data if r.get('id')]
    if registro_ids:
        # bulk update
        RegistroDefecto.objects.filter(id__in=registro_ids).update(
            estado_revision=EstadoRevision.REVISADO,
            fecha_revision=datetime.now()
        )

    if len(archivos_generados) == 1:
        nombre, path = archivos_generados[0]
        return {'file_path': path, 'filename': nombre}

    # Múltiples proveedores → ZIP en el directorio compartido
    zip_path = temp_dir / f"zip_{datetime.now().timestamp()}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nombre, path in archivos_generados:
            zf.write(path, nombre)

    # Limpiar xlsx temporales
    for _, path in archivos_generados:
        Path(path).unlink(missing_ok=True)

    return {
        'file_path': str(zip_path),
        'filename': f"reportes_por_proveedor_{fecha_str}.zip"
    }

