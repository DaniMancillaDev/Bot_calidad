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
)
from bot.handlers.cancelar_handler import create_cancelar
from bot.handlers.gestion_handler import create_limpiar, create_limpiar_fotos
from bot.handlers.consulta_handler import (
    create_reporte,
    create_estado,
    create_info_fotos,
    create_descargar,
    create_descargar_turno,
    create_turno_callback,
    create_operador_callback,
    create_reporte_turno,
    create_rpt_turno_callback,
    create_rpt_operador_callback,
    create_info,
)


async def _post_init(application):
    """Configura los comandos del menú de Telegram al iniciar."""
    comandos = [
        BotCommand("start", "Iniciar o reiniciar sesión"),
        BotCommand("estado", "Ver estado actual"),
        BotCommand("reporte", "Descargar reporte en texto"),
        BotCommand("reporte_turno", "Reporte de otro turno (Admin)"),
        BotCommand("info_fotos", "Ver estadisticas de tus fotos"),
        BotCommand("descargar", "Descargar fotos en ZIP"),
        BotCommand("descargar_todo", "Descargar turno (Admin)"),
        BotCommand("limpiar", "Borrar tus registros de hoy"),
        BotCommand("limpiar_fotos", "Borrar tus fotos del turno"),
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

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        create_procesar_respuesta(container["api_client"])
    ))

    app.add_handler(CommandHandler("reporte", create_reporte(container["api_client"])))
    
    app.add_handler(CommandHandler("estado", create_estado(container["api_client"])))
    app.add_handler(CommandHandler("info_fotos", create_info_fotos(container["api_client"])))
    app.add_handler(CommandHandler("descargar", create_descargar(container["api_client"])))
    app.add_handler(CommandHandler("descargar_todo", create_descargar_turno(container["api_client"])))
    app.add_handler(CallbackQueryHandler(create_turno_callback(container["api_client"]), pattern="^turno:"))
    app.add_handler(CallbackQueryHandler(create_operador_callback(container["api_client"]), pattern="^op:"))
    app.add_handler(CommandHandler("reporte_turno", create_reporte_turno(container["api_client"])))
    app.add_handler(CallbackQueryHandler(create_rpt_turno_callback(container["api_client"]), pattern="^rpt_turno:"))
    app.add_handler(CallbackQueryHandler(create_rpt_operador_callback(container["api_client"]), pattern="^rpt_op:"))
    app.add_handler(CommandHandler("info", create_info()))

    # ── Gestión (operaciones destructivas) ────────────────────────────────────────
    app.add_handler(CommandHandler("limpiar", create_limpiar(container["api_client"])))
    app.add_handler(CommandHandler("limpiar_fotos", create_limpiar_fotos(container["api_client"])))
    app.add_handler(CommandHandler("cancelar", create_cancelar(container["api_client"])))

    # ── Diagnóstico ───────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("test", _test_bot))

    return app
