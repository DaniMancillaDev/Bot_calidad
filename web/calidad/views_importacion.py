"""
Vistas para el Asistente de Importación Web (V1).
"""
import os
import shutil
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
import json
import os
from calidad.services.importacion import parsear_excel, parsear_txt, extraer_zip_seguro, generar_estado_inicial, commit_importacion

@login_required
def importacion_iniciar(request):
    """
    GET: Renderiza el formulario de carga (Excel + ZIP).
    POST: Recibe archivos y redirige al workspace.
    """
    import os
    if os.getenv("ENABLE_WORKSPACE_V2", "false").lower() in ("true", "1", "yes"):
        return redirect('workspace:upload')

    # Garbage Collection Perezoso: Limpiar carpeta temporal huérfana de este usuario
    session_key = request.session.session_key
    if session_key:
        temp_dir = settings.MEDIA_ROOT / 'importaciones_temp' / session_key
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                pass # Fail silently for cleanup

    if request.method == 'POST':
        data_file = request.FILES.get('data_file')
        zip_file = request.FILES.get('zip_file')
        
        if not data_file or not zip_file:
            messages.error(request, "Ambos archivos son obligatorios.")
            return redirect('importacion_iniciar')
            
        try:
            # 1. Crear sesión si no existe
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
            
            # 2. Parsear Data (Excel o TXT)
            ext = os.path.splitext(data_file.name)[1].lower()
            if ext == '.txt':
                filas = parsear_txt(data_file)
            else:
                filas = parsear_excel(data_file)
            
            # 3. Extraer ZIP a media temporal
            temp_dir = settings.MEDIA_ROOT / 'importaciones_temp' / session_key
            fotos_dict = extraer_zip_seguro(zip_file, temp_dir)
            
            # 4. Generar estado y guardar en sesión
            estado = generar_estado_inicial(filas, fotos_dict, session_key)
            request.session['importacion_activa'] = estado
            request.session.modified = True
            
            messages.success(request, f"Procesado: {len(filas)} registros y {len(fotos_dict)} fotos.")
            return redirect('importacion_workspace')
            
        except Exception as e:
            messages.error(request, f"Error al procesar: {str(e)}")
            return redirect('importacion_iniciar')
        
    return render(request, 'calidad/importacion/upload.html')

@login_required
def importacion_workspace(request):
    """
    GET: Vista principal del tablero de importación.
    """
    if 'importacion_activa' not in request.session:
        messages.error(request, "No hay importación activa.")
        return redirect('importacion_iniciar')
        
    return render(request, 'calidad/importacion/workspace.html')

@login_required
def importacion_update_ajax(request):
    """
    PATCH: Recibe acciones del frontend y muta el JSON de la sesión.
    """
    if request.method != 'PATCH':
        return JsonResponse({"error": "Método no permitido"}, status=405)
        
    estado = request.session.get('importacion_activa')
    if not estado:
        return JsonResponse({"error": "Sesión expirada"}, status=400)
        
    try:
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'MOVE_PHOTO':
            photo_id = data.get('photo_id')
            source_id = data.get('source_id')
            target_id = data.get('target_id')
            
            # Quitar del origen
            if source_id == 'huerfanas':
                if photo_id in estado['fotos_huerfanas']:
                    estado['fotos_huerfanas'].remove(photo_id)
            else:
                for row in estado['registros']:
                    if row['id'] == source_id and photo_id in row['fotos_asignadas']:
                        row['fotos_asignadas'].remove(photo_id)
                        break
                        
            # Agregar al destino
            if target_id == 'huerfanas':
                if photo_id not in estado['fotos_huerfanas']:
                    estado['fotos_huerfanas'].append(photo_id)
            else:
                for row in estado['registros']:
                    if row['id'] == target_id:
                        if photo_id not in row['fotos_asignadas']:
                            row['fotos_asignadas'].append(photo_id)
                        break
                        
        elif action == 'EDIT_RECORD':
            record_id = data.get('record_id')
            field = data.get('field')
            value = data.get('value')
            
            for row in estado['registros']:
                if row['id'] == record_id:
                    row[field] = value
                    break
        else:
            return JsonResponse({"error": "Acción desconocida"}, status=400)
            
        # Guardar cambios
        request.session['importacion_activa'] = estado
        request.session.modified = True
        return JsonResponse({"status": "ok"})
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def importacion_confirmar(request):
    """
    POST: Realiza el commit a la base de datos y limpia la sesión.
    """
    if request.method != 'POST':
        return redirect('importacion_iniciar')
        
    estado = request.session.get('importacion_activa')
    if not estado:
        messages.error(request, "La sesión de importación expiró o no existe.")
        return redirect('importacion_iniciar')
        
    try:
        commit_importacion(estado, request.user)
        
        # Limpieza de sesión
        del request.session['importacion_activa']
        request.session.modified = True
        
        messages.success(request, "Importación completada correctamente.")
        # Responder JSON si es por AJAX (fetch), o redirect normal
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({"status": "ok", "redirect": "/revisar/"})
        return redirect('revisar_orientacion')
        
    except Exception as e:
        messages.error(request, f"Error al guardar: {str(e)}")
        # No borramos la sesión ni la carpeta, el usuario puede reintentar
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({"error": str(e)}, status=500)
        return redirect('importacion_workspace')

@login_required
def importacion_cancelar(request):
    """
    Cancela la importación activa, limpia la sesión y borra los archivos temporales.
    """
    if request.method == 'POST':
        if 'importacion_activa' in request.session:
            session_id = request.session['importacion_activa'].get('session_id')
            if session_id:
                temp_dir = settings.MEDIA_ROOT / 'importaciones_temp' / session_id
                import shutil
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
            del request.session['importacion_activa']
            request.session.modified = True
            
        messages.success(request, "Importación cancelada y archivos temporales eliminados.")
        return redirect('importacion_iniciar')
        
    return redirect('dashboard')
