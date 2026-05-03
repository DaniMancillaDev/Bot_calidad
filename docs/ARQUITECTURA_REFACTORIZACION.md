# Arquitectura y Refactorización — Bot de Calidad v3.1

---

## 1. DIAGNÓSTICO DEL ESTADO ACTUAL

### 1.1 Estructura Actual

```
bot_calidad-Nueva-version-3.1/
├── main_sqlite.py          ← 867 líneas: BOT COMPLETO (handlers + state + config + auth)
├── database.py             ← 508 líneas: DBManager + instancia global `db`
├── run_bot.py              ← wrapper de desarrollo
├── run_web.bat / .sh       ← scripts de inicio
├── .env                    ← TELEGRAM_TOKEN (gitignored)
├── requirements.txt        ← dependencias (django duplicado)
├── bot_calidad.db          ← SQLite compartida
├── fotos/                  ← almacenamiento de imágenes
├── defectos/               ← datos legacy
├── plantilla_reporte.xlsx  ← template Excel
├── estado_conversaciones.json  ← estado persistido en JSON plano
├── src/                    ← MÓDULO VACÍO (solo __init__.py y helpers.py)
│   ├── config/__init__.py
│   ├── handlers/__init__.py
│   ├── models/__init__.py
│   └── utils/helpers.py    ← funciones duplicadas con database.py
└── web/                    ← Django (panel web)
    ├── config/             ← settings, urls, wsgi
    ├── calidad/
    │   ├── views.py        ← 601 líneas: TODAS las vistas + lógica de negocio
    │   ├── models.py       ← Django ORM + signals
    │   ├── admin.py        ← admin personalizado
    │   ├── urls.py
    │   └── services/reporte_excel.py  ← 335 líneas: ONNX + Excel
    └── templates/calidad/  ← 7 templates HTML
```

### 1.2 Problemas Detectados

| # | Problema | Dónde | Severidad |
|---|----------|-------|-----------|
| 1 | **Monolito de 867 líneas** | `main_sqlite.py` | 🔴 Crítico |
| 2 | **Instancia global mutable** `db = DatabaseManager()` | `database.py:507` | 🔴 Crítico |
| 3 | **Estado en JSON plano** (race conditions) | `estado_conversaciones.json` | 🔴 Crítico |
| 4 | **Código duplicado**: `_formatear_rango_fotos` vs `agrupar_secuencias` | `database.py` vs `helpers.py` | 🟡 Alto |
| 5 | **Violación SRP**: `views.py` hace todo (auth, parsing, Excel, ZIP) | `web/calidad/views.py` | 🟡 Alto |
| 6 | **Violación OCP**: `generar_excel()` con ALIAS hardcodeados | `views.py:503` | 🟡 Alto |
| 7 | **Violación DIP**: handlers importan `db` directamente (acoplamiento) | `main_sqlite.py:28` | 🟡 Alto |
| 8 | **`src/` es un módulo fantasma**: existe pero no se usa | `src/` | 🟠 Medio |
| 9 | **Legacy methods vacíos** que confunden | `database.py:435-472` | 🟠 Medio |
| 10 | **`requirements.txt` duplicado** (django 2 veces) | `requirements.txt:15,23` | 🟢 Bajo |
| 11 | **SECRET_KEY hardcodeada** en settings | `web/config/settings.py:11` | 🔴 Crítico |
| 12 | **Sin logging estructurado**: solo `print()` por todas partes | Todo el proyecto | 🟡 Alto |
| 13 | **Sin manejo de errores centralizado** | Todo el proyecto | 🟡 Alto |
| 14 | **Contadores con race condition potencial** | `database.py:394-421` | 🟡 Alto |

### 1.3 Detalle de Violaciones SOLID

**S — Single Responsibility Principle**
- `main_sqlite.py`: maneja autenticación, estado de conversación, procesamiento de fotos, generación de reportes, descarga ZIP, y configuración del bot. **7 responsabilidades en 1 archivo.**
- `views.py`: autenticación/permisos, parsing de fotos, generación Excel, manejo de ZIP, API de orientación. **5 responsabilidades en 1 archivo.**
- `DatabaseManager`: maneja usuarios, registros, contadores, estadísticas, y formateo de datos. **5 responsabilidades en 1 clase.**

**O — Open/Closed Principle**
- ALIAS de proveedores hardcodeados en `views.py:503`: `ALIAS = {'WH': 'TSCEM'}`. Para agregar un alias hay que modificar el código fuente.
- Estados de conversación como constantes sueltas: para agregar un nuevo paso hay que modificar el switch gigante de `procesar_respuesta()`.

