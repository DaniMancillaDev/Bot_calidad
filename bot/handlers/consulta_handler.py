from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
import logging
import os
import re
import tempfile
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.handlers.lock_utils import prevent_double_tap

logger = logging.getLogger(__name__)

import os
FOTOS_PATH = os.getenv("FOTOS_PATH", "media_files/fotos")
MAX_IMAGENES_POR_ZIP = 30


# ─────────────────────────────────────────
# /reporte
# ─────────────────────────────────────────
def create_reporte(api_client):
    """
    Factory para /reporte.
    Modos:
      /reporte        → registros propios
      admin           → todos los del turno/depto
    """
    async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None if update.effective_user else None
            data = await api_client.obtener_reporte(user_id)

            registros = data.get('registros', [])
            if not registros:
                await update.message.reply_text("<b>No hay registros disponibles.</b>", parse_mode="HTML")
                return

            import tempfile
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(
                    f"REPORTE DE DEFECTOS - TURNO {data['turno']} - {data['departamento']}\n"
                    f"Usuario: {data['usuario']} | Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    + "=" * 60 + "\n\n"
                )
                for r in registros:
                    fotos_str = str(r.get('fotos', '')) if r.get('fotos') else 'sin fotos'
                    tmp.write(
                        f"{fotos_str} Modelo: {r['modelo']}; Línea: {r['linea']}; "
                        f"Cantidad: {r['cantidad']}; Responsable: {r['responsable']}; "
                        f"Descripción: {r['descripcion']}\n"
                    )
                nombre_archivo = tmp.name

            with open(nombre_archivo, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=(
                        f"rep_{data['turno']}_{data['departamento']}_{datetime.now().strftime('%H%M')}.txt"
                    ),
                    caption=f"Reporte {data['turno']}/{data['departamento']} — {len(registros)} registro(s)",
                    read_timeout=300,
                    write_timeout=300,
                )
            os.remove(nombre_archivo)

        except Exception as e:
            logger.error("Error en /reporte: %s", e)
            await update.message.reply_text("<b>Error interno al generar el reporte.</b>", parse_mode="HTML")

    return reporte


# ─────────────────────────────────────────
# /estado
# ─────────────────────────────────────────
def create_estado(api_client):
    """
    Factory para /estado.

    Args:
        api_client: BotApiClient
    """
    async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None if update.effective_user else None
            
            try:
                stats = await api_client.obtener_estadisticas(user_id)
            except Exception as e:
                if "404" in str(e):
                    await update.message.reply_text("<b>Usuario no registrado.</b>", parse_mode="HTML")
                else:
                    raise e
                return

            if stats.get("rol") == "admin":
                titulo = "Estado del grupo"
                lbl_registros = "Registros del grupo"
            else:
                titulo = "Estado personal"
                lbl_registros = "Registros propios"

            msg = (
                f"<b>{titulo}</b>\n"
                f"<i>Turno {stats['turno']} — {stats['departamento']}</i>\n\n"
                f"<b>Usuario:</b> {stats['nombre']}\n"
                f"<b>{lbl_registros} hoy:</b> {stats['total_registros']}\n"
            )

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error("Error en /estado: %s", e)
            await update.message.reply_text("<b>Error interno al obtener el estado.</b>", parse_mode="HTML")

    return estado


