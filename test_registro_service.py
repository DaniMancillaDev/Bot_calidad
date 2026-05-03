import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional
from unittest.mock import Mock

import pytest

from shared.application.services.registro_service import RegistroService
from shared.domain.estado_conversacion import EstadoConversacion


@dataclass
class _Snapshot:
    conv: Optional[Dict[str, Any]]
    persist_count: int
    finalizar_count: int


class FakeConversationRepo:
    """
    Fake in-memory del repo de conversación.
    - persistir() no escribe a disco; solo incrementa contador
    - obtener() retorna el dict "vivo" (como un repo típico que devuelve referencia mutable)
    """

    def __init__(self, initial_store: Optional[Dict[int, Dict[str, Any]]] = None):
        # Importante: permitir compartir referencia a un dict vacío para simular reinicios.
        self._store: Dict[int, Dict[str, Any]] = initial_store if initial_store is not None else {}
        self.persist_count = 0
        self.finalizar_count = 0

    def tiene_conversacion(self, user_id: int) -> bool:
        return user_id in self._store

    def iniciar(self, user_id: int) -> None:
        self._store[user_id] = {
            "estado": EstadoConversacion.ESPERANDO_FOTOS.value,
            "fotos": [],
            "datos": {},
        }

    def obtener(self, user_id: int) -> Dict[str, Any]:
        return self._store[user_id]

    def persistir(self) -> None:
        self.persist_count += 1

    def finalizar(self, user_id: int) -> None:
        self.finalizar_count += 1
        self._store.pop(user_id, None)

    # Helpers para tests
    def set_conversation(
        self,
        user_id: int,
        *,
        estado: Any,
        fotos: Optional[list] = None,
        datos: Optional[dict] = None,
    ) -> None:
        self._store[user_id] = {
            "estado": estado,
            "fotos": fotos if fotos is not None else [],
            "datos": datos if datos is not None else {},
        }

    def snapshot(self, user_id: int) -> _Snapshot:
        conv = self._store.get(user_id)
        return _Snapshot(
            conv=copy.deepcopy(conv) if conv is not None else None,
            persist_count=self.persist_count,
            finalizar_count=self.finalizar_count,
        )


@pytest.fixture
def user_id() -> int:
    return 123456


@pytest.fixture
def conversation_repo() -> FakeConversationRepo:
    return FakeConversationRepo()


@pytest.fixture
def usuario_repo() -> Mock:
    repo = Mock()
    repo.obtener.return_value = {"turno": "A", "departamento": "QA"}
    return repo


@pytest.fixture
def registro_repo() -> Mock:
    repo = Mock()
    repo.guardar.return_value = True
    repo.formatear_rango_fotos.return_value = "1-2 "
    return repo


@pytest.fixture
def service(usuario_repo: Mock, registro_repo: Mock, conversation_repo: FakeConversationRepo) -> RegistroService:
    return RegistroService(
        usuario_repo=usuario_repo,
        registro_repo=registro_repo,
        conversation_repo=conversation_repo,
        db_legacy=None,
    )


def _drive_to_estado(
    service: RegistroService,
    conversation_repo: FakeConversationRepo,
    user_id: int,
    *,
    fotos: list,
):
    """
    Helper para dejar conversación lista en ESPERANDO_MODELO.
    (Inicia + TERMINAR con fotos)
    """
    # start
    r0 = service.procesar_respuesta(user_id, "hola")
    assert r0.siguiente_estado == EstadoConversacion.ESPERANDO_FOTOS
    # inject fotos then terminar
    conv = conversation_repo.obtener(user_id)
    conv["fotos"] = fotos
    r1 = service.procesar_respuesta(user_id, "TERMINAR")
    assert r1.siguiente_estado == EstadoConversacion.ESPERANDO_MODELO
    return r1


def test_inicia_conversacion_si_no_existe(service: RegistroService, conversation_repo: FakeConversationRepo, user_id: int):
    result = service.procesar_respuesta(user_id, "cualquier cosa")

    assert result.siguiente_estado == EstadoConversacion.ESPERANDO_FOTOS
    assert result.finalizado is False
    assert result.error is False
    assert conversation_repo.tiene_conversacion(user_id) is True


