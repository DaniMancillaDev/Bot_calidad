import os
import zipfile
import uuid
import openpyxl
from pathlib import Path
from django.utils.text import get_valid_filename
from django.db import transaction
import shutil
from django.conf import settings
from django.utils import timezone

def parsear_excel(file_obj):
    """
    Lee un archivo Excel y retorna una lista de diccionarios.
    Asume que la primera fila contiene las cabeceras.
    """
    wb = openpyxl.load_workbook(file_obj, data_only=True)
    ws = wb.active
    
    filas = []
    headers = []
    
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            # Normalizar cabeceras (minúsculas, sin espacios extra)
            headers = [str(cell).strip().lower() if cell else f"col_{j}" for j, cell in enumerate(row)]
            continue
            
        # Si la fila está completamente vacía, saltar
        if all(cell is None or str(cell).strip() == '' for cell in row):
            continue
            
        fila_dict = {
            "id": f"row_{uuid.uuid4().hex[:8]}", # ID único para el frontend
            "numero_fila_excel": i + 1,
            "fotos_asignadas": []
        }
        
        for j, cell in enumerate(row):
            if j < len(headers):
                val = str(cell).strip() if cell is not None else ""
                fila_dict[headers[j]] = val
                
        filas.append(fila_dict)
        
    return filas

def parsear_txt(file_obj):
    """
    Lee un reporte en texto plano (generado por descargar_txt)
    y lo convierte al mismo formato de diccionarios que parsear_excel.
    """
    import uuid
    filas = []
    content = file_obj.read().decode('utf-8')
    
    for i, line in enumerate(content.splitlines()):
        line = line.strip()
        # Ignorar cabeceras y líneas vacías
        if '===' in line or 'REPORTE' in line or 'Usuario' in line or 'Generado' in line or line.startswith('---') or not line:
            continue
            
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 6:
            fila_dict = {
                "id": f"row_{uuid.uuid4().hex[:8]}",
                "numero_fila_excel": i + 1,
                "fotos_asignadas": [],
                "fotos_rango": parts[0],
                "modelo": parts[1].replace('Modelo:', '').strip(),
                "linea": parts[2].replace('Línea:', '').strip(),
                "cantidad": parts[3].replace('Cant:', '').strip(),
                "responsable": parts[4].replace('Resp:', '').strip(),
                "defecto": parts[5].replace('Desc:', '').strip(),
            }
            filas.append(fila_dict)
            
    return filas

