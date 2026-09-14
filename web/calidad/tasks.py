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
import re
import time
from pathlib import Path
from datetime import datetime

from celery import shared_task

logger = logging.getLogger(__name__)

# ── Configuración de thumbnails ────────────────────────────────────────────────
THUMB_SIZE = (300, 300)
THUMB_QUALITY = 75
PROXY_SIZE = (1280, 1280)
PROXY_QUALITY = 85
FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")
THUMBS_PATH = os.getenv("THUMBS_PATH", "media_files/thumbs")
PROXIES_PATH = os.getenv("PROXIES_PATH", "media_files/proxies")



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
    
    proxy_dir = Path(PROXIES_PATH) / str(user_id)
    proxy_dir.mkdir(parents=True, exist_ok=True)

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
            if thumb_path.exists():
                logger.info("Lote Thumbnail: ya existe, saltando (idempotencia): %s", thumb_path.name)
                procesadas += 1
                continue

            proxy_path = proxy_dir / foto_path_obj.name
            tmp_proxy_path = proxy_dir / f"{foto_path_obj.name}.tmp"
            
            with Image.open(foto_path_obj) as original:
                img = ImageOps.exif_transpose(original)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                    
                # 1. Bajar a Proxy in-place y guardado atómico
                img.thumbnail(PROXY_SIZE, Image.LANCZOS)
                img.save(tmp_proxy_path, format='JPEG', quality=PROXY_QUALITY, optimize=True)
                os.replace(tmp_proxy_path, proxy_path)
                
                # 2. Bajar a Thumb in-place
                img.thumbnail(THUMB_SIZE, Image.LANCZOS)
                img.save(thumb_path, format='JPEG', quality=THUMB_QUALITY, optimize=True)
                
                if img is not original:
                    img.close()
                    
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


def _obtener_defecto_canonico(reg, translator):
    from shared.infrastructure.ai.defect_translator import normalize_text
    
    defecto_canonico = None
    _translation = None

    if translator is not None:
        try:
            area_ctx = reg.get('departamento') or reg.get('turno') or ''
            _translation = translator.translate(reg.get('descripcion', ''), area_ctx)
            defecto_canonico = (_translation.get('defect_en') or '').strip().upper() or None
        except Exception:
            pass

    if not defecto_canonico:
        defecto_canonico = normalize_text(reg.get('descripcion', '')).upper()
        
    return defecto_canonico, _translation

def _construir_clave_consolidacion(defecto_canonico, reg):
    from shared.infrastructure.ai.defect_translator import normalize_text
    return (
        defecto_canonico,
        normalize_text(reg.get('modelo') or '').upper(),
        normalize_text(reg.get('numero_parte') or '').upper(),
    )

def _inicializar_grupo(reg, defecto_canonico, _translation):
    grupo_base = dict(reg)
    grupo_base['cantidad'] = reg.get('cantidad') or 1

    user_id = reg.get('user_id')
    fotos_reg = reg.get('fotos_nums') or []
    
    fotos_por_usuario = {}
    if user_id and fotos_reg:
        fotos_por_usuario[str(user_id)] = list(fotos_reg)
    grupo_base['fotos_por_usuario'] = fotos_por_usuario

    id_reg = reg.get('id')
    desc_reg = (reg.get('descripcion') or '').strip()
    linea_reg = (reg.get('linea') or '').strip()

    grupo_base['ids_originales'] = [id_reg] if id_reg is not None else []
    grupo_base['descripciones_originales'] = [desc_reg] if desc_reg else []
    grupo_base['lineas_involucradas'] = [linea_reg] if linea_reg else []

    grupo_base['defecto_canonico'] = defecto_canonico
    grupo_base['linea'] = linea_reg
    
    if _translation is not None:
        grupo_base['_translation'] = _translation

    return grupo_base

def _fusionar_registro(grupo, reg):
    grupo['cantidad'] = (grupo.get('cantidad') or 1) + (reg.get('cantidad') or 1)

    user_id = reg.get('user_id')
    fotos_reg = reg.get('fotos_nums') or []
    
    if user_id and fotos_reg:
        uid_str = str(user_id)
        nums_existentes = set(grupo['fotos_por_usuario'].get(uid_str, []))
        nuevos = [n for n in fotos_reg if n not in nums_existentes]
        if nuevos:
            grupo['fotos_por_usuario'].setdefault(uid_str, []).extend(nuevos)

    id_reg = reg.get('id')
    desc_reg = (reg.get('descripcion') or '').strip()
    linea_reg = (reg.get('linea') or '').strip()

    if id_reg is not None:
        grupo['ids_originales'].append(id_reg)
    if desc_reg and desc_reg not in grupo['descripciones_originales']:
        grupo['descripciones_originales'].append(desc_reg)
    if linea_reg and linea_reg not in grupo['lineas_involucradas']:
        grupo['lineas_involucradas'].append(linea_reg)

    sn_reg = (reg.get('sn_on_set') or '').strip()
    if sn_reg:
        existing = (grupo.get('sn_on_set') or '').strip()
        grupo['sn_on_set'] = (existing + '\n' + sn_reg).strip() if existing else sn_reg

