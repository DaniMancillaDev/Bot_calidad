# Scripts recuperados fuera del código activo

Estos archivos existían en el árbol `web` de las imágenes Docker, pero no en la rama Git base. Se conservaron en:

`/mnt/Orto/bot_calidad_runtime_scripts_quarantine_20261019/`

No se integran en el código activo porque no son necesarios para el arranque normal y algunos pueden modificar PostgreSQL, Redis, media o archivos fuente.

## Clasificación

### Requieren revisión antes de usar

- `backup_and_clean.py`: elimina evidencias de la base de datos y crea un backup JSON.
- `debug_foto20.py`: modifica `metadatos` de una evidencia concreta.
- `reproduce_direct.py`: crea y confirma una importación usando rutas personales y base de datos.
- `reproduce_django.py`: ejecuta requests y confirmaciones mediante Django.
- `reproduce_flow.py`: borra registros y crea una importación.
- `run_regression_suite.py`: crea usuarios, lotes y registros en la base de datos.
- `test_final_validation_15.py`: crea datos, usa media y espera un worker Celery.
- `verify_tab_isolation.py`: crea usuarios, lotes y registros.

### Herramientas de diagnóstico

- `check_db.py`: consulta PostgreSQL y muestra conteos y rutas.
- `check_db_usage.py`: consulta uso de evidencias y metadatos.
- `scratch_jpeg.py`: crea `test.jpg` en el directorio actual.

### Parches históricos no reproducibles

- `patch_importacion.py`.
- `patch_models.py`.
- `patch_utils.py`.
- `patch_views.py`.

Estos scripts contienen rutas absolutas o lógica de edición textual. La funcionalidad que resultó necesaria ya está incorporada en el commit `df54595`; los parches originales se conservan solo como evidencia.
