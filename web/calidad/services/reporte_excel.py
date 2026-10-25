"""
Servicio de generación de reportes Excel con fotos orientadas.
Adaptación del pipeline del SIF (manipul.py) para uso en Django.

Flujo:
  1. detect_orientation(img_path)                   → ángulo sugerido (0/90/180/270)
  2. detect_orientations_batch(foto_paths)           → dict {num: angulo}
  3. generate_excel(registros, rotaciones, ...)      → genera el .xlsx con fotos

NOTA: Las funciones de detección ONNX viven en shared/infrastructure/orientation/
      y se re-exportan aquí para compatibilidad con el código existente.
"""
import logging
import os
import uuid
import warnings
from copy import copy
from pathlib import Path
from PIL import Image, ImageFile, ImageOps
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.drawing.xdr import XDRPositiveSize2D
from openpyxl.utils.units import pixels_to_EMU
from openpyxl.styles import Alignment

# Detección de orientación: importada desde shared/ (fuente de verdad única)
from shared.infrastructure.orientation.orientation_engine import (
    detect_orientation,
)
from calidad.utils import get_best_image_path
from calidad.services.report_grouping import report_group_key, FIELDS, DEV_DESCRIPTION

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
warnings.filterwarnings("ignore")
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN DE EXCEL
# ============================================================
SCALE_FACTOR   = 4     # 4x la resolución visual (nitidez extrema)
GAP            = 5     # Separación horizontal entre fotos (px)
MAX_DISPLAY_H  = 240   # Alto máximo visual de cada foto (px)
CELL_COL       = 15    # Columna P (0-indexed para AnchorMarker)
START_ROW      = 7     # Fila 8 en 0-indexed

# ── Columnas para campos en inglés ───────────────────────────────────────
COL_WHERE_FOUND = 6   # Columna F: Where Found  (área derivada del material)
COL_DEFECT_EN   = 9   # Columna I: Defect.      (nombre corporativo + síntoma)
COL_ANALYSIS_EN = 10  # Columna J: Simple Analysis
COL_REMARK      = 15  # Columna O: Remark       ("{MATERIAL} ISSUE")
COL_EVIDENCIA_PPT= 16 # Columna P: Evidencia PPT

# Plantilla — raíz del proyecto
_BASE_DIR      = Path(__file__).resolve().parent.parent.parent.parent
PLANTILLA_PATH = _BASE_DIR / "plantilla_reporte.xlsx"

# Calidad JPEG para las fotos insertadas (0-100)
# 88 = excelente calidad visual con buen ratio de compresión
JPEG_QUALITY = 95


def _get_row_height_px(ws, row_1based):
    """Obtiene la altura de una fila en píxeles (1pt ≈ 1.333px)."""
    h = ws.row_dimensions[row_1based].height
    if h is None or h <= 0:
        return 200
    return int(h * 1.333)


def _get_container_width(ws):
    """Calcula el ancho combinado en píxeles de las columnas P y Q."""
    # Usamos la nueva lógica más robusta introducida previamente
    return _get_columns_width(ws, 'P', 'Q')


def _col_width_to_px(w):
    """Convierte el ancho de columna de Excel (en caracteres) a píxeles."""
    if w is None or w <= 0:
        return 64
    return int(((256 * w + int(128 / 7)) / 256) * 7)


def _resolve_col_offset(ws, start_col, x_px, max_col=None):
    """
    Convierte un offset absoluto en píxeles (desde start_col)
    a la pareja (columna_real, offset_dentro_de_esa_columna).

    Si max_col está definido, nunca devolverá una columna mayor a max_col
    y clampea colOff al ancho de esa columna para que la imagen nunca
    escape del bloque de columnas permitido.
    """
    remaining = x_px
    col = start_col

    while True:
        col_letter = openpyxl.utils.get_column_letter(col + 1)  # 1-based
        col_w = ws.column_dimensions[col_letter].width
        col_px = _col_width_to_px(col_w)

        # Si llegamos a la columna tope, clampear offset al ancho de la columna
        if max_col is not None and col >= max_col:
            return col, min(remaining, max(col_px - 1, 0))

        if remaining < col_px:
            return col, remaining

        remaining -= col_px
        col += 1

SCALE_FACTOR   = 2     # ponytail: reducido de 4 a 2 (suficiente nitidez, mitad de peso/tiempo)

import hashlib
import uuid
import shutil

