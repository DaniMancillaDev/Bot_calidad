import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from calidad.models import RegistroDefecto, EvidenciaFotografica
from calidad.api.serializers_v2 import serialize_registro
from calidad.api.services_v2 import obtener_lotes, obtener_registros_de_lote

logger = logging.getLogger(__name__)

# Nota: csrf_exempt para facilitar desarrollo rápido, en prod requeriremos Token/Session
@csrf_exempt
@require_http_methods(["GET"])
def api_get_lotes(request):
    try:
        lotes = obtener_lotes()
        return JsonResponse({'status': 'success', 'lotes': lotes})
    except Exception as e:
        logger.error(f"Error api_get_lotes: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def api_get_registros_por_lote(request, lote_id):
    try:
        registros = obtener_registros_de_lote(lote_id)
        data = [serialize_registro(r) for r in registros]
        return JsonResponse({'status': 'success', 'registros': data})
    except Exception as e:
        logger.error(f"Error api_get_registros: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["PATCH"])
def api_patch_registro(request, registro_id):
    try:
        data = json.loads(request.body)
        registro = RegistroDefecto.objects.get(id=registro_id)

        # Campos editables directos
        CAMPOS_DIRECTOS = ["numero_parte", "linea", "cantidad", "descripcion", "responsable", "comentarios_supervisor"]
        update_fields = []
        for campo in CAMPOS_DIRECTOS:
            if campo in data:
                setattr(registro, campo, data[campo])
                update_fields.append(campo)

        if update_fields:
            registro.save(update_fields=update_fields)

        # Transición de estado centralizada
        if 'estado_revision' in data:
            nuevo_estado = data['estado_revision']
            comentarios = data.get('comentarios', '')
            supervisor = request.user if request.user.is_authenticated else None

            if nuevo_estado == 'aprobado':
                registro.aprobar(supervisor=supervisor, comentarios=comentarios)
            elif nuevo_estado == 'rechazado':
                registro.rechazar(supervisor=supervisor, comentarios=comentarios)
            else:
                registro.transitar_estado(nuevo_estado, supervisor=supervisor, comentarios=comentarios)

        return JsonResponse({'status': 'success', 'registro': serialize_registro(registro)})
    except RegistroDefecto.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Registro no encontrado'}, status=404)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error api_patch_registro: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def api_rotar_evidencia(request, evidencia_id):
    try:
        data = json.loads(request.body)
        angulo = int(data.get('angulo_rotacion', 0))
        evidencia = EvidenciaFotografica.objects.get(id=evidencia_id)
        
        evidencia.angulo_rotacion = angulo
        evidencia.save(update_fields=['angulo_rotacion'])
        
        return JsonResponse({'status': 'success'})
    except EvidenciaFotografica.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Evidencia no encontrada'}, status=404)
    except Exception as e:
        logger.error(f"Error api_rotar_evidencia: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
def api_delete_evidencia(request, evidencia_id):
    try:
        evidencia = EvidenciaFotografica.objects.get(id=evidencia_id)
        # Soft-delete: add a flag to metadatos so it doesn't appear in the Excel/UI
        if not isinstance(evidencia.metadatos, dict):
            evidencia.metadatos = {}
        evidencia.metadatos['excluida'] = True
        evidencia.save(update_fields=['metadatos'])
        return JsonResponse({'status': 'success'})
    except EvidenciaFotografica.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Evidencia no encontrada'}, status=404)
    except Exception as e:
        logger.error(f"Error api_delete_evidencia: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def api_restore_evidencia(request, evidencia_id):
    try:
        evidencia = EvidenciaFotografica.objects.get(id=evidencia_id)
        if isinstance(evidencia.metadatos, dict) and 'excluida' in evidencia.metadatos:
            evidencia.metadatos['excluida'] = False
            evidencia.save(update_fields=['metadatos'])
        return JsonResponse({'status': 'success'})
    except EvidenciaFotografica.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Evidencia no encontrada'}, status=404)
    except Exception as e:
        logger.error(f"Error api_restore_evidencia: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
