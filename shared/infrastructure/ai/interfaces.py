from typing import Protocol, runtime_checkable, TypedDict

# ============================================================
# IA — Traducción de defectos
# ============================================================

class DefectTranslation(TypedDict):
    defect_en: str
    simple_analysis_en: str

@runtime_checkable
class IDefectTranslator(Protocol):
    """
    Contrato para el servicio de traducción de defectos con IA.
    """
    def translate(self, descripcion: str, area: str) -> DefectTranslation: ...
