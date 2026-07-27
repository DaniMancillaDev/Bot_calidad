"""
shared/infrastructure/ai/defect_translator.py

Traduce descripción de defecto (español) a nomenclatura corporativa (inglés)
durante la generación del reporte Excel.

Implementación híbrida (V1.5): Catálogo JSON determinístico + Fallback Ollama.

Flujo:
  descripcion → normalize → exact_match? → component + symptom? → material_area
                                                                  → LLM fallback si no hay match
"""
import os
import re
import json
import logging
import unicodedata
from typing import Optional, Tuple
from pathlib import Path

from openai import OpenAI

from shared.infrastructure.ai.interfaces import IDefectTranslator, DefectTranslation

logger = logging.getLogger(__name__)

# ============================================================
# SYSTEM PROMPT (Reducido — solo fallback para desconocidos)
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
5. Utilizar terminología industrial corta y concisa.
6. Evitar traducciones literales que no sean utilizadas en entornos de manufactura.

---

# FORMATO DE RESPUESTA

Responder únicamente:
{"defect_en": "..."}
""".strip()

# ============================================================
# CATÁLOGO JSON
# ============================================================
CATALOG_PATH = Path(__file__).parent / "defect_catalog.json"
CATALOG: dict = {}

def load_catalog() -> None:
    """Carga el catálogo JSON en memoria. Llamado al importar el módulo."""
    global CATALOG
    try:
        if CATALOG_PATH.exists():
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                CATALOG = json.load(f)
            logger.info("Catálogo de defectos JSON cargado correctamente.")
        else:
            logger.warning("No se encontró defect_catalog.json en %s", CATALOG_PATH)
    except Exception as e:
        logger.error("Error cargando defect_catalog.json: %s", e)

load_catalog()

# ============================================================
# NORMALIZADOR
# ============================================================

def normalize_text(text: str) -> str:
    """Convierte a minúsculas, elimina acentos y normaliza espacios."""
    if not text:
        return ""
    text = text.lower().strip()
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'\s+', ' ', text)

# ============================================================
# MOTOR DETERMINÍSTICO (retorna defect_en + area_en)
# ============================================================

def deterministic_translate_defect(descripcion: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Busca coincidencias en el catálogo JSON.

    Retorna (defect_en, area_en) si hay match, o (None, None) para fallback LLM.

    Flujo:
      1. Match exacto en exact_matches.
      2. Match de componente (longest-match) + síntoma opcional.
      3. Área derivada de material_areas según componente detectado.
    """
    norm_desc = normalize_text(descripcion)

    # --- 1. Match Exacto ---
    exact_matches: dict = CATALOG.get("exact_matches", {})
    for raw_key, canonical in exact_matches.items():
        if normalize_text(raw_key) == norm_desc:
            # Los exact_matches no tienen área definida, buscar en material_areas
            area = CATALOG.get("material_areas", {}).get(canonical, "UNKNOWN")
            return canonical, area

    # --- 2. Match Componente + Síntoma ---
    components: dict = CATALOG.get("components", {})
    symptoms: dict   = CATALOG.get("symptoms",   {})
    material_areas: dict = CATALOG.get("material_areas", {})
    connectors: dict = CATALOG.get("connectors", {})

    # Normalizar claves del catálogo en tiempo de búsqueda
    found_component: Optional[str] = None
    found_symptom:   Optional[str] = None
    component_raw_key: Optional[str] = None
    symptom_raw_key: Optional[str] = None

    # Longest-match en componentes (evita que "blu" gane sobre "metal blu")
    for raw_key, canonical in sorted(components.items(), key=lambda x: len(x[0]), reverse=True):
        norm_key = normalize_text(raw_key)
        if norm_key in norm_desc:
            found_component = canonical
            component_raw_key = norm_key
            break

    # Longest-match en síntomas
    for raw_key, symptom_en in sorted(symptoms.items(), key=lambda x: len(x[0]), reverse=True):
        norm_key = normalize_text(raw_key)
        if norm_key in norm_desc:
            found_symptom = symptom_en
            symptom_raw_key = norm_key
            break

    if found_component:
        area = material_areas.get(found_component, "UNKNOWN")
        
        connector_en: Optional[str] = None
        if found_symptom and component_raw_key and symptom_raw_key:
            idx_comp = norm_desc.find(component_raw_key)
            idx_sym = norm_desc.find(symptom_raw_key)
            if idx_comp != -1 and idx_sym != -1:
                # Extraer texto entre componente y síntoma
                if idx_comp < idx_sym:
                    between = norm_desc[idx_comp + len(component_raw_key):idx_sym]
                else:
                    between = norm_desc[idx_sym + len(symptom_raw_key):idx_comp]
                
                # Buscar conectores en el texto intermedio
                padded_between = f" {normalize_text(between)} "
                for conn_key, conn_en in sorted(connectors.items(), key=lambda x: len(x[0]), reverse=True):
                    norm_conn = normalize_text(conn_key)
                    if f" {norm_conn} " in padded_between:
                        connector_en = conn_en
                        break
                        
        if found_symptom:
            if connector_en:
                defect_en = f"{found_component} {connector_en} {found_symptom}"
            else:
                defect_en = f"{found_component} {found_symptom}"
        else:
            defect_en = found_component
            
        return defect_en, area

    # --- Sin match: log y retornar None para fallback ---
    logger.warning("[CATALOG_MISS] %s", descripcion)
    return None, None


