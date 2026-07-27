import unittest
from shared.utils.photo_parser import parse_photo_numbers

class PhotoParserTest(unittest.TestCase):
    
    def test_single_number(self):
        self.assertEqual(parse_photo_numbers("1"), [1])
        self.assertEqual(parse_photo_numbers("42"), [42])

    def test_comma_separated(self):
        self.assertEqual(parse_photo_numbers("1,2,3"), [1, 2, 3])
        self.assertEqual(parse_photo_numbers("1, 2, 3"), [1, 2, 3])
        
    def test_range(self):
        self.assertEqual(parse_photo_numbers("1-5"), [1, 2, 3, 4, 5])
        self.assertEqual(parse_photo_numbers("1 - 5"), [1, 2, 3, 4, 5])
        
    def test_mixed(self):
        self.assertEqual(parse_photo_numbers("1-3,5,8-10"), [1, 2, 3, 5, 8, 9, 10])
        
    def test_legacy_parentheses_range(self):
        self.assertEqual(parse_photo_numbers("(001-005)"), [1, 2, 3, 4, 5])
        
    def test_legacy_parentheses_single(self):
        self.assertEqual(parse_photo_numbers("(001)"), [1])
        
    def test_empty_string(self):
        self.assertEqual(parse_photo_numbers(""), [])
        
    def test_none(self):
        self.assertEqual(parse_photo_numbers(None), [])
        
    def test_invalid_text(self):
        self.assertEqual(parse_photo_numbers("texto inválido"), [])
        
    def test_non_string_input(self):
        # Should gracefully handle unexpected types
        self.assertEqual(parse_photo_numbers(123), [123])
