import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pytest


def _ensure_schema(db_path: Path) -> None:
    """
    Inicializa el schema REAL usando DatabaseManager y completa tablas/columnas
    que el código productivo asume (compatibilidad legacy).
    """
    # Import tardío: evita que `database.db = DatabaseManager()` cree la DB en el root del proyecto.
    from database import DatabaseManager

    DatabaseManager(db_path=str(db_path))

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()

        # Tabla referenciada por DatabaseManager.crear_usuario() (aunque no la usemos aquí)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS contadores_usuario (
              user_id INTEGER PRIMARY KEY,
              contador_actual INTEGER DEFAULT 1,
              ultimo_numero_confirmado INTEGER DEFAULT 0
            )
            """
        )

        # Columnas usadas por guardar_registro() pero no creadas en init_database()
        cur.execute("PRAGMA table_info(registros_defectos)")
        cols = {row[1] for row in cur.fetchall()}
        if "numero_secuencia_inicio" not in cols:
            cur.execute("ALTER TABLE registros_defectos ADD COLUMN numero_secuencia_inicio INTEGER")
        if "numero_secuencia_fin" not in cols:
            cur.execute("ALTER TABLE registros_defectos ADD COLUMN numero_secuencia_fin INTEGER")

        conn.commit()


def _insert_usuario(db_path: Path, *, telegram_user_id: int, turno: str = "A", departamento: str = "QA") -> None:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO usuarios_bot (telegram_user_id, username, turno, departamento)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_user_id, f"user{telegram_user_id}", turno, departamento),
        )
        conn.commit()


def _fetchall_dicts(db_path: Path, sql: str, params: Iterable[Any] = ()) -> list[Dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Aísla efectos de import (database.py crea DB global por defecto)
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "integration.sqlite3"
    _ensure_schema(path)
    return path


@pytest.fixture
def estado_file(tmp_path: Path) -> Path:
    return tmp_path / "estado_conversaciones_test.json"


@pytest.fixture
def db_manager(db_path: Path):
    from database import DatabaseManager

    return DatabaseManager(db_path=str(db_path))


@pytest.fixture
def usuario_repo(db_manager):
    from shared.infrastructure.database.sqlite_usuario_repository import SqliteUsuarioRepository

    return SqliteUsuarioRepository(db_manager)


@pytest.fixture
def registro_repo(db_manager):
    from shared.infrastructure.database.sqlite_registro_repository import SqliteRegistroRepository

    return SqliteRegistroRepository(db_manager)


@pytest.fixture
def conversation_repo(estado_file: Path):
    from shared.infrastructure.storage.json_conversation_state import JsonConversationStateRepository

    return JsonConversationStateRepository(estado_file=str(estado_file))


@pytest.fixture
def service(usuario_repo, registro_repo, conversation_repo):
    from shared.application.services.registro_service import RegistroService

    return RegistroService(usuario_repo=usuario_repo, registro_repo=registro_repo, conversation_repo=conversation_repo, db_legacy=None)


@pytest.fixture
def user_id() -> int:
    return 424242


def _set_fotos(conversation_repo, user_id: int, fotos: list[int]) -> None:
    conv = conversation_repo.obtener(user_id)
    assert conv is not None
    conv["fotos"] = fotos
    conversation_repo.persistir()


def _load_estado_json(estado_file: Path) -> Dict[str, Any]:
    if not estado_file.exists():
        return {}
    return json.loads(estado_file.read_text(encoding="utf-8"))


def test_golden_path_completo_inserta_en_sqlite_y_finaliza(service, conversation_repo, db_path: Path, estado_file: Path, user_id: int):
    _insert_usuario(db_path, telegram_user_id=user_id, turno="A", departamento="QA")

    r0 = service.procesar_respuesta(user_id, "hola")
    assert r0.siguiente_estado is not None

    _set_fotos(conversation_repo, user_id, [1, 2, 3])
    r1 = service.procesar_respuesta(user_id, "TERMINAR")
    assert r1.error is False

    service.procesar_respuesta(user_id, "MODEL X")
    service.procesar_respuesta(user_id, "T03")
    service.procesar_respuesta(user_id, "5")
    service.procesar_respuesta(user_id, "XM")
    r_final = service.procesar_respuesta(user_id, "pantalla con manchas")

    assert r_final.finalizado is True
    assert conversation_repo.tiene_conversacion(user_id) is False
    assert str(user_id) not in _load_estado_json(estado_file)

    rows = _fetchall_dicts(db_path, "SELECT * FROM registros_defectos")
    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == user_id
    assert row["modelo"] == "MODEL X"
    assert row["linea"] == "T03"
    assert row["cantidad"] == 5
    assert row["responsable"] == "XM"
    assert row["descripcion"] == "PANTALLA CON MANCHAS"
    assert row["fotos"] == "(001-003)"
    assert row["numero_secuencia_inicio"] == 1
    assert row["numero_secuencia_fin"] == 3


def test_usuario_no_registrado_no_inserta_y_no_finaliza(service, conversation_repo, db_path: Path, user_id: int):
    # NO insertamos usuario en usuarios_bot
    service.procesar_respuesta(user_id, "hola")
    _set_fotos(conversation_repo, user_id, [10, 11])
    service.procesar_respuesta(user_id, "TERMINAR")
    service.procesar_respuesta(user_id, "M1")
    service.procesar_respuesta(user_id, "L1")
    service.procesar_respuesta(user_id, "1")
    service.procesar_respuesta(user_id, "R1")
    r = service.procesar_respuesta(user_id, "DESC")

    assert r.error is True
    assert r.finalizado is False
    assert conversation_repo.tiene_conversacion(user_id) is True

    rows = _fetchall_dicts(db_path, "SELECT * FROM registros_defectos WHERE user_id = ?", (user_id,))
    assert rows == []


def test_persistencia_real_de_estado_reinicio_con_json(service, conversation_repo, db_path: Path, estado_file: Path, user_id: int):
    _insert_usuario(db_path, telegram_user_id=user_id, turno="B", departamento="IQA")

    service.procesar_respuesta(user_id, "hola")
    _set_fotos(conversation_repo, user_id, [7, 8, 9])
    service.procesar_respuesta(user_id, "TERMINAR")
    service.procesar_respuesta(user_id, "M2")

    # "Reinicio": nuevas instancias leyendo la misma DB + mismo JSON de estado
    from database import DatabaseManager
    from shared.infrastructure.database.sqlite_usuario_repository import SqliteUsuarioRepository
    from shared.infrastructure.database.sqlite_registro_repository import SqliteRegistroRepository
    from shared.infrastructure.storage.json_conversation_state import JsonConversationStateRepository
    from shared.application.services.registro_service import RegistroService

    db2 = DatabaseManager(db_path=str(db_path))
    usuario_repo2 = SqliteUsuarioRepository(db2)
    registro_repo2 = SqliteRegistroRepository(db2)
    conv_repo2 = JsonConversationStateRepository(estado_file=str(estado_file))
    service2 = RegistroService(usuario_repo=usuario_repo2, registro_repo=registro_repo2, conversation_repo=conv_repo2, db_legacy=None)

    r_linea = service2.procesar_respuesta(user_id, "T99")
    assert r_linea.siguiente_estado is not None  # avanza a cantidad

    service2.procesar_respuesta(user_id, "2")
    service2.procesar_respuesta(user_id, "ZZ")
    r_final = service2.procesar_respuesta(user_id, "OK")

    assert r_final.finalizado is True
    rows = _fetchall_dicts(db_path, "SELECT * FROM registros_defectos WHERE user_id = ?", (user_id,))
    assert len(rows) == 1
    assert rows[0]["linea"] == "T99"


def test_cantidad_invalida_no_inserta_y_estado_permanece(service, conversation_repo, db_path: Path, user_id: int):
    _insert_usuario(db_path, telegram_user_id=user_id, turno="A", departamento="QA")

    service.procesar_respuesta(user_id, "hola")
    _set_fotos(conversation_repo, user_id, [1])
    service.procesar_respuesta(user_id, "TERMINAR")
    service.procesar_respuesta(user_id, "M")
    service.procesar_respuesta(user_id, "L")

    r_bad = service.procesar_respuesta(user_id, "3.5")
    assert r_bad.error is True

    conv = conversation_repo.obtener(user_id)
    assert conv is not None
    assert conv["estado"] == "ESPERANDO_CANTIDAD"

    rows = _fetchall_dicts(db_path, "SELECT * FROM registros_defectos WHERE user_id = ?", (user_id,))
    assert rows == []


def test_validacion_directa_en_db_select_registros_contenido_exacto(service, conversation_repo, db_path: Path, user_id: int):
    _insert_usuario(db_path, telegram_user_id=user_id, turno="C", departamento="SQA")

    service.procesar_respuesta(user_id, "hola")
    _set_fotos(conversation_repo, user_id, [100, 101, 103])
    service.procesar_respuesta(user_id, "TERMINAR")
    service.procesar_respuesta(user_id, "MOD")
    service.procesar_respuesta(user_id, "LZ")
    service.procesar_respuesta(user_id, "9")
    service.procesar_respuesta(user_id, "AA")
    service.procesar_respuesta(user_id, "desc")

    rows = _fetchall_dicts(
        db_path,
        "SELECT fotos, modelo, linea, cantidad, responsable, descripcion, user_id, turno, departamento FROM registros_defectos",
    )
    assert rows == [
        {
            "fotos": "(100-101)(103)",
            "modelo": "MOD",
            "linea": "LZ",
            "cantidad": 9,
            "responsable": "AA",
            "descripcion": "DESC",
            "user_id": user_id,
            "turno": "C",
            "departamento": "SQA",
        }
    ]