def _post_proceso_fotos(agrupados):
    for grupo in agrupados.values():
        grupo['fotos_nums'] = [
            n
            for nums in grupo['fotos_por_usuario'].values()
            for n in nums
        ]

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
    agrupados = {}

    for reg in regs:
        defecto_canonico, _translation = _obtener_defecto_canonico(reg, translator)
        clave = _construir_clave_consolidacion(defecto_canonico, reg)

        if clave in agrupados:
            _fusionar_registro(agrupados[clave], reg)
        else:
            agrupados[clave] = _inicializar_grupo(reg, defecto_canonico, _translation)

    _post_proceso_fotos(agrupados)

    return list(agrupados.values())


@shared_task(bind=True, name='calidad.tasks.generar_excel_task')
def generar_excel_task(self, registros_ids, rotaciones, fotos_dir_str, fecha_str, fotos_order=None, sn_map=None):
    """
    Tarea Celery: genera reportes Excel en background.

    Args:
        registros_ids: Lista de IDs (enteros).
        rotaciones:     Dict {clave: angulo}.
        fotos_dir_str:  Ruta al directorio de fotos como string.
        fecha_str:      Timestamp string para el nombre del archivo.

    Returns:
        Dict con 'file_path' y 'filename' del resultado.
    """
    from calidad.services.reporte_excel import generate_excel
    from calidad.models import RegistroDefecto

    fotos_dir = Path(fotos_dir_str)

    # 1. Recuperar datos actualizados de DB
    qs = RegistroDefecto.objects.filter(id__in=registros_ids)
    
    # Preservar el orden original exacto del frontend
    orden = {id_: idx for idx, id_ in enumerate(registros_ids)}
    registros_orm = sorted(qs, key=lambda r: orden[r.id])

    # 2. Reconstruir diccionarios (mantener compatibilidad y parseo de legacy)
    # Reutilizamos la misma lógica que usa el panel operativo para evitar omisiones.
    import re
    registros_data = []
    for r in registros_orm:
        try:
            raw_fotos = r.fotos
            nums = []
            if raw_fotos:
                if isinstance(raw_fotos, list):
                    nums = [int(x) for x in raw_fotos]
                else:
                    # 1. Intentar formato nuevo o individuales "1, 2" o "(001)"
                    nums = [int(n) for n in re.findall(r'\d+', str(raw_fotos))]
                    # 2. Parsear rangos legacy "(001-005)" o "1-5"
                    rangos = re.findall(r'(\d+)\s*-\s*(\d+)', str(raw_fotos))
                    for inicio, fin in rangos:
                        nums.extend(range(int(inicio), int(fin) + 1))
            f_list = sorted(list(set(nums)))
            
            # Aplicar el orden del frontend si se proporcionó
            if fotos_order and str(r.id) in fotos_order:
                # El frontend manda exactamente lo que se debe imprimir (incluyendo V2).
                # No filtramos contra f_list porque V2 puede tener fotos="WEB" (f_list vacío).
                f_list = fotos_order[str(r.id)]
                
        except Exception:
            f_list = []
        if r.fecha_registro:
            fecha_obj = r.fecha_registro.date()
        else:
            fecha_obj = datetime.now().date()

        registros_data.append({
            'id': r.id,
            'user_id': r.user_id,
            'fotos_nums': f_list,
            'modelo': r.modelo,
            'numero_parte': r.numero_parte,
            'linea': r.linea,
            'cantidad': r.cantidad,
            'responsable': r.responsable,
            'descripcion': r.descripcion,
            'departamento': r.departamento,
            'turno': r.turno,
            'fecha_obj': fecha_obj,
            'sn_on_set': (sn_map or {}).get(str(r.id), ''),
        })

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
    from django.utils import timezone
    from calidad.models import RegistroDefecto, EstadoRevision
    
    registro_ids = [r.get('id') for r in registros_data if r.get('id')]
    if registro_ids:
        # bulk update
        RegistroDefecto.objects.filter(id__in=registro_ids).update(
            estado_revision=EstadoRevision.REVISADO,
            fecha_revision=timezone.now()
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

