"""
Data migration: poblar fotos_nums desde campo legacy fotos (TextField).
Parsea "1, 2, 3" y guarda [1, 2, 3] en ArrayField.
Soporta también formato legacy "(001-005)".
Reversible: rollback limpia fotos_nums, fotos original intacto.
"""
import re
from django.db import migrations


def _parsear_fotos(fotos_str: str) -> list:
    """Soporta '1, 2, 3' y '(001-005)(007)'."""
    nums = set()

    # Formato nuevo: "1, 2, 3"
    if re.search(r'^\s*\d[\d,\s]*$', fotos_str):
        for x in fotos_str.split(','):
            x = x.strip()
            if x.isdigit():
                nums.add(int(x))
        if nums:
            return sorted(nums)

    # Formato legacy con rangos: "(001-005)"
    for inicio, fin in re.findall(r'\((\d+)-(\d+)\)', fotos_str):
        nums.update(range(int(inicio), int(fin) + 1))
    # Individuales: "(007)"
    clean = re.sub(r'\(\d+-\d+\)', '', fotos_str)
    for individual in re.findall(r'\((\d+)\)', clean):
        nums.add(int(individual))

    return sorted(nums)


def poblar_fotos_nums(apps, schema_editor):
    RegistroDefecto = apps.get_model('calidad', 'RegistroDefecto')
    db = schema_editor.connection.alias

    actualizados = errores = 0
    for reg in RegistroDefecto.objects.using(db).all().iterator(chunk_size=500):
        if not reg.fotos:
            continue
        try:
            nums = _parsear_fotos(reg.fotos)
            if nums:
                reg.fotos_nums = nums
                reg.save(using=db, update_fields=['fotos_nums'])
                actualizados += 1
        except Exception:
            errores += 1

    print(f"\n  [data migration] {actualizados} actualizados, {errores} errores.")


def revertir(apps, schema_editor):
    RegistroDefecto = apps.get_model('calidad', 'RegistroDefecto')
    RegistroDefecto.objects.using(schema_editor.connection.alias).update(fotos_nums=[])


class Migration(migrations.Migration):

    dependencies = [
        ('calidad', '0002_phase1_fotos_nums_estados_operativos'),
    ]

    operations = [
        migrations.RunPython(poblar_fotos_nums, revertir),
    ]
