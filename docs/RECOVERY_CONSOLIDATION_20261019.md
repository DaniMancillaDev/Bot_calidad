# Consolidación de runtime — 2026-10-19

## Alcance

Esta rama recupera cambios de código observados dentro de las imágenes Docker desplegadas. No contiene fotografías, sesiones de WhatsApp, bases de datos, volúmenes ni secretos de producción. La rama todavía no está publicada.

## Procedencia

- Repositorio original: `https://github.com/DaniMancillaDev/Bot_calidad`.
- Base de consolidación: `origin/feature/v2.1.0-ui-galeria-optimizaciones`, commit `9eb16a636c6948742769862cbcaf01a526941b43`.
- Commit local de consolidación funcional: `df54595` (`recovery: consolidate web runtime behavior`).
- Snapshot web: imagen `sha256:f473c5284e7970f0f52a7d77b1e007808b3e1255aeb66ced0e1287c2eea99a73`.
- Snapshot celery: imagen observada desde el contenedor `sha256:5735a4a55747e6d8885e4c0714c4f09ebf95663c2287391da161da03dac6d0f`.
- Snapshot bot: imagen `sha256:51a6de627c8c7a6287a95f4f81ec754c478619a20e136159ce94f7942eaa7d59`.
- Recuperación original, intacta: `/mnt/Orto/bot_calidad_recovery_20261019`.
- Respaldo independiente: `/mnt/Orto/bot_calidad_recovery_backup_20261019.tar`.

La copia recuperada fue comparada por SHA-256 con los árboles dentro de los contenedores. El respaldo no contiene medios ni estado de producción.

## Decisión sobre las variantes

`web` es la referencia funcional elegida para consolidar `web`, `celery` y `shared`. El `celery` runtime es anterior y contiene regresiones de seguridad: elimina comprobaciones de autenticación de varios endpoints y usa URLs públicas `/media/` en vez del proxy protegido. No se incorporó ese árbol sobre la base web.

La comparación completa no encontró funciones de producción exclusivas del árbol `celery`: sus archivos adicionales son pruebas o diagnóstico (`test_db.py`, `test_excel_v2.py`, `test_importacion_aislamiento.py`, `test_isolation.py` y `test_patch.py`). Las tareas Celery, modelos, migraciones funcionales y servicios necesarios están presentes en la variante web consolidada. Las rutas públicas y los endpoints sin autorización se consideran regresiones y no se restauran.

La rama base pública comparte gran parte del código con el runtime web. Los cambios runtime se integraron de manera explícita en modelos, API, importación, sincronización de evidencias, reportes, tareas, configuración, vistas y plantillas.

## Arquitectura actual

### Servicios

- `web/`: Django, autenticación, panel, API, galería, importaciones y reportes.
- `bot/`: bot Telegram y descarga inicial de fotografías.
- `shared/`: storage local, repositorios, contador global, utilidades y traducción de defectos.
- Celery: ejecuta tareas definidas en `web/calidad/tasks.py`.
- PostgreSQL: persistencia de Django y bloqueos de concurrencia.
- Redis: broker y backend de resultados Celery; también almacena el estado conversacional del bot.
- Nginx: proxy HTTP y entrega del contenido protegido mediante `X-Accel-Redirect`.

### Flujo Telegram

`bot/handlers/registro_handler.py` descarga la fotografía de mayor resolución disponible a un archivo temporal, la agrupa en el flujo conversacional y la entrega al backend. `web/calidad/application/workflows/defecto_workflow.py` renombra las fotografías, asigna folios, persiste el registro y solicita miniaturas.

### Evidencias y galería

`RegistroDefecto` conserva el modelo histórico. `EvidenciaFotografica` es la relación normalizada de evidencias, pero actualmente requiere un registro definitivo. La galería y los reportes consultan esa relación; por eso las futuras evidencias pendientes de WhatsApp deben tener un modelo separado.

### Celery y reportes

Las tareas de `web/calidad/tasks.py` generan proxies, miniaturas, Excel y reportes Box Condition. El orden de evidencias y las exclusiones se conservan en la preparación de los reportes.

### Importaciones

`web/workspace/` gestiona importaciones Excel/ZIP, borradores y confirmación transaccional. Ese flujo debe permanecer separado de cualquier bandeja de WhatsApp.

