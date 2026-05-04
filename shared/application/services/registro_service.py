from dataclasses import dataclass
from typing import Optional

from shared.infrastructure.database.sqlite_usuario_repository import SqliteUsuarioRepository
from shared.infrastructure.database.sqlite_registro_repository import SqliteRegistroRepository
from shared.infrastructure.storage.json_conversation_state import JsonConversationStateRepository
from shared.application.validators.registro_validators import (
    validar_cantidad,
    validar_linea,
    validar_modelo,
)
from shared.domain.estado_conversacion import EstadoConversacion, parse_estado_conversacion


@dataclass
class ProcesarRespuestaResult:
    mensaje: str = ""
    siguiente_estado: Optional[EstadoConversacion] = None
    finalizado: bool = False
    error: bool = False


class RegistroService:
    """
    Servicio de aplicación: orquesta el flujo de registro de defectos.

    Contiene TODA la lógica de negocio extraída de procesar_respuesta.
    No depende de Telegram (Update, Context) — solo de repositorios.
    """

    def __init__(
        self,
        usuario_repo: SqliteUsuarioRepository,
        registro_repo: SqliteRegistroRepository,
        conversation_repo: JsonConversationStateRepository,
        db_legacy=None,
    ):
        self._usuario_repo = usuario_repo
        self._registro_repo = registro_repo
        self._conversation_repo = conversation_repo
        self._db_legacy = db_legacy  # Para actualizar_ultimo_numero_confirmado (legacy)

    def procesar_respuesta(self, user_id: int, texto: str) -> ProcesarRespuestaResult:
        """
        Procesa la respuesta del usuario según el estado actual de la conversación.

        Args:
            user_id: ID de Telegram del usuario
            texto: Mensaje del usuario (ya en uppercase)

        Returns:
            ProcesarRespuestaResult con mensaje + siguiente estado.
        """
        mensaje = texto.strip().upper()

        # Si no tiene conversación, iniciar una
        if not self._conversation_repo.tiene_conversacion(user_id):
            self._conversation_repo.iniciar(user_id)
            return ProcesarRespuestaResult(siguiente_estado=EstadoConversacion.ESPERANDO_FOTOS)

        conv = self._conversation_repo.obtener(user_id)
        estado_actual = parse_estado_conversacion(conv.get('estado'))
        datos = conv['datos']

        # Procesar TERMINAR en estado ESPERANDO_FOTOS
        if mensaje == 'TERMINAR' and estado_actual == EstadoConversacion.ESPERANDO_FOTOS:
            if not conv['fotos']:
                return ProcesarRespuestaResult(
                    mensaje=" No has enviado ninguna foto. Por favor, envía al menos una foto.",
                    error=True,
                )
            result = ProcesarRespuestaResult(
                mensaje="<b>¡Excelente! Fotos recibidas.</b>\n\n"
                        "Para completar el reporte, responde estas 5 preguntas:\n\n"
                        "<b>[1/5] Modelo</b>\n"
                        "¿De qué modelo es el producto?\n"
                        "<code>Ej: ONN 32\" 100012589 AUO</code>",
                siguiente_estado=EstadoConversacion.ESPERANDO_MODELO,
            )
            conv['estado'] = result.siguiente_estado.value
            self._conversation_repo.persistir()
            return result

        handlers = {
            EstadoConversacion.ESPERANDO_MODELO: self._handle_modelo,
            EstadoConversacion.ESPERANDO_LINEA: self._handle_linea,
            EstadoConversacion.ESPERANDO_CANTIDAD: self._handle_cantidad,
            EstadoConversacion.ESPERANDO_RESPONSABLE: self._handle_responsable,
            EstadoConversacion.ESPERANDO_DESCRIPCION: self._handle_descripcion,
        }

        handler = handlers.get(estado_actual) if estado_actual else None
        if handler:
            result = handler(user_id, mensaje, conv, datos)

            if result.finalizado:
                self._conversation_repo.finalizar(user_id)
                return result

            if result.siguiente_estado is not None:
                conv['estado'] = result.siguiente_estado.value

            # Mantener persistencia por paso (como antes)
            self._conversation_repo.persistir()
            return result

        # Estado no reconocido (no debería ocurrir)
        return ProcesarRespuestaResult()

    def _handle_modelo(self, user_id: int, mensaje: str, conv: dict, datos: dict) -> ProcesarRespuestaResult:
        if not validar_modelo(mensaje):
            return ProcesarRespuestaResult()
        datos['modelo'] = mensaje
        return ProcesarRespuestaResult(
            mensaje="<b>[2/5] Línea de Producción</b>\n"
                    "Anotado. ¿En qué línea ocurrió?\n"
                    "<code>Ej: T03</code>",
            siguiente_estado=EstadoConversacion.ESPERANDO_LINEA,
        )

    def _handle_linea(self, user_id: int, mensaje: str, conv: dict, datos: dict) -> ProcesarRespuestaResult:
        if not validar_linea(mensaje):
            return ProcesarRespuestaResult()
        datos['linea'] = mensaje
        return ProcesarRespuestaResult(
            mensaje="<b>[3/5] Cantidad</b>\n"
                    "Perfecto. ¿Cuántos defectos encontraste?\n"
                    "<i>Solo ingresa el número.</i>",
            siguiente_estado=EstadoConversacion.ESPERANDO_CANTIDAD,
        )

    def _handle_cantidad(self, user_id: int, mensaje: str, conv: dict, datos: dict) -> ProcesarRespuestaResult:
        if not validar_cantidad(mensaje):
            return ProcesarRespuestaResult(
                mensaje="Por favor, ingresa solo números para la cantidad.",
                error=True,
            )
        datos['cantidad'] = int(mensaje)
        return ProcesarRespuestaResult(
            mensaje="<b>[4/5] Responsable</b>\n"
                    "Bien. ¿Quién es el responsable?\n"
                    "<code>Ej: XM</code>",
            siguiente_estado=EstadoConversacion.ESPERANDO_RESPONSABLE,
        )

    def _handle_responsable(self, user_id: int, mensaje: str, conv: dict, datos: dict) -> ProcesarRespuestaResult:
        datos['responsable'] = mensaje
        return ProcesarRespuestaResult(
            mensaje="<b>[5/5] Descripción</b>\n"
                    "Casi terminamos. Por último, descríbeme brevemente el defecto:",
            siguiente_estado=EstadoConversacion.ESPERANDO_DESCRIPCION,
        )

    def _handle_descripcion(self, user_id: int, mensaje: str, conv: dict, datos: dict) -> ProcesarRespuestaResult:
        datos['descripcion'] = mensaje

        # Verificar que el usuario esté registrado
        usuario = self._usuario_repo.obtener(user_id)
        if not usuario:
            return ProcesarRespuestaResult(
                mensaje="Usuario no registrado. No se puede guardar el registro.",
                error=True,
            )

        # Guardar en base de datos
        exito = self._registro_repo.guardar(
            conv['fotos'],
            datos['modelo'],
            datos['linea'],
            datos['cantidad'],
            datos['responsable'],
            datos['descripcion'],
            user_id,
            usuario['turno'],
            usuario['departamento']
        )

        if exito:
            fotos_str = self._registro_repo.formatear_rango_fotos(conv['fotos'])
            linea = (
                f"{fotos_str} Modelo: {datos['modelo']}; "
                f"Línea: {datos['linea']}; "
                f"Cantidad: {datos['cantidad']}; "
                f"Responsable: {datos['responsable']}; "
                f"Descripción: {datos['descripcion']}"
            )

            from html import escape
            resumen = (
                f"<b>Modelo:</b> {escape(datos['modelo'])} | <b>Línea:</b> {escape(datos['linea'])}\n"
                f"<b>Cantidad:</b> {datos['cantidad']} | <b>Resp:</b> {escape(datos['responsable'])}\n"
                f"<b>Detalles:</b> {escape(datos['descripcion'])}"
            )
            return ProcesarRespuestaResult(
                mensaje=(
                    "<b>¡Reporte guardado con éxito!</b>\n\n"
                    f"{resumen}\n\n"
                    "<i>Para reportar otro defecto, simplemente envíame fotos nuevas.</i>"
                ),
                finalizado=True,
            )

        return ProcesarRespuestaResult(
            mensaje="Error al guardar el registro.\nPor favor, intenta nuevamente.",
            finalizado=True,
            error=True,
        )
