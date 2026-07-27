# Auditoría Arquitectónica - Fase 6A (Interfaces y Repositorios)

## Resumen Ejecutivo

Esta auditoría evaluó los contratos arquitectónicos definidos en `shared/domain/interfaces.py` y las implementaciones de repositorios dentro de `shared/infrastructure/`. Se utilizó un análisis cruzado empleando herramientas estáticas (`vulture`), búsquedas manuales globales y validación de carga dinámica.

**Conclusión Principal**: Existe una cantidad significativa de código "zombi" arquitectónico. Varias interfaces y sus implementaciones bajo `infrastructure/database` fueron diseñadas en un intento previo de refactorización hacia DIP (Dependency Inversion Principle) que quedó abandonado en el plan (documentado en `ARQUITECTURA_REFACTORIZACION.md`), pero **nunca llegaron a integrarse en el código productivo**.

Por otro lado, otros contratos (`IDefectTranslator` y el nuevo `FotoStorage`) sí forman parte de la arquitectura actual y se encuentran inyectados en la lógica productiva.

No se detectaron mecanismos de carga dinámica para repositorios que ocultaran dependencias a los analizadores estáticos.

---

## Interfaces Analizadas

| Interface | Implementaciones | Referencias (Además de sí misma) | Uso Real en Producción | Decisión |
|-----------|------------------|----------------------------------|------------------------|----------|
| `UsuarioRepository` | `DjangoUsuarioRepository` | `ARQUITECTURA_REFACTORIZACION.md` | Ninguno. Totalmente aislado. | 🟢 ELIMINAR SEGURO |
| `RegistroRepository` | `DjangoRegistroRepository` | `ARQUITECTURA_REFACTORIZACION.md` | Ninguno. Totalmente aislado. | 🟢 ELIMINAR SEGURO |
| `ContadorRepository` | `DjangoContadorRepository` | `ARQUITECTURA_REFACTORIZACION.md` | Ninguno. (Se usa el nuevo `GlobalCounter`). | 🟢 ELIMINAR SEGURO |
| `ConversationStateRepository` | `RedisConversationState` | N/A | Ninguno. `RedisConversationState` no está en uso. | 🟢 ELIMINAR SEGURO |
| `FotoStorage` (Antiguo) | `LocalFotoStorage` (`local_foto_storage.py`) | N/A | Ninguno. Fue reemplazado por la versión nueva. | 🟢 ELIMINAR SEGURO |
| `OrientationDetector` | `OnnxOrientationDetector` | N/A | Ninguno. El código invoca a `detect_orientation` de `orientation_engine.py` directamente. | 🟢 ELIMINAR SEGURO |
| `IDefectTranslator` | `OllamaDefectTranslator`, `NullDefectTranslator` | `reporte_excel.py`, `defect_translator.py` | Activo (Inyectado en servicio de Excel). | 🟡 MANTENER |
| `FotoStorage` (Nuevo) | `LocalFotoStorage` (`foto_storage.py`) | `defecto_workflow.py`, `dependencies.py` | Activo (Manejo de media inyectado). | 🟡 MANTENER |

---

## Repositorios Analizados (`shared/infrastructure/`)

| Clase | Archivo | Referencias | Parte de Contrato | Decisión |
|-------|---------|-------------|-------------------|----------|
| `DjangoUsuarioRepository` | `database/django_usuario_repository.py` | Ninguna | `UsuarioRepository` (Muerto) | 🟢 ELIMINAR SEGURO |
| `DjangoRegistroRepository`| `database/django_registro_repository.py` | Ninguna | `RegistroRepository` (Muerto) | 🟢 ELIMINAR SEGURO |
| `DjangoContadorRepository`| `database/django_contador_repository.py` | Ninguna | `ContadorRepository` (Muerto) | 🟢 ELIMINAR SEGURO |
| `LocalFotoStorage` (Legacy) | `storage/local_foto_storage.py` | Ninguna | `FotoStorage` (Legacy) | 🟢 ELIMINAR SEGURO |
| `RedisConversationState` | `web/calidad/services/redis_conversation_state.py` | Ninguna | `ConversationStateRepository` (Muerto)| 🟢 ELIMINAR SEGURO |
| `OnnxOrientationDetector` | `orientation/onnx_orientation_detector.py`| Ninguna | `OrientationDetector` (Muerto) | 🟢 ELIMINAR SEGURO |
| `LocalFotoStorage` (Nuevo) | `storage/foto_storage.py` | `defecto_workflow.py`, `dependencies.py` | `FotoStorage` (Nuevo) | 🟡 MANTENER |
| `OllamaDefectTranslator` | `ai/defect_translator.py` | Factory local (`build_translator`) | `IDefectTranslator` (Vivo) | 🟡 MANTENER |

---

## Código Candidato a Eliminación (🟢)

1. **`shared/domain/interfaces.py`**: A excepción de `IDefectTranslator` (que convendría mover junto a la IA) y las nuevas interfaces de Storage, todo el archivo contiene interfaces de un plan obsoleto.
2. **Carpeta `shared/infrastructure/database/` completa**: Todo su contenido son adaptadores Django muertos sin clientes.
3. **`shared/infrastructure/storage/local_foto_storage.py`**: Abstracción redundante. La oficial viva es `foto_storage.py`.
4. **`shared/infrastructure/orientation/onnx_orientation_detector.py`**: Wrapper inútil.
5. **`web/calidad/services/redis_conversation_state.py`**: No se llegó a integrar.

## Código Protegido por Arquitectura (🟡)

1. **`shared/infrastructure/storage/foto_storage.py`**: Protocol e implementación en uso (DIP).
2. **`shared/infrastructure/ai/defect_translator.py`**: Protocol e implementación en uso (DIP).
3. **`shared/infrastructure/orientation/orientation_engine.py`**: Funciones activas utilizadas por `reporte_excel.py`. No usa abstracción pero tiene clientes.

---

## Recomendaciones (Siguiente Paso)

**Proceder a la Fase 6B (Eliminación Segura de Arquitectura Abandonada):**
Dado que no existe carga dinámica (`importlib` en estos contextos no existe) y el análisis ha confirmado la total desconexión de estos archivos de `main_sqlite.py`, `views.py`, y `urls.py`, se sugiere una ronda destructiva segura:

- `rm -rf shared/infrastructure/database/`
- Borrado selectivo en `interfaces.py` (moviendo los vivos a sus módulos de dominio o infraestructura correspondientes si se desea vaciar el archivo).
- Eliminación de archivos redundantes documentados arriba.