def _prepare_image_strip(img_path: Path, angle: int, target_h: int, tmp_dir: Path,
                         max_width: int = None, meta: dict = None):
    """
    Rota la imagen y la escala con lógica contain.
    ponytail: Implementado CACHE DE THUMBNAILS persistente.
    """
    try:
        from django.conf import settings
        cache_dir = Path(settings.MEDIA_ROOT) / 'thumbnails_cache'
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        stat = img_path.stat()
        # Clave unívoca: ruta + tamaño + fecha_modificacion + parametros_resize
        raw_key = f"{img_path.absolute()}_{stat.st_size}_{stat.st_mtime}_{angle}_{target_h}_{max_width}_{SCALE_FACTOR}"
        cache_key = hashlib.md5(raw_key.encode('utf-8')).hexdigest() + ".jpg"
        cached_file = cache_dir / cache_key
        
        # Necesitamos saber el disp_w y disp_h para devolverlos, asi que los calculamos rapido
        # o los guardamos en el nombre del archivo.
        
        # Para saber las dimensiones sin procesar todo de nuevo:
        # Formato de cache: {hash}_{disp_w}_{disp_h}.jpg
        import glob
        matches = glob.glob(str(cache_dir / f"{cache_key.split('.')[0]}_*_*.*"))
        if matches:
            match = Path(matches[0])
            parts = match.stem.split('_')
            disp_w = int(parts[1])
            disp_h = int(parts[2])
            # Hacer symlink o copiar a tmp_dir para que openpyxl no lo borre accidentalmente
            tmp_path = tmp_dir / f"strip_{uuid.uuid4().hex[:8]}.jpg"
            shutil.copy(match, tmp_path)
            return (tmp_path, disp_w, disp_h, meta)

        # Si no esta en cache, procesar
        img = Image.open(img_path)
        img = ImageOps.exif_transpose(img)
        if angle != 0:
            mapping = {
                90:  Image.ROTATE_270,
                180: Image.ROTATE_180,
                270: Image.ROTATE_90
            }
            if angle in mapping:
                img = img.transpose(mapping[angle])
            else:
                img = img.rotate(-angle, expand=True, resample=Image.BICUBIC)

        orig_w, orig_h = img.size

        # ── Contain scaling: respetar ambos límites ──
        ratio_h = target_h / orig_h
        ratio_w = (max_width / orig_w) if max_width else float('inf')
        ratio = min(ratio_h, ratio_w)

        disp_w = int(orig_w * ratio)
        disp_h = int(orig_h * ratio)

        # Imagen física en alta resolución
        phys_w = disp_w * SCALE_FACTOR
        phys_h = disp_h * SCALE_FACTOR
        img_hi = img.resize((phys_w, phys_h), Image.LANCZOS)

        # Guardar como JPEG
        img_hi = img_hi.convert('RGB')
        
        # Guardar en cache persistente
        cache_name = f"{cache_key.split('.')[0]}_{disp_w}_{disp_h}.jpg"
        cached_file = cache_dir / cache_name
        img_hi.save(cached_file, format='JPEG', quality=75, optimize=True)
        
        # Copiar al tmp_dir para Excel
        tmp_path = tmp_dir / f"strip_{uuid.uuid4().hex[:8]}.jpg"
        shutil.copy(cached_file, tmp_path)

        return (tmp_path, disp_w, disp_h, meta)
    except Exception as e:
        logger.error(f"Error procesando imagen para Excel {img_path}: {e}")
        return (None, 0, 0, meta)


