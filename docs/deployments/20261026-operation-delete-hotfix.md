# Borrado administrativo: excepcion PROD 2026-10-26

Autorizacion explicita del usuario: `SI, Y PONME UN REGISRTO DE PRUEBA PARA
COMPORBAR EL FUNCIONAMIENTO YO MISMO`, tras solicitar excepcion limitada a este
arreglo, respaldo/reversion y recarga de procesos web sin migraciones.

Se modifico una sola linea de `/app/web/calidad/views.py`, sobre su contenido
real de PROD: `registro.delete(force_delete=True)` en `api_delete_registro`,
despues del permiso de superusuario. No se copio el archivo completo desde DEV.
Se conservaron la proteccion del modelo, autenticacion, POST y CSRF.

- SHA256 anterior: `0c435699281df8fd44fc3ed8a909c55767229b225e12fc751af6d0727e1bcb3f`.
- SHA256 aplicado: `c07043fdfd1a7c39295a1c2a9a0af6dbb2a0b0ce489516c4a5f060fc6f5f56dd`.
- Base DEV: `72c9f0d`; cinco pruebas nuevas y nueve V2 existentes correctas
  sobre PostgreSQL temporal en RAM. Fallo PermissionError reproducido antes.
- Reemplazo atomico con hashes y metadatos preservados, SIGHUP solo al master
  Gunicorn interno 35. Workers 14093/14113 -> 14452/14454.
- Los 15 contenedores conservaron estado, imagen, arranque y RestartCount.
- Comparacion de fuentes: solo cambio `web:web/calidad/views.py`.

Validacion del endpoint instalado: SQL readonly y objeto sintetico sustituido
en memoria para no borrar datos reales; HTTP 200 para superusuario y 403 para
no superusuario, con comprobacion del flag de borrado. El borrado real y CASCADE
se probaron unicamente en la base temporal. La comprobacion en PROD no demuestra
todavia un borrado real extremo a extremo desde navegador.

Redis RDB/AOF correctos, PostgreSQL disponible, login publico HTTP 200,
contadores de errores del Btrfs raiz en cero y sin errores nuevos del kernel
observados. La presion sigue: metadatos 91.57%, espacio sin asignar 1.05 MiB.
No se hizo mantenimiento de almacenamiento, migracion ni despliegue completo.
Preflight general sigue BLOCKED; la excepcion no modifica su politica.

## Registro autorizado para comprobacion manual

Se creo mediante transaccion solo el registro **808**, modelo **PRUEBA-BORRADO**,
descripcion explicita `PRUEBA DE BORRADO ADMIN - SIN FOTOS`, cantidad 1,
linea/responsable PRUEBA y user_id sintetico 0 (sin remitente real).
No tiene fotos ni evidencias asociadas, no se tocaron originales ni registros
existentes, no se enviaron mensajes ni se publicaron tareas.
La creacion lleva referencia unica del hotfix para evitar duplicados en reintentos.
Se dejo intacto para que el usuario pruebe eliminarlo desde Operacion.
Mientras exista puede aparecer en conteos/reportes del periodo; quitarlo con
el boton del panel tras comprobarlo. No se programa borrado automatico.

## Recuperacion

Respaldo y evidencia fuera del repositorio:
`/mnt/Orto/iqa_delete_prod_hotfix_20261026T191605Z/`.
Contiene los archivos before/after, manifiesto, diff, validacion, resultado,
datos no sensibles del registro de prueba, helpers y checksums.
El cambio de codigo no respalda ni revierte las eliminaciones que el usuario
haga posteriormente. Borrar registros es permanente y elimina sus filas de
evidencias por CASCADE; los archivos originales permanecen en almacenamiento.

Para revertir codigo, comprobar identidad del contenedor y hash aplicado,
usar atomic_write.py con target y hashes aplicado/anterior, bytes de
views.before.py por stdin, y recargar solo el master verificado con SIGHUP.
Si el hash actual no coincide, detenerse: no sobrescribir trabajo posterior.
No ejecutar docker restart, compose, collectstatic ni migrate. Revertir codigo
no implica borrar automaticamente el registro de prueba ni restaurar la DB.

El hotfix esta en la capa escribible del contenedor y se pierde si se recrea
desde la imagen original. Debe incluirse en una imagen futura revisada.
No hubo push ni cambios a Celery, Telegram, WhatsApp, configuracion o esquema.
