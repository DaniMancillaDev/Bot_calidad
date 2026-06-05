"""
shared/infrastructure/ai/defect_translator.py

Traduce descripción de defecto (español) a nomenclatura corporativa (inglés)
durante la generación del reporte Excel.

Solo se invoca desde generate_excel(). NUNCA modifica la base de datos.
Si falla, retorna strings vacíos → el reporte se genera normalmente.

Variables de entorno:
    EXCEL_AI_ENABLED         = true | false (default: false)
    OLLAMA_BASE_URL          = http://localhost:11434/v1
    OLLAMA_TRANSLATE_MODEL   = qwen2.5:1.5b | qwen2.5:3b | gemma3:1b
    OLLAMA_TRANSLATE_TIMEOUT = segundos (default: 30)
    USE_JSON_FORMAT          = true | false (false para modelos que no lo soportan)
"""
import os
import re
import json
import logging
from typing import Optional

from openai import OpenAI

from shared.domain.interfaces import IDefectTranslator, DefectTranslation

logger = logging.getLogger(__name__)

# ============================================================
# SYSTEM PROMPT — nomenclatura corporativa
# NO incluye los placeholders {{DEFECTO}} / {{ÁREA}}.
# Esos van en el mensaje del usuario (ver translate()).
# ============================================================
_SYSTEM_PROMPT = """
# CONTEXTO DEL SISTEMA

Formas parte de un sistema de gestión de calidad utilizado en una planta de manufactura.

Los operadores registran defectos en español utilizando lenguaje cotidiano, abreviaciones, términos internos de la planta y descripciones no estandarizadas.

Tu función es convertir esos defectos a la nomenclatura oficial utilizada por la empresa para la generación de reportes de calidad en inglés.

SOLO debes generar los campos en inglés que serán utilizados en el reporte final.

---

# REGLAS OBLIGATORIAS

1. Responder únicamente JSON válido.
2. No escribir explicaciones ni comentarios.
3. No agregar texto fuera del JSON.
4. Todo debe estar en MAYÚSCULAS.
5. Utilizar terminología industrial.
6. Si dos descripciones representan el mismo defecto, deben generar exactamente el mismo defect_en.
7. Si una descripción contiene errores ortográficos, interpretar correctamente el significado antes de generar el resultado.
8. Evitar traducciones literales que no sean utilizadas normalmente en entornos de manufactura.

---

# FORMATO DEL CAMPO defect_en

Debe contener únicamente el nombre estandarizado del defecto. Breve y estandarizado.

Ejemplos:
ARTWORK CARTON DAMAGED
DIFFUSER PLATE DAMAGED
DIFFUSER SHEET DAMAGED
SPACER WITH LITTLE GLUE
MISSING LABEL
WRONG PART
DAMAGED COMPONENT

# FORMATO DEL CAMPO area_en

Debe ser el nombre del área donde se encontró el defecto, traducido al inglés en UPPERCASE.
Usa las reglas de "NORMALIZACIÓN DE ÁREAS".

---

# EQUIVALENCIAS CORPORATIVAS OBLIGATORIAS (prioridad absoluta)

IMPORTANTE: El valor de defect_en DEBE ser EXACTAMENTE el nombre del encabezado de la sección, sin recortes.

## ARTWORK CARTON DAMAGED
Cuando la descripción sea similar a:
caja dañada, cartón dañado, cartón golpeado, cartón maltratado, cartón aplastado,
cartón roto, caja de arte dañada, empaque dañado, cartón con golpe.

## DIFFUSER PLATE DAMAGED
Cuando la descripción sea similar a:
plato difusor, difusor, placa difusora, difusor dañado, difusor roto, difusora.

## DIFFUSER SHEET DAMAGED
Cuando la descripcion sea similar a:
hoja difusora, hoja dañada, hoja con daño, hoja golpeada, hoja maltratada, hoja rota.

## REFLECTOR FILM DAMAGED
Cuando la descripción sea similar a:
hoja reflectora, papel reflector, reflectora, reflector, film reflector, reflectorda dañada.

## PROTECT BAG DAMAGED
Cuando la descripción sea similar a:
bolsa dañada, bolsa protectora dañada, protect bag.

## DECO
Cuando la descripción sea similar a:
deco, bezel, marco decorativo.

## BACK COVER
Cuando la descripción sea similar a:
cubierta trasera, back cover, rear cover, tapa trasera.

## BLOWER BLADE
Cuando la descripción sea similar a:
metal blu, blower blade.

## SPACER WITH LITTLE GLUE
Cuando la descripción sea similar a:
separador con poca pega, separador sin pega, separador mal pegado,
falta de pegamento en separador, separador con poco adhesivo, separador despegado.

---

# SÍNTOMAS Y ESTADOS COMUNES (TRADUCCIÓN EXACTA)
Aplica estas traducciones directas cuando veas estas palabras:
- doblado -> BENT
- rayado -> SCRATCHED
- aberturas -> GAP

---

# NORMALIZACIÓN DE ÁREAS

DESEMPAQUE → UNPACKING
ENTRADA → INPUT
IQA → INCOMING QUALITY
SQA → OUTGOING QUALITY
PROD → PRODUCTION
ENG → ENGINEERING
Cuarto limpio → CLEAN ROOM

Si el área ya está en inglés, conservarla en UPPERCASE.
Si el área es desconocida, usarla tal cual en UPPERCASE.

---

# MANEJO DE NUEVOS DEFECTOS

Si el defecto no existe en las equivalencias conocidas:
1. Analizar el significado real del defecto.
2. Generar un nombre industrial corto y profesional.
3. Mantener consistencia con nomenclatura de manufactura.
4. Evitar frases largas y traducciones literales.

---

# FORMATO DE RESPUESTA

Responder únicamente:
{"defect_en": "...", "area_en": "..."}
""".strip()

