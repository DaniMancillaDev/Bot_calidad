from calidad.models import RegistroDefecto, EvidenciaFotografica

def serialize_evidencia(ev: EvidenciaFotografica) -> dict:
    return {
        'id': ev.id,
        'ruta_archivo': ev.ruta_archivo,
        'orden': ev.orden,
        'es_portada': ev.es_portada,
        'angulo_rotacion': ev.angulo_rotacion,
        'estado_ia': ev.estado_ia,
        'metadatos': ev.metadatos,
    }

def serialize_registro(reg: RegistroDefecto) -> dict:
    evidencias = reg.evidencias_v2.all()
    return {
        'id': reg.id,
        'user_id': reg.user_id,
        'modelo': reg.modelo,
        'numero_parte': reg.numero_parte,
        'linea': reg.linea,
        'cantidad': reg.cantidad,
        'defecto': reg.descripcion,
        'turno': reg.turno,
        'departamento': reg.departamento,
        'estado_revision': reg.estado_revision,
        'fecha_registro': reg.fecha_registro.isoformat() if reg.fecha_registro else None,
        'evidencias': [serialize_evidencia(e) for e in evidencias],
    }
