import os
import logging
import time
from typing import Dict, Any, List, Optional

from calidad.domain.defectos.entities import EstadoConversacion, FSMContext, FSMResult
from calidad.domain.defectos.state_machine import RegistroFSM
from calidad.services.redis_conversation_state import RedisConversationState
from shared.infrastructure.database.django_registro_repository import DjangoRegistroRepository
from shared.infrastructure.database.django_usuario_repository import DjangoUsuarioRepository
from shared.infrastructure.database.django_contador_repository import DjangoContadorRepository
from shared.infrastructure.storage.foto_storage import LocalFotoStorage

logger = logging.getLogger(__name__)

class DefectoWorkflow:
    """
    Orquestador de la máquina de estados de registro de defectos.
    Integra Redis, la FSM pura y la Base de Datos.
    """
    
    def __init__(self, foto_storage=None):
        # En el entorno de Django, REDIS_URL o CELERY_BROKER_URL está configurado.
        self._state_repo = RedisConversationState()
        self._fsm = RegistroFSM()
        self._registro_repo = DjangoRegistroRepository()
        self._usuario_repo = DjangoUsuarioRepository()
        self._contador_repo = DjangoContadorRepository()
        # Etapa 5: storage inyectado — default LocalFotoStorage para backward compat
        self._storage = foto_storage or LocalFotoStorage()

        try:
            from shared.infrastructure.ai.deepseek_extractor import DeepSeekExtractor
            self._extractor_ia = DeepSeekExtractor()
        except ImportError:
            self._extractor_ia = None

    def iniciar(self, user_id: int) -> FSMResult:
        """Inicia una nueva sesión de reporte."""
        if not self._state_repo.tiene_conversacion(user_id):
            self._state_repo.iniciar(user_id)
            return FSMResult(exito=True, mensaje="Envíame las <b>fotos</b> del defecto.")
        
        estado = self._state_repo.obtener(user_id)
        return FSMResult(
            exito=True, 
            mensaje=f"Ya tienes un reporte en curso (Estado: {estado.get('estado')}). Si deseas cancelar, usa /cancelar."
        )

    def adjuntar_fotos(self, user_id: int, fotos_ids: List[int]) -> FSMResult:
        """Añade lote de fotos al estado actual. Renombra tmp_{id} → {contador}. Avanza FSM si primer lote."""
        import os
        from datetime import datetime
        t0 = time.monotonic()

        if not self._state_repo.tiene_conversacion(user_id):
            self._state_repo.iniciar(user_id)

        estado_dict = self._state_repo.obtener(user_id)
        user_folder = self._storage.get_user_folder(user_id)  # Etapa 5: storage

        nuevos_contadores = []
        rutas_para_thumbnail = []
        for msg_id in fotos_ids:
            tmp_path = user_folder / f"tmp_{msg_id}.jpg"
            if tmp_path.exists():
                contador = self._contador_repo.obtener_y_avanzar(user_id)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nuevo_nombre = f"{contador:03d}_{timestamp}.jpg"
                nueva_ruta = user_folder / nuevo_nombre

                try:
                    os.rename(tmp_path, nueva_ruta)
                    nuevos_contadores.append(contador)
                    rutas_para_thumbnail.append(str(nueva_ruta))
                except Exception as e:
                    logger.error("rename failed %s → %s: %s", tmp_path, nueva_ruta, e)

        # Lanzar procesamiento de thumbnails por lote (más eficiente)
        if rutas_para_thumbnail:
            try:
                from calidad.tasks import generar_thumbnails_lote_task
                generar_thumbnails_lote_task.delay(user_id, rutas_para_thumbnail)
            except Exception as thumb_exc:
                logger.warning("batch thumbnail dispatch failed: %s", thumb_exc)

        estado_dict['fotos'] = list(set(estado_dict.get('fotos', []) + nuevos_contadores))
        estado_dict['fotos_sin_asignar'] = list(set(estado_dict.get('fotos_sin_asignar', []) + nuevos_contadores))

        estado_actual = EstadoConversacion.parse(estado_dict.get('estado'))

        mensaje = f"<b>¡{len(nuevos_contadores)} foto(s) recibidas!</b>\n\n¿Deseas enviar más fotos o prefieres continuar con el registro?"

        self._state_repo.guardar(user_id, estado_dict)

        # Etapa 6: structured log con timing
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "adjuntar_fotos | user_id=%s lote=%d total_fotos=%d elapsed=%.1fms",
            user_id, len(nuevos_contadores), len(estado_dict['fotos']), elapsed
        )

        return FSMResult(
            exito=True,
            mensaje=mensaje,
            nuevo_estado=EstadoConversacion.parse(estado_dict['estado']),
            finalizado=False
        )

    def responder(self, user_id: int, texto: str) -> FSMResult:
        """Procesa respuesta de texto según estado de la FSM."""
        t0 = time.monotonic()
        if not self._state_repo.tiene_conversacion(user_id):
            return FSMResult(exito=False, mensaje="No tienes un reporte en curso. Envía una foto primero.")

        estado_dict = self._state_repo.obtener(user_id)
        estado_actual = EstadoConversacion.parse(estado_dict.get('estado', 'ESPERANDO_FOTOS'))

        # Caso especial: TERMINAR en fase de fotos
        if estado_actual == EstadoConversacion.ESPERANDO_FOTOS:
            if texto.upper() == "TERMINAR":
                if not estado_dict.get('fotos'):
                    return FSMResult(exito=False, mensaje="No has enviado fotos aún.")

                estado_dict['estado'] = EstadoConversacion.ESPERANDO_MODELO.value
                self._state_repo.guardar(user_id, estado_dict)

                enable_part_number = os.getenv("ENABLE_PART_NUMBER", "false").lower() in ("true", "1", "yes")
                total_steps = 6 if enable_part_number else 5
                
                return FSMResult(
                    exito=True,
                    mensaje=(
                        "<b>¡Perfecto! Álbum cerrado.</b>\n\n"
                        f"Para completar el reporte, responde estas {total_steps} preguntas:\n\n"
                        f"<b>[1/{total_steps}] Modelo</b>\n"
                        "¿De qué modelo es el producto?\n"
                        "<code>Ej: ONN 32\" 100012589 AUO</code>"
                    ),
                    nuevo_estado=EstadoConversacion.ESPERANDO_MODELO
                )
            return FSMResult(exito=False, mensaje="Por favor envíame primero las <b>fotos</b> del defecto o presiona TERMINAR.")

        # Rechazar TERMINAR si ya no estamos en fase fotos
        if texto.upper() == "TERMINAR":
            return FSMResult(exito=False, mensaje="El álbum ya fue cerrado. Responde la pregunta actual para continuar.")

        datos = estado_dict.get('datos', {})

        # 1. Interceptar estado de confirmación IA
        if datos.get('confirmando_extraccion'):
            return self._handle_confirmacion(user_id, texto, estado_dict, datos)

        # 2. Interceptar selección de campo a corregir
        if datos.get('eligiendo_campo_correccion'):
            return self._handle_eleccion_correccion(user_id, texto, estado_dict, datos)

        # 3. Intentar extracción IA en ESPERANDO_MODELO
        if estado_actual == EstadoConversacion.ESPERANDO_MODELO and self._extractor_ia:
            # Solo usar IA si parece una oración (más de 3 palabras o más de 40 caracteres)
            # Evita falsos positivos con modelos largos como "NS-55F501NA26 AUO"
            if len(texto.split()) > 3 or len(texto) > 40:
                result_ia = self._intentar_extraccion_ia(texto, estado_dict, datos)
                if result_ia:
                    self._state_repo.guardar(user_id, estado_dict)
                    return result_ia

        context = FSMContext(
            telegram_id=user_id,
            estado=estado_actual,
            datos=estado_dict.get('datos', {})
        )

        result = self._fsm.procesar_evento(context, texto.upper())

        if result.exito:
            estado_dict['datos'] = context.datos
            estado_dict['estado'] = context.estado.value if context.estado else None

            if result.finalizado:
                guardado = self._guardar_registro(user_id, estado_dict)
                if guardado:
                    resumen = self._generar_resumen(estado_dict)
                    result.mensaje = f"<b>¡Reporte guardado con éxito!</b>\n\n{resumen}\n\n<i>Para reportar otro defecto, simplemente envíame fotos nuevas.</i>"
                    self._state_repo.finalizar(user_id)
                else:
                    result.exito = False
                    result.mensaje = "Error al guardar en base de datos."
            else:
                self._state_repo.guardar(user_id, estado_dict)

        # Etapa 6: structured timing log
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            "responder | user_id=%s estado=%s exito=%s finalizado=%s elapsed=%.1fms",
            user_id, estado_actual.value if estado_actual else None,
            result.exito, result.finalizado, elapsed
        )
        return result


    def _guardar_registro(self, user_id: int, conv: Dict) -> bool:
        """Guarda físicamente en DjangoRegistroRepository."""
        t0 = time.monotonic()
        usuario = self._usuario_repo.obtener(user_id)
        if not usuario:
            logger.error("_guardar_registro: user_id=%s no encontrado en repositorio", user_id)
            return False

        datos = conv.get('datos', {})
        exito = self._registro_repo.guardar(
            user_id=user_id,
            turno=usuario['turno'],
            departamento=usuario['departamento'],
            modelo=datos.get('modelo', ''),
            numero_parte=datos.get('numero_parte'),
            linea=datos.get('linea', ''),
            cantidad=datos.get('cantidad', 1),
            responsable=datos.get('responsable', ''),
            descripcion=datos.get('descripcion', ''),
            fotos=conv.get('fotos', [])
        )
        elapsed = (time.monotonic() - t0) * 1000
        # Etapa 6: structured log con timing
        logger.info(
            "_guardar_registro | user_id=%s exito=%s fotos=%s elapsed=%.1fms",
            user_id, exito, conv.get('fotos', []), elapsed
        )
        return exito
        
    def _generar_resumen(self, conv: Dict) -> str:
        """Genera el texto de resumen para el usuario."""
        datos = conv.get('datos', {})
        fotos_str = self._formatear_rango_fotos(conv.get('fotos', []))
        
        part_str = f"<b>Num Parte:</b> {datos.get('numero_parte')}\n" if datos.get('numero_parte') else ""
        
        return (
            f"<b>Fotos:</b> {fotos_str}\n"
            f"<b>Modelo:</b> {datos.get('modelo')}\n"
            f"{part_str}"
            f"<b>Línea:</b> {datos.get('linea')}\n"
            f"<b>Cantidad:</b> {datos.get('cantidad')}\n"
            f"<b>Responsable:</b> {datos.get('responsable')}\n"
            f"<b>Descripción:</b> {datos.get('descripcion')}"
        )

    def _formatear_rango_fotos(self, fotos: list[int]) -> str:
        if not fotos:
            return ""
        
        fotos_unicas = sorted(list(set(fotos)))
        rangos = []
        rango_actual = [fotos_unicas[0]]
        
        for i in range(1, len(fotos_unicas)):
            if fotos_unicas[i] == fotos_unicas[i-1] + 1:
                rango_actual.append(fotos_unicas[i])
            else:
                if len(rango_actual) > 1:
                    rangos.append(f"{rango_actual[0]}-{rango_actual[-1]}")
                else:
                    rangos.append(str(rango_actual[0]))
                rango_actual = [fotos_unicas[i]]
                
        if len(rango_actual) > 1:
            rangos.append(f"{rango_actual[0]}-{rango_actual[-1]}")
        else:
            rangos.append(str(rango_actual[0]))
            
        return ", ".join(rangos)

    def _intentar_extraccion_ia(self, texto_original: str, conv: dict, datos: dict) -> Optional[FSMResult]:
        logger.info("Intentando extracción con IA...")
        t0 = time.time()
        
        datos['ia_raw_request'] = texto_original
        extraido = self._extractor_ia.extraer(texto_original)
        
        t1 = time.time()
        logger.info(f"IA respondió en {t1-t0:.2f}s. Resultado: {extraido}")

        if not extraido:
            logger.warning("IA falló al extraer datos. Haciendo fallback a flujo normal.")
            import os
            enable_part_number = os.getenv("ENABLE_PART_NUMBER", "false").lower() in ("true", "1", "yes")
            total_steps = 6 if enable_part_number else 5
            
            return FSMResult(
                exito=True,
                mensaje="⚠️ La IA no pudo procesar tu mensaje completo (Posible falla de red).\n"
                        "Vamos a ingresar los datos paso a paso:\n\n"
                        f"<b>[1/{total_steps}] Modelo</b>\n¿De qué modelo es el producto?",
                nuevo_estado=EstadoConversacion.ESPERANDO_MODELO
            )

        import json
        from calidad.domain.defectos.validators import validar_modelo, validar_linea, validar_cantidad

        datos['ia_raw_response'] = json.dumps(extraido)

        if extraido.get("modelo") and validar_modelo(str(extraido["modelo"]).upper()):
            datos["modelo"] = str(extraido["modelo"]).upper()
        if extraido.get("linea") and validar_linea(str(extraido["linea"]).upper()):
            datos["linea"] = str(extraido["linea"]).upper()
        if extraido.get("cantidad") and validar_cantidad(str(extraido["cantidad"])):
            datos["cantidad"] = int(extraido["cantidad"])
        if extraido.get("responsable"):
            datos["responsable"] = str(extraido["responsable"]).upper()
        if extraido.get("descripcion"):
            datos["descripcion"] = str(extraido["descripcion"]).upper()

        resultado = self._avanzar_siguiente_campo_vacio(conv, datos)
        
        if not datos.get('confirmando_extraccion'):
            resultado.mensaje = f"🤖 <i>IA procesó parte de tu mensaje. Continuemos:</i>\n\n{resultado.mensaje}"
            
        return resultado

    def _avanzar_siguiente_campo_vacio(self, conv: dict, datos: dict) -> FSMResult:
        import os
        enable_part_number = os.getenv("ENABLE_PART_NUMBER", "false").lower() in ("true", "1", "yes")
        total_steps = 6 if enable_part_number else 5

        if not datos.get("modelo"):
            conv['estado'] = EstadoConversacion.ESPERANDO_MODELO.value
            return FSMResult(exito=True, mensaje=f"<b>[1/{total_steps}] Modelo</b>\n¿De qué modelo es el producto?", nuevo_estado=EstadoConversacion.ESPERANDO_MODELO)
        
        if enable_part_number and "numero_parte" not in datos:
            conv['estado'] = EstadoConversacion.ESPERANDO_NUMERO_PARTE.value
            return FSMResult(exito=True, mensaje="<b>[2/6] Número de Parte (Opcional)</b>\nIngresa el número de parte.\n\nSi no aplica, presiona OMITIR.", nuevo_estado=EstadoConversacion.ESPERANDO_NUMERO_PARTE)
            
        if not datos.get("linea"):
            conv['estado'] = EstadoConversacion.ESPERANDO_LINEA.value
            return FSMResult(exito=True, mensaje=f"<b>[{'3/6' if enable_part_number else '2/5'}] Línea de Producción</b>\n¿En qué línea ocurrió?", nuevo_estado=EstadoConversacion.ESPERANDO_LINEA)
        if not datos.get("cantidad"):
            conv['estado'] = EstadoConversacion.ESPERANDO_CANTIDAD.value
            return FSMResult(exito=True, mensaje=f"<b>[{'4/6' if enable_part_number else '3/5'}] Cantidad</b>\n¿Cuántos defectos encontraste? (Solo números)", nuevo_estado=EstadoConversacion.ESPERANDO_CANTIDAD)
        if not datos.get("responsable"):
            conv['estado'] = EstadoConversacion.ESPERANDO_RESPONSABLE.value
            return FSMResult(exito=True, mensaje=f"<b>[{'5/6' if enable_part_number else '4/5'}] Responsable</b>\n¿Quién es el responsable? (Ej: XM)", nuevo_estado=EstadoConversacion.ESPERANDO_RESPONSABLE)
        if not datos.get("descripcion"):
            conv['estado'] = EstadoConversacion.ESPERANDO_DESCRIPCION.value
            return FSMResult(exito=True, mensaje=f"<b>[{'6/6' if enable_part_number else '5/5'}] Descripción</b>\nPor último, descríbeme el defecto:", nuevo_estado=EstadoConversacion.ESPERANDO_DESCRIPCION)

        datos['confirmando_extraccion'] = True
        
        from html import escape
        resumen = (
            f"🤖 <b>Extracción Inteligente:</b>\n\n"
            f"1. <b>Modelo:</b> {escape(datos['modelo'])}\n"
            f"2. <b>Línea:</b> {escape(datos['linea'])}\n"
            f"3. <b>Cantidad:</b> {datos['cantidad']}\n"
            f"4. <b>Resp:</b> {escape(datos['responsable'])}\n"
            f"5. <b>Detalles:</b> {escape(datos['descripcion'])}\n\n"
            f"¿Los datos son correctos? (Responde <b>SI</b> o <b>NO</b>)"
        )
        return FSMResult(exito=True, mensaje=resumen, nuevo_estado=None)

    def _handle_confirmacion(self, user_id: int, mensaje: str, conv: dict, datos: dict) -> FSMResult:
        if mensaje.upper() in ['SI', 'SÍ']:
            datos['confirmando_extraccion'] = False
            
            guardado = self._guardar_registro(user_id, conv)
            if guardado:
                resumen = self._generar_resumen(conv)
                self._state_repo.finalizar(user_id)
                return FSMResult(exito=True, finalizado=True, mensaje=f"<b>¡Reporte guardado con éxito!</b>\n\n{resumen}\n\n<i>Para reportar otro defecto, simplemente envíame fotos nuevas.</i>")
            else:
                return FSMResult(exito=False, finalizado=True, mensaje="Error al guardar el registro en base de datos.")
                
        elif mensaje.upper() == 'NO':
            datos['confirmando_extraccion'] = False
            datos['eligiendo_campo_correccion'] = True
            self._state_repo.guardar(user_id, conv)
            return FSMResult(exito=True, mensaje="De acuerdo. ¿Qué número de dato deseas corregir? (1 al 5)")
        else:
            return FSMResult(exito=False, mensaje="⚠️ Por favor responde <b>SI</b> o <b>NO</b>.")

    def _handle_eleccion_correccion(self, user_id: int, mensaje: str, conv: dict, datos: dict) -> FSMResult:
        if mensaje not in ['1', '2', '3', '4', '5']:
            return FSMResult(exito=False, mensaje="⚠️ Por favor responde con un número del 1 al 5.")
        
        datos['eligiendo_campo_correccion'] = False
        if mensaje == '1': datos['modelo'] = None
        elif mensaje == '2': datos['linea'] = None
        elif mensaje == '3': datos['cantidad'] = None
        elif mensaje == '4': datos['responsable'] = None
        elif mensaje == '5': datos['descripcion'] = None

        result = self._avanzar_siguiente_campo_vacio(conv, datos)
        self._state_repo.guardar(user_id, conv)
        return result
