# WhatsApp — fase 1: recepción de evidencias pendientes

Esta fase añade solamente persistencia y un receptor HTTP interno para simular el
adaptador de WhatsApp. No conecta Baileys, no crea `RegistroDefecto` y no añade
interfaz web todavía.

## Endpoint

`POST /api/v1/whatsapp/ingest/`

El cliente interno debe enviar `X-WhatsApp-Ingest-Key` con el valor de
`WHATSAPP_INGEST_API_KEY`. La clave no tiene valor predeterminado seguro: si no
está configurada, todas las solicitudes son rechazadas. El grupo debe aparecer
en `WHATSAPP_ALLOWED_GROUP_IDS` (lista separada por comas).

Campos multipart requeridos: `group_id`, `message_id` y `file`. También se
aceptan `group_name`, `media_index`, `sender_id`, `sender_name`, `caption`,
`message_at`, `phone_number`, `phone_number_verified` y `historical`.

El archivo se valida por contenido con Pillow, no por el MIME declarado. En esta
fase se aceptan JPEG, PNG y WEBP hasta `WHATSAPP_MAX_IMAGE_BYTES`. Se guarda en
`WHATSAPP_PENDING_ROOT`, fuera de `MEDIA_ROOT` por defecto, usando un temporal,
`fsync` y `os.replace`. El endpoint rechaza una ruta configurada dentro de
`MEDIA_ROOT`. En Docker el valor por defecto es `/app/data/whatsapp_pending`;
la siguiente fase debe montar allí un volumen privado compartido entre los
servicios que lo necesiten.

Respuestas principales:

- `201`: imagen almacenada y estado `READY`.
- `200`: la misma combinación de grupo, mensaje y posición ya fue recibida.
- `400`: payload, imagen, fecha o posición inválidos; mensajes históricos están
  deshabilitados.
- `401`: credencial ausente o incorrecta.
- `403`: grupo no incluido en la lista blanca.
- `503`: fallo temporal de almacenamiento; la evidencia queda `FAILED` y el
  mismo mensaje puede reintentarse.

La unicidad de `(source, source_group_id, source_message_id, media_index)` es
la frontera de idempotencia. `media_index` permite representar cada archivo de
un álbum como evidencia separada sin agruparlo automáticamente.

## Identidades y modelos

`WhatsAppContact` no es un usuario web. Un contacto puede conservar un JID/LID
sin teléfono; el teléfono solo se guarda cuando el adaptador de confianza marca
explícitamente la relación como verificada. No se sobrescribe un nombre editado
por un operador.

`PendingEvidenceGroup` es el borrador que posteriormente podrá completar un
operador. Distingue `operator`/`created_by` de `WhatsAppContact` y puede enlazar
un registro definitivo cuando exista la fase de confirmación.

## Migración y reversión

`0015_whatsapp_pending_evidence` crea únicamente las tres tablas nuevas, sus
índices y la clave única. Su reversión elimina esas tablas y no modifica las
tablas históricas; por tanto, no debe aplicarse sobre una base existente sin el
respaldo y el procedimiento de mantenimiento correspondientes.

La imagen declara `/app/data` como volumen, pero el `docker-compose.yml` actual
no lo monta explícitamente en `web` ni `celery`. Para desarrollo aislado, la
siguiente fase debe usar un override con un volumen nuevo, por ejemplo:

```yaml
services:
  web:
    volumes:
      - whatsapp_pending_dev:/app/data/whatsapp_pending
  celery:
    volumes:
      - whatsapp_pending_dev:/app/data/whatsapp_pending

volumes:
  whatsapp_pending_dev:
```

Ese volumen no debe compartirse con `media_data`, Nginx ni producción. La
persistencia real debe comprobarse reiniciando únicamente el entorno temporal.

Las pruebas de `calidad.tests_whatsapp` usan la base temporal del runner de
Django y un directorio temporal de archivos. No deben apuntar a PostgreSQL,
Redis, volúmenes o credenciales de producción.

`calidad.tests_whatsapp_concurrency` requiere PostgreSQL para probar dos
conexiones concurrentes reales. En SQLite se omite explícitamente porque sus
bloqueos de archivo no representan la concurrencia de producción.

## Variables de entorno

```text
WHATSAPP_INGEST_API_KEY=<clave larga, aleatoria y fuera de Git>
WHATSAPP_ALLOWED_GROUP_IDS=<id-grupo-1,id-grupo-2>
WHATSAPP_PENDING_ROOT=<ruta privada persistente>
WHATSAPP_MAX_IMAGE_BYTES=26214400
WHATSAPP_PROCESSING_LEASE_SECONDS=300
```

Si el proceso cae después de registrar una evidencia y antes de completar el
archivo, una nueva entrega puede reclamarla cuando vence el lease. El lease usa
la hora del intento de procesamiento, no la fecha original del mensaje. La
reclamación compara atómicamente el contador de intentos para que dos reintentos
concurrentes no reclamen la misma fila.
