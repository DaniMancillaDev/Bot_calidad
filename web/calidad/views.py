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
from .models import RegistroDefecto, PerfilUsuario, EstadoRevision, PendingEvidence
from calidad.utils import get_best_image_path

# ============================================================
# CONSTANTES DE URL INTERNAS (X-Accel-Redirect)
# ============================================================

# Frontend usa estas prefixes para construir URLs de imágenes.
# Ahora apuntan a la vista proxy Django en lugar de a Nginx directo.
FOTOS_INTERNAL_PREFIX    = '/media-protegida/fotos/'
THUMBS_INTERNAL_PREFIX   = '/media-protegida/thumbs/'
PROXIES_INTERNAL_PREFIX  = '/media-protegida/proxies/'
IMPORTTEMP_INTERNAL_PREFIX = '/media-protegida/importaciones_temp/'

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


def _get_allowed_storage_ids(user):
    """Acepta carpetas históricas de Telegram y carpetas nuevas de Django."""
    if user.is_superuser:
        return None
    if not hasattr(user, 'perfil'):
        return set()

    perfiles = PerfilUsuario.objects.filter(
        turno=user.perfil.turno,
        departamento=user.perfil.departamento,
    )
    ids = set(perfiles.values_list('usuario_id', flat=True))
    ids.update(
        value for value in perfiles.values_list('telegram_user_id', flat=True)
        if value is not None
    )
    return ids


def _get_pending_evidence_count(user):
    """Cuenta evidencias WhatsApp disponibles para la bandeja del usuario."""
    from .views_pending import _has_pending_access

    if not _has_pending_access(user):
        return 0
    return PendingEvidence.objects.filter(
        status=PendingEvidence.STATUS_READY,
        group__isnull=True,
    ).count()



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
            m = _re.match(r'^(\d+)', filename)
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


