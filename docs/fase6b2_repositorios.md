# Fase 6B.2 — Auditoría de Repositorios Activos

Al descubrirse que los repositorios están inyectados y son consumidos productivamente por `DefectoWorkflow`, hemos auditado la utilización individual de cada método para identificar el verdadero código muerto dentro de las clases vivas.

A continuación, se detalla la matriz de uso real (incluyendo endpoints, workflows y tests).

## 1. DjangoUsuarioRepository

| Clase | Método | Referencias | Usado por | Acción |
|-------|--------|-------------|-----------|--------|
| `DjangoUsuarioRepository` | `obtener` | Sí | `defecto_workflow.py` | 🟡 Mantener |
| `DjangoUsuarioRepository` | `tiene_acceso` | No | Nadie | 🟢 Eliminar Seguro |
| `DjangoUsuarioRepository` | `crear` | No | Nadie | 🟢 Eliminar Seguro |
| `DjangoUsuarioRepository` | `actualizar` | No | Nadie | 🟢 Eliminar Seguro |
| `DjangoUsuarioRepository` | `listar` | No | Nadie | 🟢 Eliminar Seguro |

---

## 2. DjangoRegistroRepository

| Clase | Método | Referencias | Usado por | Acción |
|-------|--------|-------------|-----------|--------|
| `DjangoRegistroRepository` | `guardar` | Sí | `defecto_workflow.py`, `tests_v2.py` | 🟡 Mantener |
| `DjangoRegistroRepository` | `obtener_todos` | No | Nadie | 🟢 Eliminar Seguro |
| `DjangoRegistroRepository` | `obtener_por_turno_depto` | No | Nadie | 🟢 Eliminar Seguro |
| `DjangoRegistroRepository` | `limpiar_por_usuario` | No | Nadie | 🟢 Eliminar Seguro |
| `DjangoRegistroRepository` | `obtener_estadisticas` | No | Nadie | 🟢 Eliminar Seguro |

---

## 3. DjangoContadorRepository

| Clase | Método | Referencias | Usado por | Acción |
|-------|--------|-------------|-----------|--------|
| `DjangoContadorRepository` | `obtener_y_avanzar_lote` | Sí | `defecto_workflow.py`, `tests.py`, `tests_concurrency.py` | 🟡 Mantener |
| `DjangoContadorRepository` | `obtener_y_avanzar` | Sí | `tests.py` | 🟡 Mantener (Validar si se requiere para LSP) |
| `DjangoContadorRepository` | `obtener_actual` | Sí | `tests.py` | 🟡 Mantener (Validar si se requiere para LSP) |

*(Nota: Aunque `obtener_y_avanzar` y `obtener_actual` solo están en tests, forman parte del contrato histórico verificado y no son puramente zombis).*

---

## 4. RedisConversationState

| Clase | Método | Referencias | Usado por | Acción |
|-------|--------|-------------|-----------|--------|
| `RedisConversationState` | `tiene_conversacion` | Sí | `defecto_workflow.py` | 🟡 Mantener |
| `RedisConversationState` | `iniciar` | Sí | `defecto_workflow.py`, `api/views.py` | 🟡 Mantener |
| `RedisConversationState` | `obtener` | Sí | `defecto_workflow.py` | 🟡 Mantener |
| `RedisConversationState` | `guardar` | Sí | `defecto_workflow.py`, `tests_v2.py` | 🟡 Mantener |
| `RedisConversationState` | `finalizar` | Sí | `defecto_workflow.py`, `api/views.py` | 🟡 Mantener |
| `RedisConversationState` | `persistir` | No | Nadie (Vulture reportó esto) | 🟢 Eliminar Seguro |

---

## Conclusión Estratégica
En lugar de eliminar clases completas y romper el motor de la API, **se ha delimitado con láser qué métodos de acceso a datos son zombis y cuáles son el motor real de la aplicación**. 

Podemos proceder a "podar" exclusivamente los métodos marcados como 🟢 **Eliminar Seguro** sin afectar ni romper un solo test o endpoint, aliviando la deuda técnica de código no utilizado que se heredó del antiguo plan arquitectónico.