**L — Liskov Substitution Principle**
- `actualizar_contador_usuario()` es un método vacío (`pass`). Los callers esperan comportamiento que no existe. Violación LSP.

**I — Interface Segregation Principle**
- `DatabaseManager` expone una interfaz monolítica de ~25 métodos. Un handler de fotos no necesita `limpiar_registros()` ni `listar_usuarios()`, pero importa toda la clase.

**D — Dependency Inversion Principle**
- Los handlers de Telegram dependen directamente de la instancia concreta `db` (import global). No hay abstracción/inversión.
- `views.py` importa directamente el servicio de Excel. No hay interfaz que permita testing o swap.

---

## 2. PROPUESTA DE NUEVA ARQUITECTURA

### 2.1 Enfoque: Clean Architecture (Justificación)

Se elige **Clean Architecture** sobre Hexagonal porque:
- El dominio es simple (registros de defectos, usuarios, fotos) — no requiere la complejidad de puertos/adaptadores hexagonales.
- Clean Architecture permite una migración más gradual: se pueden mover capas una por una sin romper nada.
- La separación por capas (domain → application → infrastructure → interfaces) es más natural para un sistema que ya tiene 2 interfaces (Telegram + Django).

### 2.2 Nuevo Árbol de Carpetas

```
bot_calidad/
├── .env                          # Variables de entorno (gitignored)
├── .gitignore
├── pyproject.toml                # Configuración del proyecto
├── requirements.txt              # Dependencias limpias
├── README.md
│
├── shared/                       # ← NUEVO: código compartido bot + web
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py           # Configuración centralizada (env, paths)
│   ├── domain/                   # Entidades y reglas de negocio puras
│   │   ├── __init__.py
│   │   ├── entities.py           # RegistroDefecto, Usuario, Contador (dataclasses)
│   │   ├── value_objects.py      # Turno, Departamento, RangoFotos
│   │   └── interfaces.py         # Abstract repositories (ports)
│   ├── application/              # Casos de uso (orquestan domain)
│   │   ├── __init__.py
│   │   ├── registro_service.py   # Crear/consultar registros
│   │   ├── usuario_service.py    # Gestión de usuarios
│   │   ├── foto_service.py       # Gestión de fotos (almacenamiento)
│   │   └── reporte_service.py    # Generación de reportes
│   └── infrastructure/           # Implementaciones concretas
│       ├── __init__.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── sqlite_repository.py   # Implementa interfaces de domain
│       │   └── migrations/
│       ├── storage/
│       │   ├── __init__.py
│       │   └── local_storage.py       # Gestión de archivos/fotos
│       └── orientation/
│           ├── __init__.py
│           └── onnx_detector.py       # Detección de orientación ONNX
│
├── bot/                          # ← Interface: Telegram Bot
│   ├── __init__.py
│   ├── main.py                   # Entry point del bot
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── auth.py               # verificar_acceso, comando_mi_id
│   │   ├── defecto.py            # guardar_foto, procesar_respuesta
│   │   ├── consulta.py           # reporte, estado, info_fotos
│   │   └── gestion.py            # limpiar, cancelar, descargar
│   ├── conversation/
│   │   ├── __init__.py
│   │   └── state_manager.py      # Estado de conversaciones (DB-backed)
│   └── bot_builder.py            # Configuración y registro de handlers
│
├── web/                          # ← Interface: Django Panel
│   ├── manage.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py           # Django settings (usa shared.config)
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── calidad/
│   │   ├── __init__.py
│   │   ├── models.py             # Django ORM (managed=False para tablas bot)
│   │   ├── admin.py
│   │   ├── urls.py
│   │   ├── views/
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py      # Vista dashboard
│   │   │   ├── reportes.py       # Vista reportes
│   │   │   ├── fotos.py          # ver_foto, galeria
│   │   │   └── excel.py          # revisar_orientacion, generar_excel, API
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── excel_generator.py    # Generación Excel (usa shared)
│   │   │   └── permisos.py           # Lógica de permisos por turno/depto
│   │   └── migrations/
│   ├── templates/calidad/        # Sin cambios
│   └── static/                  # Sin cambios
│
├── media/                        # Archivos subidos (fotos)
│   └── fotos/
│
├── data/                         # Datos del sistema
│   └── bot_calidad.db            # SQLite
│
├── templates/                    # Plantillas de reporte
│   └── plantilla_reporte.xlsx
│
└── scripts/                     # Scripts de utilidad
    ├── run_bot.py
    ├── run_web.py
    └── setup.sh
```

