# Estado actual (Fase 7 - Auditoría Post-Refactor)

Tras la eliminación de la arquitectura obsoleta, se ha realizado una auditoría exhaustiva del sistema utilizando herramientas de análisis estático (`vulture`, `flake8`, `radon`) y validaciones dinámicas (suites de testing).

A continuación se presenta el mapa final de deuda técnica y el estado de salud del código.

## Código muerto encontrado

El análisis de código huérfano con `vulture` y `flake8` reveló una base de código notablemente limpia, siendo la mayoría de los hallazgos falsos positivos de Django (modelos, migraciones, settings).

| Archivo | Elemento detectado | Clasificación | Motivo |
|---------|--------------------|---------------|--------|
| `web/calidad/services/reporte_excel.py` | Import no utilizado: `detect_orientations_batch` | 🟢 Eliminar seguro | Import olvidado tras refactorizaciones de orientación. |
| `web/calidad/tasks.py` | Método no utilizado: `generar_thumbnail_task` | 🟢 Eliminar seguro | Tarea huérfana. |
| `web/calidad/tests.py` | Variable `mock_workflow` (múltiples) | 🟢 Eliminar seguro | Variables de asignación en mocks no leídas por asserts. |
| `web/calidad/models.py` | Atributos de Django (C01, Meta, etc) | 🔴 Mantener | Falso positivo (Django ORM). |
| `web/config/settings.py` | Configuraciones (SECRET_KEY, etc) | 🔴 Mantener | Falso positivo (Django Settings). |
| `web/workspace/migrations/*` | Variables de migración | 🔴 Mantener | Falso positivo (Django Migrations). |

*Nota: `flake8` reportó cero (0) imports no utilizados y cero redefiniciones en todo el repositorio (aparte del detectado por vulture que puede ser un import condicional o en un scope interno).*

## Complejidad

El análisis ciclomático con `radon` (Clasificaciones C y D) revela los principales cuellos de botella lógicos del sistema. Estos son los puntos que concentran mayor deuda técnica por complejidad:

| Archivo | Bloque | Complejidad | Nivel | Acción recomendada |
|---------|--------|-------------|-------|--------------------|
| `web/workspace/services/processing.py` | `process_upload_logic` | 22 | 🔴 D | Refactorizar/dividir lógica de procesamiento de subidas. |
| `web/calidad/management/commands/limpiar_temporales.py` | `Command.handle` / `Command` | 20 / 19 | 🔴 C | Simplificar el comando de limpieza. |
| `web/calidad/application/workflows/defecto_workflow.py` | `_avanzar_siguiente_campo_vacio` | 13 | 🟡 C | Evaluar simplificación de máquina de estado subyacente. |
| `web/calidad/application/workflows/defecto_workflow.py` | `_intentar_extraccion_ia` | 12 | 🟡 C | Dividir la lógica de orquestación de la IA. |
| `web/workspace/services/confirmation.py` | `confirm_import` | 11 | 🟡 C | Extraer validaciones. |
| `web/calidad/management/commands/sync_evidencias.py` | `Command.handle` | 11 | 🟡 C | Modularizar el script de sincronización. |

## Riesgos

| Riesgo | Descripción | Nivel |
|--------|-------------|-------|
| **Infraestructura de Tests Concurrentes** | Los tests en `tests_concurrency.py` validan correctamente la funcionalidad, pero el proceso falla violentamente en la fase de `teardown` (`django.db.utils.OperationalError: database "test_bot_calidad" is being accessed by other users`). | 🟡 Medio |
| **Persistencia de comportamientos Legacy** | Existen múltiples comprobaciones y bifurcaciones de código que tratan de reconciliar `fotos` (legacy, strings crudos) con `fotos_nums` (modelo ArrayField nuevo). La duplicidad sigue inserta en las vistas y el serializador. | 🟡 Medio |

## Próximas fases recomendadas

El sistema ha sido exitosamente depurado a nivel arquitectónico. Los próximos pasos deben enfocarse en la consolidación funcional y la reducción de complejidad lógica:

1. **Limpieza Quirúrgica Final (Código Muerto Menor)**: Eliminar el import `detect_orientations_batch` y la función `generar_thumbnail_task`.
2. **Solucionar el Teardown Concurrente**: Reparar la infraestructura de test de concurrencia para que cierre correctamente las conexiones a DB en lugar de dejar bloqueos transaccionales.
3. **Refactorización de `process_upload_logic`**: Desacoplar la lógica del bloque de complejidad ciclomática 22 (Clase D), para hacer el sistema de importación más robusto.
4. **Erradicación del Legacy Parser**: Una vez validado y estabilizado el nuevo parser `photo_parser.py`, eliminar por completo las bifurcaciones y scripts relacionados con `legacy_sync`.
