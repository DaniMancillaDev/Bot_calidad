# Conservacion acumulativa PROD -> DEV

## Estado vigente: proteccion posterior a d174635

La ejecucion documentada en `docs/DEV_PROTECTION_20261025.md` comprobo restauraciones
reales, integro una plantilla Box Condition saneada y conservo ambas reglas de
agrupacion como implementaciones reutilizables. DEV sigue usando su regla original.
Las decisiones pendientes del informe inicial de abajo se actualizan en ese documento.

El control previo es `scripts/preflight_prod_dev.py`. Su politica versionada es
`docs/prod_dev_reviews.json`; registra parejas exactas de hashes PROD/DEV y el motivo
de cada diferencia. Lee PROD en vivo, verifica snapshots y pruebas, y devuelve
BLOCKED/exit 1 ante fuentes no evaluados, dependencias ausentes, servicios fallidos,
persistencia Redis fallida, migraciones pendientes o conflictos sin resolver.
No despliega. No proporciona una opcion force.

No confundir READY con recuperacion completa del sistema. Los bundles y snapshots
de fuentes no respaldan PostgreSQL, Redis, sesiones o fotografias actuales.

Durante esta ejecucion se observo agotamiento de metadatos Btrfs en el disco del
Docker principal, Redis MISCONF y caida de Celery. No se ordenaron reinicios ni
ediciones sobre esos servicios. El estado operativo no puede declararse intacto
ni listo para despliegue. Ver incidente, alcance y limites en el documento nuevo.

Politica permanente: DEV conserva las capacidades verificadas de PROD y sus avances
propios. Nunca sustituir archivos completos por su fecha, ni descartar capacidades
sin decision documentada. Una sincronizacion con conflictos pendientes es parcial;
no se puede afirmar un superconjunto funcional total hasta resolverlos y probarlos.

## Integracion del 25 de octubre de 2026

- Repositorio: `/mnt/Orto/Bot_calidad_dev`.
- Rama: `feature/whatsapp-evidencias`; base `78976adf669438737a8a8f0641e9b11da2093c22`.
- Git inicial limpio; no habia cambios sin commit que preservar.
- Rama recuperable: `backup/dev-before-prod-sync-20261025-78976ad`.
- Tag de base: `backup/prod-sync-base-20261025`.
- Bundle completo externo: `/mnt/Orto/iqa_sync_backup_20261025/dev.bundle`.
  Verificado mediante `git bundle verify` y acceso al arbol con `git cat-file -e`.
  Tambien se clono sin checkout en la carpeta externa `restore-check` y se verifico
  el archivo `web/calidad/tasks.py` del HEAD original.
- Auditoria inicial: `/mnt/Orto/iqa_container_audit_20261025/COMPARACION_FUNCIONAL.md`.
- Fuentes originales preservados en `prod-sources.tar.gz`, SHA256
  `3857ab2336473a6b865d2e549a06b8c829af4612233f2d156ae34bdc918b77c4`.
  Archivo externo verificado con `gzip -t`; fuentes y bundle marcados solo lectura.
- Snapshot fresco web: `/mnt/Orto/iqa_sync_backup_20261025/prod-web-source`.
  Manifiesto `prod-web-manifest.json`, SHA256
  `f8a03ddb07e218264e984699c1ad2f73740f6bdcf1441daf320f103a1b556b9e`.
- Dependencias raiz: `prod-assets-source`, manifiesto `prod-assets-manifest.json`, SHA256
  `994cb9c772d18b8b897ba0b55aa201b0aa534177a596191c72a53cec3e51d676`.
- Los manifiestos contienen rutas y hashes, no valores de configuracion ni datos.
  Snapshots/manifiestos son de solo lectura; sus hashes permiten detectar alteraciones.
  No son una garantia de inmutabilidad frente a un administrador del host.

Origen de las imagenes originales (el piloto WhatsApp no se integra como PROD):

| Contenedor | Image ID |
| --- | --- |
| bot_calidad_web | sha256:e20a65703b24d79fc99db09df57c8340ba3e7519450140508ca8d1eff7d85842 |
| bot_calidad_celery | sha256:4953281398a441e2b654baffc1223217dc377f2a6c61f8ced3d9bcf0083b7dac |
| bot_calidad_bot | sha256:51a6de627c8c7a6287a95f4f81ec754c478619a20e136159ce94f7942eaa7d59 |

