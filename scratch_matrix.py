import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Bot_calidad.settings')
sys.path.append('/home/danim/Proyectos/Bot_calidad/web')
sys.path.append('/home/danim/Proyectos/Bot_calidad')
django.setup()

from web.calidad.views import _parse_fotos_nums, _get_min_foto
from shared.utils.photo_parser import parse_photo_numbers

class MockRegistro:
    def __init__(self, fotos):
        self.fotos = fotos
        self.id = 1
        self.user_id = 1
        self.v2_count = 0
        self.fotos_nums = None # Let the legacy function use string parsing

cases = [
    "1",
    "1,2,3",
    "1-5",
    "(001-005)",
    "invalid",
    "",
    None,
    "1, 2-4, 6",
    "001, 002, 003",
    "foto1, foto2"
]

print("| Caso (String) | _parse_fotos_nums (Legacy) | _get_min_foto (TXT/ZIP) | photo_parser.py (Nuevo) | ¿Coinciden? |")
print("|---|---|---|---|---|")

for case in cases:
    # 1. _parse_fotos_nums
    mock_qs = [MockRegistro(case)]
    try:
        parsed_legacy_dict = _parse_fotos_nums(mock_qs)[0]
        res_parse_fotos = parsed_legacy_dict['fotos_nums']
    except Exception as e:
        res_parse_fotos = f"ERROR: {e}"

    # 2. _get_min_foto
    try:
        res_get_min = _get_min_foto(MockRegistro(case))
    except Exception as e:
        res_get_min = f"ERROR: {e}"

    # 3. photo_parser
    try:
        res_photo_parser = parse_photo_numbers(case)
    except Exception as e:
        res_photo_parser = f"ERROR: {e}"
        
    coinciden = "Sí" if res_parse_fotos == res_photo_parser else "No"
    
    # Format strings for markdown
    c_str = str(case).replace('|', '\\|') if case is not None else "None"
    print(f"| `{c_str}` | `{res_parse_fotos}` | `{res_get_min}` | `{res_photo_parser}` | {coinciden} |")

