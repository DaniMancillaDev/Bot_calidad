import os
import shutil
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from workspace.models import ImportSession
from calidad.models import RegistroDefecto, EvidenciaFotografica

# Asumimos que DjangoContadorRepository está en shared.infrastructure.database.django_contador_repository
from shared.infrastructure.database.django_contador_repository import DjangoContadorRepository
from shared.utils.signals_utils import disable_telegram_signals
# Asumimos que celery tasks existen, si no las importaremos dinámicamente o ignoraremos si no aplican
# from calidad.tasks import generate_reports_bulk
# from workspace.tasks import cleanup_workspace_folder

@transaction.atomic()
def confirm_import(session_uuid, user):
    # Usar select_for_update para evitar modificaciones concurrentes a la sesión
    session = ImportSession.objects.select_for_update().get(uuid=session_uuid)
    
    if session.status != 'READY':
        raise ValueError(f"La sesión no está lista para confirmar. Estado actual: {session.status}")
    
    # 0. Revalidar que todos los drafts tengan al menos una foto y sean válidos
    drafts = list(session.drafts.all().order_by('row_index'))
    for draft in drafts:
        if not draft.is_valid:
            raise ValueError(f"Fila {draft.row_index} es inválida.")
        if not draft.assigned_photos or len(draft.assigned_photos) == 0:
            raise ValueError(f"Fila {draft.row_index} no tiene fotos asignadas.")
            
    # 1. Reservar IDs globales
    counter = DjangoContadorRepository()
    ids = counter.obtener_y_avanzar_lote(user.id, len(drafts))
    
    # 2. Silenciar señales de Telegram
    with disable_telegram_signals():
        registros_creados = []
        for idx, draft in enumerate(drafts):
            mapped = draft.mapped_data
            
            # Crear RegistroDefecto real
            registro = RegistroDefecto(
                id=ids[idx],  # Asignar ID global
                modelo=mapped.get('modelo', 'Desconocido'),
                linea=mapped.get('linea', 'N/A'),
                cantidad=int(mapped.get('cantidad', 1) if mapped.get('cantidad') else 1),
                descripcion=f"Falla: {mapped.get('defecto', 'N/A')}. {mapped.get('comentarios', '')}",
                responsable=mapped.get('responsable', 'N/A'),
                numero_parte=mapped.get('numero_parte', ''),
                turno=mapped.get('turno', ''),
                departamento=mapped.get('departamento', ''),
                user_id=user.id,
                fecha_registro=timezone.now(),
            )
            registro.save()
            
            # Mover fotos de workspace a evidencia
            for photo_name in draft.assigned_photos:
                src = os.path.join(settings.MEDIA_ROOT, session.zip_extract_path, 'photos', photo_name)
                # Crear nombre único físico
                dst_name = f"{registro.id}_{photo_name}"
                dst_folder = os.path.join(settings.MEDIA_ROOT, 'fotos', str(user.id))
                os.makedirs(dst_folder, exist_ok=True)
                dst = os.path.join(dst_folder, dst_name)
                
                if os.path.exists(src):
                    shutil.move(src, dst)
                    EvidenciaFotografica.objects.create(
                        registro=registro,
                        ruta_archivo=f"fotos/{user.id}/{dst_name}"
                    )
            
            registros_creados.append(registro.id)
    
    # 3. Marcar sesión como confirmada
    session.status = 'CONFIRMED'
    session.save(update_fields=['status'])
    
    # 4. Disparar reportes y limpieza asíncrona
    # generate_reports_bulk.delay(registros_creados)
    from workspace.tasks import cleanup_workspace_folder
    cleanup_workspace_folder.delay(session.zip_extract_path)
    
    return registros_creados