## Inventario funcional y decisiones

Las clases A-G pueden coexistir en un mismo archivo. Se revisaron funciones y
dependencias, no solo hashes. Los detalles textuales quedan en los snapshots externos.

| Clase | Archivo / funcion | PROD frente a DEV | Dependencias, riesgo y decision | Pruebas |
| --- | --- | --- | --- | --- |
| A,E | services/importacion.py: validar_importacion_sin_ambiguedades; views_importacion.py: importacion_iniciar | PROD rechaza rangos compartidos y numeros duplicados en ZIP; DEV no | Recuperado antes del workspace y de confirmar. Cambia la aceptacion de entradas ambiguas y muestra aviso; requiere corregirlas, no inventa asociaciones. V1, no sustituye workspace V2. | ImportRecoveryTests |
| A,E | services/importacion.py: commit_importacion | PROD usa nombres unicos; DEV reutiliza nombres originales | Recuperado conservando prefijo numerico, orden y portada. UUID completo y apertura exclusiva xb evitan sobrescritura incluso ante colision; misma transaccion ORM. Un fallo posterior puede dejar un archivo nuevo huerfano, como antes; no se borra automaticamente. | Nombres repetidos, colision forzada, hashes, orden, galeria, derivados y Excel |
| A | tasks.py: generar_excel_task | PROD incluye PN, tarea e indice en PPTX; DEV podia repetir nombre | Recuperada la capacidad con UUID por exportacion e indice, manteniendo PN. No cambia umbral, agrupacion ni tarea WhatsApp. Dependencias PPTX/Excel/ZIP existentes. | Dos grupos, dos ejecuciones, 40 fotos por ejecucion, apertura de XLSX/PPTX, hashes |
| A | shared/infrastructure/ai/defect_catalog.json | PROD tiene 47 entradas adicionales | Incorporadas por clave con comprobacion de conflictos. Ningun valor DEV reemplazado. Fixture de solo entradas recuperadas. | 47 entradas y 19 traducciones exactas sin IA; suite compartida |
| D | tasks.py: _consolidar_registros; services/reporte_excel.py: generate_excel | Claves y validacion de fotos diferentes | PENDIENTE: conservar regla DEV. Integrar la validacion PROD sin su clave omite fotos o falla por indices. No se toca ninguno de esos bloques. | Caracterizacion DEV; comparacion de funciones reales con datos sinteticos |
| A,B,E | calidad/tests_v2.py | PROD agrega pruebas pero conserva otras mas antiguas | No reemplazar: se conservan autenticacion, aislamiento y media protegida de DEV. Las nuevas pruebas compatibles se escriben en tests_prod_sync.py. La prueba PROD de agrupacion queda pendiente junto con la regla. | Suites V2, WhatsApp y nuevas regresiones |
| B | models.py, urls.py, api/urls.py, settings.py | DEV agrega contactos, pendientes, borradores y configuracion WhatsApp | Conservar completos; las diferencias antiguas de PROD no los sustituyen. | Suites WhatsApp, pendientes y concurrencia |
| B,E | views.py: _get_allowed_storage_ids, _enrich_galeria_registros, polling | DEV agrega permisos por ID Django/Telegram, fallback al original y conteos WhatsApp | Conservar: restaurar PROD perderia acceso legitimo y fallback de imagenes. | Permisos, galeria, aislamiento y panel |
| B | templates/calidad/base.html, operacion.html, reportes.html; static/css/panel_operativo.css; static/js/panel_operativo.js | DEV agrega bandeja, etiquetas, alertas y actualizacion automatica | Conservar: no se reemplazan fuentes UI. | Suites pendientes/panel; sin prueba manual de navegador |
| C | api/endpoints_v2.py | Diferencias solo de espacios | Sin cambio funcional: no integrar ruido. | Suite V2 conservada |
| F | migrations/0015 a 0019 | Exclusivas DEV para WhatsApp | Preservadas todas. No se crea ni modifica ninguna migracion. Solo se aplicaron en DB efimera de pruebas. | makemigrations --check --dry-run: sin cambios |
| C | bot/, main.py, pyproject.toml, uv.lock, plantilla_reporte.xlsx | Iguales por contenido entre PROD revisado y DEV | Conservar DEV; sin cambio de dependencias ni cliente Telegram. | Hashes y pruebas de repositorio legacy/contador/FSM |
| A,F,D | Daily Tracking Box Condition.xlsx; tasks.py: generar_excel_box_condition_task; Dockerfile | Plantilla solo en PROD; DEV no la copia a imagen y la tarea espera /app/Daily Tracking Box Condition.xlsx | PENDIENTE: archivo recuperado solo fuera de Git, tiene datos/fotos de ejemplo y hojas auxiliares. Requiere decision de saneamiento o provision externa y luego prueba de tarea con ruta real. No subir datos ni suprimir hojas automaticamente. | Servicio Box probado con plantilla sintetica, no despliegue de tarea por defecto |
| G | 16 auxiliares web / 18 celery, con solapamiento | Diagnosticos y parches ausentes del codigo activo DEV | Preservados fuera de Git; no ejecutados ni borrados. Varios escriben/borran registros. Ver RECOVERED_RUNTIME_SCRIPTS.md. | Inventario, no ejecucion |

