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
    CallbackQueryHandler,
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
    create_terminar_callback,
    create_omitir_callback,
    create_opcion_callback,
)
from bot.handlers.cancelar_handler import create_cancelar
from bot.handlers.consulta_handler import (
    create_estado,
    create_info,
)


async def _post_init(application):
    """Configura los comandos del menú de Telegram al iniciar."""
    comandos = [
        BotCommand("start", "Iniciar o reiniciar sesión"),
        BotCommand("estado", "Ver estado actual"),
        BotCommand("cancelar", "Cancelar registro en curso"),
        BotCommand("info", "Acerca del sistema"),
        BotCommand("mi_id", "Ver tu ID de Telegram"),
    ]
    await application.bot.set_my_commands(comandos)


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
        TypeHandler(Update, create_verificar_acceso(container["api_client"])),
        group=-1,
    )

    # ── Comandos de autenticación ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("mi_id", comando_mi_id))

    # ── Flujo principal de registro ────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", create_start(container["api_client"])))
    
    app.add_handler(MessageHandler(
        filters.PHOTO,
        create_guardar_foto(container["api_client"])
    ))

    app.add_handler(CallbackQueryHandler(
        create_terminar_callback(container["api_client"]),
        pattern="^terminar_fotos$",
    ))
    
    app.add_handler(CallbackQueryHandler(
        create_omitir_callback(container["api_client"]),
        pattern="^omitir_num_parte$",
    ))

    app.add_handler(CallbackQueryHandler(
        create_opcion_callback(container["api_client"]),
        pattern="^opcion:.*$",
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        create_procesar_respuesta(container["api_client"])
    ))

    app.add_handler(CommandHandler("estado", create_estado(container["api_client"])))
    app.add_handler(CommandHandler("info", create_info()))
    
    # Comandos de cancelación/limpieza purgada
    app.add_handler(CommandHandler("cancelar", create_cancelar(container["api_client"])))
    app.add_handler(CommandHandler("limpiar", create_cancelar(container["api_client"]))) # Alias de cancelar

    return app
