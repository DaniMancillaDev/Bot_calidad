# Auditoria del login IQA

## Revision visual posterior

Revision con ui-styling: en escritorio (900px o mas) el acceso se distribuye
en dos columnas, con identidad IQA a la izquierda y formulario a la derecha;
en pantallas menores se mantiene una sola columna. Conserva tema oscuro y
controles existentes. No se incorporan React, Tailwind ni dependencias.

La direccion visual final conserva el modo oscuro de produccion: fondo y
superficies oscuras, panel de identidad mas profundo y azul electrico como
accion primaria. En escritorio usa una proporcion aproximada 1.45:1; en movil
el panel de identidad pasa arriba. Se cargan Host Grotesk para encabezados e
Instrument Sans para controles y lectura.

Revision adicional con ui-ux-pro-max: se consultaron autenticacion accesible,
contraste y resumen de validacion. Se conserva pegar y autocomplete; el
resumen de campos invalidos recibe foco e incluye enlaces a cada campo, sin
quitar sus errores individuales. El estado vacio bajo el boton ya no ocupa
espacio. No se anade MFA ni otro mecanismo de autenticacion.

El usuario senalo que el primer cambio apenas se distinguia del anterior y
solicito conservar el tema oscuro del sistema. Se redisenó en DEV con tarjeta
oscura de 460px, marca y encabezado alineados a la izquierda, divisor y campos
contrastados. Se conservaron Django, errores y controles.
El respaldo del estado previo a este rediseno esta en
`/mnt/Orto/iqa_login_master_backup_20261027T012050Z/pre-rediseno-dev-20261027.tar.gz`.
Las medidas y colores descritos debajo corresponden al primer cambio, no a
esta revision visual. Los limites de pruebas y seguridad siguen aplicando.

Fecha: 2026-10-27 UTC (26 de octubre en Tijuana). Solo DEV; sin commit ni despliegue.

## Proteccion

Repositorio `/mnt/Orto/Bot_calidad_dev`, rama `feature/whatsapp-evidencias`.
HEAD inicial/final `ba43a3d6317e5960e66d338f8aa837e813d8436a`, inicialmente limpio.
Referencia `backup/before-login-master-audit-20261027T012050Z`.
Respaldo externo `/mnt/Orto/iqa_login_master_backup_20261027T012050Z/before.tar.gz`.
SHA256 `258e4f4bba3246d13b5fdb2c00dd686f5d6dba7844afbdf880d94a9ca079150a`.
Listado del archivo verificado; esto no constituye respaldo de datos.
Reversion: comparar archivos respaldados y revertir solo esta tarea, sin
extraer ciegamente sobre cambios posteriores. Produccion no se modifico.

## Arquitectura y hallazgos

`web/config/urls.py`: LoginView, LogoutView y AuthenticationForm nativos Django.
Sesiones de base de datos, CSRF y middleware existentes conservados.
Template independiente `web/templates/calidad/login.html`; POST convencional.
Django valida next. Logout requiere POST. Sin rutas de recuperacion/MFA/SSO
que permitan agregar enlaces funcionales. Usuario no equivale a email.

Problemas confirmados corregidos:

- Media: boton deshabilitado sin guarda explicita contra eventos de envio
  repetidos; ahora existe estado pendiente validado antes de procesar.
- Media: toggle cambiaba nombre accesible usando aria-pressed; nombre estable
  y estado anunciado ahora son coherentes con APG.
- Media: sin aviso cuando el navegador ya sabe que esta offline; ahora no
  envia, enfoca aviso y permite corregir/reintentar sin bloquear el formulario.
- Baja: CSS general, jerarquia mejorable y emblema remoto; estilos encapsulados
  bajo `.login-page`, H1 claro y favicon local existente, sin inventar marca.

## Diseno e implementacion

Tarjeta centrada 420px: dos campos no justifican panel editorial lateral.
Se conserva identidad IQA/Bot de Calidad y campos legibles del DEV previo.
Inter/system-ui, etiquetas 16px, espacio etiqueta/campo 8px, grupos 20px.
Campos de alto minimo 54px, boton 50px, toggle 48px; radios 6px/tarjeta 8px.
Sin altura fija: scroll vertical natural. No badges, modales ni dependencias.
Transiciones breves/spinner solo con movimiento permitido.

