# Consolidación del catálogo de defectos — 2026-10-19

## Fuentes comparadas

Se compararon por SHA-256 y por entrada:

- `source/web-image/app/shared/infrastructure/ai/defect_catalog.json`.
- `source/celery-image/app/shared/infrastructure/ai/defect_catalog.json`.
- `source/bot-image/app/shared/infrastructure/ai/defect_catalog.json`.
- `shared/infrastructure/ai/defect_catalog.json` de esta rama.

El catálogo consolidado coincide exactamente con el catálogo web recuperado. El catálogo Celery también coincide salvo la entrada `bracket`; el catálogo bot es anterior y no contiene varias traducciones añadidas posteriormente.

Hashes SHA-256 de los archivos comparados:

```text
web/runtime y consolidado: dbfe510653ed728e239c431c96e78f32189dc724911723692f28a7f29afd3614
celery/runtime:           02e848f13faee1bcd35efeb175a3a5a60ee482eb32a457d43fe252de5b4291b7
bot/runtime:              68083b45582346d7a6a0406890283b167d778c620445617503a27f0c02157c25
```

## Conteo por sección

| Sección | Web | Celery | Bot | Consolidado |
|---|---:|---:|---:|---:|
| `areas` | 9 | 9 | 9 | 9 |
| `exact_matches` | 11 | 11 | 8 | 11 |
| `components` | 62 | 61 | 60 | 62 |
| `material_areas` | 23 | 22 | 19 | 23 |
| `symptoms` | 22 | 22 | 20 | 22 |
| `connectors` | 7 | 7 | 7 | 7 |

## Diferencias observadas

El catálogo web añade al bot:

- `sheet flyer dañado` y `sheet flyer danado` → `DAMAGED SHEET FLYER`.
- `blu mal retrabajado` → `METAL BLU WITH BAD REWORK`.
- `sheet flyer` → `SHEET FLYER`.
- `bracket` → `BKT`.
- Las áreas de `SHEET FLYER`, `DAMAGED SHEET FLYER`, `METAL BLU WITH BAD REWORK` y `bracket`.
- Los síntomas `mal retrabajad` y `mal retrabajo`.

No se detectaron cambios de valor para las claves compartidas. Por tanto, la consolidación es aditiva: conserva las claves históricas del bot y agrega traducciones del runtime web. No se renombraron ni eliminaron identificadores.

## Decisión

Se conserva el catálogo web/consolidado como referencia para web y Celery. El bot debe adoptar el mismo archivo al reconstruirse desde esta rama; antes de desplegarlo se debe validar con ejemplos reales de Telegram que las nuevas traducciones no cambien reportes históricos.

La comparación automatizada queda protegida por [`shared/utils/tests/test_defect_catalog.py`](../shared/utils/tests/test_defect_catalog.py).
