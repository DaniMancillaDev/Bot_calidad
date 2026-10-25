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
import uuid
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

# ── Umbrales de desahogo a PowerPoint ──────────────────────────────────────────
UMBRAL_PPTX = 20          # Reporte normal consolidado


@shared_task(name='calidad.tasks.sync_evidencias_task')
def sync_evidencias_task(registro_id: int) -> None:
    """Sincroniza fotos_nums → EvidenciaFotografica (V2) en background."""
    from calidad.models import RegistroDefecto
    from calidad.services.legacy_sync import sync_fotos_to_evidencias
    try:
        sync_fotos_to_evidencias(RegistroDefecto.objects.get(id=registro_id))
    except Exception as e:
        logger.error("sync_evidencias_task failed registro_id=%s: %s", registro_id, e)


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


@shared_task(name='calidad.tasks.generar_derivados_evidencia_pendiente_task', ignore_result=True)
def generar_derivados_evidencia_pendiente_task(evidence_id: str) -> None:
    """Prepara derivados privados de una evidencia WhatsApp recién recibida."""
    from calidad.models import PendingEvidence
    from calidad.services.pending_media import generate_pending_derivatives

    evidence = PendingEvidence.objects.filter(
        pk=evidence_id,
        status=PendingEvidence.STATUS_READY,
    ).first()
    if evidence is None:
        return
    try:
        generate_pending_derivatives(evidence)
    except Exception:
        # El visor puede generarlos bajo demanda; la evidencia original ya está segura.
        logger.exception('No se pudieron generar derivados de evidencia pendiente %s', evidence_id)


