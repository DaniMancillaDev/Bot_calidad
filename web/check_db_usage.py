import os
import django
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from calidad.models import RegistroDefecto, EvidenciaFotografica

total = RegistroDefecto.objects.all().count()
legacy_fotos = RegistroDefecto.objects.exclude(fotos='').count()
fotos_nums = RegistroDefecto.objects.exclude(fotos_nums=[]).count()
evidencias = EvidenciaFotografica.objects.all().count()
estado_ia = EvidenciaFotografica.objects.exclude(estado_ia='PENDIENTE').count()
metadatos = EvidenciaFotografica.objects.exclude(metadatos={}).count()

print(f"Total Registros: {total}")
print(f"Legacy 'fotos' in use: {legacy_fotos}")
print(f"'fotos_nums' in use: {fotos_nums}")
print(f"Total Evidencias: {evidencias}")
print(f"'estado_ia' modified: {estado_ia}")
print(f"'metadatos' modified: {metadatos}")
