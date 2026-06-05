# shared.domain.interfaces — Contratos (Protocol) basados en el comportamiento REAL del sistema.
# DatabaseManager YA satisface estos protocolos sin modificaciones (structural subtyping).
# NO se usan aún en producción — solo preparan el terreno para DIP.

from typing import Protocol, Dict, List, Optional, runtime_checkable


# ============================================================
# USUARIO — mapea database.py:112-214
# ============================================================

@runtime_checkable
class UsuarioRepository(Protocol):
    """
    Contrato para acceso a datos de usuarios.

    Mapeo directo:
    - tiene_acceso()      ← database.py: usuario_tiene_acceso()
    - obtener()           ← database.py: obtener_usuario()
    - crear()             ← database.py: crear_usuario()
    - actualizar()        ← database.py: actualizar_usuario()
    - listar()            ← database.py: listar_usuarios()
    """

    def tiene_acceso(self, telegram_user_id: int) -> bool: ...
    def obtener(self, telegram_user_id: int) -> Optional[Dict]: ...
    def crear(self, telegram_user_id: int, turno: str, departamento: str,
              username: Optional[str] = None) -> bool: ...
    def actualizar(self, telegram_user_id: int,
                   turno: Optional[str] = None,
                   departamento: Optional[str] = None,
                   username: Optional[str] = None) -> bool: ...
    def listar(self) -> List[Dict]: ...


# ============================================================
# REGISTRO DE DEFECTOS — mapea database.py:220-339
# ============================================================

@runtime_checkable
class RegistroRepository(Protocol):
    """
    Contrato para registros de defectos.

    Mapeo directo:
    - guardar()                        ← database.py: guardar_registro()
    - obtener_todos()                  ← database.py: obtener_todos_registros()
    - obtener_por_turno_depto()        ← database.py: obtener_registros_por_turno_depto()
    - limpiar_por_usuario()            ← database.py: limpiar_registros_usuario()
    - obtener_estadisticas()           ← database.py: obtener_estadisticas()
    """

    def guardar(self, fotos: List[int], modelo: str, linea: str,
                cantidad: int, responsable: str, descripcion: str,
                user_id: int, turno: Optional[str] = None,
                departamento: Optional[str] = None) -> bool: ...
    def obtener_todos(self, user_id: Optional[int] = None,
                      turno: Optional[str] = None,
                      departamento: Optional[str] = None) -> List[Dict]: ...
    def obtener_por_turno_depto(self, turno: str, departamento: str,
                                user_id: Optional[int] = None) -> List[Dict]: ...
    def limpiar_por_usuario(self, user_id: int) -> bool: ...
    def obtener_estadisticas(self, user_id: Optional[int] = None,
                             turno: Optional[str] = None,
                             departamento: Optional[str] = None) -> Dict: ...


# ============================================================
# CONTADORES — mapea database.py:394-449
# ============================================================

@runtime_checkable
class ContadorRepository(Protocol):
    """
    Contrato para contadores de secuencia de fotos.

    Mapeo directo:
    - obtener_y_avanzar()    ← database.py: obtener_y_avanzar_contador()
    - obtener_actual()       ← database.py: obtener_contador_usuario()

    NOTA: Los métodos legacy vacíos (actualizar_contador_usuario, reiniciar,
    obtener_ultimo_numero_confirmado, actualizar_ultimo_numero_confirmado)
    NO se incluyen porque no tienen comportamiento real.
    """

    def obtener_y_avanzar(self, user_id: int) -> int: ...
    def obtener_actual(self, user_id: int) -> int: ...


# ============================================================
# ESTADO DE CONVERSACIÓN — mapea main_sqlite.py:103-146
# ============================================================

@runtime_checkable
class ConversationStateRepository(Protocol):
    """
    Contrato para estado de conversaciones del bot.

    Mapeo directo:
    - tiene_conversacion()    ← main_sqlite.py: user_id in conversaciones
    - obtener()               ← main_sqlite.py: conversaciones[user_id]
    - iniciar()               ← main_sqlite.py: iniciar_conversacion()
    - finalizar()             ← main_sqlite.py: finalizar_conversacion()
    - persistir()             ← main_sqlite.py: guardar_estado()

    Estructura de cada conversación (Dict):
    {
        'estado': str,              # ESPERANDO_FOTOS, ESPERANDO_MODELO, etc.
        'fotos': List[int],         # Lista de números de secuencia
        'datos': Dict,              # {'modelo': ..., 'linea': ..., etc.}
        'fotos_sin_asignar': List   # Legacy, actualmente vacío
    }

    Patrón de uso actual:
    1. conv = repo.obtener(user_id)  → obtiene dict mutable
    2. conv['estado'] = NUEVO_ESTADO → modifica in-place
    3. repo.persistir()              → guarda a disco
    """

    def tiene_conversacion(self, user_id: int) -> bool: ...
    def obtener(self, user_id: int) -> Optional[Dict]: ...
    def iniciar(self, user_id: int) -> Dict: ...
    def finalizar(self, user_id: int) -> None: ...
    def persistir(self) -> None: ...


# ============================================================
# ALMACENAMIENTO DE FOTOS — mapea main_sqlite.py:274-655 + views.py:184-321
# ============================================================

@runtime_checkable
class FotoStorage(Protocol):
    """
    Contrato para almacenamiento de fotos en filesystem.

    Mapeo directo:
    - guardar()              ← main_sqlite.py:312-328 (crear carpeta + download)
    - obtener_path()         ← views.py:229 (glob por número de secuencia)
    - listar()               ← main_sqlite.py:584-585 (os.listdir + filtro)
    - eliminar_por_numeros() ← main_sqlite.py:684-694 (cancelar: elimina por prefix)
    - eliminar_todas()       ← main_sqlite.py:522-526 (limpiar_fotos: elimina todas)

    Formato de nombre de archivo: {contador:03d}_{YYYYMMDD_HHMMSS}.png
    Estructura de carpetas: fotos/{user_id}/
    """

    def guardar(self, user_id: int, nombre_archivo: str, contenido: bytes) -> str: ...
    def obtener_path(self, user_id: int, numero: int) -> Optional[str]: ...
    def listar(self, user_id: int) -> List[str]: ...
    def eliminar_por_numeros(self, user_id: int, numeros: List[int]) -> int: ...
    def eliminar_todas(self, user_id: int) -> int: ...


# ============================================================
# DETECCIÓN DE ORIENTACIÓN — mapea reporte_excel.py:128-151
# ============================================================

@runtime_checkable
class OrientationDetector(Protocol):
    """
    Contrato para detección de orientación de imágenes.

    Mapeo directo:
    - detectar()        ← reporte_excel.py: detect_orientation()
    - detectar_batch()  ← reporte_excel.py: detect_orientations_batch()

    Retorna ángulo en grados: 0, 90, 180, 270.
    """

    def detectar(self, img_path) -> int: ...
    def detectar_batch(self, foto_paths: list) -> dict: ...

# ============================================================
# IA — Traducción de defectos
# ============================================================

from typing import TypedDict

class DefectTranslation(TypedDict):
    defect_en: str
    simple_analysis_en: str

@runtime_checkable
class IDefectTranslator(Protocol):
    """
    Contrato para el servicio de traducción de defectos con IA.
    """
    def translate(self, descripcion: str, area: str) -> DefectTranslation: ...