# ── Alias de proveedores ────────────────────────────────────────────────────
ALIAS = {
    'WH': 'TSCEM',
    **dict.fromkeys((
        'MTTO', 'MNTO', 'MTO', 'MNT', 'MANT', 'MANTTO', 'MANTENIMIENTO',
        'MANTENIMINETO', 'MANTINIMIENTO', 'MAINTENANCE', 'MAINT', 'MTCE',
    ), 'TSCEM'),
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

def _consolidar_registros(regs, translator=None):
    agrupados = {}

    for reg in regs:
        defecto_canonico, _translation = _obtener_defecto_canonico(reg, translator)
        clave = (
            (reg.get('numero_parte') or '').strip().upper(),
            (reg.get('descripcion') or '').strip().upper(),
        )

        if clave not in agrupados:
            agrupados[clave] = {
                'key': clave,
                'registros': [],
                'evidencias': [],
                'cantidad': 0,
                'modelo': reg.get('modelo', ''),
                'linea': reg.get('linea', ''),
                'numero_parte': reg.get('numero_parte', ''),
                'wo': reg.get('wo', ''),
                'invoice': reg.get('invoice', ''),
                'descripcion': reg.get('descripcion', ''),
                'responsable': reg.get('responsable', ''),
                'departamento': reg.get('departamento', ''),
                'turno': reg.get('turno', ''),
                'fecha_obj': reg.get('fecha_obj'),
                'defecto_canonico': defecto_canonico,
                '_translation': _translation,
                'ids_originales': [],
                'descripciones_originales': [],
                'lineas_involucradas': [],
                'numeros_parte_originales': [],
                'sn_on_set': '',
            }

        grupo = agrupados[clave]
        grupo['registros'].append(reg)
        grupo['cantidad'] += (reg.get('cantidad') or 1)
        grupo['evidencias'].extend(reg.get('evidencias', []))

        id_reg = reg.get('id')
        desc_reg = (reg.get('descripcion') or '').strip()
        linea_reg = (reg.get('linea') or '').strip()
        np_reg = (reg.get('numero_parte') or '').strip()
        sn_reg = (reg.get('sn_on_set') or '').strip()

        if id_reg is not None:
            grupo['ids_originales'].append(id_reg)
        if desc_reg and desc_reg not in grupo['descripciones_originales']:
            grupo['descripciones_originales'].append(desc_reg)
        if linea_reg and linea_reg not in grupo['lineas_involucradas']:
            grupo['lineas_involucradas'].append(linea_reg)
        if np_reg and np_reg not in grupo['numeros_parte_originales']:
            grupo['numeros_parte_originales'].append(np_reg)
        if sn_reg:
            existing = grupo['sn_on_set']
            grupo['sn_on_set'] = (existing + '\n' + sn_reg).strip() if existing else sn_reg

    return list(agrupados.values())


def _ordenar_evidencias(evidencias, fotos_order):
    """Filtra y ordena evidencias según el orden elegido en la pantalla."""
    if fotos_order is None:
        return list(evidencias)

    order_by_num = {int(numero): indice for indice, numero in enumerate(fotos_order)}
    validas = []
    for ev in evidencias:
        match = re.match(r'^(\d+)', Path(ev.ruta_archivo).name)
        numero = int(match.group(1)) if match else ev.id
        if numero in order_by_num:
            validas.append((order_by_num[numero], ev))

    validas.sort(key=lambda item: item[0])
    return [ev for _, ev in validas]


@shared_task(bind=True, name='calidad.tasks.generar_excel_task')
def generar_excel_task(self, registros_ids, rotaciones, fotos_dir_str, fecha_str, fotos_order=None, sn_map=None, lote_id=None):
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

    # 1. Recuperar datos actualizados de DB con prefetch a la relación real V2
    qs = RegistroDefecto.objects.filter(id__in=registros_ids).prefetch_related('evidencias_v2')
    if qs.count() != len(set(registros_ids)):
        raise ValueError("Error de Integridad en Tarea: Se enviaron IDs inexistentes o duplicados.")
    
    # Preservar el orden original exacto del frontend
    orden = {id_: idx for idx, id_ in enumerate(registros_ids)}
    registros_orm = sorted(qs, key=lambda r: orden[r.id])

    registros_data = []
    for r in registros_orm:
        if r.fecha_registro:
            fecha_obj = r.fecha_registro.date()
        else:
            fecha_obj = datetime.now().date()

        # Usar DIRECTAMENTE la relación de BD. Cero reconstrucción por filename. Cero fallbacks r.fotos.
        evidencias_validas = []
        fotos_order_registro = None
        if fotos_order is not None and str(r.id) in fotos_order:
            fotos_order_registro = fotos_order[str(r.id)]

        for ev in r.evidencias_v2.all():
            if isinstance(ev.metadatos, dict) and ev.metadatos.get('excluida'):
                continue
            evidencias_validas.append(ev)

        # El queryset viene ordenado por la DB. Reordenarlo aquí conserva el
        # drag-and-drop aunque el worker corra en otro proceso.
        evidencias_validas = _ordenar_evidencias(evidencias_validas, fotos_order_registro)

        registros_data.append({
            'id': r.id,
            'user_id': r.user_id,
            'modelo': r.modelo,
            'numero_parte': r.numero_parte,
            'wo': r.wo,
            'invoice': r.invoice,
            'linea': r.linea,
            'cantidad': r.cantidad,
            'responsable': r.responsable,
            'descripcion': r.descripcion,
            'departamento': r.departamento,
            'turno': r.turno,
            'fecha_obj': fecha_obj,
            'sn_on_set': (sn_map or {}).get(str(r.id), ''),
            'evidencias': evidencias_validas,
            'registro_obj': r,  # Para validación estricta posterior
        })

    # Agrupar registros por responsable
    grupos = {}
    for reg in registros_data:
        resp = (reg.get('responsable') or 'SIN_PROVEEDOR').strip().upper()
        alias_key = re.sub(r'[\s._-]+', '', resp)
        resp = ALIAS.get(alias_key, resp)
        grupos.setdefault(resp, []).append(reg)

    # Crear directorio temporal compartido si no existe
    temp_dir = Path(fotos_dir_str).parent / "temp_reports"
    temp_dir.mkdir(parents=True, exist_ok=True)

    archivos_generados = []
    total_grupos = len(grupos)
    export_id = uuid.uuid4().hex

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
        regs_consolidados = _consolidar_registros(regs, translator=translator)
        logger.info(
            "Consolidación [%s]: %d registros → %d grupos",
            proveedor, len(regs), len(regs_consolidados)
        )
        
        # ── Generación de PPTX (Umbral) ──────────────────────────────────────
        from calidad.services.generador_pptx import generar_pptx_grupo
        UMBRAL_PPTX = 20
        
        for idx_grupo, grupo in enumerate(regs_consolidados):
            # Soporte dual V1/V2 para umbral PPTX
            evidencias = grupo.get('evidencias')
            if evidencias is not None:
                total_fotos = len(evidencias)
            else:
                f_usuario = grupo.get('fotos_por_usuario')
                if f_usuario:
                    total_fotos = sum(len(nums) for nums in f_usuario.values())
                else:
                    total_fotos = len(grupo.get('fotos_nums', []))
                
            if total_fotos >= UMBRAL_PPTX:
                safe_defecto = "".join(c for c in str(grupo.get('defecto_canonico', 'DEFECTO')) if c.isalnum() or c in [' ', '_']).strip().replace(' ', '_')
                safe_modelo = "".join(c for c in str(grupo.get('modelo', 'MOD')) if c.isalnum() or c in [' ', '_']).strip().replace(' ', '_')
                safe_part = "".join(c for c in str(grupo.get('numero_parte', 'PN')) if c.isalnum() or c in [' ', '_']).strip().replace(' ', '_')
                safe_resp = "".join(c for c in str(grupo.get('responsable', 'RESP')) if c.isalnum() or c in [' ', '_']).strip().replace(' ', '_')
                nombre_pptx = f"{safe_defecto}_{safe_modelo}_{safe_part}_{safe_resp}_{export_id}_{idx_grupo}.pptx"
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
        nombre = f"reporte_{proveedor}.xlsx"
        archivos_generados.append((nombre, str(output_path)))

    self.update_state(state='PROGRESS', meta={'progress': 'Preparando archivo final...'})

    # ── Actualización Automática de Estado ────────────────────────────────────
    # El usuario aprobó que al exportar correctamente, los registros pasen a "revisado"
    from django.utils import timezone
    from calidad.models import RegistroDefecto, EstadoRevision, ImportacionLote
    
    registro_ids = [r.get('id') for r in registros_data if r.get('id')]
    if registro_ids:
        # bulk update registros
        RegistroDefecto.objects.filter(id__in=registro_ids).update(
            estado_revision=EstadoRevision.REVISADO,
            fecha_revision=timezone.now()
        )
        # Update lote state
        from calidad.models import ImportacionLote
        if lote_id:
            ImportacionLote.objects.filter(id=lote_id).update(estado='COMPLETADO')

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
        'filename': "reportes_por_proveedor.zip"
    }