## Variables de entorno

Se requieren variables para Django, PostgreSQL, Redis, Telegram, URL/puerto de webhook, `PYTHONPATH`, configuración de IA y flags de funcionalidades. Los valores deben venir de `.env` o del gestor de secretos; nunca deben escribirse en Compose ni en esta documentación.

## Construcción y despliegue

`Dockerfile` construye la imagen web/Celery con Python 3.13, `uv`, Tesseract y `libpq-dev`. `Dockerfile.bot` construye el proceso Telegram. Las imágenes base de Python y `uv` están fijadas por digest; ambas imágenes aceptan `SOURCE_COMMIT` y lo escriben en `org.opencontainers.image.revision`. [`scripts/build_images.sh`](../scripts/build_images.sh) construye las dos imágenes con etiquetas locales derivadas del commit y no hace push.

El Compose original de GitHub usa `build:` y `.env`; el Compose desplegado usa imágenes fijadas para web/Celery y `latest` para bot. Esa diferencia debe resolverse antes de convertir el repositorio en fuente única de despliegue.

No se ejecutaron migraciones ni despliegues en producción durante esta consolidación. Las migraciones usadas por las pruebas se aplicaron únicamente en PostgreSQL temporal.

## Backups y restauración

La restauración de código runtime puede hacerse desde el snapshot Git local y desde el tar independiente. Las bases de datos, Redis y media requieren backups separados; no forman parte de este repositorio.

## Pruebas

Ejecutadas en el árbol consolidado o en una copia archivada de la rama, siempre fuera de los contenedores y volúmenes de producción:

- Parseo AST de Python sin iniciar Django ni conectarse a servicios.
- `git diff --check` sobre la consolidación.
- Comparación de hashes contra los contenedores.

- `uv lock --check`: correcto; el entorno aislado instaló 74 paquetes.
- `django check`: correcto, sin errores.
- `django check --deploy`: tres advertencias, `security.W004`, `security.W008` y `security.W009`.
- `makemigrations --check --dry-run`: `No changes detected`.
- Suite Django completa explícita (`calidad.tests`, `calidad.tests_concurrency`, `calidad.tests_v2` y workspace): 23 pruebas, todas correctas.
- Suite de utilidades compartidas: 12 pruebas, todas correctas.
- `calidad.tests_v2` ahora comprueba sesión autenticada, rechazo anónimo, URLs de media protegidas, dual-write con ejecución explícita de la tarea y una transición realmente inválida.
- Catálogo: JSON válido y pruebas de las entradas añadidas por el runtime web.
- Construcción aislada con `Dockerfile` y `Dockerfile.bot`: correcta con etiquetas temporales, eliminadas después de la verificación.

Los tests con PostgreSQL 16 y Redis 7 temporales se ejecutaron en puertos locales efímeros y ambos contenedores fueron detenidos y eliminados. No se usó PostgreSQL, Redis, media ni volúmenes de producción.

## Riesgos residuales y decisiones pendientes

- La diferencia `web`/`celery` quedó resuelta para el código fuente: ambos deben construirse desde el mismo `Dockerfile` y commit. El árbol Celery antiguo se conserva únicamente como evidencia y no se mezcla sobre la variante segura.
- Revisar scripts de diagnóstico recuperados que escriben en bases de datos o dependen de rutas personales antes de volver a usarlos.
- Los 19 artefactos binarios temporales rastreados por GitHub se retiraron de esta rama y quedaron excluidos por `.gitignore`; permanecen recuperables desde `origin/feature/v2.1.0-ui-galeria-optimizaciones` y su historial.
- Revisar antes de producción la fijación de paquetes APT y la política de publicación de etiquetas.
- El catálogo consolidado es un superconjunto compatible del catálogo del bot recuperado; falta validación funcional con ejemplos reales de Telegram.
- No iniciar aún la integración WhatsApp.

Los scripts auxiliares que solo estaban en las imágenes se conservaron fuera de esta rama en `/mnt/Orto/bot_calidad_runtime_scripts_quarantine_20261019/`; su clasificación está en `docs/RECOVERED_RUNTIME_SCRIPTS.md`.
