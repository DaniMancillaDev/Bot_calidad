# Golden Paths — Bot de Calidad v3.1

Este documento congela el comportamiento esperado del sistema.
Cualquier cambio durante la refactorización DEBE producir los mismos outputs.

---

## GOLDEN PATH 1: Registro de defecto completo (Bot Telegram)

### Flujo
1. Usuario envía foto al bot
2. Bot responde confirmación con número de secuencia
3. Usuario envía más fotos (opcional)
4. Usuario escribe "TERMINAR"
5. Bot solicita: modelo → línea → cantidad → responsable → descripción
6. Bot guarda registro en DB y responde confirmación

### Input: Foto enviada por usuario registrado (user_id=123456, turno=A, depto=IQA)
- Telegram photo message

### Output esperado (respuesta del bot):
```
✅ Foto {contador:03d} recibida.
📁 Guardada en: fotos/{user_id}/
📸 Puedes enviar más fotos o escribir 'TERMINAR' cuando termines.
```

### Input: "TERMINAR" (con al menos 1 foto)
### Output:
```
✅ Fotos recibidas. Ahora vamos a registrar los detalles.

📝 Por favor, ingresa el Modelo del producto (ejemplo: ONN 32" 100012589 AUO):
```

### Input: Datos del defecto (5 pasos)
- Modelo: "ONN 32\" 100012589 AUO"
- Línea: "T03"
- Cantidad: "5"
- Responsable: "XM"
- Descripción: "MANCHA EN PANTALLA"

### Output final (confirmación):
```
✅ Registro guardado:
({inicio:03}-{fin:03}) Modelo: ONN 32" 100012589 AUO; Línea: T03; Cantidad: 5; Responsable: XM; Descripción: MANCHA EN PANTALLA

👤 Usuario: {user_id}
🕐 Turno: A | Depto: IQA

📸 Puedes enviar más fotos para un nuevo registro.
```

### Estado en DB después (tabla `registros_defectos`):
| Campo | Valor esperado |
|-------|---------------|
| fotos | "(001-003)" o formato rango |
| modelo | "ONN 32\" 100012589 AUO" |
| linea | "T03" |
| cantidad | 5 |
| responsable | "XM" |
| descripcion | "MANCHA EN PANTALLA" |
| user_id | 123456 |
| turno | "A" |
| departamento | "IQA" |

### Estado en filesystem después:
- Archivo creado: `fotos/{user_id}/{contador:03d}_{timestamp}.png`
- Contador avanzado en `contadores_grupo` para (turno=A, depto=IQA)

### Estado en conversaciones después:
- Conversación eliminada (finalizar_conversacion)
- `estado_conversaciones.json` sin entrada para ese user_id

---

## GOLDEN PATH 2: Generación de reporte Excel (Web Django)

### Flujo
1. Usuario se loguea en el panel web
2. Navega a /reportes/
3. Filtra por fecha/línea/responsable (opcional)
4. Click "Revisar Orientación"
5. Sistema detecta orientación de fotos vía ONNX (AJAX)
6. Usuario corrige rotaciones si es necesario
7. Click "Generar Excel"
8. Sistema genera .xlsx con fotos embebidas (o .zip si hay múltiples proveedores)

### Input: POST a /generar-excel/ con JSON:
```json
{
  "rotaciones": {"123456_1": 0, "123456_2": 90, "123456_3": 180},
  "registros": [
    {
      "id": 1,
      "user_id": 123456,
      "fotos_nums": [1, 2, 3],
      "fotos_str": "(001-003)",
      "modelo": "ONN 32\" 100012589 AUO",
      "linea": "T03",
      "descripcion": "MANCHA EN PANTALLA",
      "responsable": "XM",
      "cantidad": 5
    }
  ]
}
```

### Output esperado:
- **1 proveedor**: archivo `.xlsx` con Content-Type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **2+ proveedores**: archivo `.zip` con un `.xlsx` por proveedor
- Cada Excel tiene:
  - Fila de datos por registro (columnas B,C,F,I,L,N para fecha,modelo,línea,descripción,cantidad,responsable)
  - Fotos en tira horizontal desde columna P, rotadas según `rotaciones`
  - Usa plantilla `plantilla_reporte.xlsx` como base

