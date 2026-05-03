import os
import re
from pathlib import Path
from typing import List, Optional


class LocalFotoStorage:
    """
    Adaptador: encapsula las operaciones de filesystem que actualmente
    están dispersas en main_sqlite.py y views.py.

    Misma estructura de carpetas: fotos/{user_id}/
    Mismo formato de nombre: {contador:03d}_{timestamp}.png

    Mapeo:
    guardar()              → main_sqlite.py:312-328 (os.makedirs + escritura)
    obtener_path()         → views.py:229 (glob por número de secuencia)
    listar()               → main_sqlite.py:584-585 (os.listdir + filtro ext)
    eliminar_por_numeros() → main_sqlite.py:684-694 (os.remove por prefix)
    eliminar_todas()       → main_sqlite.py:522-526 (os.remove todas)
    """

    def __init__(self, fotos_path: str = "fotos"):
        self._fotos_path = fotos_path

    def _user_folder(self, user_id: int) -> str:
        return os.path.join(self._fotos_path, str(user_id))

    def guardar(self, user_id: int, nombre_archivo: str, contenido: bytes) -> str:
        """
        Idéntico a main_sqlite.py:312-328 (crear carpeta + escribir archivo).
        Retorna la ruta donde se guardó.
        """
        user_folder = self._user_folder(user_id)
        os.makedirs(user_folder, exist_ok=True)
        ruta = os.path.join(user_folder, nombre_archivo)
        with open(ruta, 'wb') as f:
            f.write(contenido)
        return ruta

    def obtener_path(self, user_id: int, numero: int) -> Optional[str]:
        """
        Idéntico a views.py:229 (buscar archivo por número de secuencia).
        Busca formato exacto (001.png) o con timestamp (001_2023.png).
        """
        user_folder = Path(self._user_folder(user_id))
        if not user_folder.exists():
            return None

        for ext in ['.png', '.jpg']:
            archivos = list(user_folder.glob(f"{numero:03d}{ext}")) + \
                       list(user_folder.glob(f"{numero:03d}_*{ext}"))
            if archivos:
                return str(archivos[0])
        return None

    def listar(self, user_id: int) -> List[str]:
        """
        Idéntico a main_sqlite.py:584-585 (listar imágenes en carpeta).
        """
        user_folder = self._user_folder(user_id)
        if not os.path.exists(user_folder):
            return []

        archivos = os.listdir(user_folder)
        return sorted([f for f in archivos if f.lower().endswith(('.jpg', '.png'))])

    def eliminar_por_numeros(self, user_id: int, numeros: List[int]) -> int:
        """
        Idéntico a main_sqlite.py:684-694 (cancelar: elimina por prefix).
        Retorna cantidad de archivos eliminados.
        """
        user_folder = self._user_folder(user_id)
        eliminadas = 0

        if not os.path.exists(user_folder):
            return 0

        for numero_foto in numeros:
            prefix = f"{numero_foto:03d}"
            for archivo in os.listdir(user_folder):
                if archivo.startswith(prefix) and (
                    len(archivo) == len(prefix) or not archivo[len(prefix)].isdigit()
                ):
                    try:
                        os.remove(os.path.join(user_folder, archivo))
                        eliminadas += 1
                    except Exception as e:
                        print(f"Error al eliminar foto {archivo}: {e}")
        return eliminadas

    def eliminar_todas(self, user_id: int) -> int:
        """
        Idéntico a main_sqlite.py:522-526 (limpiar_fotos: elimina todas).
        Retorna cantidad de archivos eliminados.
        """
        user_folder = self._user_folder(user_id)
        eliminadas = 0

        if not os.path.exists(user_folder):
            return 0

        for archivo in os.listdir(user_folder):
            if archivo.lower().endswith(('.jpg', '.png')):
                try:
                    os.remove(os.path.join(user_folder, archivo))
                    eliminadas += 1
                except Exception as e:
                    print(f"Error al eliminar foto {archivo}: {e}")
        return eliminadas
