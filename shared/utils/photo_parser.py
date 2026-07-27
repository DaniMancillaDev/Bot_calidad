import re
from typing import List

def parse_photo_numbers(raw_fotos) -> List[int]:
    """
    Parsea una cadena o valor crudo de fotos y devuelve una lista ordenada de números únicos.
    
    Casos soportados:
    - "1" -> [1]
    - "1,2,3" -> [1, 2, 3]
    - "1-5" -> [1, 2, 3, 4, 5]
    - "1-3,5,8-10" -> [1, 2, 3, 5, 8, 9, 10]
    - "(001-005)" -> [1, 2, 3, 4, 5]
    - "(001)" -> [1]
    - Valores inválidos / None -> []
    """
    if raw_fotos is None:
        return []
        
    try:
        raw_fotos_str = str(raw_fotos)
        nums = []
        
        # 1. Buscar rangos explícitos (ej. "1-5", "(001-005)")
        # La regex captura los números eliminando los paréntesis u otros caracteres
        rangos = re.findall(r'(\d+)\s*-\s*(\d+)', raw_fotos_str)
        for inicio_r, fin_r in rangos:
            nums.extend(range(int(inicio_r), int(fin_r) + 1))
            
        # 2. Buscar todos los números sueltos
        # (Esto también atrapará los números de los rangos, pero los sets lo limpiarán)
        todos_numeros = re.findall(r'\d+', raw_fotos_str)
        nums.extend([int(n) for n in todos_numeros])
        
        # 3. Eliminar duplicados y ordenar
        return sorted(list(set(nums)))
        
    except Exception:
        return []
