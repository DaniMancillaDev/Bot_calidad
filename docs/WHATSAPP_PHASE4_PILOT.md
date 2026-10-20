# WhatsApp — fase 4: piloto aislado

Este piloto es opcional y está separado de producción. El archivo
`docker-compose.whatsapp-pilot.yml` no reutiliza el Compose de producción,
contenedores, redes, volúmenes, base de datos ni credenciales activos.

## Estado seguro por defecto

Todos los servicios están bajo el perfil Compose `pilot`; ejecutar `up` sin
`--profile pilot` no inicia servicios. Incluso con el perfil activo,
`WA_PILOT_ENABLED` y `WA_PILOT_SHOW_QR` son `false` por defecto. Mientras esos
valores permanezcan así, Baileys no abre sesión ni muestra QR.

El piloto usa un único grupo configurado por `WA_PILOT_ALLOWED_GROUP_ID`.
`messages.upsert` solo acepta eventos `notify` del adaptador existente; los
eventos históricos, otros grupos, mensajes propios y contenidos no fotográficos
se descartan. El adaptador no envía mensajes ni marca presencia.

La red no publica PostgreSQL, Redis ni el endpoint de ingesta. Django se liga
solo a `127.0.0.1:18080` (configurable) para permitir una prueba local; no es
una exposición a Internet. La conexión saliente del adaptador es necesaria
únicamente para el protocolo de WhatsApp.

## Preparación sin conexión a WhatsApp

1. Verificar que la rama sea `feature/whatsapp-evidencias`, que el árbol esté
   limpio y que el commit de origen corresponda a la revisión que se quiere
   probar.
2. Generar un archivo privado fuera del repositorio, por ejemplo en `/tmp`, a
   partir de `whatsapp-pilot.env.example`. Usar contraseñas aleatorias y una
   clave Django independiente; no reutilizar `.env` de producción.
3. Mantener vacíos `WA_PILOT_ALLOWED_GROUP_ID`, `WA_PILOT_ENABLED=false` y
   `WA_PILOT_SHOW_QR=false` hasta que exista autorización explícita.
4. Validar el Compose sin iniciar servicios:

```sh
docker compose \
  --env-file /ruta/privada/whatsapp-pilot.env \
  -p bot_calidad_wa_pilot \
  -f docker-compose.whatsapp-pilot.yml config --quiet
```

La clave `WA_PILOT_INGEST_KEY` es obligatoria incluso con el adaptador apagado;
esto evita que el endpoint de Django quede configurado con una credencial
implícita o insegura.

## Persistencia y límites

Con el proyecto Compose fijo `bot_calidad_wa_pilot`, los volúmenes son
exclusivos y persistentes:

- `wa_pilot_postgres_data`: base de datos del piloto.
- `wa_pilot_redis_data`: broker/resultados del piloto con AOF.
- `wa_pilot_media`: fotografías y proxies del piloto.
- `wa_pilot_web_data`: pendientes privados bajo `/app/data/whatsapp_pending`.
- `wa_pilot_whatsapp_data`: credenciales/claves Signal bajo
  `/app/data/whatsapp_session` y outbox/multimedia bajo
  `/app/data/whatsapp_queue`.

No se deben montar rutas del host ni volúmenes de producción. La sesión sigue
siendo el almacén de archivos de Baileys con lock de un solo proceso; no es una
garantía de alta disponibilidad. La cola local conserva archivos hasta recibir
HTTP 200/201 de Django, pero no puede recuperar un mensaje que WhatsApp nunca
vuelva a entregar.

## Autorización necesaria para vincular la cuenta

No realizar estos pasos todavía. Requieren confirmación explícita del operador:

1. Elegir un número dedicado y un grupo de prueba que no sea el grupo real de
   inspectores.
2. Obtener el ID estable del grupo y colocarlo en
   `WA_PILOT_ALLOWED_GROUP_ID`; no usar un nombre como sustituto del ID.
3. Confirmar que el archivo privado contiene `WA_PILOT_ENABLED=true` y
   `WA_PILOT_SHOW_QR=true` solo para una ventana controlada de vinculación.