def extraer_zip_seguro(file_obj, dest_folder: Path):
    """
    Extrae únicamente archivos de imagen de un ZIP, aplanando la estructura
    de directorios (todas las fotos quedan en la raíz de dest_folder).
    Retorna la lista de diccionarios con metadatos de fotos.
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    fotos_extraidas = {}
    
    valid_extensions = ('.jpg', '.jpeg', '.png', '.jfif', '.webp')
    
    with zipfile.ZipFile(file_obj, 'r') as zf:
        for file_info in zf.infolist():
            # Ignorar directorios y archivos ocultos/macOS
            if file_info.is_dir() or file_info.filename.startswith('__MACOSX') or '/.' in file_info.filename:
                continue
                
            ext = os.path.splitext(file_info.filename)[1].lower()
            if ext in valid_extensions:
                # Aplanar ruta: solo tomar el nombre del archivo
                filename = os.path.basename(file_info.filename)
                safe_filename = get_valid_filename(filename)
                if not safe_filename:
                    safe_filename = f"foto_{uuid.uuid4().hex[:8]}{ext}"
                    
                target_path = dest_folder / safe_filename
                
                # Evitar colisiones si proveedores mandan fotos con mismo nombre en subcarpetas
                if target_path.exists():
                    safe_filename = f"{uuid.uuid4().hex[:4]}_{safe_filename}"
                    target_path = dest_folder / safe_filename
                
                # Leer y guardar el archivo
                with zf.open(file_info) as source, open(target_path, 'wb') as target:
                    target.write(source.read())
                    
                # Generar metadata para el frontend
                foto_id = f"img_{uuid.uuid4().hex[:8]}"
                fotos_extraidas[foto_id] = {
                    "id": foto_id,
                    "filename": safe_filename,
                    "original_name": filename
                    # La URL se arma en la vista porque necesita conocer el session_key
                }
                
    return fotos_extraidas

def generar_estado_inicial(filas, fotos_dict, session_id):
    """
    Genera el diccionario de estado (Workspace).
    Intenta un emparejamiento básico: si el nombre de la foto aparece
    como texto en alguna columna de la fila, se autoasigna.
    """
    import re
    fotos_huerfanas = list(fotos_dict.keys())
    
    # Enriquecer URLs de las fotos
    base_url = f"/media/importaciones_temp/{session_id}/"
    for fid, foto in fotos_dict.items():
        foto["url"] = base_url + foto["filename"]
        
    def _parsear_rango(rango_str):
        nums = []
        try:
            rangos = re.findall(r'(\d+)\s*-\s*(\d+)', str(rango_str))
            for i, f in rangos:
                nums.extend(range(int(i), int(f) + 1))
            sueltos = re.findall(r'(?<!-)\b\d+\b(?!-)', str(rango_str))
            for s in sueltos:
                nums.append(int(s))
        except Exception:
            pass
        return nums

    # Auto-matching muy básico
    for fila in filas:
        valores_fila = " ".join([str(v).lower() for v in fila.values()]).replace(".jpg", "").replace(".jpeg", "").replace(".png", "")
        rango_nums = _parsear_rango(fila.get('fotos_rango', ''))
        
        fotos_a_asignar = []
        for fid in list(fotos_huerfanas): # Copia de la lista para poder iterar y remover
            nombre_base = os.path.splitext(fotos_dict[fid]["original_name"])[0].lower()
            
            # Match por rango si existe la columna fotos_rango (como del TXT)
            matched_by_range = False
            if rango_nums:
                try:
                    # Intenta extraer un número del nombre del archivo (ej. 041.jpg -> 41)
                    num_foto = int(re.search(r'\d+', nombre_base).group())
                    if num_foto in rango_nums:
                        matched_by_range = True
                except Exception:
                    pass
            
            # Si matchea por rango numérico explícito, lo asignamos seguro.
            if matched_by_range:
                fotos_a_asignar.append(fid)
            elif len(nombre_base) >= 3:
                # Si no matcheó por rango, intentamos buscar el nombre del archivo en los textos
                # de la fila. Pero para evitar que un archivo "128.jpg" se asigne a una fila
                # solo porque su cantidad es "128", exigimos que sea una palabra completa ().
                import re
                if re.search(r'\b' + re.escape(nombre_base) + r'\b', valores_fila):
                    fotos_a_asignar.append(fid)
                
        for fid in fotos_a_asignar:
            fila["fotos_asignadas"].append(fid)
            if fid in fotos_huerfanas:
                fotos_huerfanas.remove(fid)
            
    return {
        "session_id": session_id,
        "estadisticas": {
            "total_filas": len(filas),
            "total_fotos": len(fotos_dict),
        },
        "fotos": fotos_dict,
        "fotos_huerfanas": fotos_huerfanas,
        "registros": filas
    }

def commit_importacion(session_data, user):
    """
    Toma el estado validado por el usuario, crea los registros,
    mueve las fotos y lanza la tarea asíncrona de thumbnails.
    Todo ocurre en una transacción atómica.
    """
    from calidad.models import RegistroDefecto, EvidenciaFotografica, EstadoRevision
    from calidad.tasks import generar_thumbnails_lote_task
    
    registros_data = session_data.get('registros', [])
    fotos_dict = session_data.get('fotos', {})
    session_id = session_data.get('session_id')
    
    user_id = user.perfil.telegram_user_id if hasattr(user, 'perfil') and user.perfil.telegram_user_id else user.id
    turno = user.perfil.turno if hasattr(user, 'perfil') else ''
    departamento = user.perfil.departamento if hasattr(user, 'perfil') else ''
    
    temp_dir = settings.MEDIA_ROOT / 'importaciones_temp' / session_id
    final_dir = settings.FOTOS_ROOT / str(user_id)
    final_dir.mkdir(parents=True, exist_ok=True)
    
    fotos_paths_para_celery = []
    
    with transaction.atomic():
        for row in registros_data:
            # Crear registro
            reg = RegistroDefecto.objects.create(
                user_id=user_id,
                turno=turno,
                departamento=departamento,
                modelo=str(row.get('modelo', 'IMPORTADO')).upper(),
                linea=str(row.get('linea', 'N/A')).upper(),
                cantidad=int(row.get('cantidad', 1)) if str(row.get('cantidad', 1)).isdigit() else 1,
                responsable=str(row.get('responsable', 'WEB')).upper(),
                descripcion=str(row.get('defecto', row.get('descripcion', ''))),
                estado_revision=EstadoRevision.PENDIENTE,
                fotos="WEB" if row.get('fotos_asignadas') else "", # Dummy text no numerico para legacy compat
                numero_parte=str(row.get('numero_parte', ''))[:50]
            )
            
            # Asociar fotos
            orden = 1
            for foto_id in row.get('fotos_asignadas', []):
                foto_meta = fotos_dict.get(foto_id)
                if not foto_meta:
                    continue
                    
                filename = foto_meta['filename']
                src_path = temp_dir / filename
                dst_path = final_dir / filename
                
                # Mover el archivo (si existe)
                if src_path.exists():
                    # Usamos copy para que si falla la transacción no perdamos el original
                    shutil.copy2(src_path, dst_path)
                    fotos_paths_para_celery.append(str(dst_path))
                    
                    # Guardar la ruta relativa que el sistema espera ('fotos/USER_ID/ARCHIVO.jpg')
                    rel_path = f"fotos/{user_id}/{filename}"
                    EvidenciaFotografica.objects.create(
                        registro=reg,
                        ruta_archivo=rel_path,
                        orden=orden,
                        es_portada=(orden == 1)
                    )
                    orden += 1

    # Fuera de la transacción, limpiar temporal y lanzar task
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
        
    if fotos_paths_para_celery:
        generar_thumbnails_lote_task.delay(user_id, fotos_paths_para_celery)