## Conflicto de agrupacion pendiente

La agrupacion por proveedor primero aplica alias como WH -> TSCEM. Despues:

- DEV: `(numero_parte, descripcion)`.
- PROD: `(numero_parte, modelo, responsable original)`.

Comparacion ejecutada sobre las dos funciones reales, usando registros sinteticos
con cantidades 2 y 3 y una foto cada uno:

| Diferencia entre registros | DEV | PROD |
| --- | --- | --- |
| Solo descripcion | Dos grupos, cantidades 2 y 3, fotos separadas | Un grupo de 5 con ambas fotos |
| Solo modelo | Un grupo de 5 con ambas fotos | Dos grupos de 2 y 3 |
| Solo responsable WH/TSCEM | Un grupo de 5 en el mismo proveedor | Dos grupos de 2 y 3 |

Ambos conservan listas internas de IDs/descripciones y fotos; sin embargo, una fila
consolidada usa campos representativos del primer registro. Puede perder distincion
visual de defectos en PROD o de modelo/responsable en DEV. La validacion de Excel
debe usar exactamente la clave elegida o descartara fotografias.

No se agrego selector: falta definir necesidad y resultado esperado. Se solicito
decision sobre combinar las cuatro dimensiones o mantener una regla existente.
Hasta resolverlo, PROD queda respaldado y DEV mantiene su comportamiento.
Esto es el reporte general; la agrupacion multilinea Box Condition ya existente
se conserva y se comprueba con T01/T03 y cantidad 25.

## Correccion del visor de galeria: 2026-10-26

El reporte de falta de zoom en `/fotos/` se confirmo contra las plantillas
reales DEV y PROD: SHA256 previo identico
`07f906f0df846f2a5854151af2d28ab74947e3dfe6806864d55a30040b660ba7`.
El visor solo ajustaba la imagen a la ventana; no tenia controles de zoom.

Cambio exclusivo DEV en `web/templates/calidad/galeria.html`: controles con
iconos existentes, zoom relativo al ajuste entre 100 y 400%, rueda y doble clic,
area desplazable y arrastre por raton. Restablece ajuste al cambiar foto o
reabrir. Conserva URL original, proporciones, orden, navegacion y Escape; no
escribe medios ni modifica permisos, modelos, importaciones o reportes.

Recuperacion previa: rama `backup/before-gallery-zoom-20261026-3aa8cdb`, bundle
externo anterior verificado y snapshots DEV/PROD con procedencia/hashes en
`/mnt/Orto/iqa_gallery_zoom_backup_20261026`. No reemplazar PROD por DEV.
El commit se identifica con `git log -- web/templates/calidad/galeria.html`.
El nuevo HEAD debe incorporarse al inventario de la migracion: `3aa8cdb` pasa
a ser la referencia ANTERIOR, no se debe restaurar encima del nuevo trabajo.

Prueba reproducible sin Django, BD ni servicios productivos:

```sh
python -m unittest scripts.tests.test_gallery_zoom -v
```

