# Login IQA: criterios y comprobaciones

Actualizacion 2026-10-27 UTC: [auditoria ampliada](LOGIN_AUDIT_20261027.md),
implementacion y limites reales. Solo DEV, sin commit ni despliegue.

## Objetivo

Corregir la dificultad reportada para distinguir Usuario y Contrasena sin
cambiar el mecanismo de autenticacion ni transformar el acceso en una landing.
El tema oscuro se conserva, pero los campos deben reconocerse sin enfocarlos.

## Fuentes consultadas

- [W3C: contraste no textual](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html):
  las senales visuales necesarias para identificar controles necesitan contraste
  suficiente contra sus colores adyacentes; referencia usada: 3:1.
- [W3C: contraste de texto](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html):
  para texto normal se toma como referencia 4.5:1.
- [W3C: etiquetas de formulario](https://www.w3.org/WAI/tutorials/forms/labels/):
  conservar etiquetas visibles y asociarlas mediante for/id.
- [NN/g: formularios](https://www.nngroup.com/articles/web-form-design/):
  agrupar cada etiqueta con su campo y mantener una accion principal clara.
- [GOV.UK: password input](https://design-system.service.gov.uk/components/password-input/):
  ocultar por defecto, permitir mostrar y pegar, conservar autocomplete adecuado,
  desactivar correcciones al mostrar la contrasena y ocultarla antes de enviar.

Consulta: 2026-10-26. Se usan principios concretos, no se copia un framework
ni se afirma una certificacion completa WCAG con estas pruebas parciales.

## Decisiones aplicadas

1. Etiquetas permanentes de 16px, visibles encima del campo a 8px. El placeholder
   no sustituye la etiqueta. Mayor separacion entre grupos que dentro de cada uno.
2. Campos de 54px de alto, fondo mas claro, borde de 2px perceptible incluso sin
   foco y texto de 16px. Las medidas son decisiones de diseno, no supuestos
   minimos de tamano de fuente exigidos por WCAG.
3. El borde anterior daba 1.34:1 contra el panel y 1.52:1 contra el interior.
   Borde nuevo #8b97b2: 5.69:1 contra panel #1a1d2e y 4.35:1 contra campo #2b3246.
   Texto de campo #f8fafc: 12.18:1. Placeholder #c0cadc: 7.72:1.
   Las pruebas usan los colores calculados del navegador y umbrales sin redondear.
4. Boton primario de 50px con texto de 16px; fondo mas oscuro para mantener
   contraste de texto. Control de visibilidad de 48x48px con etiqueta accesible.
5. Mensaje de error generico para credenciales incorrectas, errores por campo
   para valores ausentes, foco accesible y usuario conservado. Contrasena no
   devuelta por el servidor ni almacenada en JS/localStorage.
6. La contrasena mostrada usa spellcheck=false y autocapitalize=none. Se oculta
   al enviar y al volver mediante bfcache. No se bloquea pegar ni se agrega
   maxlength a la contrasena. No se cambia su valor al mostrar/ocultar.

## Pruebas y limites

- 45 tests correctos con PostgreSQL nuevo en RAM, incluyendo autenticacion,
  redirecciones, CSRF, XSS, borrado, permisos y evidencias pendientes.
- Navegador Chromium: dos estados de formulario en 1440x1000, 390x844 y 320x568.
  Contraste de bordes contra ambos fondos, texto y placeholder, labels y
  tamano/agrupacion de campos y contraste del boton se comprueban automaticamente.
- Se probo la plantilla anterior contra las mismas comprobaciones: falla por
  contraste en los tres tamanos; el fallo no se sustituyo por una suposicion.
- Capturas reales del tunel para formulario vacio y error. En pantallas cortas
  se permite scroll vertical normal, sin cortar el acceso al resto del formulario.
- Sin comprobacion en telefonos fisicos, Safari/Firefox, lectores de pantalla
  reales o gestores externos de contrasenas. Los atributos de compatibilidad
  comprobados no equivalen a validar todos esos productos.
- El login publicado en PROD permanece sin cambios. La demo no autentica ni
  envia credenciales. No se incorporan recuperacion de cuenta, SSO o registro.