def test_terminar_sin_fotos_rechaza_y_no_persiste(service: RegistroService, conversation_repo: FakeConversationRepo, user_id: int):
    service.procesar_respuesta(user_id, "hi")  # inicia
    before = conversation_repo.snapshot(user_id)

    result = service.procesar_respuesta(user_id, "TERMINAR")

    assert result.error is True
    assert "no has enviado ninguna foto".lower() in result.mensaje.lower()
    assert result.finalizado is False
    assert result.siguiente_estado is None
    # sin persistencia ni finalización
    after = conversation_repo.snapshot(user_id)
    assert after.persist_count == before.persist_count
    assert after.finalizar_count == before.finalizar_count
    assert conversation_repo.tiene_conversacion(user_id) is True


def test_flujo_completo_exitoso_golden_path(service: RegistroService, conversation_repo: FakeConversationRepo, registro_repo: Mock, user_id: int):
    _drive_to_estado(service, conversation_repo, user_id, fotos=[1, 2])

    r_modelo = service.procesar_respuesta(user_id, 'onn 32" 100012589 auo')
    assert r_modelo.siguiente_estado == EstadoConversacion.ESPERANDO_LINEA
    assert r_modelo.error is False
    assert conversation_repo.obtener(user_id)["datos"]["modelo"] == 'ONN 32" 100012589 AUO'

    r_linea = service.procesar_respuesta(user_id, "T03")
    assert r_linea.siguiente_estado == EstadoConversacion.ESPERANDO_CANTIDAD
    assert conversation_repo.obtener(user_id)["datos"]["linea"] == "T03"

    r_cantidad = service.procesar_respuesta(user_id, "5")
    assert r_cantidad.siguiente_estado == EstadoConversacion.ESPERANDO_RESPONSABLE
    assert conversation_repo.obtener(user_id)["datos"]["cantidad"] == 5

    r_resp = service.procesar_respuesta(user_id, "xm")
    assert r_resp.siguiente_estado == EstadoConversacion.ESPERANDO_DESCRIPCION
    assert conversation_repo.obtener(user_id)["datos"]["responsable"] == "XM"

    r_desc = service.procesar_respuesta(user_id, "pantalla con manchas")
    assert r_desc.finalizado is True
    assert r_desc.error is False
    assert conversation_repo.tiene_conversacion(user_id) is False

    registro_repo.guardar.assert_called_once()
    args, _kwargs = registro_repo.guardar.call_args
    assert args[0] == [1, 2]  # fotos
    assert args[1] == 'ONN 32" 100012589 AUO'  # modelo
    assert args[2] == "T03"  # linea
    assert args[3] == 5  # cantidad
    assert args[4] == "XM"  # responsable
    assert args[5] == "PANTALLA CON MANCHAS"  # descripcion (upper)
    assert args[6] == user_id


@pytest.mark.parametrize("cantidad_invalida", ["3.5", "abc", "12,0", "-1", " "])
def test_cantidad_invalida_marca_error_y_no_avanza(
    service: RegistroService,
    conversation_repo: FakeConversationRepo,
    registro_repo: Mock,
    user_id: int,
    cantidad_invalida: str,
):
    _drive_to_estado(service, conversation_repo, user_id, fotos=[10])
    service.procesar_respuesta(user_id, "modelo x")
    service.procesar_respuesta(user_id, "L1")

    before = conversation_repo.snapshot(user_id)
    result = service.procesar_respuesta(user_id, cantidad_invalida)

    assert result.error is True
    assert result.finalizado is False
    assert result.siguiente_estado is None  # se mantiene en cantidad
    # El service persiste por paso aunque haya error (mientras no finalice).
    after = conversation_repo.snapshot(user_id)
    assert after.persist_count == before.persist_count + 1
    assert registro_repo.guardar.call_count == 0
    assert conversation_repo.obtener(user_id)["estado"] == EstadoConversacion.ESPERANDO_CANTIDAD.value


def test_recuperacion_despues_de_error_en_cantidad(service: RegistroService, conversation_repo: FakeConversationRepo, user_id: int):
    _drive_to_estado(service, conversation_repo, user_id, fotos=[7])
    service.procesar_respuesta(user_id, "modelo")
    service.procesar_respuesta(user_id, "L2")

    r_bad = service.procesar_respuesta(user_id, "2.5")
    assert r_bad.error is True
    assert conversation_repo.obtener(user_id)["estado"] == EstadoConversacion.ESPERANDO_CANTIDAD.value

    r_ok = service.procesar_respuesta(user_id, "2")
    assert r_ok.error is False
    assert r_ok.siguiente_estado == EstadoConversacion.ESPERANDO_RESPONSABLE
    assert conversation_repo.obtener(user_id)["datos"]["cantidad"] == 2