Utiliza Chromium instalado (o CHROME_BIN) y Node con WebSocket integrado;
no instala dependencias. Prueba el JS/HTML/CSS real extraido de la plantilla
con una imagen PNG sintetica, en 1440x1000, 900x650 y 390x844. Comprueba botones,
rueda, doble clic, limites, desplazamiento, arrastre real por CDP, navegacion,
URL/proporcion, cierre y reapertura. Los tres tamanos pasan con el parche y
fallan con el snapshot anterior. Capturas scratch en
`/dev/shm/iqa-gallery-zoom-results`; iconos usan fallback tipografico de fixture,
no se valida el CDN de fuentes. No equivale a probar un telefono fisico o pinch.

No se desplego, reinicio ni modifico PROD. La ruta publica exige login;
no se eludieron permisos ni se crearon sesiones productivas para probarla.
No se ejecutaron la suite completa ni un nuevo preflight de despliegue por
este parche visual. Los controles de conservacion/almacenamiento y la revision
del nuevo diff siguen siendo obligatorios antes de aplicar nada a PROD;
no se actualizaron hashes de politica para aprobar automaticamente el cambio.

Refinamiento visual posterior: barra unica con borde tenue, iconos de 19px,
botones sin marcos individuales, hover discreto, foco de teclado visible y
objetivos tactiles de 44px. Solo CSS del visor; no cambia el zoom ni los datos.
La prueba Chromium incluye emulacion de puntero tactil para verificar esos 44px.
El tunel de muestra se actualiza por separado, no constituye despliegue PROD.

## Commits de esta integracion

| Commit | Capacidad |
| --- | --- |
| 7638b66 | Reparacion de referencia mock en prueba WhatsApp preexistente |
| 6226348 | Validacion de importaciones y preservacion de originales |
| ad067f5 | Nombres PPTX sin colision |
| 651fe14 | 47 entradas de catalogo y fixture versionada |
| 9920998 | Auditor de snapshots sin aplicar cambios |
| 52ae61b | Pruebas de interaccion galeria/derivados/Excel/cajas y regla DEV |

El commit que contiene esta politica se identifica con
`git log -- docs/PROD_DEV_SYNC.md`; no se escribe su propio hash en su contenido.

## Validacion ejecutada

Base previa: 59 pruebas Django, un error preexistente de test por usar el objeto
patch en vez del mock iniciado en tests_whatsapp.py. Se reparo esa referencia;
no se debilito ninguna asercion ni se cambio el comportamiento de WhatsApp.

Resultado posterior:

- 68 pruebas Django correctas: calidad.tests, tests_v2, tests_concurrency,
  tests_whatsapp, tests_pending_evidence, tests_whatsapp_concurrency, tests_prod_sync,
  workspace.tests.test_processing_characterization y test_processing_locking.
- 15 pruebas compartidas correctas y 23 pruebas Node del adaptador correctas.
- 4 pruebas del auditor correctas: allow-list, hashes/cambios, ausencia de escrituras
  y rechazo de symlinks/inventario alterado.
- `makemigrations --check --dry-run`: sin cambios; `git diff --check`: correcto.
- XLSX y PPTX generados y abiertos con openpyxl/python-pptx. Se compararon bytes y
  hashes de originales sinteticos. No se usaron fotografias de usuarios en pruebas.

Verificacion final de PROD: mismos Image IDs, StartedAt y RestartCount que al
inicio; hashes de tasks.py, importacion.py y catalogo sin cambios. No se hicieron
operaciones de escritura ni reinicios sobre los contenedores originales. Los
contenedores propios de pruebas se detuvieron al terminar; no se borraron volumenes.

PostgreSQL 16 y Redis 7 exclusivos de pruebas: contenedores
`iqa_sync_test_pg_20261025` y `iqa_sync_test_redis_20261025`, puertos aleatorios
solo en 127.0.0.1, DB y Redis de produccion no utilizados. El runner se invoco
directamente con django.setup() y call_command, evitando manage.py que carga
.env.local con override=True. Logs externos en `/mnt/Orto/iqa_sync_backup_20261025`.
La autodeteccion `test calidad workspace` colisiona con workspace/tests.py y el
paquete workspace/tests; se usaron etiquetas explicitas sin eliminar ninguno.

Limites: no hubo navegador manual, mensajes reales Telegram/WhatsApp ni despliegue.
Las pruebas prueban los flujos listados, no todos los estados posibles del sistema.
La plantilla con datos y la agrupacion impiden declarar el superconjunto completo.

