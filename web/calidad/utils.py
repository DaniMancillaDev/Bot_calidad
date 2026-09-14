import os
import re as _re
from pathlib import Path
from typing import Optional


def _ts_key(p: Path) -> str:
    """Extrae timestamp del nombre de archivo para orden determinístico.
    Formato esperado: NNN_YYYYMMDD_HHMMSS.ext  → '20260615_205548'
    Si no hay timestamp, usa '00000000_000000' (siempre al final).
    """
    m = _re.search(r'_(\d{8}_\d{6})', p.name)
    return m.group(1) if m else '00000000_000000'


def get_best_image_path(fotos_dir: Path, uid_str: str, num: int) -> Optional[Path]:
    """
    Busca la mejor versión disponible de una foto.
    Prioridad:
    1. Proxy 1280x1280 (media_files/proxies/...)
    2. Original 12MP (media_files/fotos/...)

    Cuando hay múltiples archivos con el mismo número (ej. huérfanas de sesiones
    anteriores), siempre se elige el que tenga el timestamp MÁS RECIENTE en el
    nombre — eliminando el race condition de selección de imagen.

    Retorna la ruta absoluta en disco, o None si no se encuentra.
    """
    proxies_path = os.getenv("PROXIES_PATH", "media_files/proxies")
    proxies_dir = Path(proxies_path) / str(uid_str)
    user_folder = fotos_dir / str(uid_str)

    for ext in ['png', 'jpg']:
        pattern1 = f"{num:03d}.{ext}"
        pattern2 = f"{num:03d}_*.{ext}"

        if proxies_dir.exists():
            archivos = sorted(
                list(proxies_dir.glob(pattern1)) + list(proxies_dir.glob(pattern2)),
                key=_ts_key,
                reverse=True,  # más reciente primero
            )
            if archivos:
                return archivos[0]

        if user_folder.exists():
            archivos = sorted(
                list(user_folder.glob(pattern1)) + list(user_folder.glob(pattern2)),
                key=_ts_key,
                reverse=True,  # más reciente primero
            )
            if archivos:
                return archivos[0]


    # Fallback para V2 (Web Imports) donde 'num' es el ID de EvidenciaFotografica
    try:
        from calidad.models import EvidenciaFotografica
        from django.conf import settings
        
        ev = EvidenciaFotografica.objects.get(id=num)
        
        filename = Path(ev.ruta_archivo).name
        proxy_path = Path(settings.MEDIA_ROOT) / 'proxies' / str(uid_str) / filename
        if proxy_path.exists():
            return proxy_path
            
        ev_path_str = ev.ruta_archivo
        if ev_path_str.startswith('media_files/'):
            ev_path_str = ev_path_str[12:]
        elif ev_path_str.startswith('/media_files/'):
            ev_path_str = ev_path_str[13:]
        ev_path_str = ev_path_str.lstrip('/')
        
        real_path = Path(settings.MEDIA_ROOT) / ev_path_str
        if real_path.exists():
            return real_path
    except Exception:
        pass

    return None


def get_orientation_image_path(fotos_dir: Path, uid_str: str, num: int) -> Optional[Path]:
    """
    Busca la versión más liviana de una foto para inferencia de IA.
    Prioridad:
    1. Thumb 300x300 (media_files/thumbs/...)
    2. Proxy 1280x1280 (media_files/proxies/...)
    3. Original 12MP (media_files/fotos/...)
    """
    thumbs_path = os.getenv("THUMBS_PATH", "media_files/thumbs")
    thumbs_dir = Path(thumbs_path) / str(uid_str)

    for ext in ['png', 'jpg']:
        pattern1 = f"{num:03d}.{ext}"
        pattern2 = f"{num:03d}_*.{ext}"

        if thumbs_dir.exists():
            archivos = sorted(
                list(thumbs_dir.glob(pattern1)) + list(thumbs_dir.glob(pattern2)),
                key=_ts_key,
                reverse=True,
            )
            if archivos:
                return archivos[0]

    # Fallback to get_best_image_path (Proxy -> Original)
    return get_best_image_path(fotos_dir, uid_str, num)
