# Auditoría de Contratos y Protocols (Fase 6B.4)

## Resumen Ejecutivo

Esta auditoría revisa específicamente los Protocols (interfaces abstractas) definidos en `shared/domain/interfaces.py` para determinar cuáles contratos tienen adherencia real en el código productivo a través de inyección de dependencias, type hints o herencia.

**Conclusión Principal**: El 85% del archivo `interfaces.py` es código huérfano. La capa de repositorios (`DjangoUsuarioRepository`, `RedisConversationState`, etc.) no implementa explícitamente estos protocolos, ni estos protocolos son requeridos como *type hints* por los servicios (`DefectoWorkflow` hace type hinting implícito por *duck typing*, sin requerir importar el Protocol).

El único Protocol con adherencia real y uso de herencia es `IDefectTranslator`.

---

## Inventario de Contratos

| Contrato | Referencias | Uso real | Acción |
|----------|-------------|----------|--------|
| `UsuarioRepository` | `__init__.py`, docstrings, `ARQUITECTURA_REFACTORIZACION.md` | Ninguno (Sin type hints, sin `isinstance`, sin herencia) | 🟢 eliminar seguro |
| `RegistroRepository` | `__init__.py`, docstrings, `ARQUITECTURA_REFACTORIZACION.md` | Ninguno (Sin type hints, sin `isinstance`, sin herencia) | 🟢 eliminar seguro |
| `ContadorRepository` | `__init__.py`, docstrings, `ARQUITECTURA_REFACTORIZACION.md` | Ninguno (Sin type hints, sin `isinstance`, sin herencia) | 🟢 eliminar seguro |
| `ConversationStateRepository` | `__init__.py`, docstrings (`redis_conversation_state.py`) | Ninguno (Sin type hints, sin `isinstance`, sin herencia) | 🟢 eliminar seguro |
| `OrientationDetector` | `__init__.py` | Ninguno (El wrapper fue eliminado previamente) | 🟢 eliminar seguro |
| `FotoStorage` (Antiguo) | `__init__.py`, `ARQUITECTURA_REFACTORIZACION.md` | Ninguno. El protocolo real está redefinido en `shared/infrastructure/storage/foto_storage.py` y se usa desde allí. | 🟢 eliminar seguro |
| `IDefectTranslator` | `defect_translator.py` (Herencia y Factory), `reporte_excel.py` (Type hint) | **Activo** (Usa herencia `class OllamaDefectTranslator(IDefectTranslator):` y se inyecta tipado en el Excel). | 🟡 mover/refactor futuro |

---

## Análisis de Carga Dinámica e Imports

La búsqueda `grep -rn "from shared.domain.interfaces"` confirmó que solo hay dos consumidores de este módulo en todo el proyecto:
1. `shared/domain/__init__.py`: Importa todo para exponerlo en el paquete (pero nadie consume ese paquete).
2. `shared/infrastructure/ai/defect_translator.py`: Importa `IDefectTranslator` y `DefectTranslation`.

No hay ninguna carga dinámica, ni uso de `getattr()` en el inyector de dependencias (`dependencies.py`).

## Recomendación Siguiente Paso

Podemos proceder a la destrucción de los 6 contratos zombis.
Respecto a `IDefectTranslator`, al ser el único sobreviviente, carece de sentido mantener la carpeta `shared/domain/` entera solo para él.

**El plan sugerido para la siguiente fase es:**
1. Mover `IDefectTranslator` (y el TypedDict `DefectTranslation`) a `shared/infrastructure/ai/interfaces.py`.
2. Actualizar las 2 referencias de importación de `defect_translator.py` y `reporte_excel.py`.
3. Eliminar la carpeta `shared/domain/` por completo, extirpando así los vestigios finales de la vieja arquitectura.