### 2.3 Responsabilidad de Cada Módulo

| Módulo | Responsabilidad | Puede importar de |
|--------|----------------|-------------------|
| `shared/domain` | Entidades puras, interfaces de repositorio. Sin dependencias externas. | Nada (puro Python) |
| `shared/application` | Casos de uso que orquestan el dominio. | `shared/domain` |
| `shared/infrastructure` | Implementaciones concretas (SQLite, filesystem, ONNX). | `shared/domain`, `shared/application` |
| `shared/config` | Configuración centralizada, env vars, paths. | Nada (stdlib + dotenv) |
| `bot/handlers` | Handlers de Telegram (interface adapter). | `shared/application`, `shared/config` |
| `bot/conversation` | Gestión de estado de conversaciones. | `shared/application`, `shared/domain` |
| `web/calidad/views` | Vistas Django (interface adapter). | `shared/application`, `shared/infrastructure` |
| `web/calidad/services` | Servicios específicos de la web. | `shared/application`, `shared/domain` |

**Regla de dependencias (flecha = "importa a"):**
```
interfaces (bot/, web/) → application → domain ← infrastructure
```
- `domain` NUNCA importa nada fuera de sí mismo.
- `infrastructure` implementa interfaces definidas en `domain`.
- `application` usa interfaces de `domain`, nunca implementaciones concretas.

### 2.4 Entidades del Dominio (Ejemplo)

```python
# shared/domain/entities.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class RegistroDefecto:
    fotos: List[int]
    modelo: str
    linea: str
    cantidad: int
    responsable: str
    descripcion: str
    user_id: int
    turno: Optional[str] = None
    departamento: Optional[str] = None
    fecha_registro: Optional[datetime] = None
    id: Optional[int] = None

@dataclass
class Usuario:
    telegram_user_id: int
    turno: str
    departamento: str
    username: Optional[str] = None

@dataclass  
class ContadorGrupo:
    turno: str
    departamento: str
    contador_actual: int = 1
```

```python
# shared/domain/value_objects.py
from enum import TextChoices
from dataclasses import dataclass

class Turno(TextChoices):
    A = 'A', 'Turno A'
    B = 'B', 'Turno B'
    C = 'C', 'Turno C'

class Departamento(TextChoices):
    IQA = 'IQA', 'IQA'
    SQA = 'SQA', 'SQA'
    PROD = 'PROD', 'Producción'
    ENG = 'ENG', 'Ingeniería'

@dataclass(frozen=True)
class RangoFotos:
    inicio: int
    fin: int

    @property
    def numeros(self) -> list[int]:
        return list(range(self.inicio, self.fin + 1))

    def __str__(self) -> str:
        if self.inicio == self.fin:
            return f"({self.inicio:03d})"
        return f"({self.inicio:03d}-{self.fin:03d})"
```

```python
# shared/domain/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from .entities import RegistroDefecto, Usuario

class RegistroRepository(ABC):
    @abstractmethod
    def guardar(self, registro: RegistroDefecto) -> bool: ...
    @abstractmethod
    def obtener_todos(self, user_id=None, turno=None, departamento=None) -> List[RegistroDefecto]: ...
    @abstractmethod
    def obtener_por_turno_depto(self, turno: str, departamento: str, user_id: int = None) -> List[RegistroDefecto]: ...
    @abstractmethod
    def limpiar_por_usuario(self, user_id: int) -> bool: ...

class UsuarioRepository(ABC):
    @abstractmethod
    def tiene_acceso(self, telegram_user_id: int) -> bool: ...
    @abstractmethod
    def obtener(self, telegram_user_id: int) -> Optional[Usuario]: ...
    @abstractmethod
    def crear(self, usuario: Usuario) -> bool: ...
    @abstractmethod
    def actualizar(self, usuario: Usuario) -> bool: ...
    @abstractmethod
    def listar(self) -> List[Usuario]: ...

class ContadorRepository(ABC):
    @abstractmethod
    def obtener_y_avanzar(self, turno: str, departamento: str) -> int: ...
    @abstractmethod
    def obtener_actual(self, turno: str, departamento: str) -> int: ...
    @abstractmethod
    def reiniciar(self, turno: str, departamento: str) -> None: ...

class FotoStorage(ABC):
    @abstractmethod
    def guardar_foto(self, user_id: int, contador: int, contenido: bytes, extension: str = '.png') -> str: ...
    @abstractmethod
    def obtener_path(self, user_id: int, numero: int) -> Optional[str]: ...
    @abstractmethod
    def eliminar_fotos_usuario(self, user_id: int) -> int: ...
    @abstractmethod
    def listar_fotos_usuario(self, user_id: int) -> List[str]: ...
```

