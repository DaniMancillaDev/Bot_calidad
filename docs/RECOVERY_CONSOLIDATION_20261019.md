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

`Dockerfile` construye la imagen web/Celery con Python 3.13, `uv`, Tesseract y `libpq-dev`. `Dockerfile.bot` construye el proceso Telegram. El Compose original de GitHub usa `build:` y `.env`; el Compose desplegado usa imágenes fijadas para web/Celery y `latest` para bot. Esa diferencia debe resolverse antes de convertir el repositorio en fuente única de despliegue.

No se ejecutaron migraciones ni despliegues durante esta consolidación.

## Backups y restauración

La restauración de código runtime puede hacerse desde el snapshot Git local y desde el tar independiente. Las bases de datos, Redis y media requieren backups separados; no forman parte de este repositorio.

## Pruebas

Realizadas hasta ahora:

- Parseo AST de Python sin iniciar Django ni conectarse a servicios.
- `git diff --check` sobre la consolidación.
- Comparación de hashes contra los contenedores.

Pendientes en entorno aislado:

- `uv sync --frozen --no-dev`.
- `django check`.
- Validación de migraciones sin PostgreSQL real.
- Tests unitarios y de regresión con SQLite temporal o una base aislada.
- Construcción de imágenes sin usar Compose ni volúmenes de producción.

## Cambios todavía pendientes

- Resolver de forma definitiva las diferencias entre `web` y `celery`.
- Revisar scripts de diagnóstico recuperados que escriben en bases de datos o dependen de rutas personales.
- Retirar del historial de publicación los artefactos binarios ya existentes en `media_files/` si se confirma que contienen datos de producción.
- Fijar la imagen del bot por digest.
- Añadir procedencia de build y commit a las imágenes.
- No iniciar aún la integración WhatsApp.

Los scripts auxiliares que solo estaban en las imágenes se conservaron fuera de esta rama en `/mnt/Orto/bot_calidad_runtime_scripts_quarantine_20261019/`; su clasificación está en `docs/RECOVERED_RUNTIME_SCRIPTS.md`.
