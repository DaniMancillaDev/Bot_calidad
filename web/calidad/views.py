"""
Vistas del Panel de Calidad.
"""
import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from .models import RegistroDefecto, PerfilUsuario, EstadoRevision
from calidad.utils import get_best_image_path

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



# ============================================================
# FUNCIONES AUXILIARES INTERNAS Y UTILS
# ============================================================

def _get_min_foto(r):
    """Extrae la primera foto de la lista (legacy helper)"""
    if getattr(r, 'fotos_nums', None):
        return min(r.fotos_nums)
    import re
    nums = re.findall(r'\d+', str(getattr(r, 'fotos', '')))
    return int(nums[0]) if nums else 99999

def _sort_by_foto(r):
    """Helper para ordernar registros"""
    return (getattr(r, 'user_id', 0), _get_min_foto(r))

class _AutoDeleteFile:
    """Wrapper para borrar archivo temporal al terminar de streamear."""
    def __init__(self, path):
        self._path = path
        self._file = open(path, 'rb')
    def __getattr__(self, name):
        return getattr(self._file, name)
    def close(self):
        self._file.close()
        import os
        try: os.unlink(self._path)
        except OSError: pass

# ============================================================
# HELPERS PARA EXPORT CON NUMERACIÓN SECUENCIAL
# ============================================================

def _build_display_map(registros_sorted, fotos_dir):
    """
    Construye un mapa {user_id: {real_num: display_num}} para renumeración
    visual durante la exportación. Solo vive en memoria, nunca se persiste.
    Recorre los registros en el mismo orden que el ZIP, garantizando consistencia
    entre ambos archivos exportados.
    """
    from shared.utils.photo_parser import parse_photo_numbers
    display_map = {}  # {user_id: {real_num: display_num}}
    counters = {}     # {user_id: int}

    for reg in registros_sorted:
        uid = reg.user_id
        if uid not in display_map:
            display_map[uid] = {}
            counters[uid] = 0

        # Fase 2: evidencias v2
        for ev in reg.evidencias_v2.all():
            import re as _re
            filename = Path(settings.MEDIA_ROOT / ev.ruta_archivo.lstrip('/')).name
            m = _re.match(r'^(\d+)_', filename)
            real_num = int(m.group(1)) if m else ev.id
            if real_num not in display_map[uid]:
                counters[uid] += 1
                display_map[uid][real_num] = counters[uid]

        # Fase 1 / Legacy
        nums = reg.fotos_nums if reg.fotos_nums else parse_photo_numbers(reg.fotos)
        for num in sorted(list(set(nums))):
            img = get_best_image_path(fotos_dir, str(uid), num)
            if img and img.exists() and num not in display_map[uid]:
                counters[uid] += 1
                display_map[uid][num] = counters[uid]

    return display_map


def _display_rango(real_nums, uid_map):
    """
    Convierte una lista de números reales en un string de rango usando
    números de display del mapa. Ej: [457,512,589] -> '001-003'.
    Si un número no está en el mapa (no hay foto en disco), lo omite.
    """
    display_nums = sorted(uid_map[n] for n in real_nums if n in uid_map)
    if not display_nums:
        return '-'

    rangos = []
    inicio = display_nums[0]
    anterior = display_nums[0]
    for n in display_nums[1:]:
        if n == anterior + 1:
            anterior = n
        else:
            rangos.append(f"{inicio:03d}" if inicio == anterior else f"{inicio:03d}-{anterior:03d}")
            inicio = anterior = n
    rangos.append(f"{inicio:03d}" if inicio == anterior else f"{inicio:03d}-{anterior:03d}")
    return ", ".join(rangos)


# ============================================================
# DASHBOARD PRINCIPAL
# ============================================================