---

## 3. PLAN DE MIGRACIÓN INCREMENTAL

### Principio: Strangler Fig Pattern
Cada paso debe dejar el sistema funcional. Se migra por capas, de adentro hacia afuera.

### Fase 0 — Preparación (sin romper nada)
**Duración estimada: 1 día**

- [ ] Crear estructura de carpetas `shared/`, `bot/` (vacías con `__init__.py`)
- [ ] Limpiar `requirements.txt` (eliminar duplicados)
- [ ] Agregar `python-dotenv` a `shared/config/settings.py` centralizado
- [ ] Mover `SECRET_KEY` a variable de entorno
- [ ] Agregar logging estructurado básico (reemplazar `print()`)

### Fase 1 — Extraer Dominio (sin romper nada)
**Duración estimada: 1-2 días**

- [ ] Crear `shared/domain/entities.py` con dataclasses que mapeen las tablas actuales
- [ ] Crear `shared/domain/value_objects.py` (Turno, Departamento, RangoFotos)
- [ ] Crear `shared/domain/interfaces.py` con repositorios abstractos
- [ ] **No se elimina código existente** — solo se crea nuevo

### Fase 2 — Extraer Infraestructura (compatibilidad dual)
**Duración estimada: 2-3 días**

- [ ] Crear `shared/infrastructure/database/sqlite_repository.py` que implemente las interfaces
- [ ] Implementación: delegar internamente a `DatabaseManager` existente (wrapper)
- [ ] Crear `shared/infrastructure/storage/local_storage.py` para gestión de fotos
- [ ] Mover lógica de orientación ONNX a `shared/infrastructure/orientation/onnx_detector.py`
- [ ] **Test**: verificar que el wrapper produce los mismos resultados que `db` directo

### Fase 3 — Extraer Application Services
**Duración estimada: 2-3 días**

- [ ] Crear `shared/application/registro_service.py` — orquesta `RegistroRepository` + `ContadorRepository`
- [ ] Crear `shared/application/usuario_service.py` — orquesta `UsuarioRepository`
- [ ] Crear `shared/application/foto_service.py` — orquesta `FotoStorage` + `ContadorRepository`
- [ ] Crear `shared/application/reporte_service.py` — orquesta generación de reportes
- [ ] **Test**: los services deben producir los mismos resultados que el código inline

### Fase 4 — Refactorizar Bot (migración de handlers)
**Duración estimada: 2-3 días**

- [ ] Mover `verificar_acceso` + `comando_mi_id` → `bot/handlers/auth.py`
- [ ] Mover `guardar_foto` + `procesar_respuesta` → `bot/handlers/defecto.py`
- [ ] Mover `reporte` + `estado` + `info_fotos` → `bot/handlers/consulta.py`
- [ ] Mover `limpiar` + `cancelar` + `descargar` + `limpiar_fotos` → `bot/handlers/gestion.py`
- [ ] Mover estado de conversaciones → `bot/conversation/state_manager.py` (respaldar en DB, no JSON)
- [ ] Mover `main()` → `bot/main.py` + `bot/bot_builder.py`
- [ ] **Punto crítico**: cada handler migrado se prueba individualmente antes de eliminar el original

### Fase 5 — Refactorizar Web (migración de vistas)
**Duración estimada: 2-3 días**

- [ ] Extraer `get_registros_permitidos` + `obtener_numeros_fotos_permitidas` → `web/calidad/services/permisos.py`
- [ ] Dividir `views.py` en `views/dashboard.py`, `views/reportes.py`, `views/fotos.py`, `views/excel.py`
- [ ] Mover `_parse_fotos_nums` + `_consolidar_registros` → `shared/application/reporte_service.py`
- [ ] Mover `reporte_excel.py` → `shared/infrastructure/orientation/` + `web/calidad/services/excel_generator.py`
- [ ] **Punto crítico**: las URLs no cambian, solo la organización interna

### Fase 6 — Eliminar Código Legacy
**Duración estimada: 1 día**

- [ ] Eliminar `main_sqlite.py` (reemplazado por `bot/main.py`)
- [ ] Eliminar `database.py` (reemplazado por `shared/infrastructure/database/`)
- [ ] Eliminar `src/` fantasma
- [ ] Eliminar métodos legacy vacíos
- [ ] Eliminar `estado_conversaciones.json` (reemplazado por DB-backed state)
- [ ] Mover `bot_calidad.db` → `data/bot_calidad.db`

