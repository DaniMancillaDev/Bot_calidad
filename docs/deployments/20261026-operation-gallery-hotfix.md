# Operacion -> galeria: excepcion PROD de 2026-10-26

Autorizacion: `si` del usuario tras la solicitud explicita de excepcion limitada
a Operacion -> galeria y ocultar barras del visor, respaldo/reversion y recarga
solo de procesos web, sin migraciones ni despliegue completo de DEV.
El preflight general permanece BLOCKED y no se altero su politica.

Base DEV: `1f3c63dac5205cdb29aa22684ffc60cad5834c0e`.
Los cambios funcionales estan conservados en `932e343` y `1f3c63d`.
No se copiaron views.py ni panel_operativo.js completos desde DEV a PROD:
se prepararon cambios puntuales sobre los archivos originales de PROD.

## Alcance aplicado

- `/app/web/calidad/views.py`: filtro opcional por registro sobre el queryset
  ya restringido por permisos; identificadores invalidos devuelven vacio.
- `/app/web/static/js/panel_operativo.js`: miniaturas hacia la galeria con
  identificador del registro de la evidencia y URL original codificada.
- `/app/static_collected/js/panel_operativo.js`: mismo parche para Nginx.
- `/app/web/templates/calidad/galeria.html`: abrir la imagen seleccionada solo
  si figura entre las miniaturas renderizadas; ocultar barras sin perder arrastre.

Reemplazos atomicos condicionados a hashes, conservando propietario, grupo,
modo y atributos. Solo SIGHUP al master Gunicorn verificado, PID interno 35.
Workers anteriores 11298/11306; posteriores 14093/14113.
Los 15 contenedores inventariados conservaron imagen, StartedAt, estado y
RestartCount. No se tocaron Celery, Telegram, WhatsApp, Redis ni PostgreSQL.

## Evidencia y reversion

Directorio externo: `/mnt/Orto/iqa_operation_prod_hotfix_20261026T190400Z/`.
Contiene MANIFEST.json, reviewed.diff, cuatro pares before/after, snapshots de
hashes de fuentes, validacion readonly previa/posterior, RESULT.json y SHA256SUMS.
RESTORE.md especifica reversion condicionada a hashes; no ejecutar un despliegue
nuevo para revertir. El respaldo de codigo sobre Orto no reemplaza al respaldo
independiente de datos ni demuestra recuperacion completa.

Se verificaron 315 registros y 1,824 evidencias antes y despues (crecimiento
legitimo respecto de informes anteriores). Diez registros reales seleccionados
desde el panel coincidieron con sus originales en la galeria; dos usuarios
existentes no pudieron acceder mediante el filtro a registros fuera de sus
permisos. Cuatro entradas invalidas devolvieron vacio. Tres originales muestreados
mantuvieron sus hashes SHA256 antes/despues. SQL forzado a solo lectura en todos
estos controles, sin crear usuarios ni sesiones.

JavaScript publico comprobado contra SHA256 de la copia estatica aplicada:
`82b06835836fbd348916a3ddc738bcdf1f5bb4f58f5b75b16d152415d27032a3`.
Login publico HTTP 200. Redis RDB/AOF ok; PostgreSQL disponible; contadores de
errores del dispositivo raiz en cero y sin errores nuevos del kernel observados.
El primer chequeo previo uso por error `/accounts/login/` (404) y se detuvo antes
de escribir PROD. Se corrigio a la ruta real `/login/`; no hubo reversion necesaria.

## Limites

No hubo login HTTPS interactivo ni prueba manual desde telefono sobre PROD.
El navegador se comprobo con datos de muestra y los datos reales mediante
render Django readonly. Los hashes de tres archivos no demuestran integridad
total de todas las fotografias. Btrfs sigue bajo presion de metadatos y requiere
su intervencion separada autorizada; no se reparo en este cambio.

El parche de fuentes vive en la capa escribible del contenedor y no esta en la
imagen original. Sobrevive reinicios del mismo contenedor, no su recreacion.
La copia estatica esta en volumen persistente, pero collectstatic puede sustituirla.
Antes de recrear servicios o ejecutar collectstatic, incorporar estos cambios a
una imagen revisada o reaplicarlos explicitamente desde el respaldo verificado.
No se hizo push, construccion, despliegue de DEV completa ni cambio de esquema.