def test_persistencia_de_estado_simula_reinicio(user_id: int, registro_repo: Mock, usuario_repo: Mock):
    """
    Simula "reinicio" creando un nuevo service con el mismo store de conversación.
    """
    store: Dict[int, Dict[str, Any]] = {}
    conversation_repo_1 = FakeConversationRepo(store)
    service_1 = RegistroService(usuario_repo=usuario_repo, registro_repo=registro_repo, conversation_repo=conversation_repo_1)

    _drive_to_estado(service_1, conversation_repo_1, user_id, fotos=[1])
    service_1.procesar_respuesta(user_id, "ModeloPersistente")
    assert store[user_id]["estado"] == EstadoConversacion.ESPERANDO_LINEA.value

    # "reinicio"
    conversation_repo_2 = FakeConversationRepo(store)
    service_2 = RegistroService(usuario_repo=usuario_repo, registro_repo=registro_repo, conversation_repo=conversation_repo_2)
    r_linea = service_2.procesar_respuesta(user_id, "T99")
    assert r_linea.siguiente_estado == EstadoConversacion.ESPERANDO_CANTIDAD
    assert store[user_id]["datos"]["linea"] == "T99"


def test_estado_corrupto_fallback_seguro_sin_side_effects(
    service: RegistroService,
    conversation_repo: FakeConversationRepo,
    registro_repo: Mock,
    user_id: int,
):
    conversation_repo.set_conversation(
        user_id,
        estado="ESTADO_QUE_NO_EXISTE",
        fotos=[1],
        datos={"modelo": "X"},
    )
    before = conversation_repo.snapshot(user_id)

    result = service.procesar_respuesta(user_id, "cualquier cosa")

    assert result.mensaje == ""
    assert result.siguiente_estado is None
    assert result.finalizado is False
    assert result.error is False
    after = conversation_repo.snapshot(user_id)
    assert after.persist_count == before.persist_count
    assert after.finalizar_count == before.finalizar_count
    assert registro_repo.guardar.call_count == 0


def test_compatibilidad_con_estado_legacy_se_normaliza_y_avanza(
    service: RegistroService,
    conversation_repo: FakeConversationRepo,
    user_id: int,
):
    conversation_repo.set_conversation(
        user_id,
        estado="esperando_cantidad",  # legacy lowercase
        fotos=[1],
        datos={"modelo": "M1", "linea": "L1"},
    )
    result = service.procesar_respuesta(user_id, "4")
    assert result.siguiente_estado == EstadoConversacion.ESPERANDO_RESPONSABLE
    assert conversation_repo.obtener(user_id)["estado"] == EstadoConversacion.ESPERANDO_RESPONSABLE.value


def test_finalizado_true_finaliza_conversacion_en_exito(service: RegistroService, conversation_repo: FakeConversationRepo, user_id: int):
    _drive_to_estado(service, conversation_repo, user_id, fotos=[9])
    service.procesar_respuesta(user_id, "M")
    service.procesar_respuesta(user_id, "L")
    service.procesar_respuesta(user_id, "1")
    service.procesar_respuesta(user_id, "R")

    assert conversation_repo.tiene_conversacion(user_id) is True
    result = service.procesar_respuesta(user_id, "DESC")
    assert result.finalizado is True
    assert conversation_repo.tiene_conversacion(user_id) is False


def test_no_guarda_registro_ni_finaliza_si_usuario_no_registrado(
    conversation_repo: FakeConversationRepo,
    registro_repo: Mock,
    user_id: int,
):
    usuario_repo = Mock()
    usuario_repo.obtener.return_value = None
    service = RegistroService(usuario_repo=usuario_repo, registro_repo=registro_repo, conversation_repo=conversation_repo)

    _drive_to_estado(service, conversation_repo, user_id, fotos=[1])
    service.procesar_respuesta(user_id, "M")
    service.procesar_respuesta(user_id, "L")
    service.procesar_respuesta(user_id, "1")
    service.procesar_respuesta(user_id, "R")

    before = conversation_repo.snapshot(user_id)
    result = service.procesar_respuesta(user_id, "DESC")

    assert result.error is True
    assert "usuario no registrado".lower() in result.mensaje.lower()
    assert result.finalizado is False
    assert registro_repo.guardar.call_count == 0
    # El handler retorna error pero el loop persiste por paso (no finaliza).
    after = conversation_repo.snapshot(user_id)
    assert after.persist_count == before.persist_count + 1
    assert after.finalizar_count == before.finalizar_count