def translate_area(area: str) -> str:
    """
    Traducción determinística de áreas (usada solo cuando el fallback LLM produce defecto
    pero no tiene área en el catálogo, o para compatibilidad con otros módulos).
    """
    norm_area = normalize_text(area)
    areas_dict: dict = CATALOG.get("areas", {})
    for k, v in areas_dict.items():
        if k in norm_area:
            return v
    return area.strip().upper() if area else ""


# ============================================================
# IMPLEMENTACIÓN HÍBRIDA (JSON + OLLAMA)
# ============================================================

class OllamaDefectTranslator(IDefectTranslator):
    """
    Implementación híbrida: Motor determinístico primero, LLM como fallback.

    Prioridad de área:
      1. material_areas del catálogo (si hay match determinístico).
      2. UNKNOWN (si el catálogo no tiene entrada para el material).
      3. LLM fallback: usa translate_area() sobre el argumento `area` recibido.
    """

    def __init__(self):
        api_key  = os.getenv("OLLAMA_API_KEY", "ollama")
        base_url = os.getenv(
            "OLLAMA_BASE_URL",
            os.getenv("DEEPSEEK_BASE_URL", "http://localhost:11434/v1")
        )
        self.model   = os.getenv("OLLAMA_TRANSLATE_MODEL", "qwen2.5:1.5b")
        self.timeout = float(os.getenv("OLLAMA_TRANSLATE_TIMEOUT", "30"))

        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=self.timeout,
            )
            logger.info(
                "OllamaDefectTranslator inicializado | model=%s url=%s",
                self.model, base_url
            )
        except Exception as e:
            logger.error("Error inicializando OllamaDefectTranslator: %s", e)
            self.client = None

    def translate(self, descripcion: str, area: str = "") -> DefectTranslation:
        """
        Retorna DefectTranslation con defect_en y simple_analysis_en.
        Si falla por cualquier causa, retorna strings vacíos (safe degraded mode).
        """
        _empty: DefectTranslation = {"defect_en": "", "simple_analysis_en": ""}

        descripcion = (descripcion or "").strip()
        if not descripcion:
            return _empty

        # ── 1. Intento Determinístico ──────────────────────────────────────
        defect_en, area_en = deterministic_translate_defect(descripcion)

        if defect_en:
            logger.debug(
                "DefectTranslator (Catálogo) OK | '%s' → '%s' | área=%s",
                descripcion[:40], defect_en, area_en
            )
            simple_analysis = f"AT {area_en} AREA WAS DETECTED {defect_en}"
            return {"defect_en": defect_en, "simple_analysis_en": simple_analysis}

        # ── 2. Fallback LLM ────────────────────────────────────────────────
        if not self.client:
            return _empty

        # El área en el fallback LLM se traduce del argumento recibido
        area_en_fallback = translate_area(area) if area else "UNKNOWN"

        user_msg = f"DEFECTO:\n{descripcion}"

        try:
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
                logger.warning(
                    "DefectTranslator: respuesta vacía | descripcion=%s", descripcion[:60]
                )
                return _empty

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
                    logger.error(
                        "DefectTranslator: JSON inválido tras regex | raw=%s", raw[:200]
                    )
                    return _empty

            defect_en = (data.get("defect_en") or "").strip().upper().replace("_", " ")

            if not defect_en:
                logger.warning(
                    "DefectTranslator: defect_en vacío | descripcion=%s | raw=%s",
                    descripcion[:60], raw[:200]
                )
                return _empty

            simple_analysis = f"AT {area_en_fallback} AREA WAS DETECTED {defect_en}"

            logger.debug(
                "DefectTranslator (LLM) OK | '%s' → '%s' | área=%s",
                descripcion[:40], defect_en, area_en_fallback
            )
            return {"defect_en": defect_en, "simple_analysis_en": simple_analysis}

        except Exception as e:
            logger.error(
                "DefectTranslator.translate() excepción | descripcion=%s | error=%s",
                descripcion[:60], e
            )
            return _empty


# ============================================================
# NULL TRANSLATOR — fallback / tests sin IA
# ============================================================

class NullDefectTranslator(IDefectTranslator):
    def translate(self, descripcion: str, area: str = "") -> DefectTranslation:
        return {"defect_en": "", "simple_analysis_en": ""}


# ============================================================
# FACTORY
# ============================================================

def build_translator() -> IDefectTranslator:
    if os.getenv("EXCEL_AI_ENABLED", "false").lower() in ("true", "1", "yes"):
        return OllamaDefectTranslator()
    return NullDefectTranslator()
