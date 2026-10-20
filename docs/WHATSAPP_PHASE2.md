# WhatsApp — fase 2: bandeja web de evidencias pendientes

Esta fase añade una bandeja autenticada para seleccionar fotografías recibidas
por WhatsApp, agruparlas manualmente y confirmar un `RegistroDefecto`. No
conecta Baileys ni crea registros automáticamente durante la ingesta.

## Rutas

- `GET /evidencias-pendientes/`: bandeja de fotografías listas y borradores.
- `POST /evidencias-pendientes/`: crea un grupo o confirma un borrador.
- `POST /evidencias-pendientes/contactos/<id>/`: cambia el nombre local de un
  contacto.
- `GET /evidencias-pendientes/<uuid>/imagen/?size=thumb`: sirve una miniatura
  protegida desde la raíz privada de WhatsApp.

Las operaciones web requieren sesión autenticada y CSRF. Los usuarios con
perfil pueden trabajar con evidencias sin grupo; los borradores quedan
visibles para su operador y los superusuarios.

## Confirmación

La selección se bloquea con `select_for_update()` dentro de una transacción.
La confirmación vuelve a bloquear el grupo y sus evidencias, copia cada
original a `MEDIA_ROOT/fotos/<usuario>/` mediante archivo temporal y crea el
`RegistroDefecto` junto con sus `EvidenciaFotografica`. La copia conserva el
archivo original pendiente para evitar pérdida si la base o el filesystem
fallan.

El grupo conserva `created_by`, `confirmed_by`, `confirmed_at` y el registro
definitivo. Cada evidencia conserva el remitente WhatsApp en `WhatsAppContact`
y también en `EvidenciaFotografica.metadatos`; los contactos no son usuarios
Django.

La tarea existente `generar_thumbnails_lote_task` se programa con
`transaction.on_commit`, por lo que nunca se ejecuta antes de que el registro
sea visible en PostgreSQL. Si Celery no está disponible, el registro y los
originales permanecen; el fallo queda en logs para reintentar operativamente.

No se añadió una migración: la fase usa las tablas y campos de `0015`.