### Fase 7 — Hardening y Testing
**Duración estimada: 2 días**

- [ ] Agregar tests unitarios para `shared/domain/`
- [ ] Agregar tests de integración para `shared/infrastructure/`
- [ ] Agregar tests para `shared/application/`
- [ ] Verificar flujo completo bot → DB → web → Excel
- [ ] Documentar API interna

---

## 4. EJEMPLOS DE CÓDIGO REFACTORIZADO

### 4.1 Caso Real: Handler de Fotos (antes en main_sqlite.py)

**ANTES** — `main_sqlite.py:274-338` (65 líneas, acoplado a `db` global, maneja storage + estado + respuesta):

```python
async def guardar_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None: return
    if update.effective_user is None: return
    user_id = update.effective_user.id
    usuario = db.obtener_usuario(user_id)  # ← acoplamiento directo
    if not usuario:
        await update.message.reply_text("⛔️ Usuario no registrado...")
        return
    if user_id not in conversaciones:  # ← estado global mutable
        iniciar_conversacion(user_id)
        await update.message.reply_text("📸 Bienvenido...")
    photo = update.message.photo[-1]
    file = await photo.get_file()
    user_folder = os.path.join(FOTOS_PATH, str(user_id))  # ← path hardcodeado
    os.makedirs(user_folder, exist_ok=True)
    contador = db.obtener_y_avanzar_contador(user_id)  # ← acoplamiento
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre_archivo = f"{contador:03d}_{timestamp}.png"
    ruta = os.path.join(user_folder, nombre_archivo)
    try:
        await file.download_to_drive(ruta)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar la foto: {str(e)}")
        return
    conversaciones[user_id]['fotos'].append(contador)  # ← estado global
    guardar_estado()
    await update.message.reply_text(f"✅ Foto {contador:03d} recibida...")
```

**DESPUÉS** — `bot/handlers/defecto.py` (inyecta servicios, sin estado global):

```python
# bot/handlers/defecto.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from shared.application.foto_service import FotoService
from shared.application.usuario_service import UsuarioService
from bot.conversation.state_manager import StateManager

logger = logging.getLogger(__name__)

class DefectoHandler:
    def __init__(
        self,
        foto_service: FotoService,
        usuario_service: UsuarioService,
        state_manager: StateManager,
    ):
        self._foto_service = foto_service
        self._usuario_service = usuario_service
        self._state = state_manager

    async def guardar_foto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        usuario = self._usuario_service.obtener(user_id)
        if not usuario:
            await update.message.reply_text(
                "⛔️ Usuario no registrado.\n"
                f"Tu ID es: `{user_id}`"
            )
            return

        if not self._state.tiene_conversacion(user_id):
            self._state.iniciar(user_id)
            await update.message.reply_text(
                f"👤 Usuario: {user_id}\n"
                f"🕐 Turno: {usuario.turno}\n"
                f"🏢 Depto: {usuario.departamento}\n\n"
                "1. Envía fotos\n2. Escribe 'TERMINAR'\n3. Ingresa detalles"
            )

        photo = update.message.photo[-1]
        file = await photo.get_file()

        contador = self._foto_service.siguiente_contador(usuario.turno, usuario.departamento)
        ruta = self._foto_service.guardar_archivo(user_id, contador, file)

        if ruta is None:
            await update.message.reply_text("❌ Error al guardar la foto.")
            logger.error("Error guardando foto user_id=%s contador=%s", user_id, contador)
            return

        self._state.agregar_foto(user_id, contador)
        await update.message.reply_text(f"✅ Foto {contador:03d} recibida.")
```

**Mejoras:**
- Inyección de dependencias (no más `db` global)
- Estado encapsulado en `StateManager` (no más dict global + JSON)
- Lógica de storage delegada a `FotoService`
- Logging estructurado en vez de `print()`
- Sin paths hardcodeados

### 4.2 Caso Real: DatabaseManager → Repository Pattern

**ANTES** — `database.py` (508 líneas, God Class, instancia global):

```python
class DatabaseManager:
    def __init__(self, db_path="bot_calidad.db"):
        # ... 25+ métodos mezclando usuarios, registros, contadores, estadísticas, formateo
    
    def usuario_tiene_acceso(self, telegram_user_id): ...
    def crear_usuario(self, ...): ...
    def obtener_usuario(self, ...): ...
    def guardar_registro(self, ...): ...
    def obtener_todos_registros(self, ...): ...
    def obtener_y_avanzar_contador(self, ...): ...
    def obtener_estadisticas(self, ...): ...
    def _formatear_rango_fotos(self, ...): ...  # ← utilidad, no DB
    # + 8 métodos legacy vacíos

db = DatabaseManager()  # ← instancia global
```