# ============================================================
# IMPLEMENTACIÓN OLLAMA
# ============================================================

class OllamaDefectTranslator:
    """
    Implementación concreta usando Ollama (OpenAI-compatible API).
    Mismo patrón que DeepSeekExtractor.
    """

    def __init__(self):
        api_key  = os.getenv("OLLAMA_API_KEY", "ollama")
        base_url = os.getenv("OLLAMA_BASE_URL",
                             os.getenv("DEEPSEEK_BASE_URL", "http://localhost:11434/v1"))
        self.model   = os.getenv("OLLAMA_TRANSLATE_MODEL", "qwen2.5:1.5b")
        self.timeout = float(os.getenv("OLLAMA_TRANSLATE_TIMEOUT", "30"))

        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self.timeout,
            )
            logger.info("OllamaDefectTranslator inicializado | model=%s url=%s", self.model, base_url)
        except Exception as e:
            logger.error("Error inicializando OllamaDefectTranslator: %s", e)
            self.client = None

    def translate(self, descripcion: str, area: str) -> DefectTranslation:
        """
        Retorna DefectTranslation con defect_en y simple_analysis_en.
        Si falla por cualquier causa, retorna strings vacíos (safe degraded mode).
        """
        _empty: DefectTranslation = {"defect_en": "", "simple_analysis_en": ""}

        if not self.client:
            return _empty

        descripcion = (descripcion or "").strip()
        area        = (area or "").strip()

        if not descripcion:
            return _empty

        user_msg = f"DEFECTO:\n{descripcion}\n\nÁREA:\n{area}"

        try:
            # Algunos modelos ligeros no soportan response_format json_object.
            # USE_JSON_FORMAT=false lo desactiva (igual que en deepseek_extractor).
            use_json = os.getenv("USE_JSON_FORMAT", "true").lower() in ("true", "1", "yes")

            kwargs: dict = dict(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=150,
            )
            if use_json:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            raw = (response.choices[0].message.content or "").strip()

            if not raw:
                logger.warning("DefectTranslator: respuesta vacía | descripcion=%s", descripcion[:60])
                return _empty

            # Parseo JSON con fallback regex (igual que deepseek_extractor)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r'\{.*?\}', raw, re.DOTALL)
                if not match:
                    logger.error("DefectTranslator: JSON inválido | raw=%s", raw[:200])
                    return _empty
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.error("DefectTranslator: JSON inválido tras regex | raw=%s", raw[:200])
                    return _empty

            defect_en = (data.get("defect_en") or "").strip().upper().replace("_", " ")
            area_en   = (data.get("area_en") or "").strip().upper().replace("_", " ")
            
            if not area_en:
                area_en = area.upper()

            simple_analysis = f"AT {area_en} AREA WAS DETECTED {defect_en}"

            if not defect_en:
                logger.warning("DefectTranslator: defect_en vacío | descripcion=%s | raw=%s",
                               descripcion[:60], raw[:200])
                return _empty

            logger.debug("DefectTranslator OK | '%s' → '%s'", descripcion[:40], defect_en)
            return {"defect_en": defect_en, "simple_analysis_en": simple_analysis}

        except Exception as e:
            logger.error("DefectTranslator.translate() excepción | descripcion=%s | error=%s",
                         descripcion[:60], e)
            return _empty


# ============================================================
# NULL TRANSLATOR — fallback / tests
# ============================================================

class NullDefectTranslator:
    """
    Retorna strings vacíos. Usado cuando EXCEL_AI_ENABLED=false
    o como stub en tests unitarios.
    Satisface IDefectTranslator sin dependencias externas.
    """

    def translate(self, descripcion: str, area: str) -> DefectTranslation:
        return {"defect_en": "", "simple_analysis_en": ""}


# ============================================================
# FACTORY
# ============================================================

def build_translator() -> IDefectTranslator:
    """
    Lee EXCEL_AI_ENABLED para decidir qué implementación retornar.
    Rollback inmediato: cambiar env var a false y reiniciar worker.
    """
    if os.getenv("EXCEL_AI_ENABLED", "false").lower() in ("true", "1", "yes"):
        return OllamaDefectTranslator()
    return NullDefectTranslator()
