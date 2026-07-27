"""
Validadores puros para el flujo de registro.

Regla: NO cambiar comportamiento. Estos helpers solo encapsulan la validación
que ya existía inline (o era permisiva) en RegistroService.
"""


def validar_cantidad(texto: str) -> bool:
    """
    Retorna True si el texto representa un entero positivo (solo dígitos).
    Mantiene la semántica de `str.isdigit()` usada previamente.
    """
    return texto.isdigit()


def validar_modelo(texto: str) -> bool:
    """
    En el flujo actual cualquier string es aceptado como modelo.
    Se deja el hook para endurecer reglas en futuras fases.
    """
    return True


def validar_linea(texto: str) -> bool:
    """
    Valida que la línea exista en el Enum definido en models.
    """
    from calidad.models import Linea
    return texto.upper() in Linea.values


def validar_responsable(texto: str) -> bool:
    """
    Se permite cualquier texto libre para responsable (ej. "Otro").
    El Enum en models sirve solo como sugerencias principales.
    """
    return bool(texto.strip())