**DESPUÉS** — 3 repositorios enfocados + 1 servicio de formateo:

```python
# shared/infrastructure/database/sqlite_repository.py
import sqlite3
from typing import List, Optional, Dict
from shared.domain.interfaces import RegistroRepository, UsuarioRepository, ContadorRepository
from shared.domain.entities import RegistroDefecto, Usuario
from shared.domain.value_objects import RangoFotos

class SqliteRegistroRepository(RegistroRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def guardar(self, registro: RegistroDefecto) -> bool:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                fotos_str = RangoFotosHelper.formatear(registro.fotos)
                cursor.execute('''
                    INSERT INTO registros_defectos
                    (fotos, modelo, linea, cantidad, responsable, descripcion,
                     user_id, turno, departamento)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (fotos_str, registro.modelo, registro.linea, registro.cantidad,
                      registro.responsable, registro.descripcion,
                      registro.user_id, registro.turno, registro.departamento))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error("Error guardando registro: %s", e)
            return False

    def obtener_por_turno_depto(self, turno: str, departamento: str,
                                 user_id: int = None) -> List[RegistroDefecto]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM registros_defectos
                    WHERE (turno = ? AND departamento = ?) OR (user_id = ?)
                    ORDER BY fecha_registro DESC
                ''', (turno, departamento, user_id))
                return [self._row_to_entity(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("Error obteniendo registros: %s", e)
            return []

    def _row_to_entity(self, row) -> RegistroDefecto:
        d = dict(row)
        return RegistroDefecto(
            id=d['id'], fotos=self._parse_fotos(d['fotos']),
            modelo=d['modelo'], linea=d['linea'],
            cantidad=d['cantidad'], responsable=d['responsable'],
            descripcion=d['descripcion'], user_id=d['user_id'],
            turno=d.get('turno'), departamento=d.get('departamento'),
            fecha_registro=d.get('fecha_registro')
        )


class SqliteUsuarioRepository(UsuarioRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def tiene_acceso(self, telegram_user_id: int) -> bool:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM usuarios_bot WHERE telegram_user_id = ?",
                    (telegram_user_id,)
                )
                return cursor.fetchone() is not None
        except sqlite3.Error:
            return False

    def obtener(self, telegram_user_id: int) -> Optional[Usuario]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM usuarios_bot WHERE telegram_user_id = ?",
                    (telegram_user_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                d = dict(row)
                return Usuario(
                    telegram_user_id=d['telegram_user_id'],
                    turno=d['turno'],
                    departamento=d['departamento'],
                    username=d.get('username')
                )
        except sqlite3.Error as e:
            logger.error("Error obteniendo usuario: %s", e)
            return None


class SqliteContadorRepository(ContadorRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def obtener_y_avanzar(self, turno: str, departamento: str) -> int:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('BEGIN EXCLUSIVE')
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT contador_actual FROM contadores_grupo WHERE turno = ? AND departamento = ?',
                    (turno, departamento)
                )
                result = cursor.fetchone()
                if result:
                    contador = result[0]
                    cursor.execute(
                        'UPDATE contadores_grupo SET contador_actual = contador_actual + 1 WHERE turno = ? AND departamento = ?',
                        (turno, departamento)
                    )
                else:
                    contador = 1
                    cursor.execute(
                        'INSERT INTO contadores_grupo (turno, departamento, contador_actual) VALUES (?, ?, 2)',
                        (turno, departamento)
                    )
                conn.commit()
                return contador
        except sqlite3.Error as e:
            logger.error("Error en contador: %s", e)
            return 1
```

**Mejoras:**
- SRP: cada repositorio tiene 1 responsabilidad
- DIP: los handlers dependen de abstracciones (interfaces), no de SQLite directamente
- LSP: sin métodos vacíos/legacy
- Testeable: se puede inyectar un mock de `RegistroRepository` para tests
- Sin instancia global: se crea en `main()` y se inyecta

---

## 5. ESTANDARIZACIÓN

