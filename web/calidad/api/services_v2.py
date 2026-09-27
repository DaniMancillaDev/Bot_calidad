from django.db.models import Count, Q
from calidad.models import RegistroDefecto
from calidad.views import get_registros_permitidos

def obtener_lotes(user=None):
    # Agrupamos los pendientes/activos
    # Un lote será (fecha_registro__date, turno, linea)
    
    if user and user.is_authenticated:
        base_qs = get_registros_permitidos(user)
    else:
        base_qs = RegistroDefecto.objects.all()

    registros = base_qs.filter(
        estado_revision__in=['pendiente', 'revisado', 'editado']
    ).select_related('supervisor').prefetch_related('evidencias_v2')
    
    lotes = {}
    for r in registros:
        if not r.fecha_registro:
            continue
            
        fecha_str = r.fecha_registro.date().isoformat()
        key = f"{fecha_str}_{r.turno}_{r.linea}"
        
        if key not in lotes:
            lotes[key] = {
                'id': key,
                'fecha': fecha_str,
                'turno': r.turno,
                'linea': r.linea,
                'cantidad_registros': 0,
                'portada_url': None
            }
            
        lotes[key]['cantidad_registros'] += 1
        
        if not lotes[key]['portada_url']:
            ev = r.evidencias_v2.filter(es_portada=True).first()
            if ev:
                lotes[key]['portada_url'] = f"/media-protegida/{ev.ruta_archivo}"
                
    return list(lotes.values())

def obtener_registros_de_lote(lote_id: str, user=None):
    parts = lote_id.split('_')
    if len(parts) != 3:
        return []
    fecha, turno, linea = parts
    
    if user and user.is_authenticated:
        base_qs = get_registros_permitidos(user)
    else:
        base_qs = RegistroDefecto.objects.all()

    qs = base_qs.filter(
        fecha_registro__date=fecha,
        turno=turno,
        linea=linea,
        estado_revision__in=['pendiente', 'revisado', 'editado']
    ).prefetch_related('evidencias_v2').order_by('-fecha_registro')
    return list(qs)
