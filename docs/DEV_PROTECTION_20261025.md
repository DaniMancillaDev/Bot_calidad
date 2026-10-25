# Proteccion verificable de DEV, 2026-10-25

## Estado inicial y recuperacion

Inicial: rama `feature/whatsapp-evidencias`, HEAD
`d174635cee87db58734331a5bf1c65a770ab8595`, arbol limpio.
No habia cambios sin commit. No se descartaron ni movieron cambios de usuario.

Referencias anteriores preservadas:

- `backup/dev-before-prod-sync-20261025-78976ad` y `backup/prod-sync-base-20261025`.
- `/mnt/Orto/iqa_sync_backup_20261025/dev.bundle`, verificado y restaurado en un
  checkout completo de `78976ad`, tree `f8e82ae07e61a79ec5760cfe5abcb4864512f3c5`.
- Snapshots/manifiestos anteriores: hashes, inventario y gzip correctos.

Nuevo punto anterior a cambios funcionales:

- Rama `backup/dev-before-protection-20261025-d174635`.
- Tag `backup/protection-base-20261025-d174635`.
- Bundle externo `dev-current.bundle` en
  `/mnt/Orto/iqa_protection_20261025T203123Z/`, SHA256
  `8a17f701d6e9711be72d41bd165e170d373d123bb4880f82923d7dd83d7c5387`.
- Se restauraron `d174635` desde una copia independiente del repositorio y desde
  ese bundle nuevo. Tree exacto `ae6fb45b29c956c175c68a6ad10938ff807276d3`.
- Checkouts `restore-old`, `restore-current` y `restore-current-bundle`, fuera de
  DEV/PROD, sin diferencias respecto a sus commits. fsck sin objetos corruptos;
  124 y 125 fuentes Python anteriores/actuales parseados correctamente.
- Un mensaje fsck sobre commits dangling no implica corrupcion; son objetos
  historicos no referenciados por las ramas clonadas.

La evidencia previa a edicion esta en `PHASE1.md` y `bundle-verification.txt` de
la carpeta externa. No se sobrescribieron backups antiguos.

## Inventario de datos: limites reales

| Componente | Ubicacion activa / evidencia encontrada | Verificacion |
| --- | --- | --- |
| PostgreSQL original | volumen bot_calidad_postgres_data | SQL del 10 de octubre con marcador completo; SHA256 verificado. No restaurado a PostgreSQL; no es backup actual |
| Fotografias originales | volumen bot_calidad_media_data | Tar del 10 de octubre, 4244 entradas legibles y hash calculado. No prueba cobertura de fotos posteriores |
| Redis original | volumen bot_calidad_redis_data | No se encontro un backup independiente verificable en las ubicaciones inspeccionadas. Un volumen activo no es backup |
| Datos bot/web/Celery | volumenes anonimos documentados por docker inspect | No se verifico una restauracion ni respaldo completo independiente |
| WhatsApp piloto | wa_pilot_postgres_data, wa_pilot_redis_data, wa_pilot_media, wa_pilot_whatsapp_data y datos web | Inventariados en lectura; no se verifico backup de DB, medios ni sesiones |
| Codigo/plantillas | bundles y snapshots externos | Restauracion de codigo comprobada; plantilla original preservada con SHA256 |

Detalle de los hashes de datos en `data-backup-inventory.json`, fuera de Git.
No se copio ni restauro informacion real en servicios activos. No se afirma
recuperacion completa del sistema; faltan backups actuales y ensayos de datos.

## Box Condition recuperado

Original: `box-template-prod.xlsx`, SHA256
`10c9072b071759e130544f095d762ac61bb9dbccf2ff4dee18dd75145f14cf6a`, intacto fuera de Git.

Inspeccion: cuatro hojas, cero formulas, cero nombres definidos, cero validaciones,
una combinacion K1:M1, configuraciones de impresion y estilos, dos fotos de ejemplo,
comentarios y metadatos SharePoint. El diagrama de proceso usa formas nativas Excel
que openpyxl no conserva por si solo. Se inspeccionaron relaciones internas.

`scripts/sanitize_box_template.py` acepta exclusivamente ese original revisado:

- Conserva cuatro hojas y sus nombres, encabezados, estilos, dimensiones,
  combinaciones, configuracion de impresion y formas del proceso.
- Limpia registros de ejemplo: fila 3+ de la primera hoja y fila 2+ de Gantt.
- Conserva los cinco rotulos funcionales del proceso; la hoja 23-09-26 ya estaba vacia.
- Retira fotos, comentarios y metadatos personales/SharePoint ajenos al reporte.
- Reconstruye sharedStrings para que los valores de ejemplo no sobrevivan ocultos.
- Rechaza originales diferentes antes de crear salida; nunca sobrescribe destinos.

