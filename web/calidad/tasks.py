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


def _consolidar_registros(regs, translator=None):
    """
    Consolidación V1: fusiona registros por defecto canónico.

    Clave de agrupación: (defecto_canonico, modelo_norm, numero_parte_norm)
    - defecto_canonico: resultado del catálogo determinístico.
    - Si el catálogo no resuelve el defecto, se usa la descripción normalizada como fallback.

    Cada grupo resultante incluye trazabilidad completa:
    - fotos_por_usuario: dict {user_id: [nums]} para recuperar fotos de múltiples usuarios.
    - ids_originales: lista de todos los IDs agrupados (para bulk_update REVISADO).
    - descripciones_originales: textos capturados por operadores (causa raíz preservada).
    - lineas_involucradas: líneas de producción donde ocurrió el defecto.
    - cantidad: suma de todas las cantidades individuales.

    IMPORTANTE: El bulk_update a REVISADO en generar_excel_task usa registros_data
    ORIGINAL (sin consolidar), por lo que este proceso no afecta ese flujo.
    """
    from shared.infrastructure.ai.defect_translator import normalize_text

    agrupados = {}

    for reg in regs:
        # ── Obtener defecto canónico ─────────────────────────────────────────
        defecto_canonico = None

        # Si el translator está disponible, usar catálogo determinístico
        if translator is not None:
            try:
                area_ctx = reg.get('departamento') or reg.get('turno') or ''
                tr = translator.translate(reg.get('descripcion', ''), area_ctx)
                defecto_canonico = (tr.get('defect_en') or '').strip().upper() or None
            except Exception:
                pass

        # Fallback: descripción normalizada si catálogo no resolvió
        if not defecto_canonico:
            defecto_canonico = normalize_text(reg.get('descripcion', '')).upper()

        # ── Construir clave de consolidación ────────────────────────────────
        clave = (
            defecto_canonico,
            normalize_text(reg.get('modelo') or '').upper(),
            normalize_text(reg.get('numero_parte') or '').upper(),
        )

        user_id = reg.get('user_id')
        fotos_reg = reg.get('fotos_nums') or []
        linea_reg = (reg.get('linea') or '').strip()
        desc_reg  = (reg.get('descripcion') or '').strip()
        id_reg    = reg.get('id')

        if clave in agrupados:
            grupo = agrupados[clave]

            # Sumar cantidad
            grupo['cantidad'] = (grupo.get('cantidad') or 1) + (reg.get('cantidad') or 1)

            # Acumular fotos por usuario (preservando estructura para recuperación en disco)
            if user_id and fotos_reg:
                uid_str = str(user_id)
                nums_existentes = set(grupo['fotos_por_usuario'].get(uid_str, []))
                nuevos = [n for n in fotos_reg if n not in nums_existentes]
                if nuevos:
                    grupo['fotos_por_usuario'].setdefault(uid_str, []).extend(nuevos)

            # Trazabilidad
            if id_reg is not None:
                grupo['ids_originales'].append(id_reg)
            if desc_reg and desc_reg not in grupo['descripciones_originales']:
                grupo['descripciones_originales'].append(desc_reg)
            if linea_reg and linea_reg not in grupo['lineas_involucradas']:
                grupo['lineas_involucradas'].append(linea_reg)

        else:
            # Primer registro del grupo — inicializar
            grupo_base = dict(reg)
            grupo_base['cantidad'] = reg.get('cantidad') or 1

            # fotos_por_usuario: dict para recuperación desde múltiples carpetas de usuario
            fotos_por_usuario = {}
            if user_id and fotos_reg:
                fotos_por_usuario[str(user_id)] = list(fotos_reg)
            grupo_base['fotos_por_usuario'] = fotos_por_usuario

            # Trazabilidad interna (no se imprime en Excel)
            grupo_base['ids_originales']         = [id_reg] if id_reg is not None else []
            grupo_base['descripciones_originales'] = [desc_reg] if desc_reg else []
            grupo_base['lineas_involucradas']      = [linea_reg] if linea_reg else []

            # Campos de presentación para Excel
            grupo_base['defecto_canonico']  = defecto_canonico
            grupo_base['linea']             = linea_reg   # primer valor; Excel lo usará si catálogo falla

            agrupados[clave] = grupo_base

    # Post-proceso: construir fotos_nums plana para compatibilidad con código legacy
    # reporte_excel.py usará fotos_por_usuario; esto es solo seguridad adicional.
    for grupo in agrupados.values():
        grupo['fotos_nums'] = [
            n
            for nums in grupo['fotos_por_usuario'].values()
            for n in nums
        ]

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

        # ── Consolidación V1 ─────────────────────────────────────────────────
        # Agrupa registros del mismo proveedor por defecto canónico.
        # XM y TSCEM ya están separados en listas distintas: nunca se mezclan.
        # El bulk_update REVISADO (línea 240) usa registros_data ORIGINAL,
        # por lo que este paso no afecta la actualización de estado en BD.
        regs_consolidados = _consolidar_registros(regs, translator=translator)
        logger.info(
            "Consolidación [%s]: %d registros → %d grupos",
            proveedor, len(regs), len(regs_consolidados)
        )
        
        # ── Generación de PPTX (Umbral) ──────────────────────────────────────
        from calidad.services.generador_pptx import generar_pptx_grupo
        UMBRAL_PPTX = 30
        
        for idx_grupo, grupo in enumerate(regs_consolidados):
            total_fotos = sum(len(nums) for nums in grupo.get('fotos_por_usuario', {}).values())
            if total_fotos >= UMBRAL_PPTX:
                safe_defecto = "".join(c for c in str(grupo.get('defecto_canonico', 'DEFECTO')) if c.isalnum() or c in [' ', '_']).strip().replace(' ', '_')
                safe_modelo = "".join(c for c in str(grupo.get('modelo', 'MOD')) if c.isalnum() or c in [' ', '_']).strip().replace(' ', '_')
                timestamp = int(datetime.now().timestamp())
                nombre_pptx = f"{safe_defecto}_{safe_modelo}_{timestamp}.pptx"
                pptx_output_path = temp_dir / nombre_pptx
                
                try:
                    generar_pptx_grupo(grupo, fotos_dir, pptx_output_path, rotaciones=rotaciones, translator=translator)
                    grupo['pptx_filename'] = nombre_pptx
                    archivos_generados.append((nombre_pptx, str(pptx_output_path)))
                    logger.info("PPTX generado: %s", nombre_pptx)
                except Exception as e:
                    logger.error("Error generando PPTX para grupo %s: %s", safe_defecto, e)
        # ────────────────────────────────────────────────────────────────────

        # Usar el directorio compartido en lugar de /tmp del contenedor
        output_path = temp_dir / f"tmp_{proveedor}_{datetime.now().timestamp()}.xlsx"

        generate_excel(
            registros=regs_consolidados,
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

