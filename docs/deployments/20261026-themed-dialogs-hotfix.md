# Dialogos del tema: excepcion PROD 2026-10-26

Autorizacion: el usuario respondio `si` a la solicitud explicita de excepcion
limitada a dialogos, respaldos/reversion, conservar fuentes reales de PROD y
recargar solo procesos web, sin migraciones, cambios de datos ni DEV completa.
Base DEV funcional: `4a3c35ec33a3295d8b4de975ce61bceb3c7b30f9`.
El preflight general sigue BLOCKED; no se debilito ni aprobo su politica.

## Alcance

Se aplico el diff revisado sobre snapshots frescos de PROD, no copias completas
de DEV. La diferencia de fin de archivo en base.html requirio reemplazar solo
el bloque global identico, conservando el resto de bytes de PROD.

- Nuevo `web/templates/calidad/partials/app_dialog.html`.
- `base.html`: incluye el dialogo compartido, manteniendo el layout PROD.
- `panel_operativo.js`, fuente y copia static_collected: esperar confirmacion
  tematizada antes de borrar o preparar Excel; conservar enlaces de galeria.
- Diccionario, workspace de importacion V1/V2, revision de orientacion y Box
  Condition: avisos/confirmaciones/entrada de texto con el mismo componente.
- La pagina DEV de evidencias WhatsApp no existe en PROD y no se incorporo.

La interfaz usa dialogos modales HTML estilizados, sin cambiar los endpoints,
CSRF, autenticacion ni reglas de borrado. No se cambiaron views.py, galeria.html,
models.py, migraciones, Compose, configuraciones, bases ni archivos de evidencias.
Se conservaron los hotfixes anteriores de navegacion, zoom y borrado autorizado.

## Aplicacion Y Evidencia

Respaldo y resultado final:
`/mnt/Orto/iqa_dialog_prod_hotfix_20261026T195408Z/`.
Incluye ocho originales, nueve candidatos, hashes, diff, identidad/estado de
contenedores, snapshots de fuentes, helpers, autorizacion y RESULT.json.
El nuevo parcial se creo de forma exclusiva; reemplazos atomicos con verificacion
de hashes y metadatos conservados para los archivos existentes.

Dos recargas SIGHUP al master Gunicorn interno 35: primero se publico el helper
y despues sus llamadores. Workers finales observados 15826 y 15846. Los 15
contenedores conservaron imagen, estado, StartedAt y RestartCount.

Antes y despues: 315 registros y 1,824 evidencias observados mediante SQL forzado
a solo lectura. Operacion, galeria y panel principal devolvieron 200 con un solo
dialogo compartido por pagina. Siete plantillas compiladas y 22 bloques JavaScript
renderizados comprobados con node --check. La galeria conserva el enlace directo
a la foto y las barras ocultas. La busqueda en plantillas/JS propios de PROD no
encuentra llamadas nativas alert/confirm/prompt restantes.

El JavaScript servido publicamente coincide con SHA256
`175d4808467dafd5d469f7d51a0f11d3e7a54a629c0c0d42a13a7a82b20c64eb`.
Pruebas Chromium del candidato real PROD en escritorio/movil: cancelar, Escape,
Enter, foco, texto vacio, mensajes como texto, callbacks/cola y borrado simulado.
Las 36 regresiones Django y cinco de scripts de DEV ya documentadas se conservan.

La primera aplicacion (`195030Z/RESULT.json`) fue ROLLED_BACK por una comprobacion
de procesos durante la terminacion transitoria de workers. Los archivos anteriores
se restauraron y el parcial recien creado se retiro; no hubo errores de almacenamiento
ni fallos de arranque observados. El comprobador se ajusto para esperar un estado
estable repetido, sin omitir la identidad del master ni reducir el minimo de workers.
Los candidatos del segundo intento tienen los mismos hashes que los probados.
El primer staging `195014Z` no se aplico: git rechazo contexto de base.html.

## Limites Y Recuperacion

RESTORE.md en el respaldo especifica reversion condicionada a hashes, conservando
el helper hasta restaurar llamadores y recargar. La primera reversion se ejecuto
realmente; no se afirma por una simulacion. No ejecutar nuevamente el controlador
como mecanismo de reversion ni sobrescribir trabajo posterior.

No se borro ni creo ningun registro, evidencia o fotografia en esta ejecucion.
No hubo migraciones, push, construccion, recreacion ni reinicio de contenedores.
Redis RDB/AOF ok, PostgreSQL disponible, login publico 200 y sin nuevos errores
del kernel/dispositivo observados. Btrfs sigue pendiente: metadatos 91.59%, solo
1.05 MiB sin asignar. No se realizo mantenimiento de almacenamiento.

No se hizo login interactivo HTTPS ni acciones destructivas en PROD para probarlo.
Safari/Firefox y telefonos fisicos no comprobados. La validacion de vistas reales
fue readonly y la de interaccion uso datos de muestra y peticiones simuladas.
El parche de fuentes no esta en la imagen original y se perdera al recrear el
contenedor; debe incluirse en una imagen revisada futura. collectstatic tambien
puede reemplazar la copia estatica si la imagen no incorpora el cambio.
