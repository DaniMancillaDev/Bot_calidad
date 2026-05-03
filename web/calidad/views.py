"""
Vistas del Panel de Calidad.
"""
import os
import re
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from .models import RegistroDefecto, UsuarioBot, PerfilUsuario


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
    Parsea el campo 'fotos' de los registros (ej. '(001-003)') 
    y extrae un set con los números enteros individuales permitidos.
    """
    numeros_permitidos = set()
    for r in registros:
        if not r.fotos:
            continue
        
        # Buscar rangos: (001-005)
        rangos = re.findall(r'\((\d+)-(\d+)\)', r.fotos)
        for inicio, fin in rangos:
            numeros_permitidos.update(range(int(inicio), int(fin) + 1))
            
        # Buscar individuales por si acaso (aunque el bot agrupa en rangos)
        # Esto atraparía (001) si existiera
        individuales = re.findall(r'\((\d+)\)', r.fotos.replace('-', 'X')) # Evitar contar los rangos
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

    context = {
        'registros':    registros,
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
            usuarios_bot = UsuarioBot.objects.filter(
                turno=request.user.perfil.turno,
                departamento=request.user.perfil.departamento
            ).values_list('telegram_user_id', flat=True)
            usuarios_permitidos = set(usuarios_bot)
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
        'seccion':    'fotos',
    }
    return render(request, 'calidad/ver_foto.html', context)


# ============================================================
# GALERÍA DE FOTOS
# ============================================================

@login_required
def galeria_fotos(request):
    """Muestra galería filtrada por turno/departamento."""
    fotos = []

    # Obtener user_ids permitidos (del mismo turno/depto)
    if request.user.is_superuser:
        # Admin ve todos los usuarios que tienen fotos
        usuarios_permitidos = None
    else:
        if hasattr(request.user, 'perfil'):
            # Buscar usuarios del bot con mismo turno y departamento
            usuarios_bot = UsuarioBot.objects.filter(
                turno=request.user.perfil.turno,
                departamento=request.user.perfil.departamento
            ).values_list('telegram_user_id', flat=True)
            usuarios_permitidos = set(usuarios_bot)
        else:
            usuarios_permitidos = set()

    fotos_base_dir = settings.MEDIA_ROOT / 'fotos'

    if fotos_base_dir.exists():
        # Iterar sobre carpetas de usuarios
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

            # Buscar fotos en la carpeta del usuario
            for archivo in sorted(user_folder.glob('*.png')):
                # Extraer número de secuencia (formato: 001_timestamp.png)
                try:
                    num = int(archivo.stem.split('_')[0])
                except (ValueError, IndexError):
                    num = 0

                fotos.append({
                    'numero': num,
                    'url': f"/media/fotos/{user_id}/{archivo.name}",
                    'nombre': archivo.name,
                    'usuario': user_id,
                })

    # Ordenar por número
    fotos.sort(key=lambda x: x['numero'])

    context = {
        'fotos':   fotos,
        'total':   len(fotos),
        'seccion': 'fotos',
    }
    return render(request, 'calidad/galeria.html', context)


# ============================================================
# REVISIÓN DE ORIENTACIÓN + GENERACIÓN DE EXCEL
# ============================================================

def _parse_fotos_nums(registros):
    """
    Extrae los números de foto individuales de los registros.
    El bot guarda rangos como '(001-005)' o '(007-023)'.
    Devuelve lista de dicts con fotos_nums (list[int]) y datos del registro.
    """
    resultado = []
    for r in registros:
        nums = []
        if r.fotos:
            rangos = re.findall(r'\((\d+)-(\d+)\)', r.fotos)
            for inicio, fin in rangos:
                nums.extend(range(int(inicio), int(fin) + 1))
            # Fotos individuales como (007)
            individuales = re.findall(r'\((\d+)\)(?!-)', r.fotos)
            for n in individuales:
                nums.append(int(n))
        resultado.append({
            'id':          r.id,
            'user_id':     r.user_id,
            'fotos_nums':  sorted(set(nums)),
            'fotos_str':   r.fotos,
            'modelo':      r.modelo,
            'linea':       r.linea,
            'descripcion': r.descripcion,
            'responsable': r.responsable,
            'cantidad':    r.cantidad,
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
    registros_data.sort(key=lambda x: (x.get('user_id'), x['fotos_nums'][0] if x['fotos_nums'] else 0))

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
            
        for num in r['fotos_nums']:
            clave = f"{user_id}_{num}"
            if clave in fotos_en_disco:
                continue
                
            for ext in ['png', 'jpg']:
                # Buscar formato exacto (001.png) o con timestamp (001_2023.png)
                archivos = list(user_folder.glob(f"{num:03d}.{ext}")) + \
                           list(user_folder.glob(f"{num:03d}_*.{ext}"))
                if archivos:
                    fotos_en_disco[clave] = {
                        'path': archivos[0],
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
    Recibe JSON con las rotaciones corregidas por el usuario,
    agrupa los registros por proveedor (responsable) y genera
    un Excel por cada uno. Si hay varios proveedores, devuelve un ZIP.
    """
    from .services.reporte_excel import generate_excel
    import zipfile

    if request.method != 'POST':
        return redirect('reportes')

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, Exception):
        return HttpResponse('JSON inválido', status=400)

    rotaciones_raw = body.get('rotaciones', {})
    # Las claves de rotaciones ahora son strings (user_id_num)
    rotaciones = {str(k): int(v) for k, v in rotaciones_raw.items()}
    registros_data = body.get('registros', [])

    if not registros_data:
        return HttpResponse('Sin registros para generar.', status=400)

    fotos_dir = settings.MEDIA_ROOT / 'fotos'
    fecha_str = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ── Alias de proveedores (nombres que son lo mismo) ─────────
    ALIAS = {
        'WH': 'TSCEM',
    }

    # ── Agrupar registros por responsable ──────────────────────
    grupos = {}
    for reg in registros_data:
        resp = (reg.get('responsable') or 'SIN_PROVEEDOR').strip().upper()
        resp = ALIAS.get(resp, resp)  # Aplicar alias
        grupos.setdefault(resp, []).append(reg)

    def _consolidar_registros(regs):
        """
        Fusiona registros que tienen el mismo (modelo, descripcion).
        Las fotos se unen y la cantidad se suma.
        """
        agrupados = {}
        for reg in regs:
            clave = (
                (reg.get('modelo') or '').strip().upper(),
                (reg.get('descripcion') or '').strip().upper(),
            )
            if clave in agrupados:
                existente = agrupados[clave]
                # Unir fotos sin duplicados, manteniendo orden
                fotos_existentes = set(existente['fotos_nums'])
                for n in reg.get('fotos_nums', []):
                    if n not in fotos_existentes:
                        existente['fotos_nums'].append(n)
                        fotos_existentes.add(n)
                # Sumar cantidades
                existente['cantidad'] = (existente.get('cantidad') or 1) + (reg.get('cantidad') or 1)
            else:
                agrupados[clave] = dict(reg)  # copia
        return list(agrupados.values())

    # ── Generar un Excel por proveedor ─────────────────────────
    archivos_generados = []  # [(nombre, path)]
    tmp_paths = []

    try:
        for proveedor, regs in grupos.items():
            # [EXPERIMENTAL] Consolidar: mismo modelo + mismo defecto → una sola fila
            # Descomentar para activar:
            # regs = _consolidar_registros(regs)

            tmp = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
            tmp.close()
            output_path = Path(tmp.name)
            tmp_paths.append(output_path)

            generate_excel(
                registros=regs,
                rotaciones=rotaciones,
                fotos_dir=fotos_dir,
                output_path=output_path,
            )

            nombre = f"reporte_{proveedor}_{fecha_str}.xlsx"
            archivos_generados.append((nombre, output_path))

        # ── Respuesta ──────────────────────────────────────────
        if len(archivos_generados) == 1:
            # Un solo proveedor → devolver .xlsx directo
            nombre, path = archivos_generados[0]
            with open(path, 'rb') as f:
                contenido = f.read()
            response = HttpResponse(
                contenido,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{nombre}"'
            return response
        else:
            # Varios proveedores → empaquetar en ZIP
            zip_tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            zip_tmp.close()
            zip_path = Path(zip_tmp.name)
            tmp_paths.append(zip_path)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for nombre, path in archivos_generados:
                    zf.write(path, nombre)

            with open(zip_path, 'rb') as f:
                contenido = f.read()

            nombre_zip = f"reportes_por_proveedor_{fecha_str}.zip"
            response = HttpResponse(contenido, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{nombre_zip}"'
            return response

    except Exception as e:
        return HttpResponse(f'Error generando Excel: {e}', status=500)

    finally:
        for p in tmp_paths:
            Path(p).unlink(missing_ok=True)

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
