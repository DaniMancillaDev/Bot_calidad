from typing import List

def formatear_rango_fotos(fotos: List[int]) -> str:
    """
    Formatea una lista de números de fotos en rangos contiguos con padding de 3 ceros.
    Ejemplo: [1, 2, 3, 5] -> "(001-003)(005)"
    """
    if not fotos:
        return ""

    fotos = sorted(fotos)
    rangos = []
    inicio = fin = fotos[0]

    for foto in fotos[1:]:
        if foto == fin + 1:
            fin = foto
        else:
            if inicio == fin:
                rangos.append(f"{inicio:03d}")
            else:
                rangos.append(f"{inicio:03d}-{fin:03d}")
            inicio = fin = foto

    if inicio == fin:
        rangos.append(f"{inicio:03d}")
    else:
        rangos.append(f"{inicio:03d}-{fin:03d}")

    return "".join([f"({rango})" for rango in rangos])


import re

def abreviar_modelo(modelo: str) -> str:
    """
    Abrevia un modelo largo preservando prefijo (marca/tamaño) y sufijo (panel).
    Soporta formatos inversos (50HFL, 65PUL) y normales (NS-50, K-100).
    Ej: '50HFL5214U/27 AMP CHOT' -> '50HFL CHOT'
    Ej: 'NS-55F501NA26 AUO' -> 'NS-55 AUO'
    """
    if len(modelo) <= 11:
        return modelo
        
    palabras = modelo.split()
    if len(palabras) >= 2:
        # Panel suele ser la última palabra
        panel = palabras[-1]
        
        # Procesar prefijo extrayendo bloque de Letras+Números o Números+Letras
        match = re.match(r'^([A-Za-z]+[-]?\d{2,3}|\d{2,3}[A-Za-z]+)', palabras[0])
        prefijo = match.group(1) if match else palabras[0][:6]
            
        return f"{prefijo} {panel}"
        
    return f"{modelo[:6]}..{modelo[-3:]}"