@shared_task(bind=True)
def generar_excel_box_condition_task(self, lote_id, fotos_dir_str, registros_ids=None, registros_data=None, rotaciones=None):
    """
    Tarea Celery aislada para el reporte Daily Tracking Box Condition.
    Acepta registros con ediciones locales en registros_data y rotaciones.
    Siempre genera Excel. El PPTX queda como exportación independiente, no como
    cambio automático por cantidad de fotografías.
    """
    from calidad.models import RegistroDefecto, ImportacionLote
    from calidad.services.reporte_box_condition import generate_box_condition_excel
    from shared.infrastructure.ai.defect_translator import build_translator
    from datetime import datetime
    from pathlib import Path

    fotos_dir = Path(fotos_dir_str)
    fecha_reporte = datetime.now()
    
    if not registros_data and registros_ids:
        registros_data = [{'id': rid} for rid in registros_ids]
        
    if not registros_data:
        # ponytail: Fail closed. La vista DEBE enviar los IDs autorizados. No inferir permisos aquí.
        raise ValueError("Error: Tarea invocada sin registros_data explícitos.")

    ids = [int(r['id']) for r in registros_data]
    qs = RegistroDefecto.objects.filter(id__in=ids).prefetch_related('evidencias_v2')
    orden = {id_: idx for idx, id_ in enumerate(ids)}
    registros_orm = sorted(list(qs), key=lambda r: orden[r.id])
    
    # ponytail: Aplicar ediciones locales sobre los objetos en memoria
    data_map = {int(r['id']): r for r in registros_data}
    for r in registros_orm:
        edits = data_map.get(r.id, {})
        if 'modelo' in edits: r.modelo = edits['modelo']
        if 'numero_parte' in edits: r.numero_parte = edits['numero_parte']
        if 'linea' in edits: r.linea = edits['linea']
        if 'descripcion' in edits: r.descripcion = edits['descripcion']
        if 'cantidad' in edits: r.cantidad = edits['cantidad']
        if 'responsable' in edits: r.responsable = edits['responsable']
        if 'wo' in edits: r.wo = edits['wo']
        if 'invoice' in edits: r.invoice = edits['invoice']
    
    if lote_id:
        for r in registros_orm:
            if str(r.importacion_id) != str(lote_id):
                raise ValueError(f"Error: El registro {r.id} no pertenece al lote {lote_id}.")
        lote = ImportacionLote.objects.get(id=lote_id)
        fecha_reporte = lote.fecha_inicio if lote.fecha_inicio else fecha_reporte
    
    # Validar si hay registros que cumplan las condiciones antes de generar
    from calidad.services.reporte_box_condition import es_box_condition, DUTY_BOX_CONDITION
    translator = build_translator()
    
    registros_validos = []
    for r in registros_orm:
        responsable_db = (r.responsable or "").strip().upper()
        if responsable_db in DUTY_BOX_CONDITION and es_box_condition(r.descripcion, translator):
            registros_validos.append(r)
            
    if not registros_validos:
        # Devuelve status especial para la UI
        return {'file_path': None, 'filename': None, 'error': 'No se encontraron defectos de Box Condition para esta selección.'}

    # Crear directorio temporal compartido si no existe
    temp_dir = Path(fotos_dir_str).parent / "temp_reports"
    temp_dir.mkdir(parents=True, exist_ok=True)
    fecha_str = fecha_reporte.strftime('%d-%b-%Y').upper()

    # ── Conteo de fotos para progreso/log; no cambia el formato de salida ──
    todas_evidencias = []

    for r in registros_validos:
        evs = [ev for ev in r.evidencias_v2.all() if not (isinstance(ev.metadatos, dict) and ev.metadatos.get('excluida'))]
        if evs:
            for ev in evs:
                todas_evidencias.append(ev)

    total_fotos = len(todas_evidencias)

    # ── Modo Excel ───────────────────────────────────────────────────────────
    template_path = Path("/app/Daily Tracking Box Condition.xlsx")
    nombre_archivo = f"Daily_Tracking_Box_Condition_{fecha_str}.xlsx"
    output_path = temp_dir / f"tmp_box_{datetime.now().timestamp()}.xlsx"

    self.update_state(state='PROGRESS', meta={'progress': f'Generando Excel Box Condition ({total_fotos} fotos)...'})

    generate_box_condition_excel(
        registros_orm=registros_validos,
        template_path=str(template_path),
        fotos_dir=fotos_dir,
        output_path=str(output_path),
        translator=translator
    )

    return {'file_path': str(output_path), 'filename': nombre_archivo}