Plantilla saneada versionada: `Daily Tracking Box Condition.xlsx`, SHA256
`13b05a747cb29f7dcb5cde5cbea5818cef3baeab8aacfcb8467f1ea099a3b46a`.
El Dockerfile la copia expresamente. La tarea usa la raiz del proyecto derivada
de settings.BASE_DIR, compatible con DEV y /app. La generacion recupera los XML
auxiliares y formas nativas tras guardar con openpyxl; ajusta solo el area de
impresion del reporte para incluir las filas generadas.

Pruebas: hashes originales sin cambio, estilos XML y formas originales conservados,
ausencia de datos/fotos de ejemplo, relaciones internas sin destinos ausentes;
tarea real genera XLSX con 18 fotos, T01/T03, cantidad 25 y asociaciones correctas.
El libro se abre programaticamente. No hubo apertura manual en Microsoft Excel o
LibreOffice, no instalados en este entorno.

## Agrupacion: ambas capacidades conservadas

`services/report_grouping.py` define claves explicitas; `_consolidar_registros`
acepta `grouping_rule` como argumento interno opcional:

- `dev_description`: parte + descripcion, predeterminada sin cambio.
- `prod_model_responsible`: parte + modelo + responsable original.

No hay selector nuevo ni cambio del flujo UI. Para reutilizar la capacidad PROD,
un consumidor explicito puede llamar `_consolidar_registros(...,
grouping_rule=PROD_MODEL_RESPONSIBLE)`. El grupo registra la regla, IDs, registros,
descripciones, cantidades y fotos. Excel valida pertenencia y la clave de esa
misma regla, evitando omitir fotos por interpretar una tupla incompatible.

Las comparativas sinteticas cubren parte, modelo, responsable, descripcion,
cantidades y fotografias. Ambas suman correctamente y retienen el detalle interno,
pero una fila puede representar varios modelos/responsables en DEV o descripciones
en PROD. Las pruebas de Excel conservan todas las fotos validas y rechazan fotos
de un registro ajeno. La eleccion de un nuevo predeterminado sigue pendiente de
decision de negocio; el preflight la bloquea sin autorizacion documentada.

## Comprobacion previa a despliegue

Herramientas:

- `audit_prod_dev.py`: inventarios y comparaciones sin aplicar cambios.
- `preflight_prod_dev.py`: verifica snapshots, PROD vivo, revisiones, recursos,
  migraciones, Git, resultados de pruebas y fuentes de la imagen construida.
- `verify_dev_image.py`: crea exclusivamente un contenedor de inspeccion sin red
  ni volumenes reales, no inicia Django, y compara fuentes/plantillas del build.
- `run_conservation_checks.py`: ejecuta pruebas reales y registra codigos de salida,
  logs con hash y fingerprint del arbol rastreado. No carga .env.local; exige
  PostgreSQL local sync_test* y Redis local de pruebas en DB 15.

`docs/prod_dev_reviews.json` evalua 313 parejas fuente/recurso en cuatro ambitos:
web, Celery, bot y recursos raiz. Contiene solo hashes, rutas y decisiones,
ningun secreto ni dato de negocio. Una diferencia nueva, aun sin conflicto Git,
bloquea hasta revisarla; modificar DEV tambien exige reevaluar las parejas afectadas.
Se distinguen mejoras integradas, diferencias intencionales y auxiliares historicos
preservados fuera del codigo activo. No se aprueban cambios automaticamente.

Ejemplo (rutas y puertos deben corresponder a servicios propios de prueba):

```sh
export DOCKER_COMMAND='sudo -n docker'
python scripts/preflight_prod_dev.py --inventory /ruta/inventory.json \
  --evidence /ruta/conservation-evidence.json --output /ruta/preflight-nuevo.json
```

El inventario externo contiene `scopes` con name, container, image, paths, root
y manifest; hay un ejemplo real en la carpeta externa de esta ejecucion.
Cada root debe contener un snapshot capturado en lectura con docker cp, sin bases,
sesiones, fotos ni variables de entorno. Crear su manifiesto con audit_prod_dev.py.
La comparacion viva usa solo inspect, tar de fuentes y SELECT de django_migrations.
Tambien lee estado de servicios e INFO persistence de Redis; nunca usa SAVE,
CONFIG SET, migraciones, reinicios o comandos que escriban datos de PROD.

