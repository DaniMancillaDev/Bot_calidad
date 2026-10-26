# Visor de evidencias: excepcion PROD de 2026-10-26

Autorizacion: mensaje del usuario `si`, inmediatamente posterior a la pregunta
explicita de excepcion documentada limitada al visor, respaldo/reversion y
recarga de procesos web, sin desplegar DEV completa ni ejecutar migraciones.
Se mantuvo registrado el riesgo conocido de metadatos Btrfs raiz (91.52%).

El preflight general sigue BLOCKED. No se modifico ni debilito su politica,
no se aprobaron hashes globalmente ni se aplicaron migraciones pendientes.
Esta autorizacion no cubre cambios funcionales o despliegues posteriores.

Se aplico SOLO `/app/web/templates/calidad/galeria.html` de `bot_calidad_web`,
contenido identico a DEV `bc55d190a112f5a7c3d04a9263a424c6e6a22b91`.

- SHA256 anterior: `07f906f0df846f2a5854151af2d28ab74947e3dfe6806864d55a30040b660ba7`.
- SHA256 aplicado: `6cabf9c382878e14956a685cb4310f774b8deada94311cdface9d5e51a8a247a`.
- Reemplazo atomico, fsync, propietario 1000:1000 y modo 0644 conservados.
- SIGHUP al master Gunicorn verificado (PID interno 35), no al PID 1.
- Workers finales observados: 11298 y 11306. Sin reiniciar/recrear contenedor.
- Imagen original conservada: `sha256:e20a65703b24d79fc99db09df57c8340ba3e7519450140508ca8d1eff7d85842`.

Validacion: sintaxis compilada con Django PROD; Chromium en tres tamanos,
zoom/arrastre/navegacion y objetivos tactiles de 44px; render real de la vista
con cuenta existente y SQL forzado a solo lectura, sin sesiones nuevas.
El render devolvio 200 con los controles y CSS aprobados. Se observaron 305
registros y 1,781 evidencias tanto antes como despues; no se escribieron registros.
La vista publica de login devolvio HTTP 200 con identificacion de navegador.

El primer control remoto con Python recibio 403 y activo la reversion real,
que funciono. El mismo 403 persistia con la plantilla original para el cliente
Python; curl y navegador recibian 200. Se repitio el parche usando un control
HTTP representativo de navegador, manteniendo criterio 200 y reversion automatica.
El resultado final satisfactorio es RESULT_ATTEMPT_2.json; RESULT.json conserva
la primera reversion y no debe interpretarse como estado final.

Comparacion contra snapshots verificados: una unica fuente revisada cambio,
`web:web/templates/calidad/galeria.html`. Todas las demas fuentes de web,
Celery, bot y assets revisadas permanecen iguales. Imagenes, StartedAt y
RestartCount de todos los contenedores conservados. No se tocaron Telegram,
WhatsApp, Celery, Redis, PostgreSQL, fotografias, configuracion o Compose.
No hubo nuevos errores Btrfs/I/O/ENOSPC observados; la presion sigue sin resolver.

Respaldo, autorizacion, diff y pruebas de reversion:
`/mnt/Orto/iqa_gallery_prod_hotfix_20261026T161932Z/`.
Incluye ambas plantillas, SHA256SUMS, helpers de validacion sin secretos y
RESTORE.md con el procedimiento condicionado por hashes. Es un respaldo de
codigo sobre Orto, NO sustituye al respaldo independiente de datos de la USB.

Limites: no hubo login HTTPS real con una cuenta del usuario ni prueba manual
en telefono. El render autorizado fue interno, con conexion PostgreSQL readonly.
El hotfix sobrevive reinicios del mismo contenedor, pero NO su recreacion desde
la imagen original. Incluir el parche en una imagen futura revisada o restaurarlo
explicitamente. Conservarlo tambien en el respaldo final de la migracion RAID.