Se agregan contexto neutral cuando next requiere acceso y enlace al panel
para usuario autenticado. No se deduce sesion expirada solo a partir de next.
Mostrar/ocultar conserva clave y foco; oculta antes del POST y al volver.
Errores genericos de credenciales; requeridos por campo con foco,
aria-describedby y aria-invalid. Usuario escapado y conservado; clave no
reflejada por servidor ni almacenada en storage. Se preserva autenticacion.

Archivos: template, `web/calidad/tests_login.py`, este informe y `docs/LOGIN_UX.md`.
Otros modulos, cuentas, contrasenas, migraciones y configuraciones no cambiados.

## Seguridad y limites

Tests cubren CSRF, next externo, escape, rotacion de sesion, invalidacion
al salir, cuenta inactiva y cookies HttpOnly/SameSite Lax/Secure segun settings.
DEBUG afecta Secure: no se certifica configuracion efectiva de PROD.
No se encontro rate limit en autenticacion/nginx versionados; defensas externas
Cloudflare no auditadas. Rate limit/MFA/cookies globales requieren aprobacion.
No se implementaron recuperacion de cuenta ni enlaces inexistentes.

Offline del navegador no prueba conectividad del servidor. Fallos durante
POST conservan la pagina de error nativa; pageshow restablece controles al
volver (evento sintetico probado, desconexion real durante POST no probada).
CSRF403/500 dependen de handlers globales que no se modifican aqui.

## Validacion real

Comando `python -B /dev/shm/run_delete_regression.py`: 51 pruebas correctas,
system checks Django sin incidencias. PostgreSQL nuevo en RAM, namespace
aislado, socket propio sin TCP, cuentas sinteticas y broker de memoria.
Modulos `tests_login`, `tests_operation_delete`, `tests_v2`, `tests_pending_evidence`.
Log inicial `/dev/shm/iqa-delete-db-jke7oobe/tests.log`; copia persistente en
directorio de respaldo citado. No uso de DB, Redis ni volumen productivos.
Login valido/invalido, requeridos, redirecciones, logout/nuevo acceso, sesion
autenticada/expirada y regresiones de permisos y evidencias incluidos.

Chromium: dos escenarios por cada resolucion 1920x1080, 1440x900, 1280x720,
1024x768, 768x1024, 390x844, 320x568. Limites horizontales, dimensiones,
contrastes calculados, campos/errores/foco, toggle, paste no bloqueado,
offline simulado, duplicados y pageshow comprobados automaticamente.
Contrastes: borde/panel 5.69:1; borde/campo 4.35:1; texto/campo 12.18:1;
placeholder/campo 7.72:1. Umbrales evaluados sin redondeo.
Capturas antes/despues guardadas fuera de Git. La primera captura file://
no resolvia el favicon: fixture corregido para incrustar el recurso real.

Pendiente: zoom nativo 200%, reflow ampliado real, eventos de teclado fisico
o CDP Tab/Enter/Space, lector de pantalla/arbol accesible, axe, Safari/Firefox
y telefonos fisicos. Reduced-motion revisado en CSS, no emulado.
Eventos sinteticos no demuestran gestores externos ni recuperacion real de red.
No se afirma certificacion WCAG 2.2 AA ni cumplimiento total del prompt.

## Fuentes

- [NNGroup](https://www.nngroup.com/articles/web-form-design/): columna unica y proximidad de etiquetas.
- [Material Web](https://github.com/material-components/material-web/blob/main/docs/components/text-field.md): etiquetas y estados. Material 3 requiere JS; no se afirma lectura integral de esas paginas.
- [WCAG contraste de controles](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) y [texto](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html): umbrales aplicados.
- [WCAG autenticacion](https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html): permitir pegar y gestores.
- [APG botones](https://www.w3.org/WAI/ARIA/apg/patterns/button/): nombre estable con aria-pressed.
- [USWDS login](https://designsystem.digital.gov/templates/authentication-pages/sign-in/): formulario sencillo, error generico y mostrar clave.
- [OWASP autenticacion](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) y [sesiones](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html): no enumeracion y controles de sesion.

## Estado final

Cambios locales sin commit. Ningun despliegue, push, reinicio productivo o
cambio de datos. Telegram/WhatsApp/evidencias/reportes no modificados.
Demo sintetica: no introducir credenciales reales. Antes de aceptar toda
la validacion quedan las pruebas explicitamente pendientes arriba.
