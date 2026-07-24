import logging
from django.conf import settings
from calidad.models import RegistroDefecto, EvidenciaFotografica

logger = logging.getLogger(__name__)

def sync_fotos_to_evidencias(registro: RegistroDefecto):
    """
    Sincroniza el ArrayField `fotos_nums` (Legacy) hacia el nuevo modelo `EvidenciaFotografica` (V2).
    Esta función asume que es llamada después de que el bot inserta las fotos en el registro.
    Es idempotente: no creará duplicados.
    """
    if not registro.fotos_nums:
        return
        
    evidencias_existentes = set(
        EvidenciaFotografica.objects.filter(registro=registro)
        .values_list('ruta_archivo', flat=True)
    )
    
    nuevas_evidencias = []
    from calidad.utils import get_best_image_path
    fotos_dir = settings.MEDIA_ROOT / "fotos"
    
    for idx, foto_num in enumerate(registro.fotos_nums):
        real_path = get_best_image_path(fotos_dir, str(registro.user_id), foto_num)
        if not real_path:
            logger.warning(f"No se encontró archivo para foto {foto_num} de registro {registro.id}")
            continue

        try:
            ruta_relativa = str(real_path.relative_to(settings.MEDIA_ROOT))
        except ValueError:
            ruta_relativa = str(real_path)
        
        if ruta_relativa not in evidencias_existentes:
            # Determinamos si es portada (la primera del array que no existía)
            # Solo si no hay ninguna evidencia previa, la primera es portada
            es_portada = (idx == 0 and not evidencias_existentes)
            
            evidencia = EvidenciaFotografica(
                registro=registro,
                ruta_archivo=ruta_relativa,
                orden=idx,
                es_portada=es_portada,
            )
            nuevas_evidencias.append(evidencia)
            evidencias_existentes.add(ruta_relativa)
            
    if nuevas_evidencias:
        EvidenciaFotografica.objects.bulk_create(nuevas_evidencias)
        logger.info(f"Sync Legacy->V2: {len(nuevas_evidencias)} evidencias sincronizadas para Registro {registro.id}")
