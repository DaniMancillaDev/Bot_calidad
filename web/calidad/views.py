"""
Vistas del Panel de Calidad.
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from .models import RegistroDefecto, PerfilUsuario, EstadoRevision

# ============================================================
# FUNCIONES AUXILIARES DE SEGURIDAD Y PERMISOS
# ============================================================

def get_registros_permitidos(user):
    """
    Filtra los registros según el usuario:
    - Superusers: ven todo.
    - Usuarios normales: ven registros de SU MISMO TURNO Y DEPARTAMENTO.
    """
    if user.is_superuser:
        return RegistroDefecto.objects.all()

    if hasattr(user, 'perfil'):
        turno = user.perfil.turno
        departamento = user.perfil.departamento

        # Filtrar por turno Y departamento
        return RegistroDefecto.objects.filter(
            turno=turno,
            departamento=departamento
        )

    return RegistroDefecto.objects.none()


def obtener_numeros_fotos_permitidas(registros):
    """
    Parsea el campo 'fotos' de los registros (soporta legacy '(001-005)' y nuevo '1, 2, 3') 
    y extrae un set con los números enteros individuales permitidos.
    """
    numeros_permitidos = set()
    for r in registros:
        if not r.fotos:
            continue
        
        # 1. Intentar formato nuevo: "1, 2, 3"
        if ',' in r.fotos or r.fotos.isdigit():
            try:
                nums = [int(x.strip()) for x in r.fotos.split(',') if x.strip()]
                numeros_permitidos.update(nums)
                continue
            except ValueError:
                pass

        # 2. Formato legacy: (001-005)
        # Buscar rangos: (001-005)
        rangos = re.findall(r'\((\d+)-(\d+)\)', r.fotos)
        for inicio, fin in rangos:
            numeros_permitidos.update(range(int(inicio), int(fin) + 1))
            
        # Buscar individuales legacy: (001)
        individuales = re.findall(r'\((\d+)\)', r.fotos.replace('-', 'X'))
        for num in individuales:
            numeros_permitidos.add(int(num))
            
    return numeros_permitidos


# ============================================================
# DASHBOARD PRINCIPAL
# ============================================================

@login_required
def dashboard(request):
    """Vista principal con estadísticas filtradas por turno o globales."""
    
    registros_base = get_registros_permitidos(request.user)

    # Filtros por fecha
    dias = int(request.GET.get('dias', 7))
    fecha_desde = datetime.now() - timedelta(days=dias)

    # Estadísticas globales (filtradas por el usuario actual)
    total_registros   = registros_base.count()
    registros_recientes = registros_base.filter(fecha_registro__gte=fecha_desde).count()

    # Defectos más frecuentes
    top_defectos = (
        registros_base
        .values('descripcion')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    # Defectos por línea
    por_linea = (
        registros_base
        .values('linea')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )

    # Registros recientes
    ultimos_registros = registros_base.all()[:10]

    # Info del usuario para el contexto
    perfil = None
    if hasattr(request.user, 'perfil'):
        perfil = request.user.perfil

    context = {
        'total_registros':     total_registros,
        'registros_recientes': registros_recientes,
        'top_defectos':        top_defectos,
        'por_linea':           por_linea,
        'ultimos_registros':   ultimos_registros,
        'dias':                dias,
        'seccion':             'dashboard',
        'perfil':              perfil,
    }
    return render(request, 'calidad/dashboard.html', context)


# ============================================================
# REPORTES (LISTA DE DEFECTOS)
# ============================================================

@login_required
def reportes(request):
    """Lista completa de registros filtrados por turno."""

    registros = get_registros_permitidos(request.user)

    # Filtros opcionales por GET
    linea       = request.GET.get('linea', '')
    responsable = request.GET.get('responsable', '')
    modelo      = request.GET.get('modelo', '')
    modo        = request.GET.get('modo', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')

    if linea:
        registros = registros.filter(linea__icontains=linea)
    if responsable:
        registros = registros.filter(responsable__icontains=responsable)
    if modelo:
        registros = registros.filter(modelo__icontains=modelo)
    # Filtros por turno y departamento (ya aplicados en get_registros_permitidos)
    # pero podemos refinar si el usuario es admin
    if request.user.is_superuser:
        turno_filtro = request.GET.get('turno', '')
        depto_filtro = request.GET.get('departamento', '')
        if turno_filtro:
            registros = registros.filter(turno=turno_filtro)
        if depto_filtro:
            registros = registros.filter(departamento=depto_filtro)
    if fecha_desde:
        registros = registros.filter(fecha_registro__date__gte=fecha_desde)
    if fecha_hasta:
        registros = registros.filter(fecha_registro__date__lte=fecha_hasta)

    # Opciones para los selects de filtro (basadas solo en lo que pueden ver)
    base_qs = get_registros_permitidos(request.user)
    lineas = base_qs.values_list('linea', flat=True).distinct().order_by('linea')
    responsables = base_qs.values_list('responsable', flat=True).distinct().order_by('responsable')

    # Pre-cargar nombres y evaluar registros para agrupar por usuario
    nombres_dict = {}
    for p in PerfilUsuario.objects.select_related('usuario').exclude(telegram_user_id__isnull=True):
        nombres_dict[p.telegram_user_id] = p.usuario.get_full_name() or p.usuario.username

    registros = list(registros.order_by('user_id', '-fecha_registro'))
    for r in registros:
        r.nombre_usuario = nombres_dict.get(r.user_id, "Desconocido")

    context = {
        'registros':    registros,
        'total_registros': len(registros),
        'lineas':       lineas,
        'responsables': responsables,
        'filtros': {
            'linea': linea, 'responsable': responsable, 'modelo': modelo,
            'modo': modo, 'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
        },
        'seccion': 'reportes',
    }
    return render(request, 'calidad/reportes.html', context)


# ============================================================
# VER FOTO INDIVIDUAL
# ============================================================

@login_required
def ver_foto(request, numero):
    """Muestra una foto si el usuario tiene permiso para verla (por turno/depto)."""

    # Validar permiso por turno/depto
    registros_permitidos = get_registros_permitidos(request.user)

    # Buscar la foto en las carpetas de usuarios permitidos
    fotos_base_dir = settings.MEDIA_ROOT / 'fotos'
    url_foto = None
    nombre = None
    user_id_encontrado = None

    if not fotos_base_dir.exists():
        raise Http404("Directorio de fotos no encontrado")

    # Obtener lista de usuarios permitidos
    if request.user.is_superuser:
        usuarios_permitidos = None  # Admin puede ver todos
    else:
        if hasattr(request.user, 'perfil'):
            usuarios_perfil = PerfilUsuario.objects.filter(
                turno=request.user.perfil.turno,
                departamento=request.user.perfil.departamento
            ).values_list('telegram_user_id', flat=True)
            usuarios_permitidos = set(usuarios_perfil)
        else:
            usuarios_permitidos = set()

    # Buscar en carpetas de usuarios
    for user_folder in fotos_base_dir.iterdir():
        if not user_folder.is_dir():
            continue

        try:
            user_id = int(user_folder.name)
        except ValueError:
            continue

        # Filtrar por usuario si no es admin
        if not request.user.is_superuser and user_id not in usuarios_permitidos:
            continue

        # Buscar archivo que empiece con el número de secuencia
        for ext in ['.png', '.jpg']:
            for archivo in user_folder.glob(f"{numero:03d}_*{ext}"):
                url_foto = f"/media/fotos/{user_id}/{archivo.name}"
                nombre = archivo.name
                user_id_encontrado = user_id
                break
        if url_foto:
            break

    if not url_foto:
        raise Http404(f"Foto {numero:03d} no encontrada o no tienes permiso")

    # Mostrar registros relacionados del usuario que tomó la foto
    registros_relacionados = registros_permitidos.filter(
        user_id=user_id_encontrado,
        fotos__contains=f"{numero:03d}"
    )

    context = {
        'url_foto':   url_foto,
        'nombre':     nombre,
        'numero':     numero,
        'usuario':    user_id_encontrado,
        'registros':  registros_relacionados,
        'prev':       numero - 1 if numero > 1 else None,
        'next_num':   numero + 1,
        'seccion':    'fotos',
    }
    return render(request, 'calidad/ver_foto.html', context)


# ============================================================
# GALERÍA DE FOTOS
# ============================================================

@login_required
def galeria_fotos(request):
    """
    Feed operativo de registros con thumbnails.
    - DB-first: lee fotos_nums + metadatos del registro, no escanea filesystem.
    - Solo thumbnails en el feed. Original solo en modal/zoom.
    - Paginación server-side: 30 registros por página.
    - HTMX-ready: si request trae HX-Request header, devuelve solo el partial.
    - Filters: turno, departamento, estado_revision, fecha, línea.
    """
    PAGE_SIZE = 30

    # ── Queryset base con permisos ────────────────────────────────────────────
    registros_qs = (
        get_registros_permitidos(request.user)
        .select_related('supervisor')         # evitar N+1 en supervisor
        .only(
            'id', 'fotos', 'fotos_nums', 'modelo', 'linea',
            'cantidad', 'responsable', 'descripcion',
            'fecha_registro', 'user_id', 'turno', 'departamento',
            'estado_revision', 'supervisor_id', 'is_duplicate', 'is_blurry',
        )
        .order_by('-fecha_registro')
    )

    # ── Filtros ───────────────────────────────────────────────────────────────
    estado_filter  = request.GET.get('estado', '')
    turno_filter   = request.GET.get('turno', '')
    depto_filter   = request.GET.get('depto', '')
    linea_filter   = request.GET.get('linea', '')
    dias_filter    = request.GET.get('dias', '')
    q_filter       = request.GET.get('q', '')   # búsqueda libre en descripcion

    if estado_filter:
        registros_qs = registros_qs.filter(estado_revision=estado_filter)
    if turno_filter:
        registros_qs = registros_qs.filter(turno=turno_filter)
    if depto_filter:
        registros_qs = registros_qs.filter(departamento=depto_filter)
    if linea_filter:
        registros_qs = registros_qs.filter(linea__icontains=linea_filter)
    if dias_filter:
        try:
            desde = datetime.now() - timedelta(days=int(dias_filter))
            registros_qs = registros_qs.filter(fecha_registro__gte=desde)
        except ValueError:
            pass
    if q_filter:
        registros_qs = registros_qs.filter(
            Q(descripcion__icontains=q_filter) |
            Q(modelo__icontains=q_filter) |
            Q(responsable__icontains=q_filter)
        )

    # ── Pre-cargar nombres de usuarios (1 query, no N) ────────────────────────
    nombres_dict = {
        p.telegram_user_id: p.usuario.get_full_name() or p.usuario.username
        for p in PerfilUsuario.objects.select_related('usuario')
                                       .exclude(telegram_user_id__isnull=True)
    }

    # ── Paginación ────────────────────────────────────────────────────────────
    paginator = Paginator(registros_qs, PAGE_SIZE)
    page_num  = request.GET.get('page', 1)
    try:
        page = paginator.page(page_num)
    except Exception:
        page = paginator.page(1)

    # ── Enriquecer registros con URLs de thumb y original ─────────────────────
    thumbs_root = settings.THUMBS_ROOT
    fotos_root  = settings.FOTOS_ROOT
    thumbs_url  = settings.THUMBS_URL
    fotos_url   = settings.FOTOS_URL

    registros_enriquecidos = []
    for reg in page.object_list:
        fotos_data = []
        user_folder_fotos  = fotos_root  / str(reg.user_id)
        user_folder_thumbs = thumbs_root / str(reg.user_id)

        # Usar fotos_nums (Fase 1). Fallback: parsear campo legacy.
        nums = reg.fotos_nums if reg.fotos_nums else []
        if not nums and reg.fotos:
            try:
                nums = [int(x.strip()) for x in reg.fotos.split(',') if x.strip().isdigit()]
            except Exception:
                nums = []

        for num in nums:
            # Buscar archivo con prefix num (ej. 001_20240101_120000.jpg)
            patron = f"{num:03d}_*.jpg"
            fotos_encontradas = sorted(user_folder_fotos.glob(patron))
            if not fotos_encontradas:
                continue
            foto_file = fotos_encontradas[0]
            thumb_file = user_folder_thumbs / foto_file.name

            # Thumb URL: usar thumb si existe, fallback al original
            if thumb_file.exists():
                thumb_src = f"{thumbs_url}{reg.user_id}/{foto_file.name}"
            else:
                thumb_src = f"{fotos_url}{reg.user_id}/{foto_file.name}"

            fotos_data.append({
                'num':       num,
                'thumb_url': thumb_src,
                'orig_url':  f"{fotos_url}{reg.user_id}/{foto_file.name}",
                'nombre':    foto_file.name,
            })

        registros_enriquecidos.append({
            'reg':            reg,
            'fotos':          fotos_data,
            'nombre_usuario': nombres_dict.get(reg.user_id, f'ID {reg.user_id}'),
        })

    context = {
        'registros':          registros_enriquecidos,
        'page':               page,
        'paginator':          paginator,
        'total':              paginator.count,
        'estados':            EstadoRevision.choices,
        # Valores actuales de filtro
        'f_estado':           estado_filter,
        'f_turno':            turno_filter,
        'f_depto':            depto_filter,
        'f_linea':            linea_filter,
        'f_dias':             dias_filter,
        'f_q':                q_filter,
        'seccion':            'fotos',
    }

    # HTMX: solo el partial si viene de una solicitud incremental
    if request.headers.get('HX-Request'):
        return render(request, 'calidad/partials/feed_page.html', context)

    return render(request, 'calidad/galeria.html', context)


# ============================================================
# REVISIÓN DE ORIENTACIÓN + GENERACIÓN DE EXCEL
# ============================================================

def _parse_fotos_nums(registros):
    """
    Extrae los números de foto individuales de los registros.
    Soporta formato nuevo '1, 2, 3' y legacy '(001-005)'.
    Resistente a registros como dict (JSON) o como objeto (ORM).
    """
    import re
    resultado = []
    for r in registros:
        is_dict = isinstance(r, dict)
        
        fotos_str = r.get('fotos', '') if is_dict else getattr(r, 'fotos', '')
        user_id = r.get('user_id') if is_dict else getattr(r, 'user_id', None)
        
        nums = []
        if fotos_str:
            # 1. Intentar detectar números individuales (formato nuevo o individuales legacy)
            # re.findall(r'\d+', ...) saca todos los grupos de dígitos
            nums = [int(n) for n in re.findall(r'\d+', str(fotos_str))]
            
            # 2. Si hay rangos legacy (001-005), completar el medio
            # (re.findall anterior solo sacó el inicio y fin)
            rangos = re.findall(r'\((\d+)-(\d+)\)', str(fotos_str))
            for inicio, fin in rangos:
                nums.extend(range(int(inicio), int(fin) + 1))

        resultado.append({
            'id':          r.get('id') if is_dict else getattr(r, 'id', None),
            'user_id':     user_id,
            'fotos_nums':  sorted(list(set(nums))),
            'fotos_str':   fotos_str,
            'modelo':      r.get('modelo', '') if is_dict else getattr(r, 'modelo', ''),
            'linea':       r.get('linea', '') if is_dict else getattr(r, 'linea', ''),
            'descripcion': r.get('descripcion', '') if is_dict else getattr(r, 'descripcion', ''),
            'responsable': r.get('responsable', '') if is_dict else getattr(r, 'responsable', ''),
            'cantidad':    r.get('cantidad', 1) if is_dict else getattr(r, 'cantidad', 1),
        })
    return resultado


@login_required
def revisar_orientacion(request):
    """
    Página de revisión de orientación de fotos antes de generar el Excel.
    Muestra todas las fotos del turno con su ángulo auto-detectado,
    y permite al usuario corregirlas con botones de rotación.
    """
    from .services.reporte_excel import detect_orientations_batch

    registros_data = []
    fecha_desde = ''
    fecha_hasta = ''
    
    if request.method == 'POST' and request.POST.get('registros_data'):
        # Recibir registros pre-procesados o agrupados desde el panel operativo
        try:
            registros_data = json.loads(request.POST.get('registros_data'))
        except json.JSONDecodeError:
            pass
    else:
        # Lógica original: cargar desde base de datos
        registros_qs = get_registros_permitidos(request.user)

        # Filtros opcionales heredados desde la página de reportes
        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        if fecha_desde:
            registros_qs = registros_qs.filter(fecha_registro__date__gte=fecha_desde)
        if fecha_hasta:
            registros_qs = registros_qs.filter(fecha_registro__date__lte=fecha_hasta)

        registros_data = _parse_fotos_nums(registros_qs)
    
    # Ordenar registros por usuario y número de inicio para que la tabla sea coherente
    registros_data.sort(key=lambda x: (x.get('user_id'), x['fotos_nums'][0] if x.get('fotos_nums') else 0))

    fotos_dir = settings.MEDIA_ROOT / 'fotos'

    # Encontrar qué fotos existen en disco usando clave compuesta {user_id}_{numero}
    fotos_en_disco = {}
    for r in registros_data:
        user_id = r.get('user_id')
        if not user_id:
            continue
            
        user_folder = fotos_dir / str(user_id)
        if not user_folder.exists():
            continue
            
        for num in r.get('fotos_nums', []):
            clave = f"{user_id}_{num}"
            if clave in fotos_en_disco:
                continue
                
            # Buscar cualquier archivo que empiece con el número (formato 001 o 1)
            # y que sea una imagen común.
            prefix_3 = f"{num:03d}"
            prefix_raw = str(num)
            
            # Glob case-insensitive manual (o simplemente buscar los prefijos comunes)
            posibles = list(user_folder.glob(f"{prefix_3}*")) + \
                      list(user_folder.glob(f"{prefix_raw}*"))
            
            for path in posibles:
                ext = path.suffix.lower()
                if ext in ['.jpg', '.jpeg', '.png']:
                    fotos_en_disco[clave] = {
                        'path': path,
                        'user_id': user_id,
                        'numero': num
                    }
                    break

    # Construir lista de fotos para el template
    fotos_preview = []
    for clave, data in fotos_en_disco.items():
        fotos_preview.append({
            'clave':    clave,
            'numero':   data['numero'],
            'user_id':  data['user_id'],
            'url':      f"/media/fotos/{data['user_id']}/{data['path'].name}",
            'angulo':   0, # Se calculará vía AJAX
        })

    # Ordenar por usuario y luego por número de foto para que aparezcan en secuencia (001, 002...)
    fotos_preview.sort(key=lambda x: (x['user_id'], x['numero']))

    context = {
        'registros':          registros_data,
        'registros_json':     json.dumps(registros_data, default=str),
        'fotos_preview':      fotos_preview,
        'filtros': {'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta},
        'seccion':            'reportes',
    }
    return render(request, 'calidad/revisar_orientacion.html', context)

@login_required
@require_POST
def api_detectar_orientacion(request):
    """
    Detecta la orientación de una lista de fotos vía AJAX.
    """
    from .services.reporte_excel import detect_orientation

    try:
        body = json.loads(request.body)
        claves = body.get('fotos', [])
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    orientaciones = {}

    for clave in claves:
        try:
            user_id_str, num_str = str(clave).split('_')
            user_folder = fotos_dir / user_id_str
            num_int = int(num_str)
            
            for ext in ['png', 'jpg']:
                # Buscar formato exacto (001.png) o con timestamp (001_2023.png)
                archivos = list(user_folder.glob(f"{num_int:03d}.{ext}")) + \
                           list(user_folder.glob(f"{num_int:03d}_*.{ext}"))
                if archivos:
                    ang = detect_orientation(archivos[0])
                    orientaciones[clave] = ang
                    break
        except Exception:
            pass

    return JsonResponse(orientaciones)


@login_required
def generar_excel(request):
    """
    Encola la generación de Excel con Celery y devuelve un task_id.
    El estado se almacena en Redis (no en memoria del proceso).
    """
    from .tasks import generar_excel_task

    if request.method != 'POST':
        return redirect('reportes')

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return HttpResponse('JSON inválido', status=400)

    rotaciones_raw = body.get('rotaciones', {})
    rotaciones = {str(k): int(v) for k, v in rotaciones_raw.items()}
    registros_data = body.get('registros', [])

    if not registros_data:
        return HttpResponse('Sin registros para generar.', status=400)

    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Encolar tarea Celery — no bloquea el proceso web
    task = generar_excel_task.delay(
        registros_data=registros_data,
        rotaciones=rotaciones,
        fotos_dir_str=str(fotos_dir),
        fecha_str=fecha_str,
    )

    return JsonResponse({'task_id': task.id})


@login_required
def api_excel_status(request, task_id):
    """
    Consulta el estado de una tarea Celery por su task_id.
    Compatible con múltiples workers y servidores (estado en Redis).
    """
    from celery.result import AsyncResult

    result = AsyncResult(task_id)

    if result.state == 'PENDING':
        return JsonResponse({'status': 'processing', 'progress': 'En cola...'})

    if result.state == 'PROGRESS':
        meta = result.info or {}
        return JsonResponse({'status': 'processing', 'progress': meta.get('progress', '...')})

    if result.state == 'SUCCESS':
        data = result.result or {}
        return JsonResponse({
            'status': 'done',
            'file_path': data.get('file_path'),
            'filename': data.get('filename'),
        })

    if result.state == 'FAILURE':
        return JsonResponse({'status': 'error', 'error': str(result.info)}, status=500)

    return JsonResponse({'status': result.state.lower()})


@login_required
def api_download_excel(request, task_id):
    """
    Descarga el archivo generado por la tarea Celery.
    Lee el path desde el resultado en Redis, sirve el archivo y lo borra.
    """
    from celery.result import AsyncResult

    result = AsyncResult(task_id)

    if result.state != 'SUCCESS':
        return HttpResponse('Archivo no listo', status=400)

    data = result.result or {}
    path = data.get('file_path')
    nombre = data.get('filename')

    if not path or not Path(path).exists():
        return HttpResponse('Archivo no encontrado', status=404)

    with open(path, 'rb') as f:
        contenido = f.read()

    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass

    content_type = (
        'application/zip'
        if nombre.endswith('.zip')
        else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response = HttpResponse(contenido, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response

# ============================================================
# PANEL OPERATIVO Y POLLING LIGERO
# ============================================================

@login_required
def panel_operativo(request):
    """Vista HTML principal del Panel Operativo."""
    # Obtenemos los registros iniciales permitidos del día o los últimos N días
    dias = int(request.GET.get('dias', 1))
    fecha_desde = datetime.now() - timedelta(days=dias)
    registros_qs = get_registros_permitidos(request.user).filter(fecha_registro__gte=fecha_desde)
    
    # Preparar el JSON inicial igual que en revisar_orientacion
    registros_data = _parse_fotos_nums(registros_qs)
    
    # Obtener el último ID para el polling
    last_id = registros_qs.first().id if registros_qs.exists() else 0
    
    context = {
        'registros_json': json.dumps(registros_data, default=str),
        'last_id': last_id,
        'seccion': 'operacion',
    }
    return render(request, 'calidad/operacion.html', context)

@login_required
def api_check_updates(request):
    """Endpoint de peso pluma para SQLite. Solo hace SELECT MAX(id)."""
    try:
        last_id = int(request.GET.get('last_id', 0))
    except ValueError:
        return JsonResponse({'error': 'Invalid last_id'}, status=400)
        
    registros_base = get_registros_permitidos(request.user)
    
    from django.db.models import Max
    max_id_dict = registros_base.aggregate(Max('id'))
    max_id = max_id_dict['id__max'] or 0
    
    if max_id > last_id:
        # Hay nuevos registros
        nuevos_count = registros_base.filter(id__gt=last_id).count()
        return JsonResponse({'has_updates': True, 'max_id': max_id, 'nuevos_count': nuevos_count})
    
    return JsonResponse({'has_updates': False, 'max_id': max_id})

@login_required
def api_get_nuevos(request):
    """Devuelve el JSON de los registros más nuevos que last_id."""
    try:
        last_id = int(request.GET.get('last_id', 0))
    except ValueError:
        return JsonResponse({'error': 'Invalid last_id'}, status=400)
        
    registros_base = get_registros_permitidos(request.user)
    nuevos_qs = registros_base.filter(id__gt=last_id).order_by('-fecha_registro')
    
    registros_data = _parse_fotos_nums(nuevos_qs)
    
    return JsonResponse({'registros': registros_data})

@require_POST
@login_required
def api_delete_registro(request, registro_id):
    """Permite a un admin eliminar un registro."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
        
    registro = get_object_or_404(RegistroDefecto, id=registro_id)
    registro.delete()
    return JsonResponse({'success': True})

@require_POST
@login_required
def api_edit_registro(request, registro_id):
    """Permite a un admin editar un registro."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
        
    import json
    try:
        data = json.loads(request.body)
        registro = get_object_or_404(RegistroDefecto, id=registro_id)
        
        # Solo permitir editar campos seguros
        if 'modelo' in data: registro.modelo = data['modelo']
        if 'linea' in data: registro.linea = data['linea']
        if 'descripcion' in data: registro.descripcion = data['descripcion']
        if 'responsable' in data: registro.responsable = data['responsable']
        if 'cantidad' in data: registro.cantidad = int(data['cantidad'])
        
        registro.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
