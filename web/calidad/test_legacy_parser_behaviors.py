from django.test import TestCase
from calidad.views import _parse_fotos_nums, _get_min_foto
from shared.utils.photo_parser import parse_photo_numbers

class MockRegistro:
    def __init__(self, fotos):
        self.fotos = fotos
        self.id = 1
        self.user_id = 1
        self.v2_count = 0
        self.fotos_nums = None


class LegacyParserBehaviorTest(TestCase):
    """
    Test de caracterización para capturar explícitamente el comportamiento 
    de los parsers legacy frente al nuevo photo_parser.py.
    No modificar este archivo a menos que haya una decisión de negocio para
    migrar a los nuevos comportamientos funcionales.
    """

    def _get_legacy_parse_fotos_nums(self, fotos_str):
        qs = [MockRegistro(fotos_str)]
        return _parse_fotos_nums(qs)[0]['fotos_nums']

    def _get_legacy_min_foto(self, fotos_str):
        return _get_min_foto(MockRegistro(fotos_str))

    def test_case_single_number(self):
        """Caso 1: '1'"""
        case = "1"
        self.assertEqual(self._get_legacy_parse_fotos_nums(case), [1])
        self.assertEqual(self._get_legacy_min_foto(case), 1)
        self.assertEqual(parse_photo_numbers(case), [1])

    def test_case_comma_separated(self):
        """Caso 2: '1,2,3'"""
        case = "1,2,3"
        self.assertEqual(self._get_legacy_parse_fotos_nums(case), [1, 2, 3])
        self.assertEqual(self._get_legacy_min_foto(case), 1)
        self.assertEqual(parse_photo_numbers(case), [1, 2, 3])

    def test_case_hyphen_range(self):
        """Caso 3: '1-5'"""
        # _parse_fotos_nums AHORA detecta '1-5' correctamente (migrado a photo_parser)
        case = "1-5"
        self.assertEqual(self._get_legacy_parse_fotos_nums(case), [1, 2, 3, 4, 5])
        # TXT/ZIP _get_min_foto sigue siendo legacy, min de 1-5 es 1
        self.assertEqual(self._get_legacy_min_foto(case), 1)
        
        self.assertEqual(parse_photo_numbers(case), [1, 2, 3, 4, 5])

    def test_case_parentheses_range(self):
        """Caso 4: '(001-005)'"""
        # _parse_fotos_nums sí lo detecta por los paréntesis.
        case = "(001-005)"
        self.assertEqual(self._get_legacy_parse_fotos_nums(case), [1, 2, 3, 4, 5])
        self.assertEqual(self._get_legacy_min_foto(case), 1)
        
        # photo_parser extrae y procesa el rango
        self.assertEqual(parse_photo_numbers(case), [1, 2, 3, 4, 5])

    def test_case_invalid_formats(self):
        """Caso 5: formatos inválidos o texto aleatorio"""
        case = "foto uno y dos"
        # _parse_fotos_nums devuelve []
        self.assertEqual(self._get_legacy_parse_fotos_nums(case), [])
        
        # _get_min_foto devuelve 99999 si no hay números
        self.assertEqual(self._get_legacy_min_foto(case), 99999)
        
        self.assertEqual(parse_photo_numbers(case), [])

    def test_case_empty_values(self):
        """Caso 6: valores vacíos ('' o None)"""
        self.assertEqual(self._get_legacy_parse_fotos_nums(""), [])
        self.assertEqual(self._get_legacy_parse_fotos_nums(None), [])
        
        self.assertEqual(self._get_legacy_min_foto(""), 99999)
        self.assertEqual(self._get_legacy_min_foto(None), 99999)
        
        self.assertEqual(parse_photo_numbers(""), [])
        self.assertEqual(parse_photo_numbers(None), [])

    def test_case_mixed_separators(self):
        """Caso 7: mezcla de separadores '1, 2-4, (006-008)'"""
        case = "1, 2-4, (006-008)"
        
        # _parse_fotos_nums AHORA procesa rangos con o sin paréntesis (migrado a photo_parser)
        self.assertEqual(self._get_legacy_parse_fotos_nums(case), [1, 2, 3, 4, 6, 7, 8])
        self.assertEqual(self._get_legacy_min_foto(case), 1)
        
        self.assertEqual(parse_photo_numbers(case), [1, 2, 3, 4, 6, 7, 8])
