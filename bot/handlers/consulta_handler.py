"""
bot/handlers/consulta_handler.py

Responsabilidad única: comandos de solo lectura / consulta.
  - /reporte     → genera y envía reporte .txt
  - /estado      → muestra contador y estadísticas del grupo
  - /info_fotos  → estadísticas de imágenes en disco
  - /descargar   → empaqueta y envía fotos en ZIP

SRP : solo cambia si cambia la forma de presentar información al usuario.
DIP : recibe repos e interfaces, sin acceso a `db` ni filesystem directo.
ISP : cada factory recibe SOLO las dependencias que necesita.
"""
import os
import re
import tempfile
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot.helpers.zip_helper import crear_y_enviar_zip

FOTOS_PATH = "fotos"
MAX_IMAGENES_POR_ZIP = 30


# ─────────────────────────────────────────
# /reporte
# ─────────────────────────────────────────
def create_reporte(usuario_repo, registro_repo):
    """
    Factory para /reporte.

    Modos:
      /reporte        → registros propios del usuario
      /reporte grupo  → registros del grupo turno/depto (requiere rol admin/supervisor)

    Args:
        usuario_repo:  .obtener(user_id)
        registro_repo: .obtener_todos(user_id), .obtener_por_turno_depto(turno, departamento, user_id)
    """
    async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None
            usuario = usuario_repo.obtener(user_id)
            if not usuario:
                await update.message.reply_text("\u26a0\ufe0f Usuario no registrado.")
                return

            partes = (update.message.text or "").strip().lower().split()
            modo = partes[1] if len(partes) > 1 else "usuario"

            if modo == "grupo":
                if usuario.get("rol") not in ("admin", "supervisor"):
                    await update.message.reply_text("<b>No tienes permiso para ver el grupo.</b>", parse_mode="HTML")
                    return
                registros = registro_repo.obtener_por_turno_depto(
                    turno=usuario["turno"],
                    departamento=usuario["departamento"],
                    user_id=user_id,
                )
            else:
                registros = registro_repo.obtener_todos(user_id=user_id)

            if not registros:
                msg = (
                    "<b>No hay registros para tu turno/departamento.</b>"
                    if modo == "grupo"
                    else "<b>No tienes registros aún.</b>"
                )
                await update.message.reply_text(msg, parse_mode="HTML")
                return

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(
                    f"REPORTE DE DEFECTOS - TURNO {usuario['turno']} - {usuario['departamento']}\n"
                )
                tmp.write(
                    f"Usuario: {user_id} | Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                tmp.write("=" * 60 + "\n\n")
                for reg in registros:
                    for linea in reg["lineas_formateadas"]:
                        tmp.write(linea + "\n")
                nombre_archivo = tmp.name

            with open(nombre_archivo, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=(
                        f"reporte_{usuario['turno']}_{usuario['departamento']}"
                        f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    ),
                    caption=(
                        f"\U0001f4ca Reporte {usuario['turno']}/{usuario['departamento']}"
                        f" - {len(registros)} registros"
                    ),
                )
            os.remove(nombre_archivo)

        except Exception as e:
            print(f"Error en /reporte: {e}")
            await update.message.reply_text("<b>Error interno al generar el reporte.</b>", parse_mode="HTML")

    return reporte


# ─────────────────────────────────────────
# /estado
# ─────────────────────────────────────────
def create_estado(usuario_repo, contador_repo, registro_repo):
    """
    Factory para /estado.

    Args:
        usuario_repo:  .obtener(user_id)
        contador_repo: .obtener_actual(user_id)
        registro_repo: .obtener_estadisticas(turno, departamento)
    """
    async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None
            usuario = usuario_repo.obtener(user_id)
            if not usuario:
                await update.message.reply_text("<b>Usuario no registrado.</b>", parse_mode="HTML")
                return

            contador = contador_repo.obtener_actual(user_id)
            stats = registro_repo.obtener_estadisticas(
                turno=usuario["turno"],
                departamento=usuario["departamento"],
            )

            msg = f"<b>ESTADO DEL GRUPO</b>\n<i>(Turno {usuario['turno']} - {usuario['departamento']})</i>\n\n"
            msg += f"<b>Usuario:</b> <code>{user_id}</code>\n"
            msg += f"<b>Siguiente foto:</b> {contador:03d}\n"
            msg += f"<b>Registros del grupo:</b> {stats.get('total_registros', 0)}\n"
            if stats.get("ultimo_registro"):
                msg += f"<b>Último registro:</b> {stats['ultimo_registro']}"

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            print(f"Error en /estado: {e}")
            await update.message.reply_text("<b>Error interno al obtener el estado.</b>", parse_mode="HTML")

    return estado


# ─────────────────────────────────────────
# /info_fotos
# ─────────────────────────────────────────
def create_info_fotos(usuario_repo):
    """
    Factory para /info_fotos.

    Args:
        usuario_repo: .obtener(user_id)
    """
    def _extraer_numero(nombre: str) -> int:
        m = re.match(r"^(\d+)", nombre)
        return int(m.group(1)) if m else -1

    async def info_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        user_id = update.effective_user.id
        usuario = usuario_repo.obtener(user_id)
        if not usuario:
            await update.message.reply_text("<b>Usuario no registrado.</b>", parse_mode="HTML")
            return
        try:
            user_folder = os.path.join(FOTOS_PATH, str(user_id))
            if not os.path.exists(user_folder):
                await update.message.reply_text("<i>No tienes imágenes guardadas.</i>", parse_mode="HTML")
                return

            imgs = sorted(
                [f for f in os.listdir(user_folder) if f.lower().endswith((".jpg", ".png"))],
                key=_extraer_numero,
            )
            if not imgs:
                await update.message.reply_text("<i>No tienes imágenes guardadas.</i>", parse_mode="HTML")
                return

            numeros = [_extraer_numero(f) for f in imgs if _extraer_numero(f) != -1]
            rango_ini, rango_fin = min(numeros), max(numeros)
            jpgs = [f for f in imgs if f.lower().endswith(".jpg")]
            pngs = [f for f in imgs if f.lower().endswith(".png")]
            mb = sum(os.path.getsize(os.path.join(user_folder, f)) for f in imgs) / (1024 * 1024)

            msg = "<b>INFORMACIÓN DE FOTOS</b>\n\n"
            msg += f"<b>Total:</b> {len(imgs)}\n"
            msg += f"<b>Formato:</b> {len(jpgs)} JPG | {len(pngs)} PNG\n"
            msg += f"<b>Rango actual:</b> {rango_ini:03d} – {rango_fin:03d}\n"
            msg += f"<b>Tamaño total:</b> {mb:.1f} MB\n\n"

            msg += "<b>Sugerencias de descarga:</b>\n"
            msg += "• Clic directo para todas: /descargar\n"
            msg += "• O copia este comando para bajar por lotes:\n"
            msg += f"  <code>/descargar {rango_ini:03d}-{rango_ini+49:03d}</code>\n"
            if rango_fin > rango_ini + 49:
                msg += f"  <code>/descargar {rango_ini+50:03d}-{rango_fin:03d}</code>\n"

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            print(f"Error en /info_fotos: {e}")
            await update.message.reply_text("<b>Error interno al obtener información.</b>", parse_mode="HTML")

    return info_fotos


# ─────────────────────────────────────────
# /descargar
# ─────────────────────────────────────────
def create_descargar(usuario_repo):
    """
    Factory para /descargar [inicio-fin].

    Args:
        usuario_repo: .obtener(user_id)
    """
    def _extraer_numero(nombre: str) -> int:
        m = re.match(r"^(\d+)", nombre)
        return int(m.group(1)) if m else -1

    async def descargar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id if update.effective_user else None
        usuario = usuario_repo.obtener(user_id)
        if not usuario:
            await update.message.reply_text("<b>Usuario no registrado.</b>", parse_mode="HTML")
            return

        args = update.message.text.strip().split()
        rango = None

        if len(args) > 1:
            match = re.match(r"(\d{1,3})-(\d{1,3})", args[1])
            if match:
                ini, fin = int(match.group(1)), int(match.group(2))
                if ini > fin:
                    await update.message.reply_text("<b>El rango es inválido.</b>", parse_mode="HTML")
                    return
                rango = (ini, fin)
            else:
                await update.message.reply_text(
                    "<b>Formato inválido.</b> Usa:\n"
                    "• /descargar (para bajar todas)\n"
                    "• O especifica un rango (copia el siguiente):\n"
                    "  <code>/descargar 1-50</code>",
                    parse_mode="HTML"
                )
                return

        user_folder = os.path.join(FOTOS_PATH, str(user_id))
        if not os.path.exists(user_folder):
            await update.message.reply_text("<b>No tienes imágenes guardadas.</b>", parse_mode="HTML")
            return

        imgs = [f for f in os.listdir(user_folder) if f.lower().endswith((".jpg", ".png"))]
        if not imgs:
            await update.message.reply_text("<b>No tienes imágenes guardadas.</b>", parse_mode="HTML")
            return

        if rango:
            ini, fin = rango
            imgs = [f for f in imgs if ini <= _extraer_numero(f) <= fin]
            if not imgs:
                await update.message.reply_text(
                    f"<b>No se encontraron imágenes en el rango {ini:03d}-{fin:03d}.</b>",
                    parse_mode="HTML"
                )
                return

        imgs = sorted(imgs)

        if len(imgs) > MAX_IMAGENES_POR_ZIP:
            await update.message.reply_text(
                f"<b>{len(imgs)} imágenes encontradas.</b>\n"
                f"<i>Se enviarán en lotes de {MAX_IMAGENES_POR_ZIP}.</i>",
                parse_mode="HTML"
            )
            lotes = [
                imgs[i: i + MAX_IMAGENES_POR_ZIP]
                for i in range(0, len(imgs), MAX_IMAGENES_POR_ZIP)
            ]
            for i, lote in enumerate(lotes, 1):
                await update.message.reply_text(f"<b>Enviando lote {i}/{len(lotes)}...</b>", parse_mode="HTML")
                await crear_y_enviar_zip(update, lote, f"lote_{i:02d}_de_{len(lotes):02d}", user_id)
            await update.message.reply_text(f"<b>¡Completado! {len(imgs)} imágenes enviadas.</b>", parse_mode="HTML")
        else:
            await update.message.reply_text(f"<b>Creando ZIP con {len(imgs)} imágenes...</b>", parse_mode="HTML")
            await crear_y_enviar_zip(update, imgs, "completo", user_id)

    return descargar
