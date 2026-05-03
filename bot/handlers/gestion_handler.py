"""
bot/handlers/gestion_handler.py

Responsabilidad única: operaciones destructivas de limpieza.
  - /limpiar       → elimina los registros de BD del usuario y reinicia contador
  - /limpiar_fotos → elimina las imágenes en disco del usuario y reinicia contador

SRP : solo cambia si cambia la política de limpieza.
DIP : recibe repos, no DatabaseManager ni acceso directo al filesystem.
ISP : cada factory recibe SOLO las dependencias que necesita.
"""
import os

from telegram import Update
from telegram.ext import ContextTypes

FOTOS_PATH = "fotos"


def create_limpiar(conversation_repo, usuario_repo, registro_repo, contador_repo):
    """
    Factory para /limpiar.

    Elimina SOLO los registros de la BD del usuario actual y reinicia el
    contador de su grupo turno/departamento.

    Args:
        conversation_repo: .finalizar(user_id)
        usuario_repo:      .obtener(user_id)
        registro_repo:     .limpiar_por_usuario(user_id) → bool
        contador_repo:     .reiniciar(user_id)
    """
    async def limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None
            usuario = usuario_repo.obtener(user_id)

            if not usuario:
                await update.message.reply_text("⚠️ <b>Usuario no registrado.</b>", parse_mode="HTML")
                return

            exito = registro_repo.limpiar_por_usuario(user_id)

            if exito:
                contador_repo.reiniciar(user_id)
                conversation_repo.finalizar(user_id)
                await update.message.reply_text(
                    "<b>Registros limpiados:</b>\n\n"
                    f"• <b>Usuario:</b> <code>{user_id}</code>\n"
                    f"• <b>Turno:</b> {usuario['turno']}\n"
                    f"• <b>Depto:</b> {usuario['departamento']}\n\n"
                    "<i>Solo se eliminaron TUS registros.</i>",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("<b>Error al limpiar registros.</b>", parse_mode="HTML")

        except Exception as e:
            print(f"Error en /limpiar: {e}")
            await update.message.reply_text("<b>Error interno al limpiar registros.</b>", parse_mode="HTML")

    return limpiar


def create_limpiar_fotos(conversation_repo, usuario_repo, contador_repo):
    """
    Factory para /limpiar_fotos.

    Elimina SOLO las imágenes en disco del usuario y reinicia su contador.

    Args:
        conversation_repo: .finalizar(user_id)
        usuario_repo:      .obtener(user_id)
        contador_repo:     .reiniciar(user_id)
    """
    async def limpiar_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None
            usuario = usuario_repo.obtener(user_id)

            if not usuario:
                await update.message.reply_text("⚠️ <b>Usuario no registrado.</b>", parse_mode="HTML")
                return

            user_folder = os.path.join(FOTOS_PATH, str(user_id))
            fotos_eliminadas = 0

            if os.path.exists(user_folder):
                for nombre in os.listdir(user_folder):
                    ruta = os.path.join(user_folder, nombre)
                    if os.path.isfile(ruta):
                        os.remove(ruta)
                        fotos_eliminadas += 1

            contador_repo.reiniciar(user_id)
            conversation_repo.finalizar(user_id)

            await update.message.reply_text(
                "<b>Fotos eliminadas:</b>\n\n"
                f"• <b>Usuario:</b> <code>{user_id}</code>\n"
                f"• <b>Fotos eliminadas:</b> {fotos_eliminadas}\n"
                "• <b>Contador reiniciado a:</b> 001\n\n"
                "<i>Solo se eliminaron TUS fotos.</i>",
                parse_mode="HTML"
            )

        except Exception as e:
            print(f"Error en /limpiar_fotos: {e}")
            await update.message.reply_text("<b>Error interno al eliminar fotos.</b>", parse_mode="HTML")

    return limpiar_fotos