@login_required
def dashboard(request):
    """Vista principal con estadísticas filtradas por turno o globales."""
    
    registros_base = get_registros_permitidos(request.user)

    # Filtros por fecha
    dias = int(request.GET.get('dias', 7))
    fecha_desde = timezone.now() - timedelta(days=dias)

    # Estadísticas globales (filtradas por el usuario actual)
    total_registros   = registros_base.count()
    registros_recientes = registros_base.filter(fecha_registro__gte=fecha_desde).count()

    # Defectos más frecuentes
    top_defectos = list(
        registros_base
        .values('descripcion')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    # Defectos por línea con cálculo porcentual proporcional para barra visual
    por_linea = list(
        registros_base
        .values('linea')
        .annotate(total=Count('id'))
        .order_by('-total')[:8]
    )
    max_linea = max((item['total'] for item in por_linea), default=1) if por_linea else 1
    for item in por_linea:
        item['porcentaje'] = round((item['total'] / max_linea) * 100, 1) if max_linea > 0 else 0

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
# HELPERS
# ============================================================

def _parse_aware_dt(dt_str: str, end: bool = False):
    """
    Parsea un string date ('YYYY-MM-DD') o datetime ('YYYY-MM-DDTHH:MM')
    devolviendo un datetime timezone-aware usando el timezone local del servidor.
    Si end=True y el string es solo una fecha, fija la hora a 23:59:59.
    Si end=True y es datetime sin segundos, fija segundos a 59 para cubrir el minuto completo.
    """
    if not dt_str:
        return None
    from django.utils import timezone as tz
    try:
        if 'T' in dt_str or ' ' in dt_str:
            # 'YYYY-MM-DDTHH:MM' o 'YYYY-MM-DD HH:MM'
            dt = datetime.fromisoformat(dt_str.replace('T', ' '))
            if end and dt.second == 0 and dt.microsecond == 0:
                dt = dt.replace(second=59, microsecond=999999)
        else:
            # Solo fecha
            d = datetime.strptime(dt_str, '%Y-%m-%d')
            dt = d.replace(hour=23, minute=59, second=59, microsecond=999999) if end else d
        if tz.is_naive(dt):
            dt = tz.make_aware(dt)
        return dt
    except (ValueError, TypeError):
        return None


# ============================================================
# REPORTES (LISTA DE DEFECTOS)
# ============================================================

@login_required
def reportes(request):
    """Lista completa de registros filtrados por turno y presets temporales."""

    registros = get_registros_permitidos(request.user)

    linea       = request.GET.get('linea', '')
    responsable = request.GET.get('responsable', '')
    modelo      = request.GET.get('modelo', '')
    
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    preset      = request.GET.get('preset', '')
    
    # Primera carga sin parámetros: por defecto Hoy (d0)
    if not request.GET:
        preset = 'd0'

    if linea:
        registros = registros.filter(linea__icontains=linea)
    if responsable:
        registros = registros.filter(responsable__icontains=responsable)
    if modelo:
        registros = registros.filter(modelo__icontains=modelo)

    if request.user.is_superuser:
        turno_filtro = request.GET.get('turno', '')
        depto_filtro = request.GET.get('departamento', '')
        if turno_filtro:
            registros = registros.filter(turno=turno_filtro)
        if depto_filtro:
            registros = registros.filter(departamento=depto_filtro)

    # Filtrado por datetime-local o presets
    dt_desde = _parse_aware_dt(fecha_desde, end=False) if fecha_desde else None
    dt_hasta = _parse_aware_dt(fecha_hasta, end=True) if fecha_hasta else None

    if dt_desde:
        registros = registros.filter(fecha_registro__gte=dt_desde)
    if dt_hasta:
        registros = registros.filter(fecha_registro__lte=dt_hasta)

    if not dt_desde and not dt_hasta:
        _HOURS = {'h1': 1, 'h4': 4, 'h8': 8, 'h24': 24}
        if preset in _HOURS:
            delta = timedelta(hours=_HOURS[preset])
            dt_desde = timezone.now() - delta
            registros = registros.filter(fecha_registro__gte=dt_desde)
        elif preset == 'd0':
            hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            registros = registros.filter(fecha_registro__gte=hoy_inicio)
        elif preset == 'd1':
            hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            ayer_inicio = hoy_inicio - timedelta(days=1)
            registros = registros.filter(fecha_registro__gte=ayer_inicio, fecha_registro__lt=hoy_inicio)
        elif preset.startswith('d') and preset[1:].isdigit():
            dias_count = int(preset[1:])
            dt_desde = timezone.now() - timedelta(days=dias_count)
            registros = registros.filter(fecha_registro__gte=dt_desde)

    rango_activo = 'custom' if (preset == 'custom' or (not preset and (fecha_desde or fecha_hasta))) else (preset or 'd0')

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
        'preset_activo': rango_activo,
        'filtros': {
            'linea': linea, 'responsable': responsable, 'modelo': modelo,
            'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta,
            'preset': preset
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

        img_path = get_best_image_path(fotos_base_dir, str(user_id), numero)
        if img_path:
            url_foto = f"/media/proxies/{user_id}/{img_path.name}" if "proxies" in str(img_path) else f"/media/fotos/{user_id}/{img_path.name}"
            nombre = img_path.name
            user_id_encontrado = user_id
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

def _build_galeria_queryset(request):
    registros_qs = (
        get_registros_permitidos(request.user)
        .select_related('supervisor')
        .prefetch_related('evidencias_v2')
        .only(
            'id', 'fotos', 'fotos_nums', 'modelo', 'linea',
            'cantidad', 'responsable', 'descripcion',
            'fecha_registro', 'user_id', 'turno', 'departamento',
            'estado_revision', 'supervisor_id', 'is_duplicate', 'is_blurry',
        )
        .order_by('-fecha_registro')
    )

    filtros = {
        'estado': request.GET.get('estado', ''),
        'turno': request.GET.get('turno', ''),
        'depto': request.GET.get('depto', ''),
        'linea': request.GET.get('linea', ''),
        'dias': request.GET.get('dias', ''),
        'q': request.GET.get('q', ''),
        'fecha_desde': request.GET.get('fecha_desde', ''),
        'fecha_hasta': request.GET.get('fecha_hasta', '')
    }

    if filtros['estado']:
        registros_qs = registros_qs.filter(estado_revision=filtros['estado'])
    if filtros['turno']:
        registros_qs = registros_qs.filter(turno=filtros['turno'])
    if filtros['depto']:
        registros_qs = registros_qs.filter(departamento=filtros['depto'])
    if filtros['linea']:
        registros_qs = registros_qs.filter(linea__icontains=filtros['linea'])
    if filtros['dias']:
        try:
            desde = timezone.now() - timedelta(days=int(filtros['dias']))
            registros_qs = registros_qs.filter(fecha_registro__gte=desde)
        except ValueError:
            pass
    if filtros['fecha_desde']:
        try:
            registros_qs = registros_qs.filter(fecha_registro__gte=filtros['fecha_desde'])
        except ValueError:
            pass
    if filtros['fecha_hasta']:
        try:
            registros_qs = registros_qs.filter(fecha_registro__lte=f"{filtros['fecha_hasta']} 23:59:59")
        except ValueError:
            pass

    q_filter = filtros['q']
    if q_filter:
        import re
        m = re.match(r'^(\d+)\s*-\s*(\d+)$', q_filter.strip())
        if m:
            start_num = int(m.group(1))
            end_num = int(m.group(2))
            range_list = list(range(start_num, end_num + 1))
            registros_qs = registros_qs.filter(
                Q(descripcion__icontains=q_filter) |
                Q(modelo__icontains=q_filter) |
                Q(responsable__icontains=q_filter) |
                Q(fotos_nums__overlap=range_list)
            )
        elif q_filter.strip().isdigit():
            num = int(q_filter.strip())
            registros_qs = registros_qs.filter(
                Q(descripcion__icontains=q_filter) |
                Q(modelo__icontains=q_filter) |
                Q(responsable__icontains=q_filter) |
                Q(fotos__icontains=q_filter) |
                Q(fotos_nums__contains=[num])
            )
        else:
            registros_qs = registros_qs.filter(
                Q(descripcion__icontains=q_filter) |
                Q(modelo__icontains=q_filter) |
                Q(responsable__icontains=q_filter) |
                Q(fotos__icontains=q_filter)
            )
            
    return registros_qs, filtros

def _enrich_galeria_registros(object_list):
    import re
    num_prefix_re = re.compile(r'^(\d+)_')

    nombres_dict = {
        p.telegram_user_id: p.usuario.get_full_name() or p.usuario.username
        for p in PerfilUsuario.objects.select_related('usuario')
                                       .exclude(telegram_user_id__isnull=True)
    }

    thumbs_root = Path(settings.THUMBS_ROOT)
    fotos_root  = Path(settings.FOTOS_ROOT)
    proxies_root = Path(settings.MEDIA_ROOT) / 'proxies'
    thumbs_url  = settings.THUMBS_URL
    fotos_url   = settings.FOTOS_URL
    proxies_url = settings.MEDIA_URL + 'proxies/'

    # Pre-indexar carpetas de usuario en memoria (O(1) lookups sin I/O de disco redundante)
    user_ids = {reg.user_id for reg in object_list if reg.user_id}
    user_photos_index = {}
    user_thumbs_index = {}
    user_proxies_index = {}

    for uid in user_ids:
        uid_str = str(uid)
        photos_map = {}
        uf_fotos = fotos_root / uid_str
        if uf_fotos.is_dir():
            try:
                for entry in os.scandir(uf_fotos):
                    if entry.is_file() and entry.name.lower().endswith('.jpg'):
                        m = num_prefix_re.match(entry.name)
                        if m:
                            num = int(m.group(1))
                            if num not in photos_map:
                                photos_map[num] = entry.name
            except Exception:
                pass
        user_photos_index[uid] = photos_map

        thumbs_set = set()
        uf_thumbs = thumbs_root / uid_str
        if uf_thumbs.is_dir():
            try:
                thumbs_set = {entry.name for entry in os.scandir(uf_thumbs) if entry.is_file()}
            except Exception:
                pass
        user_thumbs_index[uid] = thumbs_set

        proxies_set = set()
        uf_proxies = proxies_root / uid_str
        if uf_proxies.is_dir():
            try:
                proxies_set = {entry.name for entry in os.scandir(uf_proxies) if entry.is_file()}
            except Exception:
                pass
        user_proxies_index[uid] = proxies_set

    registros_enriquecidos = []
    for reg in object_list:
        fotos_data = []

        thumbs_set = user_thumbs_index.get(reg.user_id, set())
        proxies_set = user_proxies_index.get(reg.user_id, set())

        # Evidencias v2
        for ev in reg.evidencias_v2.all():
            path = ev.ruta_archivo
            if path.startswith('media_files/'):
                path = path[12:]
            elif path.startswith('/media_files/'):
                path = path[13:]
                
            path = path.lstrip('/')
            filename = os.path.basename(path)
            num_display = ev.id
            m = num_prefix_re.match(filename)
            if m:
                num_display = int(m.group(1))

            thumb_src = f"{thumbs_url}{reg.user_id}/{filename}" if filename in thumbs_set else f"{proxies_url}{reg.user_id}/{filename}"
            orig_src = f"{proxies_url}{reg.user_id}/{filename}" if filename in proxies_set else f"{fotos_url}{reg.user_id}/{filename}"

            fotos_data.append({
                'num': num_display,
                'thumb_url': thumb_src,
                'orig_url': orig_src,
                'nombre': filename,
            })

        # Fotos legacy
        nums = reg.fotos_nums if reg.fotos_nums else []
        if not nums and reg.fotos:
            try:
                nums = [int(x.strip()) for x in reg.fotos.split(',') if x.strip().isdigit()]
            except Exception:
                nums = []

        photos_map = user_photos_index.get(reg.user_id, {})
        thumbs_set = user_thumbs_index.get(reg.user_id, set())
        proxies_set = user_proxies_index.get(reg.user_id, set())

        for num in nums:
            foto_filename = photos_map.get(num)
            if not foto_filename:
                continue

            thumb_src = f"{thumbs_url}{reg.user_id}/{foto_filename}" if foto_filename in thumbs_set else f"{fotos_url}{reg.user_id}/{foto_filename}"
            orig_src = f"{proxies_url}{reg.user_id}/{foto_filename}" if foto_filename in proxies_set else f"{fotos_url}{reg.user_id}/{foto_filename}"

            if not any(f['nombre'] == foto_filename for f in fotos_data):
                fotos_data.append({
                    'num':       num,
                    'thumb_url': thumb_src,
                    'orig_url':  orig_src,
                    'nombre':    foto_filename,
                })

        registros_enriquecidos.append({
            'reg':            reg,
            'fotos':          fotos_data,
            'nombre_usuario': nombres_dict.get(reg.user_id, f'ID {reg.user_id}'),
        })
        
    return registros_enriquecidos

def _build_galeria_context(page, paginator, registros_enriquecidos, filtros):
    return {
        'registros':          registros_enriquecidos,
        'page':               page,
        'paginator':          paginator,
        'total':              paginator.count,
        'estados':            EstadoRevision.choices,
        'f_estado':           filtros.get('estado', ''),
        'f_turno':            filtros.get('turno', ''),
        'f_depto':            filtros.get('depto', ''),
        'f_linea':            filtros.get('linea', ''),
        'f_dias':             filtros.get('dias', ''),
        'f_q':                filtros.get('q', ''),
        'seccion':            'fotos',
    }

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
    registros_qs, filtros = _build_galeria_queryset(request)

    PAGE_SIZE = 30
    paginator = Paginator(registros_qs, PAGE_SIZE)
    page_num  = request.GET.get('page', 1)
    
    try:
        page = paginator.page(page_num)
    except Exception:
        page = paginator.page(1)

    registros_enriquecidos = _enrich_galeria_registros(page.object_list)
    context = _build_galeria_context(page, paginator, registros_enriquecidos, filtros)

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
    from shared.utils.photo_parser import parse_photo_numbers
    resultado = []
    
    # Pre-cargar mapeo de nombres de usuario
    nombres_dict = {}
    try:
        from calidad.models import PerfilUsuario
        for p in PerfilUsuario.objects.select_related('usuario').exclude(telegram_user_id__isnull=True):
            nombres_dict[p.telegram_user_id] = p.usuario.get_full_name() or p.usuario.username
    except Exception:
        pass

    # Pre-cargar count de evidencias_v2 para evitar N+1 queries si es ORM
    if registros and not isinstance(registros[0], dict):
        try:
            from django.db.models import Count
            registros = registros.annotate(v2_count=Count('evidencias_v2'))
        except Exception:
            pass

    for r in registros:
        is_dict = isinstance(r, dict)
        
        fotos_str = r.get('fotos', '') if is_dict else getattr(r, 'fotos', '')
        user_id = r.get('user_id') if is_dict else getattr(r, 'user_id', None)
        
        nums = []
        if fotos_str:
            nums = parse_photo_numbers(str(fotos_str))
        
        # Integrar conteo de Fase 2 (Evidencias en Base de Datos)
        v2_count = r.get('v2_count', 0) if is_dict else getattr(r, 'v2_count', 0)
        
        if not fotos_str and v2_count > 0:
            fotos_str = f"{v2_count} foto(s)"
            nums = list(range(1, v2_count + 1))

        fotos_rango = getattr(r, 'fotos_rango', fotos_str) if not is_dict else r.get('fotos_rango', fotos_str)
        nombre_usuario = getattr(r, 'nombre_usuario', None) if not is_dict else r.get('nombre_usuario')
        if not nombre_usuario and user_id:
            nombre_usuario = nombres_dict.get(user_id, f"Operador {user_id}")

        resultado.append({
            'id':             r.get('id') if is_dict else getattr(r, 'id', None),
            'user_id':        user_id,
            'nombre_usuario': nombre_usuario or "Desconocido",
            'fotos_nums':     sorted(list(set(nums))),
            'fotos_str':      fotos_str,
            'fotos_rango':    fotos_rango,
            'modelo':         r.get('modelo', '') if is_dict else getattr(r, 'modelo', ''),
            'numero_parte':   r.get('numero_parte', '') if is_dict else getattr(r, 'numero_parte', ''),
            'linea':          r.get('linea', '') if is_dict else getattr(r, 'linea', ''),
            'descripcion':    r.get('descripcion', '') if is_dict else getattr(r, 'descripcion', ''),
            'responsable':    r.get('responsable', '') if is_dict else getattr(r, 'responsable', ''),
            'cantidad':       r.get('cantidad', 1) if is_dict else getattr(r, 'cantidad', 1),
            'fecha_registro': r.get('fecha_registro') if is_dict else getattr(r, 'fecha_registro', None),
        })
    return resultado


def _get_orientacion_registros(request):
    fecha_desde = ''
    fecha_hasta = ''
    registros_data = []
    
    if request.method == 'POST' and request.POST.get('registros_data'):
        try:
            registros_data = json.loads(request.POST.get('registros_data'))
        except json.JSONDecodeError:
            pass
    else:
        registros_qs = get_registros_permitidos(request.user)

        fecha_desde = request.GET.get('fecha_desde', '')
        fecha_hasta = request.GET.get('fecha_hasta', '')
        if fecha_desde:
            registros_qs = registros_qs.filter(fecha_registro__date__gte=fecha_desde)
        if fecha_hasta:
            registros_qs = registros_qs.filter(fecha_registro__date__lte=fecha_hasta)

        registros_data = _parse_fotos_nums(registros_qs)
        
    return registros_data, fecha_desde, fecha_hasta

def _build_fotos_en_disco(registros_data):
    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    fotos_en_disco = {}
    
    from calidad.models import EvidenciaFotografica
    registro_ids = [r['id'] for r in registros_data if r.get('id')]
    evidencias_qs = EvidenciaFotografica.objects.filter(registro_id__in=registro_ids)
    
    evs_por_registro = {}
    for ev in evidencias_qs:
        if ev.registro_id not in evs_por_registro:
            evs_por_registro[ev.registro_id] = []
        evs_por_registro[ev.registro_id].append(ev)

    for r in registros_data:
        user_id = r.get('user_id')
        if not user_id:
            continue
            
        user_folder = fotos_dir / str(user_id)
        actual_nums = []
        
        if user_folder.exists():
            for num in r.get('fotos_nums', []):
                clave = f"{user_id}_{num}"
                if clave in fotos_en_disco:
                    actual_nums.append(num)
                    continue
                    
                img_path = get_best_image_path(fotos_dir, str(user_id), num)
                if img_path:
                    fotos_en_disco[clave] = {
                        'path': img_path,
                        'user_id': user_id,
                        'numero': num,
                        'es_legacy': True,
                    }
                    actual_nums.append(num)
                    
        evs = evs_por_registro.get(r['id'], [])
        for ev in evs:
            ev_path_str = ev.ruta_archivo
            if ev_path_str.startswith('media_files/'):
                ev_path_str = ev_path_str[12:]
            elif ev_path_str.startswith('/media_files/'):
                ev_path_str = ev_path_str[13:]
            ev_path_str = ev_path_str.lstrip('/')
            
            real_path = Path(settings.MEDIA_ROOT) / ev_path_str
            if real_path.exists():
                import re
                num = ev.id
                m = re.match(r'^(\d+)_', real_path.name)
                if m:
                    num = int(m.group(1))
                    
                clave = f"{user_id}_{num}"
                actual_nums.append(num)
                
                fotos_en_disco[clave] = {
                    'path': real_path,
                    'user_id': user_id,
                    'numero': num,
                    'evidencia': ev,
                    'es_legacy': False,
                    'ruta_rel': ev_path_str
                }

        r['fotos_nums'] = sorted(list(set(actual_nums)))
        
    return fotos_en_disco, evidencias_qs

def _build_fotos_preview(fotos_en_disco, evidencias_qs):
    ev_by_path = {}
    for ev in evidencias_qs:
        ev_by_path[ev.ruta_archivo] = ev

    fotos_preview = []
    for clave, data in fotos_en_disco.items():
        real_path = data['path']
        if data['es_legacy']:
            try:
                ruta_rel = str(real_path.relative_to(settings.MEDIA_ROOT))
            except ValueError:
                ruta_rel = str(real_path)

            ev = ev_by_path.get(ruta_rel)
            fotos_preview.append({
                'clave':        clave.split('_v2_')[0],
                'numero':       data['numero'],
                'user_id':      data['user_id'],
                'url':          f"/media/{ruta_rel}",
                'angulo':       ev.angulo_rotacion if ev else 0,
                'evidencia_id': ev.id if ev else None,
                'excluida':     bool(ev.metadatos.get('excluida')) if ev and isinstance(ev.metadatos, dict) else False,
            })
        else:
            ev = data['evidencia']
            fotos_preview.append({
                'clave':        clave.split('_v2_')[0],
                'numero':       data['numero'],
                'user_id':      data['user_id'],
                'url':          f"/media/{data['ruta_rel']}",
                'angulo':       ev.angulo_rotacion,
                'evidencia_id': ev.id,
                'excluida':     bool(ev.metadatos.get('excluida')) if isinstance(ev.metadatos, dict) else False,
            })

    fotos_preview.sort(key=lambda x: (x['user_id'], x['numero']))
    return fotos_preview

@login_required
def revisar_orientacion(request):
    """
    Página de revisión de orientación de fotos antes de generar el Excel.
    Muestra todas las fotos del turno con su ángulo auto-detectado,
    y permite al usuario corregirlas con botones de rotación.
    """
    registros_data, fecha_desde, fecha_hasta = _get_orientacion_registros(request)
    
    registros_data.sort(key=lambda x: (x.get('user_id'), x['fotos_nums'][0] if x.get('fotos_nums') else 0))
    
    fotos_en_disco, evidencias_qs = _build_fotos_en_disco(registros_data)
    
    fotos_preview = _build_fotos_preview(fotos_en_disco, evidencias_qs)

    context = {
        'registros':           registros_data,
        'registros_json':      json.dumps(registros_data, default=str),
        'fotos_preview_json':  json.dumps(fotos_preview),
        'filtros': {'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta},
        'seccion':             'reportes',
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
            
            from .utils import get_orientation_image_path
            img_path = get_orientation_image_path(fotos_dir, user_id_str, num_int)
            if img_path:
                ang = detect_orientation(img_path)
                orientaciones[clave] = ang
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
    sn_map = {str(r['id']): r.get('sn_on_set', '') for r in registros_data if 'id' in r}
    
    # Extraer el orden de fotos definido en el frontend
    fotos_order = {str(r['id']): r.get('fotos_nums', []) for r in registros_data if 'id' in r}

    if not registros_data:
        return HttpResponse('Sin registros para generar.', status=400)

    registros_ids = [int(r['id']) for r in registros_data if 'id' in r]

    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    fecha_str = timezone.now().strftime('%Y%m%d_%H%M%S')

    # Encolar tarea Celery — no bloquea el proceso web
    task = generar_excel_task.delay(
        registros_ids=registros_ids,
        rotaciones=rotaciones,
        fotos_dir_str=str(fotos_dir),
        fecha_str=fecha_str,
        fotos_order=fotos_order,
        sn_map=sn_map,
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
    """Vista HTML principal del Panel Operativo con presets y filtros temporales unificados."""
    
    fecha_desde_str = request.GET.get('fecha_desde', '')
    fecha_hasta_str = request.GET.get('fecha_hasta', '')
    preset = request.GET.get('preset', '')
    
    # Compatibilidad con querystring legacy ?rango=...
    if not preset and not fecha_desde_str and not fecha_hasta_str:
        rango_legacy = request.GET.get('rango')
        if rango_legacy:
            preset = f"h{rango_legacy.replace('h', '')}" if 'h' in rango_legacy else 'h24'
    
    registros_base = get_registros_permitidos(request.user)
    
    dt_desde = _parse_aware_dt(fecha_desde_str, end=False) if fecha_desde_str else None
    dt_hasta = _parse_aware_dt(fecha_hasta_str, end=True) if fecha_hasta_str else None
    
    registros_qs = registros_base
    if dt_desde:
        registros_qs = registros_qs.filter(fecha_registro__gte=dt_desde)
    if dt_hasta:
        registros_qs = registros_qs.filter(fecha_registro__lte=dt_hasta)
        
    # Si no hubo fechas explícitas pero sí preset rápido
    if not dt_desde and not dt_hasta:
        _HOURS = {'h1': 1, 'h4': 4, 'h8': 8, 'h24': 24}
        if preset in _HOURS:
            delta = timedelta(hours=_HOURS[preset])
            dt_desde = timezone.now() - delta
            registros_qs = registros_base.filter(fecha_registro__gte=dt_desde)
        elif preset == 'd0':
            # Hoy
            hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            registros_qs = registros_base.filter(fecha_registro__gte=hoy_inicio)
        elif preset == 'd1':
            # Ayer
            hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            ayer_inicio = hoy_inicio - timedelta(days=1)
            registros_qs = registros_base.filter(fecha_registro__gte=ayer_inicio, fecha_registro__lt=hoy_inicio)
        elif preset.startswith('d') and preset[1:].isdigit():
            # d7, d14, d30...
            dias_count = int(preset[1:])
            dt_desde = timezone.now() - timedelta(days=dias_count)
            registros_qs = registros_base.filter(fecha_registro__gte=dt_desde)
        else:
            # Default últimas 24h
            preset = 'h24'
            registros_qs = registros_base.filter(fecha_registro__gte=timezone.now() - timedelta(hours=24))

    # Control de Polling: pausar si el límite superior está en el pasado
    now = timezone.now()
    disable_polling = bool(dt_hasta and dt_hasta < (now - timedelta(minutes=1)))
    
    registros_data = _parse_fotos_nums(registros_qs)
    
    # Si polling está deshabilitado enviamos last_id=None, sino enviamos el MAX(id) actual
    if disable_polling:
        last_id = None
    else:
        last_id = registros_qs.first().id if registros_qs.exists() else 0
    
    rango_activo = 'custom' if (preset == 'custom' or (not preset and (fecha_desde_str or fecha_hasta_str))) else preset
    
    context = {
        'registros_json': json.dumps(registros_data, default=str),
        'last_id': last_id,
        'rango_activo': rango_activo,
        'preset_activo': preset or rango_activo,
        'seccion': 'operacion',
        'filtros': {
            'fecha_desde': fecha_desde_str,
            'fecha_hasta': fecha_hasta_str,
            'preset': preset
        }
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

# ============================================================
# DICCIONARIO AI
# ============================================================

@login_required
def gestionar_diccionario(request):
    """Vista para editar el diccionario (materiales, defectos, síntomas)."""
    # BASE_DIR apunta a la carpeta "web", por lo que "shared" está en el nivel superior.
    catalog_path = settings.BASE_DIR.parent / 'shared' / 'infrastructure' / 'ai' / 'defect_catalog.json'
    
    try:
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
    except FileNotFoundError:
        catalog = {}
        
    # Formatear como JSON string para el frontend
    catalog_json = json.dumps(catalog, indent=2, ensure_ascii=False)
        
    context = {
        'catalog_json': catalog_json,
        'seccion': 'diccionario',
    }
    return render(request, 'calidad/diccionario.html', context)

@require_POST
@login_required
def api_guardar_diccionario(request):
    """Guarda el diccionario editado en el archivo JSON."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Solo administradores pueden modificar el diccionario.'}, status=403)
        
    try:
        data = json.loads(request.body)
        nuevo_diccionario = data.get('diccionario')
        
        if not nuevo_diccionario:
            return JsonResponse({'error': 'No se recibió el diccionario.'}, status=400)
            
        # Validar que es un dict válido
        if not isinstance(nuevo_diccionario, dict):
            return JsonResponse({'error': 'El diccionario debe ser un objeto JSON válido.'}, status=400)
            
        catalog_path = settings.BASE_DIR.parent / 'shared' / 'infrastructure' / 'ai' / 'defect_catalog.json'
        
        with open(catalog_path, 'w', encoding='utf-8') as f:
            json.dump(nuevo_diccionario, f, indent=2, ensure_ascii=False)
            
        return JsonResponse({'success': True})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================
# DESCARGA: TXT + ZIP (antes en el bot, ahora en la web)
# ============================================================

@login_required
def descargar_txt(request):
    """Genera y descarga un .txt con los registros del usuario/turno."""
    registros_qs = get_registros_permitidos(request.user)
    
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    dt_desde = _parse_aware_dt(fecha_desde, end=False)
    dt_hasta = _parse_aware_dt(fecha_hasta, end=True)
    if dt_desde:
        registros_qs = registros_qs.filter(fecha_registro__gte=dt_desde)
    if dt_hasta:
        registros_qs = registros_qs.filter(fecha_registro__lte=dt_hasta)

    perfil = getattr(request.user, 'perfil', None)
    turno = perfil.turno if perfil else '?'
    depto = perfil.departamento if perfil else '?'
    usuario = request.user.get_full_name() or request.user.username

    # Obtener nombres de usuarios
    from django.contrib.auth.models import User
    usuarios_map = {}
    for u in User.objects.select_related('perfil').all():
        if hasattr(u, 'perfil') and u.perfil.telegram_user_id:
            usuarios_map[u.perfil.telegram_user_id] = u.get_full_name() or u.username
        else:
            usuarios_map[u.id] = u.get_full_name() or u.username

    # Ordenar primero por usuario, luego por número de foto
    # ponytail: sorted() en Python porque min(fotos_nums) no es trivial en ORM con ArrayField.
    # ceiling: N*log(N) en memoria.
    registros_sorted = sorted(registros_qs, key=_sort_by_foto)

    # Mapa de numeración secuencial visual-only (no persiste)
    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    display_map = _build_display_map(registros_sorted, fotos_dir)

    lines = [
        f"REPORTE DE DEFECTOS - TURNO {turno} - {depto}",
        f"Generado por: {usuario} | Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]

    from itertools import groupby
    for user_id, grupo in groupby(registros_sorted, key=lambda x: x.user_id):
        nombre_usuario = usuarios_map.get(user_id, f"Operador_{user_id}")
        registros_grupo = list(grupo)
        uid_map = display_map.get(user_id, {})

        lines.append(f"--- {nombre_usuario} ({len(registros_grupo)} registros) ---")
        for r in registros_grupo:
            nums_reales = sorted(list(set(r.fotos_nums))) if r.fotos_nums else []
            fotos_display = _display_rango(nums_reales, uid_map) if uid_map else (r.fotos_rango or '-')
            lines.append(
                f"{fotos_display} | Modelo: {r.modelo} | Línea: {r.linea} | "
                f"Cant: {r.cantidad} | Resp: {r.responsable} | Desc: {r.descripcion}"
            )
        lines.append("")


    content = "\n".join(lines)
    filename = f"rep_{turno}_{depto}_{datetime.now().strftime('%H%M')}.txt"
    return HttpResponse(
        content,
        content_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@login_required
def descargar_zip(request):
    """Empaqueta y descarga las fotos del usuario en un ZIP."""
    import zipfile
    import tempfile
    from django.http import FileResponse

    registros_qs = get_registros_permitidos(request.user)
    
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    dt_desde = _parse_aware_dt(fecha_desde, end=False)
    dt_hasta = _parse_aware_dt(fecha_hasta, end=True)
    if dt_desde:
        registros_qs = registros_qs.filter(fecha_registro__gte=dt_desde)
    if dt_hasta:
        registros_qs = registros_qs.filter(fecha_registro__lte=dt_hasta)
        
    # Mismo orden y agrupación que el TXT
    registros_sorted = sorted(registros_qs, key=_sort_by_foto)

    # Mapa de numeración secuencial visual-only — mismo algoritmo que TXT
    # ponytail: se recalcula por separado pero con mismos inputs → mismo resultado garantizado.
    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    display_map = _build_display_map(registros_sorted, fotos_dir)
    
    # Obtener nombres de usuarios
    from django.contrib.auth.models import User
    usuarios_map = {}
    for u in User.objects.select_related('perfil').all():
        if hasattr(u, 'perfil') and u.perfil.telegram_user_id:
            usuarios_map[u.perfil.telegram_user_id] = u.get_valid_name() if hasattr(u, 'get_valid_name') else (u.get_full_name() or u.username).replace(" ", "_")
        else:
            usuarios_map[u.id] = (u.get_full_name() or u.username).replace(" ", "_")

    fotos_dir = settings.MEDIA_ROOT / 'fotos'

    # Usar tempfile para no saturar la RAM si descargan muchos a la vez
    fd, temp_path = tempfile.mkstemp(suffix=".zip", prefix="descarga_")
    os.close(fd)

    count = 0
    try:
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for reg in registros_sorted:
                user_id = reg.user_id
                nombre_dir = usuarios_map.get(user_id, f"Operador_{user_id}")
                uid_map = display_map.get(user_id, {})

                # Fase 2: Evidencias en DB
                for ev in reg.evidencias_v2.all():
                    ev_path = Path(settings.MEDIA_ROOT) / ev.ruta_archivo.lstrip('/')
                    if ev.ruta_archivo.startswith('media_files/'):
                        ev_path = Path(settings.MEDIA_ROOT) / ev.ruta_archivo[12:].lstrip('/')

                    if ev_path.exists():
                        import re as _re
                        m = _re.match(r'^(\d+)_', ev_path.name)
                        real_num = int(m.group(1)) if m else ev.id
                        display_num = uid_map.get(real_num)
                        if display_num is None:
                            continue  # no en mapa = ya contado o sin foto
                        arcname = f"{nombre_dir}/{display_num:03d}{ev_path.suffix}"
                        if arcname not in zf.namelist():
                            count += 1
                            zf.write(ev_path, arcname=arcname)

                # Fase 1 / Legacy
                nums = reg.fotos_nums if reg.fotos_nums else []
                if not nums:
                    from shared.utils.photo_parser import parse_photo_numbers
                    nums = parse_photo_numbers(reg.fotos)

                for num in sorted(list(set(nums))):
                    img = get_best_image_path(fotos_dir, str(user_id), num)
                    if img and img.exists():
                        display_num = uid_map.get(num)
                        if display_num is None:
                            continue
                        arcname = f"{nombre_dir}/{display_num:03d}{img.suffix}"
                        if arcname not in zf.namelist():
                            count += 1
                            zf.write(img, arcname=arcname)

        if count == 0:
            os.unlink(temp_path)
            return HttpResponse("No hay fotos para descargar.", status=404)

        perfil = getattr(request.user, 'perfil', None)
        turno = perfil.turno if perfil else 'X'
        filename = f"fotos_{turno}_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"

        response = FileResponse(_AutoDeleteFile(temp_path), content_type="application/zip")
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception:
        try: os.unlink(temp_path)
        except OSError: pass
        raise
