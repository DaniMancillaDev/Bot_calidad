import unittest
import re

class LegacyParserBehaviorsTest(unittest.TestCase):
    """
    Test para documentar y capturar el comportamiento restrictivo actual (legacy)
    de ciertas vistas (galeria, descargar_txt) antes de decidir si migrar al photo_parser nuevo.
    """

    def test_galeria_view_parser(self):
        # Implementación actual en views.py:501
        fotos_str = "1-5"
        nums = [int(n) for n in re.findall(r'\d+', str(fotos_str))]
        rangos = re.findall(r'\((\d+)-(\d+)\)', str(fotos_str))
        for inicio, fin in rangos:
            nums.extend(range(int(inicio), int(fin) + 1))
            
        # El comportamiento legacy extrae [1, 5] en vez de [1, 2, 3, 4, 5] si faltan los paréntesis.
        self.assertEqual(sorted(list(set(nums))), [1, 5])
        
        # Con paréntesis sí funciona
        fotos_str_parenthesis = "(1-5)"
        nums_p = [int(n) for n in re.findall(r'\d+', str(fotos_str_parenthesis))]
        rangos_p = re.findall(r'\((\d+)-(\d+)\)', str(fotos_str_parenthesis))
        for inicio, fin in rangos_p:
            nums_p.extend(range(int(inicio), int(fin) + 1))
            
        self.assertEqual(sorted(list(set(nums_p))), [1, 2, 3, 4, 5])

    def test_descargar_txt_min_foto_parser(self):
        # Implementación actual en views.py:1028 y 1088 (helper _min_foto)
        fotos_str = "1-5"
        nums = re.findall(r'\d+', str(fotos_str or ''))
        min_foto = int(nums[0]) if nums else 99999
        
        # El comportamiento legacy ignora los rangos completamente y solo toma los dígitos sueltos,
        # lo que da como resultado min_foto = 1.
        self.assertEqual(min_foto, 1)
        self.assertEqual(nums, ['1', '5']) # Demuestra que no expande el rango