# ─────────────────────────────────────────
# /info_fotos
# ─────────────────────────────────────────
def create_info_fotos(api_client):
    """
    Factory para /info_fotos.
    """
    async def info_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        user_id = update.effective_user.id if update.effective_user else None
        
        try:
            info = await api_client.obtener_info_evidencia(user_id)
            if info.get("total", 0) == 0:
                await update.message.reply_text(
                    "<b>Sin evidencias registradas.</b>\n"
                    "<i>Envia fotos en cualquier momento para comenzar a capturar evidencias.</i>",
                    parse_mode="HTML"
                )
                return

            msg = "<b>Evidencias almacenadas</b>\n\n"
            msg += f"<b>Total:</b> {info['total']} imagen(es)\n"
            msg += f"<b>Formato:</b> {info['jpgs']} JPG — {info['pngs']} PNG\n"
            if info['rango_min'] > 0 or info['rango_max'] > 0:
                msg += f"<b>Rango:</b> {info['rango_min']:03d} – {info['rango_max']:03d}\n"
            else:
                msg += "<b>Rango:</b> archivos temporales (sin numeracion final)\n"
            msg += f"<b>Tamano:</b> {info['size_mb']:.1f} MB\n"

            msg += "\n<b>Descarga disponible:</b>\n"
            msg += "  /descargar — descarga todas las fotos\n"
            if info['rango_min'] > 0:
                msg += "\nPara descargar por rango (maximo 30 por lote):\n"
                msg += f"  <code>/descargar {info['rango_min']:03d}-{info['rango_min']+MAX_IMAGENES_POR_ZIP-1:03d}</code>\n"
                if info['rango_max'] > info['rango_min'] + MAX_IMAGENES_POR_ZIP - 1:
                    msg += f"  <code>/descargar {info['rango_min']+MAX_IMAGENES_POR_ZIP:03d}-{info['rango_max']:03d}</code>\n"

            await update.message.reply_text(msg, parse_mode="HTML")

        except Exception as e:
            logger.error("Error en /info_fotos: %s", e)
            await update.message.reply_text("<b>Error interno al obtener información.</b>", parse_mode="HTML")

    return info_fotos


# ─────────────────────────────────────────
# /descargar
# ─────────────────────────────────────────
def create_descargar(api_client):
    """
    Factory para /descargar [inicio-fin].
    Descarga la evidencia del propio usuario.
    """
    async def descargar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id if update.effective_user else None
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
                    "• O especifica un rango:\n"
                    "  <code>/descargar 1-50</code>",
                    parse_mode="HTML"
                )
                return

        try:
            info = await api_client.obtener_info_evidencia(user_id)
            if info.get("total", 0) == 0:
                await update.message.reply_text("<b>No tienes imágenes guardadas.</b>", parse_mode="HTML")
                return
                
            try:
                stats = await api_client.obtener_estadisticas(user_id)
                nombre_op = stats.get('nombre')
                if not nombre_op:
                    nombre_op = f"Usuario_{user_id}"
            except Exception:
                nombre_op = f"Usuario_{user_id}"
                
            nombre_limpio = str(nombre_op).replace(" ", "_")

            if rango:
                ini, fin = rango
                msg = await update.message.reply_text(f"<b>Generando ZIP ({ini:03d}-{fin:03d})...</b>", parse_mode="HTML")
                zip_path = None
                try:
                    zip_path, count = await api_client.descargar_evidencia(user_id, inicio=ini, fin=fin)
                    from datetime import datetime
                    timestamp = datetime.now().strftime('%H%M')
                    with open(zip_path, "rb") as f:
                        await update.message.reply_document(
                            document=f,
                            filename=f"{nombre_limpio}_{ini:03d}-{fin:03d}_{timestamp}.zip",
                            caption=f"{count} imagen(es) — rango {ini:03d}-{fin:03d}.",
                            read_timeout=300,
                            write_timeout=300,
                        )
                    os.remove(zip_path)
                    await msg.delete()
                    await update.message.reply_text(f"<b>Descarga completada.</b> {count} imagen(es) enviadas.", parse_mode="HTML")
                except Exception as e:
                    await msg.edit_text("<b>Error al descargar.</b> " + (str(e) if "404" in str(e) else ""), parse_mode="HTML")
                return

            # Bajar todo (con batching si es necesario)
            if info["total"] > MAX_IMAGENES_POR_ZIP:
                await update.message.reply_text(
                    f"<b>{info['total']} imágenes encontradas.</b>\n"
                    f"<i>Se enviarán en lotes de {MAX_IMAGENES_POR_ZIP}.</i>",
                    parse_mode="HTML"
                )
                r_min, r_max = info['rango_min'], info['rango_max']
                lotes = []
                for i in range(r_min, r_max + 1, MAX_IMAGENES_POR_ZIP):
                    lotes.append((i, min(i + MAX_IMAGENES_POR_ZIP - 1, r_max)))
                
                for i, (ini, fin) in enumerate(lotes, 1):
                    msg = await update.message.reply_text(f"<b>Enviando lote {i} de {len(lotes)}...</b>", parse_mode="HTML")
                    try:
                        zip_path, count = await api_client.descargar_evidencia(user_id, inicio=ini, fin=fin)
                        from datetime import datetime
                        timestamp = datetime.now().strftime('%H%M')
                        with open(zip_path, "rb") as f:
                            await update.message.reply_document(
                                document=f,
                                filename=f"{nombre_limpio}_p{i}_{timestamp}.zip",
                                caption=f"Lote {i} de {len(lotes)} — {count} imagen(es).",
                                read_timeout=300,
                                write_timeout=300,
                            )
                        os.remove(zip_path)
                        await msg.delete()
                    except Exception as e:
                        if "404" not in str(e): # Skip empty batches if they happen
                            await update.message.reply_text(f"<b>Error en el lote {i}.</b> {e}", parse_mode="HTML")
                await update.message.reply_text("<b>Descarga completada.</b> Todas las imágenes han sido enviadas.", parse_mode="HTML")
            else:
                msg = await update.message.reply_text(f"<b>Generando ZIP con {info['total']} imagen(es)...</b>", parse_mode="HTML")
                zip_path = None
                try:
                    zip_path, count = await api_client.descargar_evidencia(user_id)
                    from datetime import datetime
                    timestamp = datetime.now().strftime('%H%M')
                    with open(zip_path, "rb") as f:
                        await update.message.reply_document(
                            document=f,
                            filename=f"{nombre_limpio}_{timestamp}.zip",
                            caption=f"{count} imagen(es) en total.",
                            read_timeout=300,
                            write_timeout=300,
                        )
                    await msg.delete()
                finally:
                    if zip_path and os.path.exists(zip_path):
                        try:
                            os.remove(zip_path)
                        except OSError:
                            pass

        except Exception as e:
            logger.error("Error en /descargar: %s", e)
            if "404" in str(e):
                await update.message.reply_text("<b>No tienes imágenes guardadas para descargar.</b>", parse_mode="HTML")
            else:
                await update.message.reply_text("<b>Error de red o timeout. Inténtalo de nuevo.</b>", parse_mode="HTML")

    return descargar


