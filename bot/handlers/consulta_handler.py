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

from telegram import Update
from telegram.ext import ContextTypes

from bot.helpers.zip_helper import crear_y_enviar_zip

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
            user_id = update.effective_user.id if update.effective_user else None
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
                        f"reporte_{data['turno']}_{data['departamento']}"
                        f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
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
            user_id = update.effective_user.id if update.effective_user else None
            
            try:
                stats = await api_client.obtener_estadisticas(user_id)
            except Exception as e:
                if "404" in str(e):
                    await update.message.reply_text("<b>Usuario no registrado.</b>", parse_mode="HTML")
                else:
                    raise e
                return

            if stats.get("rol") == "admin":
                msg = f"<b>ESTADO DEL GRUPO (Admin)</b>\n<i>(Turno {stats['turno']} - {stats['departamento']})</i>\n\n"
            else:
                msg = f"<b>ESTADO PERSONAL</b>\n<i>(Turno {stats['turno']} - {stats['departamento']})</i>\n\n"

            msg += f"<b>Usuario:</b> {stats['nombre']}\n"
            msg += f"<b>Siguiente foto:</b> {stats['siguiente_foto']:03d}\n"
            
            lbl_registros = "Registros del grupo" if stats.get("rol") == "admin" else "Tus registros"
            msg += f"<b>{lbl_registros}:</b> {stats['total_registros']}\n"

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

    Args:
        api_client: BotApiClient
    """
    def _extraer_numero(nombre: str) -> int:
        m = re.match(r"^(\d+)", nombre)
        return int(m.group(1)) if m else -1

    async def info_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user:
            return
        user_id = update.effective_user.id
        
        perfil = await api_client.obtener_perfil(user_id)
        if not perfil:
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
            if numeros:
                rango_ini, rango_fin = min(numeros), max(numeros)
            else:
                rango_ini, rango_fin = 0, 0
                
            jpgs = [f for f in imgs if f.lower().endswith(".jpg")]
            pngs = [f for f in imgs if f.lower().endswith(".png")]
            mb = sum(os.path.getsize(os.path.join(user_folder, f)) for f in imgs) / (1024 * 1024)

            msg = "<b>INFORMACIÓN DE FOTOS</b>\n\n"
            msg += f"<b>Total:</b> {len(imgs)}\n"
            msg += f"<b>Formato:</b> {len(jpgs)} JPG | {len(pngs)} PNG\n"
            if numeros:
                msg += f"<b>Rango actual:</b> {rango_ini:03d} – {rango_fin:03d}\n"
            else:
                msg += "<b>Rango actual:</b> (solo archivos temporales o sin número)\n"
            msg += f"<b>Tamaño total:</b> {mb:.1f} MB\n\n"

            msg += "<b>Sugerencias de descarga:</b>\n"
            msg += "• Clic directo para todas: /descargar\n"
            if numeros:
                msg += "• O copia este comando para bajar por lotes:\n"
                msg += f"  <code>/descargar {rango_ini:03d}-{rango_ini+49:03d}</code>\n"
                if rango_fin > rango_ini + 49:
                    msg += f"  <code>/descargar {rango_ini+50:03d}-{rango_fin:03d}</code>\n"

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

    Args:
        api_client: BotApiClient
    """
    def _extraer_numero(nombre: str) -> int:
        m = re.match(r"^(\d+)", nombre)
        return int(m.group(1)) if m else -1

    async def descargar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        user_id = update.effective_user.id if update.effective_user else None
        
        perfil = await api_client.obtener_perfil(user_id)
        if not perfil:
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
            "<i>Versión 3.1</i>\n\n"
            "<b>Desarrollado por:</b> Daniel Hernandez\n\n"
            "Bot especializado en el registro y gestión de reportes de calidad en línea de producción."
        )
        await update.message.reply_text(texto, parse_mode="HTML")
        
    return info