## Procedimiento repetible (PROD siempre en lectura)

1. Registrar rama, HEAD y `git status --porcelain`. Si hay trabajo sin commit,
   preservarlo fuera del repo (diff binario staged/unstaged y archivos sin rastrear
   revisados, sin secretos). No hacer stash destructivo ni cambiar de rama encima.
   Crear rama/tag identificables, bundle y verificar la recuperacion antes de editar.
2. Registrar imagen, contenedor y fecha. Usar solo `docker inspect`, `docker cp`
   y lectura de fuentes. No ejecutar codigo recuperado ni comandos de negocio.
   Capturar web/, shared/, bot/ y dependencias raiz en carpetas externas distintas
   por servicio; no copiar .env, sesiones, media, bases, node_modules o volumenes.
   Revisar plantillas por datos sensibles; no versionarlas sin saneamiento acordado.
3. Crear manifiesto fuera del snapshot:

   ```sh
   python scripts/audit_prod_dev.py manifest --snapshot /ruta/snapshot \
     --id contenedor@sha256:IMAGEN --output /ruta/manifiesto-nuevo.json
   sha256sum /ruta/manifiesto-nuevo.json
   ```

4. Archivar fuera de Git, anotar hashes y marcar solo lectura. Verificar hash del
   archivo, lista recuperable y manifiesto contra el snapshot. Los tags Git no
   sustituyen a los archivos que solo viven en contenedores.
5. Comparar sin aplicar:

   ```sh
   python scripts/audit_prod_dev.py compare --snapshot /ruta/snapshot \
     --manifest /ruta/manifiesto-nuevo.json --dev /mnt/Orto/Bot_calidad_dev \
     --baseline /ruta/manifiesto-anterior.json --output /ruta/reporte-nuevo.json
   ```

   El auditor verifica contenido e inventario, excluye rutas sensibles, no conecta
   a bases ni Docker y solo crea el reporte nuevo. No escribe fuentes, no fusiona
   ni despliega. Reporta DEV-only, ausentes, distintos y novedades del snapshot.
   Un hash distinto exige revision funcional A-G; no indica cual version es mejor.
6. Revisar llamadas, dependencias, permisos, datos y pruebas. Integrar capacidades
   por bloques en commits locales, conservar lo exclusivo del otro lado y dejar
   conflictos pendientes sin frenar cambios independientes. Nunca elegir versiones
   completas por comodidad ni introducir opciones sin una necesidad acordada.
7. Ejecutar regresiones con DB/Redis/media efimeros, sin .env de produccion; conservar
   suites DEV y reproducir interacciones PROD. Revisar migraciones, exportaciones,
   galeria, datos/fotos y canales afectados. Registrar comandos, resultados y limites.
8. Actualizar esta trazabilidad, verificar que PROD conserva imagen/arranque/hashes,
   y comprobar estado Git final. No hacer push, merge a PROD o despliegue automatico.
   Las excepciones requieren decision explicita documentada.

## Recuperacion sin destruir trabajo

Para inspeccionar la base: `git show backup/prod-sync-base-20261025:ruta`.
Para recuperar en otra carpeta, usar un worktree de la rama backup o clonar el
bundle externo. No aplicar reset --hard ni clean sobre DEV.
Para deshacer integraciones, revisar y revertir commits propios uno por uno,
preservando cambios posteriores. Los snapshots de PROD permanecen independientes.
No restaurar datos de negocio como parte de una reversion de codigo.

## 2026-10-26: miniaturas de Operacion hacia el visor (solo DEV)

Origen: defecto confirmado en el JavaScript servido por PROD y en DEV: las
miniaturas enlazaban al original protegido, evitando la galeria y su zoom.
Ahora cada miniatura enlaza a `/fotos/?registro=ID&foto=URL_CODIFICADA` usando
el registro de la propia evidencia, incluso en filas agrupadas del panel.
El filtro se aplica sobre `get_registros_permitidos`, nunca sobre todos los
registros. Un identificador invalido devuelve un conjunto vacio. El visor
solo abre una URL que ya figure entre las miniaturas autorizadas renderizadas;
no carga URLs arbitrarias recibidas en la consulta. No se modifican fotos,
asociaciones, colas ni las acciones existentes de mas fotos/badge.