4. Iniciar únicamente el perfil del piloto y observar el QR localmente; nunca
   pegarlo en tickets, chats ni logs.
5. Una vez vinculada la cuenta, detener el servicio, cambiar
   `WA_PILOT_SHOW_QR=false` y conservar la sesión en el volumen privado.
6. Arrancar el piloto con el mismo nombre de proyecto y volver a comprobar que
   la sesión se reutiliza. No ejecutar ningún comando de producción.

La cuenta dedicada reduce el impacto operativo, pero Baileys no es la API
oficial de WhatsApp. La cuenta puede ser desconectada o restringida y la
compatibilidad del protocolo debe comprobarse durante el piloto.

## Procedimiento de prueba controlado

Antes de cada prueba comprobar el grupo allowlist, el número de commit, el
estado de los servicios del proyecto `bot_calidad_wa_pilot` y que no haya
contenedores de producción involucrados. No usar el grupo real todavía.

| Prueba | Procedimiento | Resultado esperado / aceptación |
|---|---|---|
| Foto individual | Enviar una imagen al grupo de prueba | Una evidencia pendiente, con grupo, remitente, fecha, caption si existe y hash; cero registros definitivos automáticos. |
| Seis consecutivas | Enviar seis mensajes de imagen separados | Seis evidencias individuales y seis claves de mensaje distintas. |
| Álbum de seis | Enviar seis imágenes como álbum | Seis evidencias si el proveedor entrega seis mensajes utilizables; si entrega menos, documentar los eventos realmente recibidos, sin inventar recuperación. |
| Dos remitentes | Enviar imágenes desde dos números | El grupo pendiente puede contener ambas; cada evidencia conserva su `sender_whatsapp_id`/alterno y ningún remitente necesita usuario Django. |
| Reinicio | Detener y volver a iniciar solo `whatsapp-adapter` con el mismo proyecto | No se crean duplicados; la sesión/outbox persisten y los archivos no confirmados siguen disponibles. |
| Django temporalmente caído | Detener solo `web` después de descargar una imagen; volver a levantarlo | La outbox permanece pendiente y reintenta; solo HTTP 200/201 marca entrega. |
| Bandeja | Acceder por `http://127.0.0.1:18080/evidencias-pendientes/` con un usuario de prueba | Miniaturas/originales protegidos; se ven grupo, remitente, fecha y caption. |
| Confirmación | Seleccionar varias, agrupar y confirmar con datos completos | Una transacción crea el registro definitivo; una segunda confirmación no duplica ni reasigna evidencias. |
| Trazabilidad | Revisar galería y detalle del registro | Se conserva el remitente WhatsApp de cada evidencia y el usuario web que confirmó el registro. |

Para simular la caída de Django, detener solo el servicio del proyecto de
piloto, nunca `bot_calidad_web`. Para inspeccionar la cola usar metadatos del
proyecto piloto; no imprimir el contenido de `outbox.json` ni de la sesión.

## Detención y reversión

El piloto se revierte deteniendo únicamente su proyecto:

```sh
docker compose --env-file /ruta/privada/whatsapp-pilot.env \
  -p bot_calidad_wa_pilot -f docker-compose.whatsapp-pilot.yml stop
```

No ejecutar `down -v` durante una prueba normal: los volúmenes contienen la
sesión, la outbox y las evidencias pendientes. Si se autoriza una eliminación
posterior, verificar antes que cada volumen tenga el prefijo del proyecto
`bot_calidad_wa_pilot` y que no contenga datos que deban conservarse.

## Evidencia y límites

Las pruebas automatizadas existentes cubren allowlist, mensajes históricos,
duplicados, reintentos, timeouts, medios expirados, remitentes y persistencia
de la cola. Este documento añade el procedimiento del piloto real, pero no
afirma que se haya ejecutado. La recepción durante una desconexión depende de
lo que WhatsApp/Baileys vuelva a entregar; no existe garantía absoluta de
recuperación histórica.