# ============================================================
# GENERACIÓN DEL EXCEL
def _get_columns_width(ws, col_start: str, col_end: str) -> int:
    """Calcula el ancho combinado en píxeles de un rango de columnas."""
    start_idx = openpyxl.utils.column_index_from_string(col_start)
    end_idx = openpyxl.utils.column_index_from_string(col_end)
    
    total_px = 0
    for col_idx in range(start_idx, end_idx + 1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        w = ws.column_dimensions[col_letter].width
        # Si w es None, se asume el ancho estándar de Excel
        total_px += _col_width_to_px(w or 8.43)
    return total_px


# ============================================================

def generate_excel(
    registros: list,
    rotaciones: dict,
    fotos_dir: Path,
    output_path: Path,
    plantilla_path: Path = None,
    translator=None,  # Optional[IDefectTranslator] — si None, no escribe campos EN
) -> Path:
    """
    Genera el reporte Excel con fotos en tira horizontal (filmstrip).
    Cada foto se escala a la altura de la fila y se colocan una al
    lado de la otra empezando desde la columna P.
    """
    import tempfile
    import shutil

    plantilla = plantilla_path or PLANTILLA_PATH
    fotos_dir = Path(fotos_dir)

    if plantilla.exists():
        wb = openpyxl.load_workbook(plantilla)
        ws = wb["SQA DAILY"] if "SQA DAILY" in wb.sheetnames else wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Reporte Defectos"

    tmp_dir = Path(tempfile.mkdtemp())

    try:
        from datetime import datetime
        import concurrent.futures
        today_str = datetime.now().strftime("%Y-%m-%d")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Capturar estilos de la fila plantilla (primera fila de datos)
            # para replicarlos en filas nuevas y preservar formato de la plantilla.
            _TEMPLATE_ROW = START_ROW + 1  # 1-based
            _MAX_COL = ws.max_column or 20
            template_styles = {}
            for _c in range(1, _MAX_COL + 1):
                _cell = ws.cell(row=_TEMPLATE_ROW, column=_c)
                template_styles[_c] = {
                    'font':         copy(_cell.font),
                    'fill':         copy(_cell.fill),
                    'border':       copy(_cell.border),
                    'alignment':    copy(_cell.alignment),
                    'number_format': _cell.number_format,
                }

            
            # Agrupar preservando el orden original en O(N)
            import unicodedata
            def normalize_defecto(texto):
                texto = str(texto or '').strip().lower()
                return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
                
            grupos = {}
            for r in registros:
                llave = (r.get('user_id', 0), normalize_defecto(r.get('descripcion', '')))
                grupos.setdefault(llave, []).append(r)
                    
            registros = [r for g in grupos.values() for r in g]
            
            for idx, registro in enumerate(registros):
                row        = START_ROW + idx
                row_1based = row + 1
                nums_fotos = registro.get('fotos_nums', [])

                # Agregar encabezado dinámicamente si es la primera fila de datos
                if idx == 0:
                    ws.cell(row=START_ROW, column=7).value = "Part Number"

                # Copiar estilos de la fila plantilla a filas nuevas (idx > 0)
                if idx > 0:
                    for _c, _style in template_styles.items():
                        _cell = ws.cell(row=row_1based, column=_c)
                        _cell.font         = copy(_style['font'])
                        _cell.fill         = copy(_style['fill'])
                        _cell.border       = copy(_style['border'])
                        _cell.alignment    = copy(_style['alignment'])
                        _cell.number_format = _style['number_format']

                # Escribir datos de texto
                # Se eliminó la fecha por petición del usuario (se deja en blanco)

                ws.cell(row=row_1based, column=3).value  = str(registro.get('modelo') or '').upper()
                ws.cell(row=row_1based, column=4).value  = str(registro.get('wo') or '').upper()
                ws.cell(row=row_1based, column=5).value  = str(registro.get('invoice') or '').upper()
                ws.cell(row=row_1based, column=6).value  = str(registro.get('linea') or '').upper()
                ws.cell(row=row_1based, column=7).value  = str(registro.get('numero_parte') or "").upper()
                # Columna H: SN on set (series, una por línea en Excel)
                sn_raw = (registro.get('sn_on_set') or '').strip().upper()
                if sn_raw:
                    cell_sn = ws.cell(row=row_1based, column=8)
                    cell_sn.value = sn_raw
                    # Preservar alineación de plantilla, solo forzar wrap_text
                    existing_align = copy(cell_sn.alignment)
                    cell_sn.alignment = Alignment(
                        horizontal=existing_align.horizontal,
                        vertical=existing_align.vertical or 'top',
                        wrap_text=True,
                        indent=existing_align.indent,
                        shrink_to_fit=existing_align.shrink_to_fit,
                    )
                ws.cell(row=row_1based, column=9).value  = str(registro.get('descripcion') or '').upper()
                ws.cell(row=row_1based, column=12).value = registro.get('cantidad', 1)
                ws.cell(row=row_1based, column=14).value = str(registro.get('responsable') or '').upper()

                # ── Traducción (Catálogo determinístico + fallback LLM) ──────────
                # Solo activo si EXCEL_AI_ENABLED=true. Nunca bloquea la generación.
                if translator is not None:
                    tr = registro.get('_translation')
                    if tr is None:
                        try:
                            area = registro.get('departamento', registro.get('turno', ''))
                            tr   = translator.translate(registro.get('descripcion', ''), area)
                        except Exception as _tr_err:
                            logger.error("generate_excel: traducción falló en fila %d: %s", row_1based, _tr_err)
                            tr = None

                    if tr:
                        defect_en      = tr.get('defect_en', '')
                        analysis_en    = tr.get('simple_analysis_en', '')

                        # Where Found: área derivada del material (catálogo → material_areas)
                        # simple_analysis tiene forma "AT {AREA} AREA WAS DETECTED {DEFECT}"
                        # Extraemos el área del propio analysis para no duplicar lógica.
                        where_found = ''
                        if analysis_en and analysis_en.startswith('AT '):
                            # "AT CLEAN ROOM AREA WAS DETECTED ..." → "CLEAN ROOM"
                            try:
                                where_found = analysis_en.split(' AREA WAS DETECTED')[0].replace('AT ', '', 1).strip()
                            except Exception:
                                where_found = ''

                        # Remark: "{MATERIAL} ISSUE"
                        # Material = defect_en sin conectores ni síntomas
                        remark = ''
                        if defect_en:
                            material = defect_en
                            # 1. Quitar conectores y lo que les sigue
                            for conn in [" WITH LITTLE", " WITH", " WITHOUT"]:
                                if conn in material:
                                    material = material.split(conn)[0].strip()
                                    break
                            # 2. Quitar síntomas de dos palabras
                            if material.endswith(" LIGHT LEAK"):
                                material = material[:-11].strip()
                            # 3. Quitar síntomas de una palabra
                            tokens = material.split()
                            _ONE_WORD_SYMPTOMS = {
                                'DAMAGED', 'SCRATCHED', 'BENT', 'DEFORMED',
                                'MISSING', 'DIRTY', 'WET', 'STAINED', 'GAP',
                            }
                            if len(tokens) > 1 and tokens[-1] in _ONE_WORD_SYMPTOMS:
                                material = ' '.join(tokens[:-1])
                            remark = f"{material} ISSUE"

                        if defect_en:
                            ws.cell(row=row_1based, column=COL_DEFECT_EN).value   = str(defect_en or '').upper()
                        if analysis_en:
                            ws.cell(row=row_1based, column=COL_ANALYSIS_EN).value = str(analysis_en or '').upper()
                        if where_found:
                            ws.cell(row=row_1based, column=COL_WHERE_FOUND).value = str(where_found or '').upper()
                        if remark:
                            ws.cell(row=row_1based, column=COL_REMARK).value      = str(remark or '').upper()
                # Forzar negritas (bold) y wrap (ajuste de texto) en toda la fila
                for _c in range(1, _MAX_COL + 1):
                    _cell = ws.cell(row=row_1based, column=_c)
                    if _cell.value:
                        _font = copy(_cell.font)
                        _font.bold = True
                        _cell.font = _font
                        _align = copy(_cell.alignment)
                        _align.wrap_text = True
                        _align.vertical = 'center'
                        _cell.alignment = _align

                # ────────────────────────────────────────────────────────────────

                # ── Vínculo PPTX ────────────────────────────────────────────────
                pptx_filename = registro.get('pptx_filename')
                if pptx_filename:
                    cell_pptx = ws.cell(row=row_1based, column=COL_EVIDENCIA_PPT)
                    cell_pptx.value = "Abrir PPTX"
                    cell_pptx.hyperlink = f"./{pptx_filename}"
                    cell_pptx.style = "Hyperlink"
                
                    # Omitir la inserción de imágenes en este Excel para esta fila
                    continue
                # ────────────────────────────────────────────────────────────────

                # ── FOTOS (RELACION DIRECTA BD V2) ──────────────────────────────
                evidencias = registro.get('evidencias', [])
                if not evidencias:
                    continue

                # ── Vínculo PPTX ────────────────────────────────────────────────
                pptx_filename = registro.get('pptx_filename')
                if pptx_filename:
                    cell_pptx = ws.cell(row=row_1based, column=COL_EVIDENCIA_PPT)
                    cell_pptx.value = "Abrir PPTX"
                    cell_pptx.hyperlink = f"./{pptx_filename}"
                    cell_pptx.style = "Hyperlink"
                    continue

                # Ancho del bloque P+Q
                block_w_px = _get_container_width(ws)
                row_h_px = _get_row_height_px(ws, row_1based)
                target_h = min(row_h_px, MAX_DISPLAY_H)

                x_offset = 8
                y_offset = 8
                max_y_reached = target_h + 8

                args_list = []
                from django.conf import settings
                for ev in evidencias:
                    # VALIDACIÓN OBLIGATORIA (Regla 9)
                    if ev.registro_id not in [r.get('id') for r in registro['registros']]:
                        logger.error(f"VALIDATION FAILED: photo_id={ev.id} registro_id={ev.registro_id} no pertenece al grupo de registros")
                        continue
                    evidence_record = {field: getattr(ev.registro, field) for field in FIELDS}
                    if report_group_key(evidence_record, registro.get('grouping_rule', DEV_DESCRIPTION)) != registro['key']:
                        logger.error(f"VALIDATION FAILED: photo_id={ev.id} metadata mismatch con {registro['key']}")
                        continue

                    ev_path_str = ev.ruta_archivo
                    if ev_path_str.startswith('media_files/'):
                        ev_path_str = ev_path_str[12:]
                    elif ev_path_str.startswith('/media_files/'):
                        ev_path_str = ev_path_str[13:]
                    
                    real_path = Path(settings.MEDIA_ROOT) / ev_path_str.lstrip('/')
                    if not real_path.exists():
                        continue
                        
                    # Mapeo de clave rotación (usado por frontend)
                    import re as _re
                    m = _re.match(r'^(\d+)', real_path.name)
                    num_for_rot = int(m.group(1)) if m else ev.id
                    clave_rotacion = f"{ev.registro.user_id}_{num_for_rot}"
                    if clave_rotacion in rotaciones:
                        angle = rotaciones[clave_rotacion]
                    elif str(clave_rotacion) in rotaciones:
                        angle = rotaciones[str(clave_rotacion)]
                    else:
                        # La DB es la fuente de verdad después de refrescar la página.
                        angle = ev.angulo_rotacion or 0
                    
                    meta = {
                        "photo_id": ev.id,
                        "registro_id": ev.registro_id,
                        "numero_parte": ev.registro.numero_parte,
                        "defecto": ev.registro.descripcion,
                        "filename": real_path.name,
                        "group_key": registro['key']
                    }
                    args_list.append((real_path, angle, target_h, tmp_dir, None, meta))

                # Ejecutar manteniendo el orden y la identidad (Regla 8)
                resultados_imagenes = list(executor.map(lambda p: _prepare_image_strip(*p), args_list))

                for tmp_path, disp_w, disp_h, meta in resultados_imagenes:
                    if meta:
                        logger.info(f"EXCEL PHOTO: photo_id={meta['photo_id']} registro_id={meta['registro_id']} numero_parte={meta['numero_parte']} defecto={meta['defecto']} filename={meta['filename']} group_key={meta['group_key']}")
                    if tmp_path is None:
                        continue

                    # WRAP: Si esta foto se sale de P+Q, saltar a la siguiente línea
                    if x_offset + disp_w > block_w_px - 8:
                        x_offset = 8
                        y_offset += target_h + GAP
                        max_y_reached = y_offset + target_h

                    try:
                        xl_img = OpenpyxlImage(str(tmp_path))
                    except Exception as e:
                        logger.error("Error openpyxl: %s", e)
                        continue

                    # Resolver en qué columna real cae esta imagen
                    real_col, real_col_off = _resolve_col_offset(ws, CELL_COL, x_offset, max_col=CELL_COL + 1)

                    xl_img.anchor = OneCellAnchor(
                        _from=AnchorMarker(
                            col=real_col,
                            colOff=pixels_to_EMU(real_col_off),
                            row=row,
                            rowOff=pixels_to_EMU(y_offset),
                        ),
                        ext=XDRPositiveSize2D(
                            pixels_to_EMU(disp_w),
                            pixels_to_EMU(disp_h),
                        ),
                    )
                    ws.add_image(xl_img)

                    # Avanzar horizontalmente
                    x_offset += disp_w + GAP

                # Expandir la altura de la fila si usamos múltiples líneas de fotos
                needed_pt = (max_y_reached + 8) * 0.75
                current_pt = ws.row_dimensions[row_1based].height or 0
                ws.row_dimensions[row_1based].height = max(needed_pt, current_pt)

            # Limpiar el excedente de filas de la plantilla para que no queden
            # formulas o bordes vacíos colgando, y si hay un pie de página o sumatoria, suba.
            last_data_row = START_ROW + len(registros)
            max_row = ws.max_row
            # openpyxl max_row puede incluir filas vacías formateadas
            if max_row > last_data_row:
                # Buscamos si hay un "Grand Total" o similar más abajo
                # Para ser seguros y no borrar un total, solo borramos las filas
                # inmediatas que no tienen valor en la columna 1 o 2
                pass
                
            # Mejor borramos todas las filas entre last_data_row y el primer Grand Total?
            # En openpyxl delete_rows es más fácil.
            # Como me pidieron borrar "no mas para que se vea mas pro":
            if max_row > last_data_row:
                ws.delete_rows(last_data_row + 1, max_row - last_data_row)

            wb.save(str(output_path))
            return output_path

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