Base: `1bfa6b5f4acec407f8618e5027b1385cc72030eb`.
Respaldo externo: `/mnt/Orto/iqa_operation_link_backup_20261026T164644Z/before.tar.gz`,
SHA256 `f81b708947bc52979be2e66cea87886b969f0cc666de59284ef9a9db2b428942`.
El archivo tar fue listado correctamente; la referencia Git de recuperacion
es la rama `backup/before-operation-gallery-link-20261026T164644Z`.
La reversion debe limitarse a este cambio revisado, sin sustituir archivos
completos ni descartar avances posteriores.

Validacion: `python -B -m unittest scripts.tests.test_operation_gallery_link
scripts.tests.test_gallery_zoom -v`: 3 pruebas correctas, incluyendo Chromium
en 1440x1000, 900x650 y 390x844. Se verifica destino/codificacion del enlace,
seleccion exacta, rechazo de URL desconocida y regresion de zoom/navegacion.
La prueba del filtro usa un queryset simulado: no sustituye una prueba Django
con PostgreSQL ni una comprobacion autenticada de permisos extremo a extremo.
`node --check web/static/js/panel_operativo.js` y `git diff --check` correctos.
PROD no modificado; no desplegado. El preflight y cualquier autorizacion de
despliegue siguen siendo necesarios; la excepcion previa era solo del visor.

### Ajuste visual posterior: barras del visor

Se ocultan exclusivamente las barras de desplazamiento del visor mediante
`scrollbar-width: none` y el pseudoelemento WebKit; se conserva `overflow: auto`
para no perder el arrastre, el desplazamiento tactil ni el acceso a los bordes.
No se cambia la tira de miniaturas. Respaldo externo previo:
`/mnt/Orto/iqa_gallery_scrollbars_backup_20261026T185724Z/before.tar.gz`,
SHA256 `3af38369049c8adc0ca20da512f8d35b7abc47ca7ad72ed7ffd6161637789156`.
Las mismas 3 pruebas pasan, incluyendo ausencia de barras por estilo calculado
y arrastre real en Chromium para los tres tamanos. No probado en dispositivos
fisicos ni otros motores. Se refresco solo el servidor de demo aislado del
tunel existente; PROD permanece intacto.

### Aplicacion autorizada a PROD

Posteriormente, el usuario autorizo explicitamente una excepcion acotada para
Operacion -> galeria y visor sin barras. Se aplicaron solo los bloques necesarios
sobre los fuentes reales de PROD y su copia estatica, sin sustituir DEV/PROD.
Validacion y limites: `docs/deployments/20261026-operation-gallery-hotfix.md`.
La politica general sigue BLOCKED; esta excepcion no habilita otros despliegues.

## 2026-10-26: borrado administrativo desde Operacion (solo DEV)

Causa confirmada en DEV y fuentes PROD: `api_delete_registro` llamaba `delete()`
sin `force_delete=True`, obligatorio por la proteccion de `RegistroDefecto`.
La prueba previa reprodujo PermissionError para el superusuario. Se corrige
solo esa llamada, despues de la comprobacion `is_superuser`, sin retirar
la proteccion del modelo, POST obligatorio, autenticacion ni CSRF.

El borrado sigue siendo permanente: desaparecen el registro y sus filas de
evidencias por CASCADE, igual que en la API V2 existente. No elimina archivos
originales del almacenamiento. No se introduce borrado logico ni recuperacion.
No se probo ni ejecuto un borrado contra datos productivos.

Base Git: `e98ed18`. Rama de recuperacion:
`backup/before-operation-delete-20261026T191125Z`.
Respaldo de views.py: `/mnt/Orto/iqa_delete_fix_backup_20261026T191125Z/before.tar.gz`,
SHA256 `3e2b92909a8f58cade49a863d6b972dfe69934d6794631250422b6293e7ffd14`.

Pruebas: PostgreSQL nuevo en RAM, socket Unix local, sin listener TCP, sin
volumenes ni bases productivas, broker en memoria. El proceso temporal se
detuvo al terminar. Antes: 4 pruebas correctas y un error reproducible.
Despues: 5 nuevas pruebas y 9 pruebas V2 existentes correctas (14 en total).
Se comprobaron superusuario, usuario normal y staff sin privilegio superuser,
anonimo, GET, CSRF, ID ya eliminado, bloqueo del modelo, otro registro intacto,
eliminacion de filas relacionadas y hash del original sintetico conservado.
Las migraciones del test se aplicaron solo a PostgreSQL temporal.
La nueva suite queda incluida en `run_conservation_checks.py`.

