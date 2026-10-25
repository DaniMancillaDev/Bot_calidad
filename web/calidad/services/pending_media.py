"""Derivados privados para evidencias pendientes de WhatsApp."""

import os
import uuid
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps


PENDING_DERIVATIVE_SPECS = {
    'thumb': ((360, 360), 78),
    'proxy': ((1280, 1280), 85),
}


def _root():
    root = Path(settings.WHATSAPP_PENDING_ROOT).resolve()
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        root.relative_to(media_root)
    except ValueError:
        return root
    raise OSError('El almacenamiento pendiente no puede estar dentro de MEDIA_ROOT.')


def pending_original_path(evidence):
    root = _root()
    path = (root / evidence.file_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise OSError('Ruta de evidencia pendiente no permitida.') from exc
    if not path.is_file():
        raise FileNotFoundError('Archivo de evidencia pendiente no encontrado.')
    return path


def pending_derivative_path(evidence, variant):
    if variant not in PENDING_DERIVATIVE_SPECS:
        raise ValueError('Variante de evidencia pendiente no soportada.')
    return _root() / '.derivatives' / str(evidence.id) / f'{variant}.jpg'


def ensure_pending_derivative(evidence, variant):
    """Devuelve un derivado privado y lo crea atómicamente solo si falta."""
    target = pending_derivative_path(evidence, variant)
    if target.is_file():
        return target

    source = pending_original_path(evidence)
    size, quality = PENDING_DERIVATIVE_SPECS[variant]
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f'.{target.name}.{uuid.uuid4().hex}.tmp')
    try:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            try:
                if image.mode not in ('RGB', 'L'):
                    image = image.convert('RGB')
                image.thumbnail(size, Image.Resampling.LANCZOS)
                image.save(temporary, format='JPEG', quality=quality, optimize=True)
            finally:
                if image is not original:
                    image.close()
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def generate_pending_derivatives(evidence):
    """Genera los tamaños usados por la bandeja sin tocar el original."""
    return [ensure_pending_derivative(evidence, variant) for variant in PENDING_DERIVATIVE_SPECS]
