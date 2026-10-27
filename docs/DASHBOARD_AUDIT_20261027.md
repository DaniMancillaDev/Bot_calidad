# Auditoria y rediseño del Dashboard IQA

Fecha: 2026-10-27 UTC. Entorno: DEV, rama `feature/whatsapp-evidencias`.
Produccion no fue modificada, no hubo despliegue ni commit.

## Diagnostico

La vista `web/calidad/views.py:dashboard` ya entrega datos reales y filtrados
por permisos: total de registros, actividad del periodo, defectos frecuentes,
registros por linea y los diez registros recientes. El problema estaba en la
presentacion: el encabezado no explicaba el contexto operativo, los filtros
estaban separados del contenido, las tarjetas tenian la misma jerarquia y las
acciones principales quedaban escondidas en la navegacion superior.

No se agregaron metricas de pendientes, porcentajes de calidad ni tendencias
porque no existen en el contexto actual y no se deben inventar.

## Direccion ui-ux-pro-max

Se ejecuto la busqueda de sistema para `internal quality operations dashboard`
con densidad alta, movimiento bajo y variacion moderada. Tambien se consulto
la guia UX de jerarquia KPI y alertas. Se aplicaron las recomendaciones utiles
al stack real: jerarquia de encabezados, escala tipografica consistente,
acciones visibles, contraste, estados vacios, navegacion por teclado y
reduced-motion.

El resultado conserva el tema oscuro existente y usa una estetica SaaS
operativa: superficies oscuras, borde sutil, acento indigo semantico, poca
decoracion y densidad informativa controlada. No se introdujeron React,
Tailwind, graficas nuevas ni dependencias.

## Cambios

Archivo principal: `web/templates/calidad/dashboard.html`.

- Cabecera con titulo, descripcion y contexto de permisos.
- Barra de periodo con `aria-current` para el filtro activo.
- KPIs separados por nombre, valor, periodo y nota contextual.
- Registros por linea como barras comparativas con etiqueta accesible.
- Tipos de defecto como lista ordenada y legible.
- Acciones rapidas reales: panel operativo, reportes y galeria.
- Tabla reciente con encabezados, enlaces y overflow horizontal controlado.
- Estados vacios explicativos.
- Breakpoints para 1024, 760 y 480 px.
- Reduced-motion sin transiciones perceptibles.

No cambiaron URLs, consultas ORM, permisos, definiciones de indicadores ni
integraciones de Telegram, WhatsApp, Redis o Celery.

## Validacion

- Compilacion real de la plantilla con Django: correcta.
- `git diff --check`: correcto.
- Preview aislado con datos sinteticos, sin base productiva: correcto.
- Capturas verificadas a 1440x900 y 390x844.
- Los valores de la preview son demostrativos y no representan produccion.
- La suite aislada existente de 51 pruebas se ejecuto durante esta serie de
  cambios y termino correctamente; no modifica datos productivos.

Pendiente: una prueba con una cuenta real de DEV para validar el contenido
segun cada permiso y una comprobacion con datos productivos no es parte de
esta ejecucion. La tabla movil usa desplazamiento horizontal porque conserva
las ocho columnas y su informacion completa.
