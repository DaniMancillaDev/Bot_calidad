"""
shared/infrastructure/storage/foto_storage.py

Abstracción de storage para imágenes del bot.
Etapa 5 — Fase 1: Aislar dependencia de media_files/fotos.

Interfaz: FotoStorage (Protocol)
Implementación actual: LocalFotoStorage
Implementación futura: S3FotoStorage / MinioFotoStorage

REGLAS:
- Toda operación de disco pasa por esta interfaz.
- Nunca usar os.path / Path directamente fuera de esta capa.
- Intercambiar backend = cambiar solo la implementación en dependencies.py.
"""
import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class FotoStorage(Protocol):
    """
    Contrato de storage para fotos del bot.
    Implementaciones: LocalFotoStorage, S3FotoStorage (futura).
    """

    def get_user_folder(self, user_id: int) -> Path:
        """Retorna Path a la carpeta del usuario. La crea si no existe."""
        ...

    def get_thumb_folder(self, user_id: int) -> Path:
        """Retorna Path a la carpeta de thumbnails. La crea si no existe."""
        ...

    def get_foto_path(self, user_id: int, nombre: str) -> Path:
        """Retorna Path absoluta a una foto específica."""
        ...

    def get_thumb_path(self, user_id: int, nombre: str) -> Path:
        """Retorna Path absoluta a un thumbnail específico."""
        ...

    def foto_exists(self, user_id: int, nombre: str) -> bool:
        """Verifica si la foto existe en storage."""
        ...

    def thumb_exists(self, user_id: int, nombre: str) -> bool:
        """Verifica si el thumbnail existe en storage."""
        ...

    def delete_foto(self, user_id: int, nombre: str) -> bool:
        """Elimina una foto. Retorna True si se eliminó, False si no existía."""
        ...

    def list_fotos(self, user_id: int) -> list[str]:
        """Lista todos los nombres de archivo de fotos del usuario."""
        ...


class LocalFotoStorage:
    """
    Implementación Local del FotoStorage.
    Guarda fotos en el filesystem local del contenedor.
    Compatible con el volumen compartido Docker actual.

    Reemplazar por S3FotoStorage cuando se migre a cloud.
    """

    def __init__(self, base_path: str | None = None, thumbs_path: str | None = None):
        self._base = Path(base_path or os.getenv("FOTOS_PATH", "media_files/fotos"))
        self._thumbs = Path(thumbs_path or os.getenv("THUMBS_PATH", "media_files/thumbs"))

    def get_user_folder(self, user_id: int) -> Path:
        folder = self._base / str(user_id)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def get_thumb_folder(self, user_id: int) -> Path:
        folder = self._thumbs / str(user_id)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def get_foto_path(self, user_id: int, nombre: str) -> Path:
        return self._base / str(user_id) / nombre

    def get_thumb_path(self, user_id: int, nombre: str) -> Path:
        return self._thumbs / str(user_id) / nombre

    def foto_exists(self, user_id: int, nombre: str) -> bool:
        return self.get_foto_path(user_id, nombre).exists()

    def thumb_exists(self, user_id: int, nombre: str) -> bool:
        return self.get_thumb_path(user_id, nombre).exists()

    def delete_foto(self, user_id: int, nombre: str) -> bool:
        path = self.get_foto_path(user_id, nombre)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_fotos(self, user_id: int) -> list[str]:
        folder = self._base / str(user_id)
        if not folder.exists():
            return []
        return sorted(
            f.name for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in ('.jpg', '.jpeg', '.png')
        )