def _filter_registros_from_request(request, base_qs=None):
    """
    Aplica filtros de request (linea, responsable, modelo, turno, depto,
    datetime-local o presets como h1, h4, h8, h24, d0, d1, d7, etc.)
    de forma unificada para vistas y exportaciones.
    """
    if base_qs is None:
        registros = get_registros_permitidos(request.user)
    else:
        registros = base_qs

    linea       = request.GET.get('linea', '')
    responsable = request.GET.get('responsable', '')
    modelo      = request.GET.get('modelo', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    preset      = request.GET.get('preset', '')
    lote_id     = request.GET.get('lote_id', '')

    # Filtrar por lote si se proporciona explícitamente
    if lote_id and lote_id.isdigit():
        registros = registros.filter(importacion_id=int(lote_id))
    else:
        # Aislamiento estricto: Las consultas globales (legacy) NO deben incluir registros de importaciones masivas.
        registros = registros.filter(importacion__isnull=True)

    # Primera carga sin parámetros: por defecto Hoy (d0), a menos que estemos filtrando por lote
    if not request.GET and not lote_id:
        preset = 'd0'

    if linea:
        registros = registros.filter(linea__icontains=linea)
    if responsable:
        registros = registros.filter(responsable__icontains=responsable)
    if modelo:
        from calidad.models import PerfilUsuario
        from django.db.models import Q
        matching_user_ids = list(PerfilUsuario.objects.filter(
            Q(usuario__first_name__icontains=modelo) |
            Q(usuario__last_name__icontains=modelo) |
            Q(usuario__username__icontains=modelo)
        ).values_list('telegram_user_id', flat=True))
        matching_user_ids = [uid for uid in matching_user_ids if uid is not None]

        registros = registros.filter(
            Q(descripcion__icontains=modelo) |
            Q(modelo__icontains=modelo) |
            Q(responsable__icontains=modelo) |
            Q(numero_parte__icontains=modelo) |
            Q(linea__icontains=modelo) |
            Q(departamento__icontains=modelo) |
            Q(user_id__in=matching_user_ids) |
            Q(fotos__icontains=modelo)
        )

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
    return registros, fecha_desde, fecha_hasta, preset, rango_activo


# ============================================================
# REPORTES (LISTA DE DEFECTOS)
# ============================================================

@login_required
def reportes(request):
    """Lista completa de registros filtrados por turno y presets temporales."""
    registros, fecha_desde, fecha_hasta, preset, rango_activo = _filter_registros_from_request(request)

    linea       = request.GET.get('linea', '')
    responsable = request.GET.get('responsable', '')
    modelo      = request.GET.get('modelo', '')

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

    latest_record_id = base_qs.order_by('-id').values_list('id', flat=True).first() or 0

    context = {
        'registros':    registros,
        'total_registros': len(registros),
        'latest_record_id': latest_record_id,
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
def serve_protected_media(request, subpath):
    """
    Proxy autorizado de archivos de media vía X-Accel-Redirect.
    
    Flujo:
      Browser → Django (auth + permisos) → X-Accel-Redirect → Nginx internal → archivo
    
    Seguridad:
    - Solo usuarios autenticados.
    - Path traversal bloqueado: resolvemos la ruta y verificamos que queda dentro de MEDIA_ROOT.
    - Política de turno/departamento: el user_id de la carpeta debe estar autorizado
      por get_registros_permitidos (misma política que todos los endpoints).
    - Superuser puede ver todo.
    """
    import posixpath
    
    # 1. Sanitizar y resolver la ruta — bloquear traversal
    subpath_clean = posixpath.normpath(subpath).lstrip('/')
    full_path = (Path(settings.MEDIA_ROOT) / subpath_clean).resolve()
    
    try:
        full_path.relative_to(Path(settings.MEDIA_ROOT).resolve())
    except ValueError:
        raise Http404("Ruta no permitida")
    
    if not full_path.exists() or not full_path.is_file():
        raise Http404("Archivo no encontrado")
    
    # 2. Verificar autorización por turno/depto
    # El path tiene la forma: fotos/<user_id>/<filename> o proxies/<user_id>/<filename>
    # etc. Extraemos el user_id del segundo segmento para validar.
    parts = subpath_clean.split('/')
    PROTECTED_PREFIXES = ('fotos', 'thumbs', 'proxies')
    
    if len(parts) >= 2 and parts[0] in PROTECTED_PREFIXES:
        try:
            path_user_id = int(parts[1])
        except ValueError:
            raise Http404("Ruta no permitida")
        
        if not request.user.is_superuser:
            # Acepta tanto el ID histórico de Telegram como el ID Django.
            allowed_user_ids = _get_allowed_storage_ids(request.user)
            if path_user_id not in allowed_user_ids:
                raise Http404("Sin permiso para este archivo")
    elif parts[0] == 'importaciones_temp':
        # Temporales de importación: solo el usuario que subió la sesión puede verlos.
        # El session_id es el session_key del usuario, impredecible externamente.
        # No exponemos datos de negocio, pero por seguridad verificamos que el
        # session_key en la URL coincida con la sesión activa del usuario.
        if not request.user.is_superuser:
            session_key = request.session.session_key
            if len(parts) < 2 or parts[1] != session_key:
                raise Http404("Sin permiso para este archivo temporal")
    else:
        # Directorio desconocido dentro de MEDIA_ROOT — bloquear por defecto
        raise Http404("Ruta no permitida")
    
    # 3. Devolver respuesta vacía con cabecera X-Accel-Redirect
    # Nginx ve la cabecera, cancela la respuesta Django y entrega el archivo directamente.
    # La URL interna apunta a /protected/ que Nginx tiene como `internal`.
    internal_url = f"/protected/{subpath_clean}"
    
    response = HttpResponse()
    response['X-Accel-Redirect'] = internal_url
    response['Content-Type'] = ''  # Nginx infiere el tipo correcto
    return response


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
            usuarios_permitidos = _get_allowed_storage_ids(request.user)
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
            url_foto = f"/media-protegida/proxies/{user_id}/{img_path.name}" if "proxies" in str(img_path) else f"/media-protegida/fotos/{user_id}/{img_path.name}"
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
            'numero_parte', 'cantidad', 'responsable', 'descripcion',
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

    registro_id = request.GET.get('registro')
    if registro_id is not None:
        if registro_id.isascii() and registro_id.isdigit() and 0 < len(registro_id) <= 18:
            registros_qs = registros_qs.filter(pk=int(registro_id))
        else:
            registros_qs = registros_qs.none()

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
        
        # Buscar IDs de Telegram de los operarios que coincidan con el texto
        from calidad.models import PerfilUsuario
        from django.db.models import Q
        matching_user_ids = list(PerfilUsuario.objects.filter(
            Q(usuario__first_name__icontains=q_filter) |
            Q(usuario__last_name__icontains=q_filter) |
            Q(usuario__username__icontains=q_filter)
        ).values_list('telegram_user_id', flat=True))
        # Remove None values
        matching_user_ids = [uid for uid in matching_user_ids if uid is not None]

        m = re.match(r'^(\d+)\s*-\s*(\d+)$', q_filter.strip())
        if m:
            start_num = int(m.group(1))
            end_num = int(m.group(2))
            range_list = list(range(start_num, end_num + 1))
            registros_qs = registros_qs.filter(
                Q(descripcion__icontains=q_filter) |
                Q(modelo__icontains=q_filter) |
                Q(responsable__icontains=q_filter) |
                Q(numero_parte__icontains=q_filter) |
                Q(linea__icontains=q_filter) |
                Q(departamento__icontains=q_filter) |
                Q(user_id__in=matching_user_ids) |
                Q(fotos_nums__overlap=range_list)
            )
        elif q_filter.strip().isdigit():
            num = int(q_filter.strip())
            registros_qs = registros_qs.filter(
                Q(descripcion__icontains=q_filter) |
                Q(modelo__icontains=q_filter) |
                Q(responsable__icontains=q_filter) |
                Q(numero_parte__icontains=q_filter) |
                Q(linea__icontains=q_filter) |
                Q(departamento__icontains=q_filter) |
                Q(user_id__in=matching_user_ids) |
                Q(fotos__icontains=q_filter) |
                Q(fotos_nums__contains=[num])
            )
        else:
            registros_qs = registros_qs.filter(
                Q(descripcion__icontains=q_filter) |
                Q(modelo__icontains=q_filter) |
                Q(responsable__icontains=q_filter) |
                Q(numero_parte__icontains=q_filter) |
                Q(linea__icontains=q_filter) |
                Q(departamento__icontains=q_filter) |
                Q(user_id__in=matching_user_ids) |
                Q(fotos__icontains=q_filter)
            )
            
    return registros_qs, filtros

def _enrich_galeria_registros(object_list):
    import re
    num_prefix_re = re.compile(r'^(\d+)')

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
    proxies_url = '/media-protegida/proxies/'

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

            orig_src = f"/media-protegida/{path}"
            if filename in thumbs_set:
                thumb_src = f"{thumbs_url}{reg.user_id}/{filename}"
            elif filename in proxies_set:
                thumb_src = f"{proxies_url}{reg.user_id}/{filename}"
            else:
                thumb_src = orig_src

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
            orig_src = f"{fotos_url}{reg.user_id}/{foto_filename}"

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
        
        # Integrar conteo de Fase 2 (Evidencias en Base de Datos)
        v2_count = r.get('v2_count', 0) if is_dict else getattr(r, 'v2_count', 0)
        
        nums = []
        if fotos_str:
            # Bugfix: Si el registro viene de Importacion Web, trae fotos="1" como dummy
            # Si tiene v2_count, ignoramos el "1" para no traer la foto 001.jpg por error.
            if v2_count > 0 and str(fotos_str).strip() == "1":
                nums = []
            else:
                nums = parse_photo_numbers(str(fotos_str))
                
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
            'invoice':        r.get('invoice', '') if is_dict else getattr(r, 'invoice', ''),
            'wo':             r.get('wo', '') if is_dict else getattr(r, 'wo', ''),
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
    
    # ponytail: Leer IDs de la sesión para evitar URLs kilométricas
    rev_id = request.GET.get('rev_id')
    if rev_id:
        ids_str = request.session.get(f'revisar_ids_{rev_id}', '')
    else:
        ids_str = request.session.get('revisar_ids', '')
    
    if ids_str:
        try:
            ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
            if ids:
                from django.db.models import Case, When
                preserved_order = Case(*[When(id=id_, then=pos) for pos, id_ in enumerate(ids)])
                registros_qs = get_registros_permitidos(request.user).filter(id__in=ids).order_by(preserved_order)
                
                # ponytail: Si la URL exige un lote, purgar cualquier ID basura en sesión que sea de otro lote
                lote_id = request.GET.get('lote_id')
                if lote_id and lote_id.isdigit():
                    registros_qs = registros_qs.filter(importacion_id=int(lote_id))
                    
                registros_data = _parse_fotos_nums(registros_qs)
                return registros_data, fecha_desde, fecha_hasta
        except Exception:
            pass
            
    # Si no hay IDs explícitos, usar filtros de request estándar
    registros_qs, fecha_desde, fecha_hasta, preset, _ = _filter_registros_from_request(request)
    registros_data = _parse_fotos_nums(registros_qs)
    
    # ponytail: Pre-filtrado estricto si venimos de generar Box Condition
    if request.GET.get('box_condition') == '1':
        from calidad.services.reporte_box_condition import es_box_condition, DUTY_BOX_CONDITION
        from shared.infrastructure.ai.defect_translator import build_translator
        translator = build_translator()
        
        filtered_data = []
        for r in registros_data:
            resp = (r.get('responsable') or '').strip().upper()
            if resp in DUTY_BOX_CONDITION and es_box_condition(r.get('descripcion'), translator):
                filtered_data.append(r)
        registros_data = filtered_data
        
    return registros_data, fecha_desde, fecha_hasta

def _build_fotos_en_disco(registros_data):
    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    fotos_en_disco = {} # key will be (registro_id, clave)
    
    from calidad.models import EvidenciaFotografica
    registro_ids = [r['id'] for r in registros_data if r.get('id')]
    evidencias_qs = EvidenciaFotografica.objects.filter(
        registro_id__in=registro_ids
    ).order_by('registro_id', 'orden', 'id')
    
    evs_por_registro = {}
    for ev in evidencias_qs:
        if ev.registro_id not in evs_por_registro:
            evs_por_registro[ev.registro_id] = []
        evs_por_registro[ev.registro_id].append(ev)

    for r in registros_data:
        evs = evs_por_registro.get(r['id'], [])
        whatsapp_evs = [
            ev for ev in evs
            if isinstance(ev.metadatos, dict)
            and ev.metadatos.get('source') == PendingEvidence.SOURCE_WHATSAPP
        ]
        r['whatsapp_evidence_count'] = len(whatsapp_evs)
        r['whatsapp_sender_count'] = len({
            ev.metadatos.get('sender_whatsapp_id') for ev in whatsapp_evs
            if ev.metadatos.get('sender_whatsapp_id')
        })

        user_id = r.get('user_id')
        if not user_id:
            continue
            
        user_folder = fotos_dir / str(user_id)
        
        # ponytail: Detectar V2 para limpiar rangos falsos (ej. fotos="1" -> [1])
        has_v2 = False
        for ev in evs:
            path_name = Path(ev.ruta_archivo).name
            if not path_name.split('.')[0].isdigit():
                has_v2 = True
                break
                
        # Si es V2, ignoramos lo que diga la columna fotos (que suele ser "1" o "WEB")
        # para no inyectar fotos fantasma.
        base_nums = [] if has_v2 else r.get('fotos_nums', [])
        actual_nums = []
        
        if user_folder.exists():
            for num in base_nums:
                clave = f"{user_id}_{num}"
                if clave in fotos_en_disco:
                    actual_nums.append(num)
                    continue
                    
                img_path = get_best_image_path(fotos_dir, str(user_id), num)
                if img_path:
                    try:
                        ruta_rel = str(img_path.relative_to(settings.MEDIA_ROOT))
                    except ValueError:
                        ruta_rel = str(img_path).replace(str(settings.MEDIA_ROOT), '').lstrip('/')
                    
                    def _norm(p):
                        p = p.lstrip('/')
                        for pfx in ('media_files/', 'mediafiles/'):
                            if p.startswith(pfx):
                                return p[len(pfx):]
                        return p
                    
                    ruta_rel_norm = _norm(ruta_rel)
                    ev_for_legacy = next((e for e in evs if _norm(e.ruta_archivo) == ruta_rel_norm), None)
                    if ev_for_legacy and isinstance(ev_for_legacy.metadatos, dict) and ev_for_legacy.metadatos.get('excluida'):
                        continue

                    fotos_en_disco[(r.get('id'), clave)] = {
                        'path': img_path,
                        'user_id': user_id,
                        'numero': num,
                        'orden': ev_for_legacy.orden if ev_for_legacy else None,
                        'es_legacy': True,
                        'registro_id': r.get('id'),
                    }
                    actual_nums.append(num)
                    
        for ev in evs:
            if isinstance(ev.metadatos, dict) and ev.metadatos.get('excluida'):
                continue

            ev_path_str = ev.ruta_archivo
            if ev_path_str.startswith('media_files/'):
                ev_path_str = ev_path_str[12:]
            elif ev_path_str.startswith('/media_files/'):
                ev_path_str = ev_path_str[13:]
            ev_path_str = ev_path_str.lstrip('/')
            
            real_path = Path(settings.MEDIA_ROOT) / ev_path_str
            if real_path.exists():
                import re as _re
                m = _re.match(r'^(\d+)', real_path.name)
                num = int(m.group(1)) if m else ev.id
                    
                clave = f"{user_id}_{num}"
                actual_nums.append(num)
                
                fotos_en_disco[(r.get('id'), clave)] = {
                    'path': real_path,
                    'user_id': user_id,
                    'numero': num,
                    'orden': ev.orden,
                    'evidencia': ev,
                    'es_legacy': False,
                    'ruta_rel': ev_path_str,
                    'registro_id': r.get('id'),
                }

        r['fotos_nums'] = list(dict.fromkeys(actual_nums))
        
    return fotos_en_disco, evidencias_qs


def _build_fotos_preview(fotos_en_disco, evidencias_qs):
    ev_by_path = {}
    for ev in evidencias_qs:
        ev_by_path[ev.ruta_archivo] = ev

    thumbs_root = Path(settings.THUMBS_ROOT)
    proxies_root = Path(settings.MEDIA_ROOT) / 'proxies'
    thumbs_url  = settings.THUMBS_URL
    proxies_url = '/media-protegida/proxies/'

    # Pre-indexar thumbs y proxies por usuario para verificación O(1) en memoria
    user_ids = {data['user_id'] for data in fotos_en_disco.values() if data.get('user_id')}
    user_thumbs = {}
    user_proxies = {}
    for uid in user_ids:
        t_dir = thumbs_root / str(uid)
        user_thumbs[uid] = {entry.name for entry in os.scandir(t_dir) if entry.is_file()} if t_dir.is_dir() else set()
        p_dir = proxies_root / str(uid)
        user_proxies[uid] = {entry.name for entry in os.scandir(p_dir) if entry.is_file()} if p_dir.is_dir() else set()

    fotos_preview = []
    for (reg_id, string_clave), data in fotos_en_disco.items():
        real_path = data['path']
        filename = real_path.name
        user_id = data['user_id']

        has_thumb = filename in user_thumbs.get(user_id, set())
        has_proxy = filename in user_proxies.get(user_id, set())

        if data['es_legacy']:
            try:
                ruta_rel = str(real_path.relative_to(settings.MEDIA_ROOT))
            except ValueError:
                ruta_rel = str(real_path)

            orig_url = f"/media-protegida/{ruta_rel}"
            ev = ev_by_path.get(ruta_rel)
            angulo = ev.angulo_rotacion if ev else 0
            ev_id = ev.id if ev else None
            excluida = bool(ev.metadatos.get('excluida')) if ev and isinstance(ev.metadatos, dict) else False
        else:
            ev = data['evidencia']
            orig_url = f"/media-protegida/{data['ruta_rel']}"
            angulo = ev.angulo_rotacion
            ev_id = ev.id
            excluida = bool(ev.metadatos.get('excluida')) if isinstance(ev.metadatos, dict) else False

        thumb_src = f"{thumbs_url}{user_id}/{filename}" if has_thumb else (f"{proxies_url}{user_id}/{filename}" if has_proxy else orig_url)
        proxy_src = f"{proxies_url}{user_id}/{filename}" if has_proxy else orig_url
        fotos_preview.append({
            'clave':        string_clave.split('_v2_')[0],
            'numero':       data['numero'],
            'orden':        data.get('orden'),
            'user_id':      user_id,
            'url':          orig_url,
            'thumb_url':    thumb_src,
            'proxy_url':    proxy_src,
            'angulo':       angulo,
            'evidencia_id': ev_id,
            'excluida':     excluida,
            'registro_id':  data.get('registro_id'),
        })

    fotos_preview.sort(key=lambda x: (
        x['user_id'],
        x['registro_id'] or 0,
        x['orden'] if x['orden'] is not None else float('inf'),
        x['numero'],
    ))
    return fotos_preview

@login_required
def revisar_orientacion(request):
    """
    Página de revisión de orientación de fotos antes de generar el Excel.
    Muestra todas las fotos del turno con su ángulo auto-detectado,
    y permite al usuario corregirlas con botones de rotación.
    """
    if request.method == 'POST':
        order_raw = request.POST.get('order')
        if order_raw is not None:
            requested_order = [
                int(value) for value in order_raw.split(',')
                if value.strip().isdigit()
            ]
            rev_id = request.POST.get('rev_id') or request.GET.get('rev_id')
            session_key = f'revisar_ids_{rev_id}' if rev_id else 'revisar_ids'
            current_order = [
                int(value) for value in request.session.get(session_key, '').split(',')
                if value.strip().isdigit()
            ]

            is_same_set = (
                requested_order
                and len(requested_order) == len(set(requested_order))
                and len(requested_order) == len(current_order)
                and set(requested_order) == set(current_order)
            )
            if not is_same_set:
                return JsonResponse(
                    {'ok': False, 'message': 'El orden no pertenece al lote actual.'},
                    status=400,
                )

            request.session[session_key] = ','.join(map(str, requested_order))
            return JsonResponse({'ok': True})

        raw_ids = request.POST.get('ids', '')
        ids_solicitados = [int(i) for i in raw_ids.split(',') if i.strip().isdigit()]
        redirect_url = request.get_full_path()
        if ids_solicitados:
            permitidos = set(get_registros_permitidos(request.user).filter(id__in=ids_solicitados).values_list('id', flat=True))
            ids_validos = [str(i) for i in ids_solicitados if i in permitidos]
            
            import uuid
            from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse
            
            rev_id = uuid.uuid4().hex[:8]
            request.session[f'revisar_ids_{rev_id}'] = ','.join(ids_validos)
            
            active_revs = request.session.get('active_revs', [])
            active_revs.append(rev_id)
            if len(active_revs) > 5:
                old_rev = active_revs.pop(0)
                request.session.pop(f'revisar_ids_{old_rev}', None)
            request.session['active_revs'] = active_revs
            
            parsed = urlparse(redirect_url)
            query = parse_qsl(parsed.query)
            query = [q for q in query if q[0] != 'rev_id']
            query.append(('rev_id', rev_id))
            redirect_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), parsed.fragment))
        else:
            request.session['revisar_ids'] = ''
            
        return redirect(redirect_url)

    registros_data, fecha_desde, fecha_hasta = _get_orientacion_registros(request)
    
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
    fotos_order = {str(r['id']): r.get('fotos_nums', []) for r in registros_data if 'id' in r}
    

    if not registros_data:
        return HttpResponse('Sin registros para generar.', status=400)

    registros_ids = [int(r['id']) for r in registros_data if 'id' in r]
    registros_ids_set = set(registros_ids)
    
    lote_id = request.GET.get('lote_id', '')
    
    from calidad.models import RegistroDefecto, ImportacionLote
    registros_bd = RegistroDefecto.objects.filter(id__in=registros_ids_set)
    
    # Validar que no haya IDs inexistentes
    if registros_bd.count() != len(registros_ids_set):
        return HttpResponse('Error de integridad: Se enviaron IDs inexistentes o duplicados.', status=400)

    # ── Validación estricta de Integridad del Lote ──
    if lote_id and lote_id.isdigit():
        if not ImportacionLote.objects.filter(id=int(lote_id)).exists():
            return HttpResponse(f'Error: El lote {lote_id} no existe.', status=400)
        for r in registros_bd:
            if str(r.importacion_id) != lote_id:
                return HttpResponse(f'Error de integridad: El registro {r.id} no pertenece al lote {lote_id}.', status=400)

    # ── Autorización (NUEVO) ──
    # ponytail: La vista es la frontera. Solo enviamos a Celery lo autorizado.
    ids_autorizados = set(get_registros_permitidos(request.user).filter(id__in=registros_ids_set).values_list('id', flat=True))
    
    
    if not ids_autorizados:
        return HttpResponse('Error de autorización: No tiene permiso para exportar ninguno de los registros solicitados.', status=403)
        
    # Filtrar silenciosamente para comportarse como Box Condition
    registros_ids = [id_ for id_ in registros_ids if id_ in ids_autorizados]

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
        lote_id=lote_id if lote_id else None
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
            'error': data.get('error'),
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

    if nombre.endswith('.zip'):
        content_type = 'application/zip'
    elif nombre.endswith('.pptx'):
        content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    else:
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
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
    
    lote_id = request.GET.get('lote_id')
    dt_desde = _parse_aware_dt(fecha_desde_str, end=False) if fecha_desde_str else None
    dt_hasta = _parse_aware_dt(fecha_hasta_str, end=True) if fecha_hasta_str else None
    
    registros_qs = registros_base
    
    if lote_id and lote_id.isdigit():
        registros_qs = registros_qs.filter(importacion_id=int(lote_id))
        preset = 'lote'
    else:
        if dt_desde:
            registros_qs = registros_qs.filter(fecha_registro__gte=dt_desde)
        if dt_hasta:
            registros_qs = registros_qs.filter(fecha_registro__lte=dt_hasta)
            
    # Si no hubo fechas explícitas ni lote_id pero sí preset rápido
    if not dt_desde and not dt_hasta and not lote_id:
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

    # Control de Polling: pausar si el límite superior está en el pasado o si estamos viendo un lote fijo
    now = timezone.now()
    disable_polling = bool(dt_hasta and dt_hasta < (now - timedelta(minutes=1))) or bool(lote_id)
    
    registros_data = _parse_fotos_nums(registros_qs)
    
    # ponytail: Pre-filtrado estricto si venimos de generar Box Condition
    if request.GET.get('box_condition') == '1':
        from calidad.services.reporte_box_condition import es_box_condition, DUTY_BOX_CONDITION
        from shared.infrastructure.ai.defect_translator import build_translator
        translator = build_translator()
        
        filtered_data = []
        for r in registros_data:
            resp = (r.get('responsable') or '').strip().upper()
            if resp in DUTY_BOX_CONDITION and es_box_condition(r.get('descripcion'), translator):
                filtered_data.append(r)
        registros_data = filtered_data
    
    # Preparar previews visuales (thumbnails reales desde DB)
    fotos_en_disco, evidencias_qs = _build_fotos_en_disco(registros_data)
    fotos_preview_list = _build_fotos_preview(fotos_en_disco, evidencias_qs)
    
    fotos_by_reg = {}
    for fp in fotos_preview_list:
        rid = fp.get('registro_id')
        if rid:
            if rid not in fotos_by_reg:
                fotos_by_reg[rid] = []
            fotos_by_reg[rid].append(fp)
            
    for r in registros_data:
        r['fotos_preview'] = fotos_by_reg.get(r['id'], [])
    
    # Si polling está deshabilitado enviamos last_id=None, sino enviamos el MAX(id) actual
    if disable_polling:
        last_id = None
    else:
        last_id = registros_qs.first().id if registros_qs.exists() else 0
    
    rango_activo = 'custom' if (preset == 'custom' or (not preset and (fecha_desde_str or fecha_hasta_str))) else preset
    
    context = {
        'registros_json': json.dumps(registros_data, default=str),
        'last_id': last_id,
        'pending_evidence_count': _get_pending_evidence_count(request.user),
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
    pending_evidence_count = _get_pending_evidence_count(request.user)
    
    from django.db.models import Max
    max_id_dict = registros_base.aggregate(Max('id'))
    max_id = max_id_dict['id__max'] or 0
    
    if max_id > last_id:
        # Hay nuevos registros
        nuevos_count = registros_base.filter(id__gt=last_id).count()
        return JsonResponse({
            'has_updates': True,
            'max_id': max_id,
            'nuevos_count': nuevos_count,
            'pending_evidence_count': pending_evidence_count,
        })
    
    return JsonResponse({
        'has_updates': False,
        'max_id': max_id,
        'pending_evidence_count': pending_evidence_count,
    })

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
    
    fotos_en_disco, evidencias_qs = _build_fotos_en_disco(registros_data)
    fotos_preview_list = _build_fotos_preview(fotos_en_disco, evidencias_qs)
    
    fotos_by_reg = {}
    for fp in fotos_preview_list:
        rid = fp.get('registro_id')
        if rid:
            if rid not in fotos_by_reg:
                fotos_by_reg[rid] = []
            fotos_by_reg[rid].append(fp)
            
    for r in registros_data:
        r['fotos_preview'] = fotos_by_reg.get(r['id'], [])
    
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
    registros_qs, _, _, _, _ = _filter_registros_from_request(request)

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
    filename = f"reporte_{turno}_{depto}.txt"
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

    registros_qs, _, _, _, _ = _filter_registros_from_request(request)
        
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
                        m = _re.match(r'^(\d+)', ev_path.name)
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
        filename = f"fotos_{turno}.zip"

        response = FileResponse(_AutoDeleteFile(temp_path), content_type="application/zip")
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception:
        try: os.unlink(temp_path)
        except OSError: pass
        raise

@login_required
def generar_excel_box_condition(request):
    """
    Encola la generación del Excel Box Condition con Celery.
    Acepta IDs explícitos (desde /operacion/) o un lote_id (desde /reportes/).
    """
    from .tasks import generar_excel_box_condition_task
    from django.http import JsonResponse
    import json

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    lote_id = request.GET.get('lote_id')
    registros_data = []
    rotaciones = {}
    
    try:
        body = json.loads(request.body)
        registros_data = body.get('registros', [])
        rotaciones = body.get('rotaciones', {})
    except Exception:
        pass

    if not lote_id and not registros_data:
        return JsonResponse({'error': 'Se requieren registros explícitos o un lote_id.'}, status=400)

    from calidad.models import ImportacionLote
    if lote_id:
        if not ImportacionLote.objects.filter(id=lote_id).exists():
            return JsonResponse({'error': 'Lote no encontrado'}, status=404)
        # ponytail: validar que el usuario tenga acceso a registros de este lote
        permitidos_lote = get_registros_permitidos(request.user).filter(importacion_id=lote_id)
        if not permitidos_lote.exists():
            return JsonResponse({'error': 'No tienes permisos para este lote'}, status=403)
            
        if not registros_data:
            # ponytail: la vista DEBE resolver la intersección permitidos ∩ lote. No delegar a Celery.
            registros_data = [{'id': r_id} for r_id in permitidos_lote.values_list('id', flat=True)]

    if registros_data:
        # ponytail: validar que los IDs explícitos pertenezcan al usuario
        ids_solicitados = [int(r.get('id')) for r in registros_data if str(r.get('id', '')).isdigit()]
        if ids_solicitados:
            permitidos = set(get_registros_permitidos(request.user).filter(id__in=ids_solicitados).values_list('id', flat=True))
            registros_data = [r for r in registros_data if int(r.get('id')) in permitidos]
            if not registros_data:
                return JsonResponse({'error': 'No tienes permisos para estos registros'}, status=403)

    fotos_dir = settings.MEDIA_ROOT / 'fotos'

    task = generar_excel_box_condition_task.delay(
        lote_id=lote_id,
        fotos_dir_str=str(fotos_dir),
        registros_data=registros_data,
        rotaciones=rotaciones
    )

    return JsonResponse({'task_id': task.id})

@login_required
def api_lotes_importacion(request):
    """Lista de lotes de importación autorizados para el usuario actual."""
    from django.db.models import Count
    from calidad.models import ImportacionLote
    
    permitidos_qs = get_registros_permitidos(request.user)
    lotes_ids = permitidos_qs.values_list('importacion_id', flat=True).distinct()
    
    data = list(
        ImportacionLote.objects.filter(id__in=lotes_ids)
        .annotate(total_registros=Count('registros'))
        .order_by('-fecha_inicio')[:50]
        .values('id', 'fecha_inicio', 'total_registros')
    )
    for l in data:
        l['fecha'] = l.pop('fecha_inicio').strftime('%d-%b-%Y %H:%M')
    return JsonResponse({'lotes': data})

@login_required
def revisar_box_condition(request):
    """
    Segunda etapa específica para Box Condition.
    Filtra los IDs provenientes de la selección principal y muestra una vista
    enfocada en selección local y edición de estos candidatos.
    """
    rev_id = request.GET.get('rev_id')
    if rev_id:
        ids_str = request.session.get(f'revisar_ids_{rev_id}', '')
    else:
        ids_str = request.session.get('revisar_ids', '')
    lote_id = request.GET.get('lote_id')

    if not ids_str:
        # ponytail: fallback a lote completo si viene lote_id (flujo importacion→revisar→box-condition directo)
        if lote_id:
            ids = list(
                get_registros_permitidos(request.user)
                .filter(importacion_id=lote_id)
                .values_list('id', flat=True)
                .order_by('id')
            )
            if not ids:
                return redirect('panel_operativo')
        else:
            return redirect('panel_operativo')
    else:
        try:
            ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
        except ValueError:
            return redirect('panel_operativo')
        
    from django.db.models import Case, When
    preserved_order = Case(*[When(id=id_, then=pos) for pos, id_ in enumerate(ids)])
    registros_qs = get_registros_permitidos(request.user).filter(id__in=ids).order_by(preserved_order)
    
    # Obtenemos los registros con sus fotos pre-parseadas
    registros_data = _parse_fotos_nums(registros_qs)
    
    from calidad.services.reporte_box_condition import es_box_condition, DUTY_BOX_CONDITION
    from shared.infrastructure.ai.defect_translator import build_translator
    translator = build_translator()
    
    candidatos = []
    for r in registros_data:
        resp = (r.get('responsable') or '').strip().upper()
        if resp in DUTY_BOX_CONDITION and es_box_condition(r.get('descripcion'), translator):
            candidatos.append(r)
            
    # Traer fotos thumbnail para visualización rápida
    fotos_en_disco, evidencias_qs = _build_fotos_en_disco(candidatos)
    fotos_preview = _build_fotos_preview(fotos_en_disco, evidencias_qs)
    
    # Agrupar las previews por registro para que el template las pinte fácil
    fotos_by_reg = {}
    for f in fotos_preview:
        if f['registro_id'] not in fotos_by_reg:
            fotos_by_reg[f['registro_id']] = []
        fotos_by_reg[f['registro_id']].append(f)
        
    # Filtrar también los fotos_preview para que solo queden las fotos de los candidatos
    fotos_preview_filtradas = [f for f in fotos_preview if f['registro_id'] in [c['id'] for c in candidatos]]

    # Reutilizamos el mismo JSON shape que /revisar/
    context = {
        'registros':           candidatos,
        'registros_json':      json.dumps(candidatos, default=str),
        'fotos_preview_json':  json.dumps(fotos_preview_filtradas),
        'filtros':             {},
        'seccion':             'revisar'
    }
    return render(request, 'calidad/revisar_box_condition.html', context)
