"""
bot/handlers/cancelar_handler.py

Responsabilidad única: cancelar un registro en curso y hacer rollback
del contador de fotos al valor previo a la sesión.

SRP : solo cambia si cambia la política de cancelación.
DIP : recibe repos, no DatabaseManager ni estado global.
ISP : recibe SOLO los tres repos que necesita.
"""
import os

from telegram import Update
from telegram.ext import ContextTypes

FOTOS_PATH = "fotos"


def create_cancelar(conversation_repo, usuario_repo, contador_repo):
    """
    Factory para /cancelar.

    Lógica:
      1. Elimina las fotos de la sesión actual del disco.
      2. Revierte el contador del grupo a min(fotos)-1
         (rollback seguro: no baja de 1 ni invade sesiones de otros usuarios).
      3. Finaliza la conversación en el repositorio de estado.

    Args:
        conversation_repo: .obtener(), .finalizar()
        usuario_repo:      .obtener(user_id)
        contador_repo:     .establecer(user_id, valor)
    """
    async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return

        try:
            user_id = update.effective_user.id
            usuario = usuario_repo.obtener(user_id)

            if not usuario:
                await update.message.reply_text("<b>Usuario no registrado.</b>", parse_mode="HTML")
                return

            conv = conversation_repo.obtener(user_id)
            
            # ── Cancelación de buffers temporales (Álbumes en progreso) ──
            media_groups = context.user_data.get("media_groups", {})
            for mg_id, grupo in list(media_groups.items()):
                if grupo.get("timer_task"):
                    grupo["timer_task"].cancel()
                
                # Borramos el mensaje de "Espera" si sigue ahí
                wait_msg_id = grupo.get("wait_msg_id")
                if wait_msg_id:
                    try:
                        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=wait_msg_id)
                    except Exception:
                        pass
            
            # Vaciamos el buffer completamente
            context.user_data["media_groups"] = {}
            
            if not conv:
                await update.message.reply_text("<b>No hay ningún registro en proceso.</b>", parse_mode="HTML")
                return

            fotos = conv.get("fotos") or []
            fotos_eliminadas = 0

            # ── Borrado por prefijo de número de secuencia ──────────────
            user_folder = os.path.join(FOTOS_PATH, str(user_id))
            if fotos and os.path.exists(user_folder):
                archivos = os.listdir(user_folder)
                for numero_foto in fotos:
                    prefijo = f"{int(numero_foto):03d}_"
                    for archivo in archivos:
                        if archivo.startswith(prefijo):
                            ruta = os.path.join(user_folder, archivo)
                            if os.path.exists(ruta):
                                os.remove(ruta)
                                fotos_eliminadas += 1

            # ── Rollback del contador ────────────────────────────────────
            # Usa min(fotos) para que la próxima foto reciba exactamente
            # el primer número que se usó en esta sesión cancelada.
            contador_revertido = None
            if fotos:
                valor_anterior = max(1, min(fotos))
                contador_repo.establecer(user_id, valor_anterior)
                contador_revertido = valor_anterior

            conversation_repo.finalizar(user_id)

            msg = "<b>Registro cancelado.</b>\n\n"
            msg += f"<b>Fotos eliminadas del intento:</b> {fotos_eliminadas}\n"
            if contador_revertido is not None:
                msg += f"<b>La siguiente foto será:</b> {contador_revertido:03d}"
            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            print(f"Error en /cancelar: {e}")
            await update.message.reply_text("<b>Error interno al cancelar la operación.</b>", parse_mode="HTML")

    return cancelar