### Alias de proveedores (hardcodeado actualmente):
```python
ALIAS = {'WH': 'TSCEM'}
```
- Si responsable="WH", el archivo se nombra `reporte_TSCEM_*.xlsx`

---

## GOLDEN PATH 3: Autenticación y permisos (Bot + Web)

### 3A. Bot — Verificación de acceso

### Input: Mensaje de usuario NO registrado (user_id no está en `usuarios_bot`)
### Output:
```
⛔️ ACCESO DENEGADO ⛔️

No tienes permisos para usar este bot.
Escribe /mi_id para obtener tu identificador y registrarte.
```
- Se levanta `ApplicationHandlerStop` (no se ejecutan más handlers)

### Input: Usuario registrado envía /mi_id
### Output:
```
🤖 Tu ID de Telegram es: {user_id}

Copia y pásale este número al Administrador del sistema para que te dé de alta.
```

### 3B. Web — Permisos por turno/departamento

### Input: Usuario normal (no admin) con perfil turno=B, depto=SQA
### Comportamiento:
- Dashboard: solo ve estadísticas de registros con turno=B AND departamento=SQA
- Reportes: solo ve registros de su turno/depto
- Galería: solo ve fotos de usuarios con mismo turno/depto
- Excel: solo genera con registros permitidos

### Input: Superuser
### Comportamiento:
- Ve TODOS los registros sin filtro
- Ve TODAS las fotos
- Puede filtrar por turno y departamento adicionalmente

### 3C. Sincronización Django → Bot
### Input: Se crea/edita PerfilUsuario con telegram_user_id=123456, turno=A, depto=IQA
### Output automático (signal `post_save`):
- Se crea/actualiza registro en `usuarios_bot` con mismo telegram_user_id, turno, departamento
- El bot inmediatamente reconoce al usuario como registrado

---

## OUTPUTS CRÍTICOS QUE NO DEBEN CAMBIAR

| # | Output | Formato | Dónde se valida |
|---|--------|---------|----------------|
| 1 | Formato de rango de fotos | `({inicio:03}-{fin:03})` | `database.py:_formatear_rango_fotos` |
| 2 | Nombre de archivo de foto | `{contador:03d}_{YYYYMMDD_HHMMSS}.png` | `main_sqlite.py:321` |
| 3 | Estructura del Excel | Plantilla + datos en columnas fijas + fotos en P | `reporte_excel.py` |
| 4 | Mensajes del bot | Texto exacto con emojis | `main_sqlite.py` (cada handler) |
| 5 | Estructura DB | Tablas: `registros_defectos`, `usuarios_bot`, `contadores_grupo`, `contadores_usuario`, `calidad_perfilusuario` | `database.py:init_database` |
| 6 | Respuesta ZIP del bot | Lotes de 30 imágenes máximo | `main_sqlite.py:605` |
| 7 | Respuesta Excel web | 1 xlsx o 1 zip con múltiples xlsx | `views.py:generar_excel` |
| 8 | Contadores atómicos | `BEGIN EXCLUSIVE` + increment | `database.py:403` |

---

## COMANDOS DE VALIDACIÓN RÁPIDA

### Verificar que el bot arranca:
```bash
cd c:\Users\Dani Mancilla\Downloads\bot_calidad-Nueva-version-3.1
python -c "from database import db; print('DB OK:', db.obtener_contador_usuario(1))"
```

### Verificar que la web arranca:
```bash
cd c:\Users\Dani Mancilla\Downloads\bot_calidad-Nueva-version-3.1\web
python manage.py check
```

### Verificar estructura de DB:
```bash
python -c "import sqlite3; conn=sqlite3.connect('bot_calidad.db'); cursor=conn.cursor(); cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\"); print('Tablas:', [r[0] for r in cursor.fetchall()])"
```

### Verificar imports del bot:
```bash
python -c "from main_sqlite import main; print('Bot imports OK')"
```