Logs previos y posteriores conservados junto al respaldo externo. Preflight
general BLOCKED; no se desplego este cambio, no se reinicio PROD ni se tocaron
sus registros, fotos, sesiones o colas. La autorizacion anterior era unicamente
para navegacion y barras del visor; no cubre el borrado administrativo.

### Autorizacion posterior: borrado y registro de prueba

El usuario autorizo despues expresamente aplicar solo el arreglo de borrado y
crear un registro para comprobarlo manualmente. Se aplico el cambio de una linea
en PROD y se creo el registro 808 PRUEBA-BORRADO sin fotos. No se borro ningun
registro productivo. Ver `docs/deployments/20261026-operation-delete-hotfix.md`
para alcance, validacion, efectos del registro sintetico y limites de reversion.

## 2026-10-26: avisos integrados en el tema (solo DEV y demo)

Solicitud del usuario: sustituir los cuadros del navegador ("esta pagina dice")
por avisos acordes al resto de paginas. Se conserva la API existente
`showConfirmModal` y sus callbacks, usando un parcial compartido con `<dialog>`
estilizado. No se sobrescriben `window.alert`, `confirm` ni `prompt`.

El parcial `calidad/partials/app_dialog.html` se incluye desde base.html y desde
el workspace independiente. Incorpora confirmacion, aviso y captura de texto;
las llamadas que antes bloqueaban el hilo esperan ahora la respuesta mediante
await. Las cancelaciones no ejecutan callbacks ni peticiones. Escape cancela;
el foco inicial va a Cancelar (o al campo en ediciones) y el navegador mantiene
el foco dentro del dialogo modal. Los mensajes se insertan como texto, nunca HTML.
Las aperturas simultaneas se encolan para no sobrescribir una confirmacion.

Actualizados los llamadores de Operacion, diccionario, borradores de WhatsApp,
importaciones y revisiones de orientacion/Box Condition. Se quitaron las llamadas
`.replace` erroneas sobre el resultado de showConfirmModal en avisos existentes.
No se cambian endpoints, permisos, reglas de borrado, archivos ni base de datos.

Recuperacion previa: rama `backup/before-themed-dialogs-20261026T192202Z` y
`/mnt/Orto/iqa_dialogs_backup_20261026T192202Z/before.tar.gz`, SHA256
`88977f630b6f00b09af3950763a073bb9c31f50927a5913e718dfb487be6f999`.
El tar fue listado sin errores; no sustituir archivos completos sobre cambios
posteriores al revertir. Base Git anterior: `cb5308e`.

Pruebas: Chromium real 1440x1000 y 390x844 para confirmar/cancelar, foco,
Escape, Enter, texto vacio, texto no interpretado como HTML, callback unico,
cola de avisos y flujo real del metodo eliminarRegistro con fetch simulado.
Se verifico que cancelar no cambia filas ni envia solicitudes. Capturas
`/dev/shm/iqa-app-dialog-1440.png` y `iqa-app-dialog-390.png`.
Cinco pruebas de scripts correctas al incluir navegacion y zoom existentes.
Las ocho plantillas afectadas compilan con Django; node --check y diff --check
correctos. El buscador de regresion ya no encuentra alert/confirm/prompt nativos
en las plantillas propias ni en web/static/js. La demo aislada de Operacion
tambien abre el dialogo nuevo y conserva su fila al cancelar.
Regresion adicional: 36 pruebas Django correctas (`tests_operation_delete`,
`tests_v2`, `tests_pending_evidence`) contra PostgreSQL nuevo en RAM; incluye
confirmacion concurrente, permisos, borradores, orden, exclusion y recuperacion.
Solo se aplicaron migraciones al PostgreSQL temporal y se detuvo al finalizar.
Log persistente junto al respaldo externo: `django-regression.log`.

No se publico este cambio en PROD. Las excepciones previas no lo incluyen.
No se probaron Safari/Firefox ni mensajeria real; no se ocultaron avisos propios
de seguridad del navegador ni se modifico el administrador de Django/terceros.
