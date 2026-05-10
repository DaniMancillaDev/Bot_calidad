"""
web/calidad/tasks.py

Tareas Celery para generación de reportes Excel en background.

Reemplaza el threading.Thread + EXCEL_TASKS dict en views.py.
- Cada tarea tiene un task_id real de Celery (UUID).
- El estado se guarda en Redis, no en memoria del proceso.
- Compatible con múltiples workers y múltiples instancias de Gunicorn.
"""
import os
import zipfile
import tempfile
import re
from pathlib import Path
from datetime import datetime

from celery import shared_task


# ── Alias de proveedores ────────────────────────────────────────────────────
ALIAS = {
    'WH': 'TSCEM',
}


def _consolidar_registros(regs):
    """
    Fusiona registros con mismo (modelo, descripcion).
    Fotos se unen, cantidades se suman.
    """
    agrupados = {}
    for reg in regs:
        clave = (
            (reg.get('modelo') or '').strip().upper(),
            (reg.get('descripcion') or '').strip().upper(),
        )
        if clave in agrupados:
            existente = agrupados[clave]
            fotos_existentes = set(existente['fotos_nums'])
            for n in reg.get('fotos_nums', []):
                if n not in fotos_existentes:
                    existente['fotos_nums'].append(n)
                    fotos_existentes.add(n)
            existente['cantidad'] = (existente.get('cantidad') or 1) + (reg.get('cantidad') or 1)
        else:
            agrupados[clave] = dict(reg)
    return list(agrupados.values())


@shared_task(bind=True, name='calidad.tasks.generar_excel_task')
def generar_excel_task(self, registros_data, rotaciones, fotos_dir_str, fecha_str):
    """
    Tarea Celery: genera reportes Excel en background.

    Args:
        registros_data: Lista de dicts de registros.
        rotaciones:     Dict {clave: angulo}.
        fotos_dir_str:  Ruta al directorio de fotos como string.
        fecha_str:      Timestamp string para el nombre del archivo.

    Returns:
        Dict con 'file_path' y 'filename' del resultado.
    """
    from web.calidad.services.reporte_excel import generate_excel

    fotos_dir = Path(fotos_dir_str)

    # Agrupar registros por responsable
    grupos = {}
    for reg in registros_data:
        resp = (reg.get('responsable') or 'SIN_PROVEEDOR').strip().upper()
        resp = ALIAS.get(resp, resp)
        grupos.setdefault(resp, []).append(reg)

    # Crear directorio temporal compartido si no existe
    temp_dir = Path(fotos_dir_str).parent / "temp_reports"
    temp_dir.mkdir(parents=True, exist_ok=True)

    archivos_generados = []
    total_grupos = len(grupos)

    for i, (proveedor, regs) in enumerate(grupos.items(), 1):
        # Actualizar progreso visible via Celery state
        self.update_state(
            state='PROGRESS',
            meta={'progress': f'Procesando {proveedor} ({i}/{total_grupos})'}
        )

        # Usar el directorio compartido en lugar de /tmp del contenedor
        output_path = temp_dir / f"tmp_{proveedor}_{datetime.now().timestamp()}.xlsx"

        generate_excel(
            registros=regs,
            rotaciones=rotaciones,
            fotos_dir=fotos_dir,
            output_path=output_path,
        )
        nombre = f"reporte_{proveedor}_{fecha_str}.xlsx"
        archivos_generados.append((nombre, str(output_path)))

    self.update_state(state='PROGRESS', meta={'progress': 'Preparando archivo final...'})

    if len(archivos_generados) == 1:
        nombre, path = archivos_generados[0]
        return {'file_path': path, 'filename': nombre}

    # Múltiples proveedores → ZIP en el directorio compartido
    zip_path = temp_dir / f"zip_{datetime.now().timestamp()}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nombre, path in archivos_generados:
            zf.write(path, nombre)

    # Limpiar xlsx temporales
    for _, path in archivos_generados:
        Path(path).unlink(missing_ok=True)

    return {
        'file_path': str(zip_path),
        'filename': f"reportes_por_proveedor_{fecha_str}.zip"
    }
