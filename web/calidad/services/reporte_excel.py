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
import warnings
from pathlib import Path
from PIL import Image, ImageFile, ImageOps
import openpyxl
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.drawing.xdr import XDRPositiveSize2D
from openpyxl.utils.units import pixels_to_EMU

# Detección de orientación: importada desde shared/ (fuente de verdad única)
from shared.infrastructure.orientation.orientation_engine import (
    detect_orientation,
    detect_orientations_batch,
)

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
CELL_COL       = 15    # Columna P (0-indexed)
START_ROW      = 7     # Fila 8 en 0-indexed

# ── Columnas para campos en inglés (POC) ──────────────────────────────────
# Ajusta estos valores según tu plantilla.
# Valores actuales: I=9, J=10
COL_DEFECT_EN   = 9   # Columna I: defect_en (reemplaza descripción en español)
COL_ANALYSIS_EN = 10  # Columna J: simple_analysis_en

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



def _prepare_image_strip(img_path: Path, angle: int, target_h: int, tmp_dir: Path,
                         max_width: int = None):
    """
    Rota la imagen y la escala con lógica contain:
    - Alto máximo = target_h
    - Ancho máximo = max_width (si se pasa)
    Nunca deforma. Guarda en alta resolución (×SCALE_FACTOR).
    Retorna (path_tmp, display_w, display_h) o (None, 0, 0).
    """
    try:
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

        # Guardar como JPEG (mucho más liviano que PNG)
        img_hi = img_hi.convert('RGB')
        tmp_path = tmp_dir / f"strip_{img_path.stem}_{angle}.jpg"
        img_hi.save(tmp_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return tmp_path, disp_w, disp_h
    except Exception as e:
        logger.error("No se pudo procesar %s: %s", img_path.name, e)
        return None, 0, 0


def _prepare_image_for_slot(img_path: Path, angle: int, slot_w: int, tmp_dir: Path):
    """
    Rota la imagen y la escala para llenar el ancho del slot.
    Escala por ancho primero (ratio = slot_w / orig_w), sin límite de altura.
    Nunca deforma. Guarda en alta resolución (×SCALE_FACTOR).
    Retorna (path_tmp, display_w, display_h) o (None, 0, 0).
    """
    try:
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

        # ── Width-first scaling: llenar ancho del slot ──
        ratio = slot_w / orig_w

        disp_w = slot_w
        disp_h = int(orig_h * ratio)

        # Imagen física en alta resolución
        phys_w = disp_w * SCALE_FACTOR
        phys_h = disp_h * SCALE_FACTOR
        img_hi = img.resize((phys_w, phys_h), Image.LANCZOS)

        # Guardar como JPEG
        img_hi = img_hi.convert('RGB')
        tmp_path = tmp_dir / f"slot_{img_path.stem}_{angle}.jpg"
        img_hi.save(tmp_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return tmp_path, disp_w, disp_h
    except Exception as e:
        logger.error("No se pudo procesar %s: %s", img_path.name, e)
        return None, 0, 0


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


def place_image_contain(
    ws,
    image_path: str | Path,
    col_start: str = "P",
    col_end: str = "Q",
    row: int = 15,
    max_height: int = None,
    padding: int = 0,
    align: str = "center",
    auto_row_height: bool = False,
    logger_obj=None
) -> None:
    """
    Inserta una imagen en Excel simulando object-fit: contain.
    Mantiene la proporción y alinea sin deformar.
    
    :param ws: Worksheet de openpyxl
    :param image_path: ruta local a la imagen
    :param col_start: letra de columna inicial (ej. "P")
    :param col_end: letra de columna final (ej. "Q")
    :param row: fila (1-indexed) donde colocar la imagen
    :param max_height: px máximos permitidos en altura (None = usa alto de fila)
    :param padding: px de margen interno
    :param align: "center", "left", "right"
    :param auto_row_height: ajusta la fila si la imagen la excede
    :param logger_obj: opcional, para debugear
    """
    if logger_obj:
        logger_obj.debug("Procesando imagen: %s en %s%s:%s%s", image_path, col_start, row, col_end, row)
        
    try:
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        if logger_obj:
            logger_obj.error("Error al abrir imagen %s: %s", image_path, e)
        return

    orig_w, orig_h = img.size
    
    # 1. Cálculo de ancho del bloque
    block_width_px = _get_columns_width(ws, col_start, col_end)
    effective_width = max(1, block_width_px - (padding * 2))
    
    # Altura disponible
    if max_height is None:
        effective_height = _get_row_height_px(ws, row) - (padding * 2)
    else:
        effective_height = max_height - (padding * 2)
        
    if effective_height <= 0:
        effective_height = 1

    # 2. Escalado proporcional (contain)
    ratio_w = effective_width / orig_w
    ratio_h = effective_height / orig_h
    ratio = min(ratio_w, ratio_h)
    
    disp_w = int(orig_w * ratio)
    disp_h = int(orig_h * ratio)
    
    # Lazy resize en memoria (Bono: no genera archivos físicos temporales)
    import io
    img_byte_arr = io.BytesIO()
    
    # Escalar físicamente si la original es muy grande (manteniendo nitidez con SCALE_FACTOR)
    phys_w, phys_h = disp_w * SCALE_FACTOR, disp_h * SCALE_FACTOR
    if phys_w < orig_w and phys_h < orig_h:
        img = img.resize((phys_w, phys_h), Image.LANCZOS)
    
    img = img.convert('RGB')
    img.save(img_byte_arr, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    img_byte_arr.seek(0)
    xl_img = OpenpyxlImage(img_byte_arr)

    # 3. Alineación
    if align == "center":
        x_offset = padding + (effective_width - disp_w) // 2
    elif align == "right":
        x_offset = padding + effective_width - disp_w
    else:  # left
        x_offset = padding
        
    y_offset = padding

    # 4. Anchor correcto — offset absoluto desde col_start
    # Evita gap visual en fronteras de columna
    start_col_idx = openpyxl.utils.column_index_from_string(col_start) - 1  # 0-indexed
    row_idx = row - 1  # 0-indexed para openpyxl
    
    end_col_idx = openpyxl.utils.column_index_from_string(col_end) - 1  # 0-indexed
    anchor_col, anchor_colOff = _resolve_col_offset(ws, start_col_idx, x_offset, max_col=end_col_idx)
    xl_img.anchor = OneCellAnchor(
        _from=AnchorMarker(
            col=anchor_col,
            colOff=pixels_to_EMU(anchor_colOff),
            row=row_idx,
            rowOff=pixels_to_EMU(y_offset),
        ),
        ext=XDRPositiveSize2D(
            pixels_to_EMU(disp_w),
            pixels_to_EMU(disp_h),
        ),
    )
    ws.add_image(xl_img)
    
    # 5. Bono: auto altura de fila
    if auto_row_height:
        needed_pt = (disp_h + (padding * 2)) * 0.75  # 1px = 0.75pt
        current_pt = ws.row_dimensions[row].height or 0
        if needed_pt > current_pt:
            ws.row_dimensions[row].height = needed_pt

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
        today_str = datetime.now().strftime("%Y-%m-%d")

        for idx, registro in enumerate(registros):
            row        = START_ROW + idx
            row_1based = row + 1
            nums_fotos = registro.get('fotos_nums', [])

            # Agregar encabezado dinámicamente si es la primera fila de datos
            if idx == 0:
                ws.cell(row=START_ROW, column=7).value = "Part Number"

            # Escribir datos de texto
            ws.cell(row=row_1based, column=2).value  = today_str
            ws.cell(row=row_1based, column=3).value  = registro.get('modelo', '')
            ws.cell(row=row_1based, column=6).value  = registro.get('linea', '')
            ws.cell(row=row_1based, column=7).value  = registro.get('numero_parte') or ""
            ws.cell(row=row_1based, column=9).value  = registro.get('descripcion', '')
            ws.cell(row=row_1based, column=12).value = registro.get('cantidad', 1)
            ws.cell(row=row_1based, column=14).value = registro.get('responsable', '')

            # ── Traducción IA (POC) ────────────────────────────────────────
            # Solo activo si EXCEL_AI_ENABLED=true. Nunca bloquea la generación.
            if translator is not None:
                try:
                    area = registro.get('departamento', registro.get('turno', ''))
                    tr   = translator.translate(registro.get('descripcion', ''), area)
                    if tr['defect_en']:
                        ws.cell(row=row_1based, column=COL_DEFECT_EN).value   = tr['defect_en']
                    if tr['simple_analysis_en']:
                        ws.cell(row=row_1based, column=COL_ANALYSIS_EN).value = tr['simple_analysis_en']
                except Exception as _tr_err:
                    logger.error("generate_excel: traducción falló en fila %d: %s", row_1based, _tr_err)
            # ────────────────────────────────────────────────────────────────

            if not nums_fotos:
                continue

            # Ancho del bloque P+Q (sin combinar celdas, solo visual)
            block_w_px = _get_container_width(ws)

            # Limitar la altura de cada foto
            row_h_px = _get_row_height_px(ws, row_1based)
            target_h = min(row_h_px, MAX_DISPLAY_H)

            # ── TIRA HORIZONTAL CON WRAPPING ────────────────
            x_offset = 8
            y_offset = 8
            max_y_reached = target_h + 8  # Rastrear qué tan alta se vuelve la fila

            for num in nums_fotos:
                user_id = registro.get('user_id')
                if not user_id:
                    continue
                
                user_folder = fotos_dir / str(user_id)
                if not user_folder.exists():
                    continue

                img_path = None
                for ext in ['png', 'jpg']:
                    archivos = list(user_folder.glob(f"{num:03d}.{ext}")) + \
                               list(user_folder.glob(f"{num:03d}_*.{ext}"))
                    if archivos:
                        img_path = archivos[0]
                        break
                        
                if not img_path:
                    continue
                
                clave_rotacion = f"{user_id}_{num}"
                angle = rotaciones.get(clave_rotacion) or rotaciones.get(str(clave_rotacion)) or 0
                tmp_path, disp_w, disp_h = _prepare_image_strip(
                    img_path, angle, target_h, tmp_dir
                )
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

        wb.save(str(output_path))
        return output_path

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

