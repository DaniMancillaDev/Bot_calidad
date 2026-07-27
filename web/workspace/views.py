import os
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
from .models import ImportSession, DraftRegistro
from .tasks import process_workspace_upload
from .services.confirmation import confirm_import
from django.core.paginator import Paginator

@login_required
@require_http_methods(["GET"])
def workspace_ui(request, session_uuid):
    session = get_object_or_404(ImportSession, uuid=session_uuid, supervisor=request.user)
    return render(request, 'workspace/workspace.html', {'session_uuid': session.uuid})

@csrf_exempt
@login_required
@require_http_methods(["POST"])
def upload_workspace(request):
    excel_file = request.FILES.get('excel')
    zip_file = request.FILES.get('zip')
    
    if not excel_file or not zip_file:
        return JsonResponse({'error': 'Faltan archivos'}, status=400)
        
    session = ImportSession.objects.create(
        supervisor=request.user,
        excel_original_name=excel_file.name,
        zip_original_name=zip_file.name
    )
    
    tmp_dir = os.path.join(settings.MEDIA_ROOT, 'workspace', 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    
    zip_path = os.path.join(tmp_dir, f"{session.uuid}.zip")
    with open(zip_path, 'wb+') as dest:
        for chunk in zip_file.chunks():
            dest.write(chunk)
            
    # Guardar excel (preservar extension)
    ext = os.path.splitext(excel_file.name)[1]
    excel_path = os.path.join(tmp_dir, f"{session.uuid}_excel{ext}")
    with open(excel_path, 'wb+') as dest:
        for chunk in excel_file.chunks():
            dest.write(chunk)
            
    process_workspace_upload.delay(session.uuid)
    
    return JsonResponse({'uuid': str(session.uuid)})

@login_required
@require_http_methods(["GET"])
def workspace_status(request, session_uuid):
    session = get_object_or_404(ImportSession, uuid=session_uuid, supervisor=request.user)
    return JsonResponse({
        'status': session.status,
        'total_rows': session.total_rows,
        'validated_rows': session.validated_rows,
        'error_message': session.error_message,
    })

@login_required
@require_http_methods(["GET"])
def api_drafts(request):
    session_uuid = request.GET.get('session')
    session = get_object_or_404(ImportSession, uuid=session_uuid, supervisor=request.user)
    
    drafts_qs = session.drafts.all().order_by('row_index')
    
    page = request.GET.get('page', 1)
    paginator = Paginator(drafts_qs, 10)
    drafts_page = paginator.get_page(page)
    
    data = []
    for d in drafts_page:
        data.append({
            'id': d.id,
            'row_index': d.row_index,
            'mapped_data': d.mapped_data,
            'assigned_photos': d.assigned_photos,
            'is_valid': d.is_valid,
            'validation_errors': d.validation_errors
        })
        
    return JsonResponse({
        'results': data,
        'has_next': drafts_page.has_next(),
        'has_previous': drafts_page.has_previous(),
        'num_pages': paginator.num_pages,
        'current_page': drafts_page.number
    })

@csrf_exempt
@login_required
@require_http_methods(["GET", "PATCH"])
def api_draft_detail(request, draft_id):
    draft = get_object_or_404(DraftRegistro, id=draft_id, session__supervisor=request.user)
    
    if request.method == "GET":
        return JsonResponse({
            'id': draft.id,
            'row_index': draft.row_index,
            'raw_data': draft.raw_data,
            'mapped_data': draft.mapped_data,
            'assigned_photos': draft.assigned_photos,
            'is_valid': draft.is_valid,
            'validation_errors': draft.validation_errors
        })
        
    if request.method == "PATCH":
        data = json.loads(request.body)
        if 'mapped_data' in data:
            draft.mapped_data.update(data['mapped_data'])
        if 'assigned_photos' in data:
            draft.assigned_photos = data['assigned_photos']
            
        draft.is_valid = False # Forzar revalidacion despues
        draft.save()
        return JsonResponse({'status': 'ok'})

@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_validate_all(request, session_uuid):
    session = get_object_or_404(ImportSession, uuid=session_uuid, supervisor=request.user)
    drafts = session.drafts.all()
    
    valid_count = 0
    for draft in drafts:
        errors = []
        md = draft.mapped_data
        
        # Validaciones basicas
        if not md.get('modelo'):
            errors.append("Modelo requerido.")
        if not md.get('cantidad'):
            errors.append("Cantidad requerida.")
        if not draft.assigned_photos or len(draft.assigned_photos) == 0:
            errors.append("Se requiere al menos 1 foto.")
            
        draft.validation_errors = errors
        draft.is_valid = len(errors) == 0
        draft.save()
        
        if draft.is_valid:
            valid_count += 1
            
    session.validated_rows = valid_count
    if valid_count == session.total_rows and session.total_rows > 0:
        session.status = 'READY'
    else:
        session.status = 'DRAFT'
    session.save()
    
    return JsonResponse({
        'total_rows': session.total_rows,
        'validated_rows': session.validated_rows,
        'status': session.status
    })

@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_confirm(request, session_uuid):
    try:
        registros = confirm_import(session_uuid, request.user)
        return JsonResponse({'status': 'ok', 'creados': len(registros)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
