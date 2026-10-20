# WhatsApp — fase 3: adaptador Baileys

El adaptador está en la carpeta whatsapp/ y permanece deshabilitado por
defecto. Solo arranca Baileys cuando WHATSAPP_ENABLED=true; construir la imagen
no vincula una cuenta ni abre una sesión.

## Versión y límites deliberados

La versión está fijada a @whiskeysockets/baileys@7.0.0-rc14 en
whatsapp/package.json y package-lock.json. En la fecha de esta implementación
es una release candidate; el piloto debe validar esta versión con una cuenta
dedicada antes de producción. Baileys es una biblioteca no oficial y WhatsApp
puede cambiar el protocolo, cerrar sesiones o restringir el número.

La documentación oficial exige Node.js 20 o superior, recomienda persistir las
credenciales fuera del árbol fuente y advierte que useMultiFileAuthState es una
solución sencilla, no un almacén de sesión de producción. Esta fase usa esa
utilidad para un único piloto porque permite QR, reinicios y el menor número de
piezas. El siguiente escalón es implementar un AuthenticationState durable en
base de datos o almacenamiento secreto.

## Flujo

messages.upsert solo procesa eventos notify, nunca append (historial). Solo
acepta remoteJid de grupo incluido exactamente en
WHATSAPP_ALLOWED_GROUP_IDS, ignora mensajes propios y solo extrae imageMessage,
incluidos envoltorios efímeros/view-once. La descarga ocurre inmediatamente y
tiene límite de tamaño. Cada archivo entra en una cola local persistente antes
de enviarse a POST /api/v1/whatsapp/ingest/.

La clave de idempotencia es grupo + ID de mensaje + posición del medio. La cola
conserva metadatos y el archivo hasta recibir HTTP 200 o 201 de Django; un 200
de duplicado también confirma que Django ya lo recibió. Los estados sending
vuelven a pending al reiniciar. Las descargas fallidas quedan registradas y
una redeliveración puede reintentarlas. La cola mantiene la fila entregada
para que una reconexión no duplique la evidencia.

participant, participantAlt, senderPn y senderLid se conservan como
identificador principal y alterno cuando Baileys los proporciona. Un LID no se
convierte en número: el endpoint guarda el alterno en
sender_alt_whatsapp_id, y solo se envía teléfono verificado cuando el
identificador principal es un JID telefónico explícito.

El adaptador no llama a métodos de envío de mensajes ni marca presencia en
línea (markOnlineOnConnect: false). No consulta conversaciones privadas ni
otros grupos después del filtro local.

## Configuración privada

Variables mínimas cuando se habilita:

    WHATSAPP_ENABLED=true
    WHATSAPP_ALLOWED_GROUP_IDS=120363000000@g.us
    WHATSAPP_INGEST_URL=http://web:8000/api/v1/whatsapp/ingest/
    WHATSAPP_INGEST_API_KEY=<la misma clave privada que Django>
    WHATSAPP_SESSION_DIR=/app/data/whatsapp_session
    WHATSAPP_QUEUE_DIR=/app/data/whatsapp_queue
    WHATSAPP_QR_IN_TERMINAL=true

/app/data debe ser un volumen privado y exclusivo del adaptador. Nunca se debe
compartir con MEDIA_ROOT, Nginx, el repositorio ni producción. El QR y los
archivos de sesión son credenciales; no deben aparecer en logs, Git, backups
públicos ni tickets.

El Compose de producción no se modifica en esta fase. Para el futuro piloto se
debe añadir el adaptador como servicio separado, con red interna, volumen
dedicado y la clave inyectada por un gestor de secretos.

## Pruebas

npm test cubre mensajes simulados, historial, allowlist, LID/JID, duplicados,
cola persistente, fallos de red, confirmación 200/201 y fallos de descarga.
docker-compose.whatsapp-adapter-test.yml levanta PostgreSQL 16, Redis 7,
Django y un cliente Node temporal en una red y almacenamiento temporales;
prueba migraciones y el endpoint real sin Baileys ni WhatsApp.

La prueba no demuestra recuperación de mensajes que WhatsApp nunca vuelva a
entregar tras una desconexión. Baileys no ofrece una garantía de captura
histórica absoluta; append se descarta intencionadamente. La conciliación de
mensajes, el almacén de sesión basado en DB y la prueba piloto con una cuenta
dedicada siguen pendientes.