# ─────────────────────────────────────────
# /descargar_turno (Admin/Supervisor)
# ─────────────────────────────────────────
def create_descargar_turno(api_client):
    """Factory para /descargar_turno."""

    async def descargar_turno(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return

        user_id = update.effective_user.id if update.effective_user else None
        try:
            turnos = await api_client.obtener_turnos(user_id)
            if not turnos:
                await update.message.reply_text("<b>No hay turnos disponibles para exportar.</b>", parse_mode="HTML")
                return

            keyboard = [[InlineKeyboardButton(f"Turno {t}", callback_data=f"turno:{t}")] for t in turnos]
            await update.message.reply_text(
                "<b>Descarga de evidencia</b>\nSelecciona el turno:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error("Error en /descargar_turno: %s", e)
            await update.message.reply_text("<b>Error interno al obtener turnos.</b>", parse_mode="HTML")

    return descargar_turno


def create_turno_callback(api_client):
    """Factory para manejar la selección de turno."""

    @prevent_double_tap
    async def turno_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id if update.effective_user else None
        turno = query.data.split(":")[1]

        try:
            operadores = await api_client.obtener_operadores(user_id, turno)
            if not operadores:
                await query.edit_message_text(f"<b>Sin registros en Turno {turno}.</b>", parse_mode="HTML")
                return

            keyboard = [[InlineKeyboardButton("Todos", callback_data=f"op:{turno}:todos")]]
            # Cache id→nombre for use in operador_callback
            context.user_data["op_nombres"] = {"todos": "Todos"}
            for op in operadores:
                context.user_data["op_nombres"][str(op['id'])] = op['nombre']
                keyboard.append([InlineKeyboardButton(op['nombre'], callback_data=f"op:{turno}:{op['id']}")])

            await query.edit_message_text(
                f"<b>Turno {turno}</b>\nSelecciona un operador:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error("Error en turno_callback: %s", e)
            await query.edit_message_text("<b>Error interno al obtener operadores.</b>", parse_mode="HTML")

    return turno_callback


def create_operador_callback(api_client):
    """Factory para manejar la selección de operador y descargar el ZIP."""
    @prevent_double_tap
    async def operador_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id if update.effective_user else None
        _, turno, op_id = query.data.split(":")

        await query.edit_message_text("<b>Generando ZIP desde el servidor...</b>", parse_mode="HTML")

        try:
            zip_path = None
            try:
                zip_path, count = await api_client.descargar_evidencia(user_id, turno=turno, operador=op_id)
                
                from datetime import datetime
                timestamp = datetime.now().strftime('%H%M')
                op_nombres = context.user_data.get("op_nombres", {})
                nombre = op_nombres.get(str(op_id), op_id)
                nombre_limpio = nombre.replace(" ", "_")
                sufijo = f"T{turno}_{nombre_limpio}"
                
                size_mb = os.path.getsize(zip_path) / (1024 * 1024)
                if size_mb > 49.0:
                    await query.message.reply_text(
                        f"⚠️ <b>El archivo es demasiado grande para enviarlo por Telegram ({size_mb:.1f} MB).</b>\n"
                        f"El límite de Telegram es de 50 MB.\n\n"
                        f"<i>Sugerencia: Descarga la evidencia de cada operador de forma individual en lugar de usar el botón 'Todos'.</i>",
                        parse_mode="HTML"
                    )
                else:
                    with open(zip_path, "rb") as f:
                        await query.message.reply_document(
                            document=f,
                            filename=f"{sufijo}_{timestamp}.zip",
                            caption=f"Evidencia Turno {turno} — Operador: {nombre}.",
                            read_timeout=300,
                            write_timeout=300,
                        )
                
                await query.delete_message()
            finally:
                if zip_path and os.path.exists(zip_path):
                    try:
                        os.remove(zip_path)
                    except OSError:
                        pass
        except Exception as e:
            logger.error("Error en operador_callback: %s", e)
            if "404" in str(e):
                await query.edit_message_text("<b>No se encontraron imágenes para este turno/operador.</b>", parse_mode="HTML")
            else:
                await query.edit_message_text("<b>Error de red o timeout al generar ZIP. Intenta de nuevo.</b>", parse_mode="HTML")

    return operador_callback


# ─────────────────────────────────────────
# /info
# ─────────────────────────────────────────
def create_info():
    """
    Factory para el comando /info (sin dependencias externas).
    Muestra la información del sistema y créditos del desarrollador.
    """
    async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
            
        texto = (
            "<b>Agente IQA</b>\n"
            "<i>Version 3.1</i>\n\n"
            "<b>Desarrollado por:</b> Daniel Hernandez\n\n"
            "Bot especializado en el registro y gestion de reportes de calidad en linea de produccion."
        )
        await update.message.reply_text(texto, parse_mode="HTML")
        
    return info


# ─────────────────────────────────────────
# /reporte_turno  (Admin)
# ─────────────────────────────────────────

def _generar_txt_reporte(data: dict, nombre_op: str) -> str:
    """Construye el contenido del archivo .txt a partir de la respuesta del API."""
    turno = data.get('turno', '-')
    departamento = data.get('departamento', '-')
    operador_id = data.get('operador_id', 'todos')
    registros = data.get('registros', [])

    alcance = "Todos los operadores" if operador_id == "todos" else f"Operador: {nombre_op}"

    lineas = [
        f"REPORTE DE DEFECTOS - TURNO {turno} - {departamento}",
        f"Alcance: {alcance} | Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]

    for r in registros:
        fotos_str = str(r.get('fotos', '')) if r.get('fotos') else 'sin fotos'
        lineas.append(
            f"{fotos_str} Modelo: {r.get('modelo', '')}; Línea: {r.get('linea', '')}; "
            f"Cantidad: {r.get('cantidad', 0)}; Responsable: {r.get('responsable', '')}; "
            f"Descripción: {r.get('descripcion', '')}"
        )

    return "\n".join(lineas) + "\n"


def create_reporte_turno(api_client):
    """Factory para /reporte_turno (Admin). Selecciona turno via inline keyboard."""

    async def reporte_turno(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return

        user_id = update.effective_user.id if update.effective_user else None
        try:
            turnos = await api_client.obtener_turnos(user_id)
            if not turnos:
                await update.message.reply_text(
                    "<b>No hay turnos disponibles para reportar.</b>",
                    parse_mode="HTML"
                )
                return

            keyboard = [[InlineKeyboardButton(f"Turno {t}", callback_data=f"rpt_turno:{t}")] for t in turnos]
            await update.message.reply_text(
                "<b>Reporte de turno</b>\nSelecciona el turno:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error("Error en /reporte_turno: %s", e)
            await update.message.reply_text(
                "<b>Error interno al obtener turnos.</b>",
                parse_mode="HTML"
            )

    return reporte_turno


def create_rpt_turno_callback(api_client):
    """Factory para el callback de seleccion de turno en /reporte_turno."""

    @prevent_double_tap
    async def rpt_turno_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id if update.effective_user else None
        turno = query.data.split(":")[1]

        try:
            operadores = await api_client.obtener_operadores(user_id, turno)
            if not operadores:
                await query.edit_message_text(
                    f"<b>Sin registros en Turno {turno}.</b>",
                    parse_mode="HTML"
                )
                return

            keyboard = [[InlineKeyboardButton("Todos los operadores", callback_data=f"rpt_op:{turno}:todos")]]
            context.user_data["rpt_op_nombres"] = {"todos": "Todos los operadores"}
            for op in operadores:
                context.user_data["rpt_op_nombres"][str(op['id'])] = op['nombre']
                keyboard.append([InlineKeyboardButton(op['nombre'], callback_data=f"rpt_op:{turno}:{op['id']}")])

            await query.edit_message_text(
                f"<b>Turno {turno}</b>\nSelecciona un operador:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error("Error en rpt_turno_callback: %s", e)
            await query.edit_message_text(
                "<b>Error interno al obtener operadores.</b>",
                parse_mode="HTML"
            )

    return rpt_turno_callback


def create_rpt_operador_callback(api_client):
    """Factory para el callback de seleccion de operador: genera y envia el .txt."""
    @prevent_double_tap
    async def rpt_operador_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id if update.effective_user else None
        _, turno, op_id = query.data.split(":")

        op_nombres = context.user_data.get("rpt_op_nombres", {})
        nombre_op = op_nombres.get(str(op_id), op_id)

        await query.edit_message_text(
            f"<b>Generando reporte...</b>\nTurno {turno} \u2014 {nombre_op}.",
            parse_mode="HTML"
        )

        try:
            data = await api_client.obtener_reporte_turno(user_id, turno=turno, operador_id=op_id)
            registros = data.get('registros', [])

            if not registros:
                await query.edit_message_text(
                    f"<b>Sin registros para este filtro.</b>\n"
                    f"<i>Turno {turno} \u2014 {nombre_op}.</i>",
                    parse_mode="HTML"
                )
                return

            contenido = _generar_txt_reporte(data, nombre_op)

            timestamp = datetime.now().strftime('%H%M')
            nombre_limpio = nombre_op.replace(" ", "_")
            nombre_archivo = f"rep_{turno}_{nombre_limpio}_{timestamp}.txt"

            import tempfile
            fd, tmp_path = tempfile.mkstemp(suffix=".txt")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(contenido)

                with open(tmp_path, "rb") as f:
                    await query.message.reply_document(
                        document=f,
                        filename=nombre_archivo,
                        caption=(
                            f"Reporte Turno {turno} \u2014 {nombre_op}.\n"
                            f"{len(registros)} registro(s)."
                        ),
                        read_timeout=300,
                        write_timeout=300,
                    )
            finally:
                os.remove(tmp_path)

            await query.delete_message()

        except Exception as e:
            logger.error("Error en rpt_operador_callback: %s", e)
            await query.edit_message_text(
                "<b>Error interno al generar el reporte.</b>",
                parse_mode="HTML"
            )

    return rpt_operador_callback
