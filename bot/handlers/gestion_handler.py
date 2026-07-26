"""
bot/handlers/gestion_handler.py

Responsabilidad única: operaciones destructivas de limpieza.
  - /limpiar_fotos → elimina las imágenes en disco del usuario (no afecta contador)

Bot hace: borrado físico de fotos del volumen (solo limpiar_fotos).
Backend hace: borrado BD (vía API).
"""
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

FOTOS_PATH   = os.getenv("FOTOS_PATH",   "media_files/fotos")
THUMBS_PATH  = os.getenv("THUMBS_PATH",  "media_files/thumbs")
PROXIES_PATH = os.getenv("PROXIES_PATH", "media_files/proxies")


def _borrar_archivos_usuario(user_id: int, solo_temporales: bool = True, simulacion: bool = False) -> dict:
    """
    Borra o simula el borrado de fotos.
    Retorna métricas de lo encontrado.
    """
    metricas = {'tmp_encontrados': 0, 'tmp_borrados': 0, 'historicos_encontrados': 0}
    
    for base in [FOTOS_PATH, THUMBS_PATH, PROXIES_PATH]:
        folder = os.path.join(base, str(user_id))
        if not os.path.exists(folder):
            continue
        for nombre_archivo in os.listdir(folder):
            ruta = os.path.join(folder, nombre_archivo)
            if os.path.isfile(ruta):
                if nombre_archivo.startswith("tmp_"):
                    metricas['tmp_encontrados'] += 1
                    if not simulacion:
                        try:
                            os.remove(ruta)
                            metricas['tmp_borrados'] += 1
                        except OSError as e:
                            logger.warning("No se pudo borrar temporal %s: %s", ruta, e)
                else:
                    if base == FOTOS_PATH:
                        metricas['historicos_encontrados'] += 1
                        
    logger.info("Auditoría archivos usuario %s: %s", user_id, metricas)
    return metricas


#                     "Los registros históricos y evidencias no fueron modificados.\n"
#                     "Para mantenimiento de archivos utiliza el panel web.",
#                     parse_mode="HTML"
#                 )
#             else:
#                 await update.message.reply_text("<b>Error al cancelar sesión.</b>", parse_mode="HTML")
# 
#         except Exception as e:
#             logger.error("Error en /limpiar: %s", e)
#             await update.message.reply_text(
#                 "<b>Error interno.</b>", parse_mode="HTML"
#             )
# 
#     return limpiar


def create_limpiar_fotos(api_client):
    """
    Factory para /limpiar_fotos.

    Args:
        api_client:        BotApiClient
    """
    async def limpiar_fotos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        try:
            user_id = update.effective_user.id if update.effective_user else None

            # Obtener perfil para mostrar nombre en respuesta
            perfil = await api_client.obtener_perfil(user_id)
            nombre = perfil.get('nombre', str(user_id)) if perfil else str(user_id)

            # Fase 0/1: Simulación, NO borrar nada físico por carpeta
            metricas_archivos = _borrar_archivos_usuario(user_id, simulacion=True)

            # Llama a API para obtener métricas reales contra BD
            resp = await api_client.limpiar_fotos_sesion(user_id)

            if resp.get('status') == 'analysis':
                huerfanas = resp.get('fotos_huerfanas', 0)
                en_uso = resp.get('fotos_en_uso', 0)
                
                await update.message.reply_text(
                    "<b>Reporte de Almacenamiento (Modo Análisis)</b>\n\n"
                    f"<b>Usuario:</b> {nombre}\n"
                    f"<b>Fotos en uso (BD):</b> {en_uso}\n"
                    f"<b>Candidatas a limpieza (Huérfanas):</b> {huerfanas}\n\n"
                    "<i>El borrado automático está desactivado por seguridad. Utilice el panel web para el mantenimiento.</i>",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text("<b>Error en análisis de fotos.</b>", parse_mode="HTML")

        except Exception as e:
            logger.error("Error en /limpiar_fotos: %s", e)
            await update.message.reply_text(
                "<b>Error interno en el reporte de fotos.</b>", parse_mode="HTML"
            )

    return limpiar_fotos
