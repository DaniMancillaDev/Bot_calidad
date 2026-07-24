import os
import logging
from django.db import migrations
from django.conf import settings

logger = logging.getLogger(__name__)

def migrate_fotos(apps, schema_editor):
    RegistroDefecto = apps.get_model('calidad', 'RegistroDefecto')
    EvidenciaFotografica = apps.get_model('calidad', 'EvidenciaFotografica')
    
    registros = RegistroDefecto.objects.exclude(fotos_nums__exact=[]).exclude(fotos_nums__isnull=True)
    
    evidencias_to_create = []
    
    for registro in registros:
        for idx, foto_num in enumerate(registro.fotos_nums):
            ruta_relativa = f"fotos/{registro.user_id}/{foto_num}.jpg"
            ruta_absoluta = os.path.join(settings.MEDIA_ROOT, ruta_relativa)
            
            missing = not os.path.exists(ruta_absoluta)
            if missing:
                logger.warning(f"Migración V2: Falta imagen física {ruta_absoluta} (Registro {registro.id})")
            
            evidencia = EvidenciaFotografica(
                registro=registro,
                ruta_archivo=ruta_relativa,
                orden=idx,
                es_portada=(idx == 0),
                metadatos={'missing_file': missing} if missing else {}
            )
            evidencias_to_create.append(evidencia)
    
    if evidencias_to_create:
        EvidenciaFotografica.objects.bulk_create(evidencias_to_create)
        logger.info(f"Migración V2: {len(evidencias_to_create)} evidencias creadas.")

def reverse_migrate(apps, schema_editor):
    EvidenciaFotografica = apps.get_model('calidad', 'EvidenciaFotografica')
    EvidenciaFotografica.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('calidad', '0006_evidenciafotografica'),
    ]

    operations = [
        migrations.RunPython(migrate_fotos, reverse_migrate),
    ]
