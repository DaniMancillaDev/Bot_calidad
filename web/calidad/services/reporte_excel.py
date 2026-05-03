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

# ============================================================
# CONFIGURACIÓN DE EXCEL
# ============================================================
SCALE_FACTOR   = 2     # 2x la resolución visual (buen zoom sin peso excesivo)
GAP            = 5     # Separación horizontal entre fotos (px)
MAX_DISPLAY_H  = 200   # Alto máximo visual de cada foto (px) — NO llena toda la fila
CELL_COL       = 15    # Columna P (0-indexed)
START_ROW      = 7     # Fila 8 en 0-indexed

# Plantilla — raíz del proyecto
_BASE_DIR      = Path(__file__).resolve().parent.parent.parent.parent
PLANTILLA_PATH = _BASE_DIR / "plantilla_reporte.xlsx"

# Calidad JPEG para las fotos insertadas (0-100)
# 88 = excelente calidad visual con buen ratio de compresión
JPEG_QUALITY = 88


def _get_row_height_px(ws, row_1based):
    """Obtiene la altura de una fila en píxeles (1pt ≈ 1.333px)."""
    h = ws.row_dimensions[row_1based].height
    if h is None or h <= 0:
        return 200
    return int(h * 1.333)


def _get_container_width(ws):
    """Calcula el ancho combinado en píxeles de las columnas P y Q."""
    p_w = ws.column_dimensions['P'].width or 8.43
    q_w = ws.column_dimensions['Q'].width or 8.43
    return _col_width_to_px(p_w) + _col_width_to_px(q_w)


def _col_width_to_px(w):
    """Convierte el ancho de columna de Excel (en caracteres) a píxeles."""
    if w is None or w <= 0:
        return 64
    return int(((256 * w + int(128 / 7)) / 256) * 7)


def _resolve_col_offset(ws, start_col, x_px):
    """
    Convierte un offset absoluto en píxeles (desde start_col)
    a la pareja (columna_real, offset_dentro_de_esa_columna).

    Esto garantiza que colOff nunca exceda el ancho de una columna,
    evitando solapamientos en la transición entre columnas P y Q.
    """
    remaining = x_px
    col = start_col

    while True:
        col_letter = openpyxl.utils.get_column_letter(col + 1)  # 1-based
        col_w = ws.column_dimensions[col_letter].width
        col_px = _col_width_to_px(col_w)

        if remaining < col_px:
            return col, remaining

        remaining -= col_px
        col += 1



def _prepare_image_strip(img_path: Path, angle: int, target_h: int, tmp_dir: Path):
    """
    Rota la imagen y la escala para que tenga EXACTAMENTE target_h de alto,
    dejando que el ancho se ajuste proporcionalmente.

    Guarda en alta resolución (×SCALE_FACTOR) para nitidez al hacer zoom.
    Retorna (path_tmp, display_w, display_h) o (None, 0, 0).
    """
    try:
        img = Image.open(img_path)
        img = ImageOps.exif_transpose(img)
        if angle != 0:
            # CSS rota en sentido horario (CW) con ángulos positivos.
            # PIL rota en sentido anti-horario (CCW) con ángulos positivos.
            # Invertimos el ángulo para que el Excel coincida exactamente con la vista web.
            img = img.rotate(-angle, expand=True)

        orig_w, orig_h = img.size

        # Escalar para que el ALTO sea exactamente target_h
        ratio  = target_h / orig_h
        disp_w = int(orig_w * ratio)
        disp_h = target_h  # exacto

        # Imagen física en alta resolución
        phys_w = disp_w * SCALE_FACTOR
        phys_h = disp_h * SCALE_FACTOR
        img_hi = img.resize((phys_w, phys_h), Image.LANCZOS)

        # Guardar como JPEG (mucho más liviano que PNG)
        img_hi = img_hi.convert('RGB')  # JPEG no soporta alpha
        tmp_path = tmp_dir / f"strip_{img_path.stem}_{angle}.jpg"
        img_hi.save(tmp_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return tmp_path, disp_w, disp_h
    except Exception as e:
        print(f"[ERROR] No se pudo procesar {img_path.name}: {e}")
        return None, 0, 0


# ============================================================
# GENERACIÓN DEL EXCEL
# ============================================================

def generate_excel(
    registros: list,
    rotaciones: dict,
    fotos_dir: Path,
    output_path: Path,
    plantilla_path: Path = None,
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

            # Escribir datos de texto
            ws.cell(row=row_1based, column=2).value  = today_str
            ws.cell(row=row_1based, column=3).value  = registro.get('modelo', '')
            ws.cell(row=row_1based, column=6).value  = registro.get('linea', '')
            ws.cell(row=row_1based, column=9).value  = registro.get('descripcion', '')
            ws.cell(row=row_1based, column=12).value = registro.get('cantidad', 1)
            ws.cell(row=row_1based, column=14).value = registro.get('responsable', '')

            if not nums_fotos:
                continue

            # Ancho máximo permitido (Columnas P+Q combinadas)
            max_w_px = _get_container_width(ws)

            # Altura de la fila en px (base)
            row_h_px = _get_row_height_px(ws, row_1based)

            # Limitar la altura de cada foto
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
                    # Buscar formato exacto (001.png) o con timestamp (001_2023.png)
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
                if x_offset + disp_w > max_w_px - 8:
                    x_offset = 8
                    y_offset += target_h + GAP
                    max_y_reached = y_offset + target_h

                try:
                    xl_img = OpenpyxlImage(str(tmp_path))
                except Exception as e:
                    print(f"[ERROR] openpyxl: {e}")
                    continue

                # Resolver en qué columna real cae esta imagen
                real_col, real_col_off = _resolve_col_offset(ws, CELL_COL, x_offset)

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

