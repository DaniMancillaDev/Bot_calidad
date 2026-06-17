"""
Generador de PowerPoint de desahogo.
Solo imágenes. Sin texto. Sin portada.

Layout de 2 pasos:
  1. Calcular altura real renderizada de cada fila (considerando constraint de ancho).
  2. Apilar filas con ROW_GAP fijo y centrar el bloque verticalmente en el slide.

Resultado: filas juntas como en la imagen de referencia, sin espacio vacío
           entre ellas aunque las fotos sean landscape.
"""
import logging
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# ── Dimensiones slide ─────────────────────────────────────────────────────────
SLIDE_W = 10.0      # pulgadas
SLIDE_H = 7.5       # pulgadas

OUTER_MARGIN_H = 0.25   # Margen lateral (izq/der)
OUTER_MARGIN_V = 0.20   # Margen exterior arriba/abajo del bloque total
GAP_H          = 0.10   # Gap horizontal entre fotos
ROW_GAP        = 0.10   # Gap vertical entre filas (pequeño y fijo)

MAX_FILAS_POR_SLIDE = 2
MAX_FOTOS_POR_FILA  = 4


# ── Helpers ───────────────────────────────────────────────────────────────────

from calidad.utils import get_best_image_path

def _get_image_path(fotos_dir: Path, uid_str: str, num: int):
    return get_best_image_path(fotos_dir, uid_str, num)


def _open_dims(img_path: Path, angle: int = 0):
    """Devuelve (w, h) con corrección EXIF y rotación aplicada."""
    try:
        with Image.open(img_path) as im:
            im = ImageOps.exif_transpose(im)
            if angle in (90, 270):
                # La rotación intercambia ancho y alto
                return im.size[1], im.size[0]
            return im.size
    except Exception:
        return (1, 1)


def _build_rows(fotos_items: list) -> list:
    """fotos_items: lista de tuplas (path, uid_str, num)."""
    rows = []
    for i in range(0, len(fotos_items), MAX_FOTOS_POR_FILA):
        rows.append(fotos_items[i:i + MAX_FOTOS_POR_FILA])
    return rows


def _calc_row_render_height(row_items: list, available_w: float, max_h: float) -> tuple:
    """
    row_items: lista de tuplas (path, angle).
    Retorna (foto_h, foto_ws).
    """
    dims = [_open_dims(p, angle) for (p, angle) in row_items]
    n = len(row_items)

    # Anchura natural de cada foto a la altura máxima
    widths_nat = [max_h * (w / h) for (w, h) in dims]
    total_gaps = GAP_H * (n - 1)
    avail_for_imgs = available_w - total_gaps

    if sum(widths_nat) > avail_for_imgs:
        # Constraint de ancho: reducir escala uniformemente
        scale   = avail_for_imgs / sum(widths_nat)
        foto_h  = max_h * scale
        foto_ws = [w * scale for w in widths_nat]
    else:
        # Caben a altura máxima
        foto_h  = max_h
        foto_ws = widths_nat

    return foto_h, foto_ws


def _place_row(slide, row_items: list, y_top: float, available_w: float,
               foto_h: float, foto_ws: list):
    """
    row_items: lista de tuplas (path, angle).
    Centra el bloque horizontalmente. y_top es el borde superior de las fotos.
    """
    total_gaps = GAP_H * (len(row_items) - 1)
    block_w    = sum(foto_ws) + total_gaps
    x_start    = OUTER_MARGIN_H + (available_w - block_w) / 2

    x_cursor = x_start
    for (img_path, angle), fw in zip(row_items, foto_ws):
        try:
            # Aplicar rotación: pre-rotar y guardar en buffer para python-pptx
            from io import BytesIO
            with Image.open(img_path) as im:
                im = ImageOps.exif_transpose(im)
                if angle in (90, 180, 270):
                    mapping = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}
                    im = im.transpose(mapping[angle])
                buf = BytesIO()
                im.convert('RGB').save(buf, format='JPEG', quality=92)
                buf.seek(0)

            slide.shapes.add_picture(
                buf,
                Inches(x_cursor),
                Inches(y_top),
                width=Inches(fw),
                height=Inches(foto_h),
            )
        except Exception as e:
            logger.error("Error insertando foto PPTX: %s — %s", img_path.name, e)
        x_cursor += fw + GAP_H


def _layout_slide(slide, slide_rows: list):
    """
    slide_rows: lista de filas; cada fila es lista de tuplas (path, angle).
    """
    n_rows      = len(slide_rows)
    available_w = SLIDE_W - 2 * OUTER_MARGIN_H
    max_row_h   = (SLIDE_H - 2 * OUTER_MARGIN_V - ROW_GAP * (n_rows - 1)) / n_rows

    row_data = [
        _calc_row_render_height(row, available_w, max_row_h)
        for row in slide_rows
    ]

    actual_heights = [rd[0] for rd in row_data]
    total_block_h  = sum(actual_heights) + ROW_GAP * (n_rows - 1)
    y_cursor       = OUTER_MARGIN_V + (SLIDE_H - 2 * OUTER_MARGIN_V - total_block_h) / 2

    for row_items, (foto_h, foto_ws) in zip(slide_rows, row_data):
        _place_row(slide, row_items, y_cursor, available_w, foto_h, foto_ws)
        y_cursor += foto_h + ROW_GAP


# ── Generador principal ───────────────────────────────────────────────────────

def generar_pptx_grupo(grupo: dict, fotos_dir: Path, output_path: Path,
                       rotaciones: dict = None, translator=None):
    """
    Genera PPTX de desahogo: solo imágenes, sin texto, sin portada.
    rotaciones: dict {"uid_num" -> angulo} igual que en generate_excel.
    """
    prs = Presentation()

    try:
        blank_layout = prs.slide_layouts[6]   # Blank
    except IndexError:
        blank_layout = prs.slide_layouts[0]

    # Recolectar tuplas (path, angle) en orden
    rotaciones = rotaciones or {}
    fotos_items = []
    for uid_str, nums in grupo.get('fotos_por_usuario', {}).items():
        for num in nums:
            p = _get_image_path(fotos_dir, uid_str, num)
            if p:
                clave = f"{uid_str}_{num}"
                angle = rotaciones.get(clave) or rotaciones.get(str(clave)) or 0
                fotos_items.append((p, angle))

    if not fotos_items:
        prs.save(str(output_path))
        return output_path

    all_rows = _build_rows(fotos_items)

    # Particionar en slides de MAX_FILAS_POR_SLIDE filas
    for slide_idx in range(0, len(all_rows), MAX_FILAS_POR_SLIDE):
        slide_rows = all_rows[slide_idx:slide_idx + MAX_FILAS_POR_SLIDE]

        slide = prs.slides.add_slide(blank_layout)
        for shape in list(slide.shapes):
            try:
                shape.element.getparent().remove(shape.element)
            except Exception:
                pass

        _layout_slide(slide, slide_rows)

    prs.save(str(output_path))
    logger.info(
        "PPTX generado: %s | %d fotos | %d slides",
        output_path.name, len(fotos_items), len(prs.slides)
    )
    return output_path