### 5.1 Convenciones de Nombres

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Archivos Python | `snake_case.py` | `registro_service.py` |
| Clases | `PascalCase` | `RegistroDefecto`, `FotoService` |
| Funciones/métodos | `snake_case` | `obtener_registros()` |
| Constantes | `UPPER_SNAKE` | `FOTOS_PATH`, `MAX_DISPLAY_H` |
| Interfaces abstractas | Prefijo `I` o sufijo `ABC` | `RegistroRepository(ABC)` |
| Implementaciones | Prefijo de tecnología | `SqliteRegistroRepository` |
| Tests | `test_<modulo>.py` | `test_registro_service.py` |
| Templates | `snake_case.html` | `dashboard.html` (sin cambio) |

### 5.2 Estructura de Servicios

```python
# Patrón estándar para cualquier servicio:
class MiServicio:
    def __init__(self, repo: MiRepositoryABC):
        self._repo = repo  # Inyección por constructor

    def mi_caso_de_uso(self, param: str) -> Resultado:
        # 1. Validar input
        # 2. Orquestar repositorio(s)
        # 3. Aplicar reglas de negocio
        # 4. Retornar resultado
        ...
```

### 5.3 Manejo de Dependencias

```python
# shared/config/dependencies.py
from shared.infrastructure.database.sqlite_repository import (
    SqliteRegistroRepository,
    SqliteUsuarioRepository,
    SqliteContadorRepository,
)
from shared.infrastructure.storage.local_storage import LocalFotoStorage
from shared.application.registro_service import RegistroService
from shared.application.foto_service import FotoService
from shared.application.usuario_service import UsuarioService

def build_container(config: Settings):
    """Construye el contenedor de dependencias (manual DI)."""
    db_path = config.database_path

    # Infrastructure
    registro_repo = SqliteRegistroRepository(db_path)
    usuario_repo = SqliteUsuarioRepository(db_path)
    contador_repo = SqliteContadorRepository(db_path)
    foto_storage = LocalFotoStorage(config.fotos_path)

    # Application
    registro_service = RegistroService(registro_repo, contador_repo)
    foto_service = FotoService(foto_storage, contador_repo)
    usuario_service = UsuarioService(usuario_repo)

    return {
        'registro_service': registro_service,
        'foto_service': foto_service,
        'usuario_service': usuario_service,
    }
```

### 5.4 Manejo de Errores

```python
# shared/domain/exceptions.py
class CalidadBotError(Exception):
    """Base exception para el dominio."""

class UsuarioNoEncontradoError(CalidadBotError):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"Usuario {user_id} no encontrado")

class RegistroInvalidoError(CalidadBotError):
    def __init__(self, campo: str, valor):
        self.campo = campo
        super().__init__(f"Campo '{campo}' inválido: {valor}")

class FotoStorageError(CalidadBotError):
    def __init__(self, ruta: str, causa: str):
        super().__init__(f"Error almacenando foto en {ruta}: {causa}")
```

### 5.5 Logging

```python
# Convención estándar en todo el proyecto:
import logging

logger = logging.getLogger(__name__)

# Niveles:
# DEBUG   - Detalles internos (query SQL, paths)
# INFO    - Eventos de negocio (registro guardado, usuario creado)
# WARNING - Situaciones recuperables (foto no encontrada, modelo ONNX no cargado)
# ERROR   - Errores que afectan la operación (DB caída, escritura fallida)

# Formato:
logger.info("Registro guardado user_id=%s registro_id=%s", user_id, registro_id)
logger.error("Error guardando registro user_id=%s: %s", user_id, e)
```

### 5.6 Configuración

```python
# shared/config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    MEDIA_DIR: Path = BASE_DIR / "media"
    FOTOS_PATH: Path = MEDIA_DIR / "fotos"
    DB_PATH: Path = DATA_DIR / "bot_calidad.db"

    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

    # Web
    DJANGO_SECRET_KEY: str = os.getenv("DJANGO_SECRET_KEY", "cambiar-en-produccion")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    ALLOWED_HOSTS: list = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

    # Excel
    PLANTILLA_PATH: Path = BASE_DIR / "templates" / "plantilla_reporte.xlsx"
    JPEG_QUALITY: int = 88
    MAX_DISPLAY_H: int = 200

    def ensure_dirs(self):
        for d in [self.DATA_DIR, self.MEDIA_DIR, self.FOTOS_PATH]:
            d.mkdir(parents=True, exist_ok=True)

settings = Settings()
```

---

## 6. ESCALABILIDAD

### 6.1 Separación Futura a Microservicios

La arquitectura propuesta ya prepara el terreno:

| Microservicio futuro | Módulo actual | Trigger para separar |
|----------------------|---------------|---------------------|
| **Bot Service** | `bot/` | Cuando el bot necesite escalar independientemente |
| **Quality API** | `shared/application/` + `web/` | Cuando se agreguen más clientes (app móvil, n8n) |
| **Report Service** | `shared/infrastructure/orientation/` + `excel_generator.py` | Cuando el procesamiento ONNX sea cuello de botella |
| **Storage Service** | `shared/infrastructure/storage/` | Cuando se migre a S3/Azure Blob |

Las interfaces abstractas en `shared/domain/interfaces.py` permiten cambiar implementación sin tocar negocio.

### 6.2 Colas y Procesamiento Asíncrono

**Problema actual**: La detección de orientación ONNX es síncrona y bloquea el request HTTP.

**Propuesta incremental**:

1. **Fase 1** (ahora): Usar `celery` + Redis para generación de Excel asíncrona
   - El usuario solicita Excel → se encola tarea → se notifica cuando está listo
   - Evita timeouts en la web

2. **Fase 2**: Procesamiento de fotos asíncrono
   - Cuando el bot recibe foto → se encola orientación + thumbnail
   - El usuario no espera

3. **Fase 3**: Webhooks de Telegram en vez de polling
   - `application.run_webhook()` en vez de `run_polling()`
   - Mejor uso de recursos

### 6.3 Caching

- **Dashboard stats**: Cache con TTL de 5 min (Redis o `cachetools` en memoria)
- **Detección de orientación**: Cache por path de archivo (la misma foto siempre da el mismo ángulo)
- **Contadores**: Ya son atómicos en SQLite, pero si se migra a PostgreSQL se puede usar `SELECT ... FOR UPDATE`

### 6.4 Manejo de Cargas Pesadas (OCR / ONNX)

- **Batch processing**: `detect_orientations_batch()` ya existe, pero es secuencial. Paralelizar con `concurrent.futures.ThreadPoolExecutor` (ONNX es CPU-bound, GIL se libera en numpy)
- **Modelo ONNX singleton**: Ya implementado con `_onnx_session`. Correcto.
- **Límite de tamaño de imagen**: Agregar validación antes de procesar (rechazar >10MB)

---

## 7. RIESGOS Y MITIGACIÓN

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Estado de conversaciones se pierde al migrar de JSON a DB | Media | Alto | Migrar con script de conversión; mantener fallback a JSON por 1 versión |
| Django ORM (`managed=False`) deja de leer tablas si se renombra DB | Baja | Alto | Mantener nombre de tablas; solo mover archivo `.db` de carpeta |
| Bot se rompe durante migración de handlers | Media | Crítico | Migrar handler por handler; mantener `main_sqlite.py` como fallback hasta que todos estén migrados |
| Race condition en contadores durante transición | Baja | Medio | Los contadores ya usan `BEGIN EXCLUSIVE`; no cambiar esta lógica |
| Import paths rotos en Django | Media | Alto | Actualizar `settings.py` y `urls.py` antes de mover archivos |
| ONNX model no carga en nueva ruta | Baja | Medio | El modelo se descarga de HuggingFace (no es local); solo cambiar import path |
| Señal `post_save` de Django se rompe al mover models | Media | Alto | No mover `models.py` hasta Fase 5; las señales se quedan en el mismo archivo |

### Estrategia de Rollback

Cada fase se hace en una branch git separada. Si algo falla:
1. Revertir la branch
2. El código anterior sigue funcionando (no se eliminó hasta Fase 6)
3. Se puede mantener un flag `USE_NEW_ARCHITECTURE = True/False` para switching rápido durante la transición

---

## RESUMEN EJECUTIVO

| Aspecto | Estado Actual | Estado Propuesto |
|---------|--------------|-----------------|
| Líneas por archivo | 867 (main), 601 (views), 508 (database) | <150 por archivo |
| Acoplamiento | Directo (import `db` global) | Invertido (interfaces + inyección) |
| Cohesión | Baja (7 responsabilidades en main) | Alta (1 responsabilidad por módulo) |
| Testeabilidad | Casi imposible (globals, side effects) | Alta (DI, interfaces, sin estado global) |
| Estado | JSON plano + dict global | DB-backed + StateManager encapsulado |
| Logging | `print()` | `logging` estructurado |
| Configuración | Hardcodeada + `.env` parcial | Centralizada en `Settings` |
| Errores | `str(e)` al usuario | Excepciones tipadas + logging |
| Legacy | 8 métodos vacíos | Eliminados |
| Escalabilidad | Monolito acoplado | Preparado para microservicios |

**Esfuerzo total estimado**: 12-15 días de trabajo para un desarrollador, distribuidos en 7 fases incrementales.
