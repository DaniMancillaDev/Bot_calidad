"""
bot/app.py

Composition Root parcial: construye la aplicación de Telegram
e inyecta las dependencias del contenedor en cada handler.

Responsabilidad única: WIRING — conectar handlers con dependencias.
No contiene lógica de negocio. No sabe de Telegram internals.

OCP: agregar un nuevo comando = agregar import + add_handler.
     No se modifica nada existente.
"""
from telegram import Update, BotCommand
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from bot.handlers.auth_handler import comando_mi_id, create_verificar_acceso
from bot.handlers.registro_handler import (
    create_start,
    create_guardar_foto,
    create_procesar_respuesta,
)
from bot.handlers.cancelar_handler import create_cancelar
from bot.handlers.gestion_handler import create_limpiar, create_limpiar_fotos
from bot.handlers.consulta_handler import (
    create_reporte,
    create_estado,
    create_info_fotos,
    create_descargar,
    create_info,
)


async def _post_init(application):
    """Configura los comandos del menú de Telegram al iniciar."""
    comandos = [
        BotCommand("start", "Iniciar o reiniciar sesión"),
        BotCommand("estado", "Ver estado actual"),
        BotCommand("reporte", "Descargar reporte en texto"),
        BotCommand("info_fotos", "Ver estadísticas de tus fotos"),
        BotCommand("descargar", "Descargar fotos en ZIP"),
        BotCommand("limpiar", "Borrar tus registros de hoy"),
        BotCommand("cancelar", "Cancelar registro en curso"),
        BotCommand("info", "Acerca del sistema"),
        BotCommand("mi_id", "Ver tu ID de Telegram"),
    ]
    await application.bot.set_my_commands(comandos)


async def _test_bot(update, context):
    """Comando de diagnóstico rápido."""
    if not update.message:
        return
    await update.message.reply_text(
        "**BOT FUNCIONANDO CORRECTAMENTE**\n\n"
        "Arquitectura Clean Architecture + SOLID activa.\n"
        "Usa /start para comenzar.",
        parse_mode="Markdown",
    )


def build_application(token: str, container: dict):
    """
    Construye y devuelve la Application de Telegram completamente configurada.

    Args:
        token:     Token del bot de Telegram.
        container: Dict con repos e interfaces (output de build_container()).

    Returns:
        Application lista para llamar .run_polling().
    """
    # Configurar timeouts para evitar errores de conexión con fotos pesadas
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    
    app = ApplicationBuilder() \
        .token(token) \
        .request(request) \
        .concurrent_updates(True) \
        .post_init(_post_init) \
        .build()

    # ── Middleware de seguridad (grupo -1 = se ejecuta ANTES que cualquier handler) ──
    app.add_handler(
        TypeHandler(Update, create_verificar_acceso(container["usuario_repo"])),
        group=-1,
    )

    # ── Comandos de autenticación ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("mi_id", comando_mi_id))

    # ── Flujo principal de registro ────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", create_start(container["conversation_repo"])))

    # ── Consultas (solo lectura) ───────────────────────────────────────────────────
    app.add_handler(CommandHandler(
        "reporte",
        create_reporte(container["usuario_repo"], container["registro_repo"]),
    ))
    app.add_handler(CommandHandler(
        "estado",
        create_estado(container["usuario_repo"], container["contador_repo"], container["registro_repo"]),
    ))
    app.add_handler(CommandHandler(
        "info_fotos",
        create_info_fotos(container["usuario_repo"]),
    ))
    app.add_handler(CommandHandler(
        "descargar",
        create_descargar(container["usuario_repo"]),
    ))
    app.add_handler(CommandHandler(
        "info",
        create_info(),
    ))

    # ── Gestión (operaciones destructivas) ────────────────────────────────────────
    app.add_handler(CommandHandler(
        "limpiar",
        create_limpiar(
            container["conversation_repo"],
            container["usuario_repo"],
            container["registro_repo"],
            container["contador_repo"],
        ),
    ))
    app.add_handler(CommandHandler(
        "limpiar_fotos",
        create_limpiar_fotos(
            container["conversation_repo"],
            container["usuario_repo"],
            container["contador_repo"],
        ),
    ))
    app.add_handler(CommandHandler(
        "cancelar",
        create_cancelar(
            container["conversation_repo"],
            container["usuario_repo"],
            container["contador_repo"],
        ),
    ))

    # ── Diagnóstico ───────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("test", _test_bot))

    # ── Mensajes (fotos y texto libre) ────────────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.PHOTO,
        create_guardar_foto(
            container["usuario_repo"],
            container["contador_repo"],
            container["conversation_repo"],
            container["foto_storage"],
        ),
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        create_procesar_respuesta(container["registro_service"]),
    ))

    return app
