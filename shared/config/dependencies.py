from database import DatabaseManager
from shared.infrastructure.database.sqlite_usuario_repository import SqliteUsuarioRepository
from shared.infrastructure.database.sqlite_registro_repository import SqliteRegistroRepository
from shared.infrastructure.database.sqlite_contador_repository import SqliteContadorRepository
from shared.infrastructure.storage.json_conversation_state import JsonConversationStateRepository
from shared.infrastructure.storage.local_foto_storage import LocalFotoStorage
from shared.application.services.registro_service import RegistroService


def build_container(db: DatabaseManager = None):
    """
    Construye el contenedor de dependencias (inyección manual).
    Recibe la instancia existente de DatabaseManager para no crear una nueva.
    """
    if db is None:
        from database import db as _db
        db = _db

    usuario_repo = SqliteUsuarioRepository(db)
    registro_repo = SqliteRegistroRepository(db)
    contador_repo = SqliteContadorRepository(db)
    conversation_repo = JsonConversationStateRepository()
    foto_storage = LocalFotoStorage()

    registro_service = RegistroService(
        usuario_repo=usuario_repo,
        registro_repo=registro_repo,
        conversation_repo=conversation_repo,
        db_legacy=db,
    )

    return {
        'usuario_repo': usuario_repo,
        'registro_repo': registro_repo,
        'contador_repo': contador_repo,
        'conversation_repo': conversation_repo,
        'foto_storage': foto_storage,
        'registro_service': registro_service,
    }