Antes de la comprobacion, construir una imagen aislada y verificarla:

```sh
python scripts/verify_dev_image.py --image IMAGEN_DEV --output /ruta/image-proof.json
# Configurar DATABASE_URL y CELERY_BROKER_URL solo para servicios efimeros locales.
.venv/bin/python scripts/run_conservation_checks.py \
  --image-proof /ruta/image-proof.json --output /ruta/evidence-nuevo.json
```

Usar el Python del venv para todos los scripts que requieren dependencias del proyecto.
Los archivos de salida son nuevos y externos al repositorio. No sobrescribir evidencia.
No usar dev.sh ni manage.py con .env.local de produccion para estas pruebas.

Un resultado READY y exit 0 es necesario, no ejecuta ningun despliegue y no prueba
todos los estados posibles. El mecanismo no intercepta un docker compose manual:
futuros operadores y agentes deben respetar AGENTS.md y conectar este paso a su CI.
No hay flag force. Las excepciones funcionales requieren status authorized_exception,
authorized_by, authorization_ref y reason en politica versionada y nuevas pruebas.
Las migraciones pendientes no se ejecutan ni se omiten automaticamente.

## Pruebas y evidencia

La suite completa final cubre Telegram/contador/repositorios, WhatsApp/ingesta por
tandas, borradores, concurrencia, orden, exclusiones y recuperacion, galeria, permisos,
importaciones, Excel/PPTX, cajas, ambas agrupaciones y auditor/preflight.
DB PostgreSQL y Redis exclusivos de pruebas; media sintetica temporal.
Se conservan los intentos fallidos y la evidencia posterior correcta.

Construccion completa con Dockerfile: realizada en un daemon temporal con data-root
externo, driver vfs y paquetes fijados por uv.lock. Imagen verificada
`sha256:7615b612b97a44210ae5b6c3fe61f84c109424c0f91c65209d415b374079d56a`,
151 hashes correctos. Imagen exportada fuera del Docker productivo en
`verified-dev-image.tar`, SHA256
`cfc2c8e2a23a6887defcd9719dedb6443ea476c642f39ec3c429d6b3eba483f0`.
No se desplego. El contenedor de inspeccion no monto datos reales.

La evidencia final, logs y reporte del preflight estan en
`/mnt/Orto/iqa_protection_20261025T203123Z/`. El HEAD final y los commits se registran
en Git y en el resumen externo, evitando referencias circulares dentro del commit.

## Incidente operativo y bloqueo real

El build inicial en el Docker principal fallo por ENOSPC: Btrfs tiene grupos de
datos asignados y casi ningun espacio sin asignar para ampliar metadatos, aunque
df indique unos 25 GB libres. No se hizo prune ni limpieza de imagenes/volumenes
anteriores. Solo se intento retirar el contenedor temporal de instalacion fallida
creado por esta tarea, comprobando que no tenia mounts ni datos de usuario.

El daemon temporal de build compartia namespace de red y desactivo docker0;
esto interrumpio las pruebas. Se detuvo ese daemon y se restablecieron el puente,
su direccion y las conexiones de los dos servicios propios de prueba. No se
reiniciaron contenedores originales ni se alteraron sus puentes dedicados.
No repetir este tipo de aislamiento incompleto; usar VM/host de build separado.

Durante la ejecucion, Redis de PROD registro fallo de persistencia/MISCONF y Celery
salio con error. Su reinicio automatico fallo al montar overlay por ENOSPC.
Web/PostgreSQL/Redis/bot conservaron sus StartedAt y no se ordenaron reinicios
ni ediciones sobre servicios originales. Sus fuentes e imagenes no fueron cambiados.
No puede afirmarse que el estado operativo de PROD permanecio intacto.

No se hizo balance/reconfiguracion de Btrfs ni se desactivo la proteccion de Redis.
La recuperacion operativa requiere una intervencion autorizada fuera de esta
sincronizacion. El preflight bloquea por el servicio caido/persistencia y por
migraciones WhatsApp pendientes y la decision de agrupacion; no se autoriza despliegue.

## Recuperar sin perder trabajo

Verificar el bundle con `git bundle verify`, clonarlo fuera de DEV/PROD, seleccionar
la referencia de respaldo y comprobar HEAD, tree, diff y fsck. No usar reset --hard,
clean -fd ni restaurar codigo sobre datos activos. Los snapshots de fuentes y la
plantilla original permanecen externos e independientes de los bundles.
La recuperacion de DB/Redis/media/sesiones exige backups propios y ensayos separados;
no es parte de una reversion de codigo.
