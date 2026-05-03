# ================================
# 🗄️ BASE DE DATOS SQLITE - BOT DE CALIDAD (MULTIUSUARIO)
# ================================
# Versión multiusuario con aislamiento por turno y departamento.
# Sistema de lotes y modo epidémico eliminados.
# ================================

import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Union, Tuple

class DatabaseManager:
    """
    Gestor de base de datos SQLite para el bot de calidad.
    Versión multiusuario con soporte para turnos y departamentos.
    """

    def __init__(self, db_path: str = "bot_calidad.db"):
        """
        Inicializa el gestor de base de datos.

        Args:
            db_path (str): Ruta del archivo de base de datos SQLite
        """
        self.db_path = db_path
        # Habilitar modo WAL para permitir concurrencia real (lecturas/escrituras simultáneas)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA synchronous=NORMAL;')
        self.init_database()

    def init_database(self):
        """
        Inicializa la base de datos creando las tablas necesarias.
        Versión multiusuario con aislamiento por turno y departamento.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # ================================
                # 📋 TABLA: Registros de defectos (MULTIUSUARIO)
                # ================================
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS registros_defectos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fotos TEXT NOT NULL,           -- Rango de fotos (ej: "(001-003)")
                        modelo TEXT NOT NULL,           -- Modelo del producto
                        linea TEXT NOT NULL,            -- Línea de producción
                        cantidad INTEGER,               -- Cantidad de defectos
                        responsable TEXT NOT NULL,      -- Responsable del defecto
                        descripcion TEXT NOT NULL,      -- Descripción del defecto
                        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        -- Campos multiusuario:
                        user_id INTEGER NOT NULL,       -- ID del usuario de Telegram (obligatorio)
                        turno TEXT,                     -- Turno: A, B, C
                        departamento TEXT               -- Departamento: IQA, SQA, etc.
                    )
                ''')

                # ================================
                # 🗑️ ELIMINAR TABLA OBSOLETA (usuarios_bot)
                # ================================
                cursor.execute('DROP TABLE IF EXISTS usuarios_bot')

                # ================================
                # 📊 TABLA: Contadores compartidos por Turno y Depto
                # ================================
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS contadores_grupo (
                        turno TEXT,
                        departamento TEXT,
                        contador_actual INTEGER DEFAULT 1,
                        PRIMARY KEY (turno, departamento)
                    )
                ''')

                # ================================
                # 🗑️ ELIMINAR TABLAS OBSOLETAS (si existen)
                # ================================
                tablas_obsoletas = [
                    'lotes_epidemico',
                    'lotes_activos',
                    'fotos_por_responsable',
                    'control_contador'
                ]
                for tabla in tablas_obsoletas:
                    cursor.execute(f'DROP TABLE IF EXISTS {tabla}')

                conn.commit()
                print("OK: Base de datos inicializada correctamente (multiusuario)")
                print("OK: Tablas: registros_defectos, contadores_usuario")

        except Exception as e:
            print(f"Error al inicializar la base de datos: {e}")
            raise

    # ================================
    # 🔒 AUTENTICACIÓN Y USUARIOS
    # ================================

    def usuario_tiene_acceso(self, telegram_user_id: int) -> bool:
        """
        Verifica si el ID de Telegram está registrado en Django.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Verificar si la tabla de Django existe
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calidad_perfilusuario'")
                if not cursor.fetchone():
                    return False

                cursor.execute("SELECT id FROM calidad_perfilusuario WHERE telegram_user_id = ?", (telegram_user_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error verificando acceso: {e}")
            return False

    def usuario_es_staff(self, telegram_user_id: int) -> bool:
        """
        Verifica si el usuario de Telegram está vinculado a un usuario Django is_staff.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Si no existen tablas Django, no hay staff que validar.
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calidad_perfilusuario'")
                if not cursor.fetchone():
                    return False
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_user'")
                if not cursor.fetchone():
                    return False

                cursor.execute(
                    """
                    SELECT au.is_staff
                    FROM calidad_perfilusuario p
                    JOIN auth_user au ON au.id = p.usuario_id
                    WHERE p.telegram_user_id = ?
                    LIMIT 1
                    """,
                    (telegram_user_id,),
                )
                row = cursor.fetchone()
                return bool(row[0]) if row else False
        except Exception as e:
            print(f"Error verificando is_staff para {telegram_user_id}: {e}")
            return False

    def crear_usuario(self, telegram_user_id: int, turno: str, departamento: str, username: str = None) -> bool:
        """
        Ya no es utilizado. Los usuarios se crean desde Django.
        """
        raise NotImplementedError("La creación de usuarios ahora se maneja exclusivamente desde Django.")

    def obtener_usuario(self, telegram_user_id: int) -> Optional[Dict]:
        """Obtiene la información de un usuario desde las tablas nativas de Django."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calidad_perfilusuario'")
                if not cursor.fetchone():
                    return None
                    
                query = """
                    SELECT p.telegram_user_id, u.username, u.first_name, u.last_name, 
                           p.turno, p.departamento, u.is_superuser
                    FROM calidad_perfilusuario p
                    JOIN auth_user u ON p.usuario_id = u.id
                    WHERE p.telegram_user_id = ?
                """
                cursor.execute(query, (telegram_user_id,))
                row = cursor.fetchone()
                
                if row:
                    t_id = row['telegram_user_id']
                    username = row['username']
                    first_name = row['first_name'] or ""
                    last_name = row['last_name'] or ""
                    
                    nombre = f"{first_name} {last_name}".strip()
                    if not nombre:
                        nombre = username or str(t_id)

                    return {
                        'telegram_user_id': t_id,
                        'username': username,
                        'nombre': nombre,
                        'turno': row['turno'],
                        'departamento': row['departamento'],
                        'rol': 'admin' if row['is_superuser'] else 'operador'
                    }
                return None
        except Exception as e:
            print(f"❌ Error al obtener usuario {telegram_user_id}: {e}")
            return None

    def actualizar_usuario(self, telegram_user_id: int, turno: str = None, departamento: str = None, username: str = None) -> bool:
        """Ya no es utilizado. Actualizaciones desde Django."""
        raise NotImplementedError("La actualización de usuarios se maneja exclusivamente desde Django.")

    def listar_usuarios(self) -> List[Dict]:
        """Lista todos los usuarios registrados."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                query = """
                    SELECT p.telegram_user_id, u.username, u.first_name, u.last_name, 
                           p.turno, p.departamento, u.is_superuser
                    FROM calidad_perfilusuario p
                    JOIN auth_user u ON p.usuario_id = u.id
                """
                cursor.execute(query)
                results = []
                for row in cursor.fetchall():
                    first_name = row['first_name'] or ""
                    last_name = row['last_name'] or ""
                    nombre = f"{first_name} {last_name}".strip() or row['username']
                    
                    results.append({
                        'telegram_user_id': row['telegram_user_id'],
                        'username': row['username'],
                        'nombre': nombre,
                        'turno': row['turno'],
                        'departamento': row['departamento'],
                        'rol': 'admin' if row['is_superuser'] else 'operador'
                    })
                return results
        except Exception as e:
            print(f"❌ Error al listar usuarios: {e}")
            return []

    # ================================
    # 📝 REGISTROS DE DEFECTOS
    # ================================

    def guardar_registro(self, fotos: List[int], modelo: str, linea: str,
                        cantidad: int, responsable: str, descripcion: str,
                        user_id: int, turno: str = None, departamento: str = None) -> bool:
        """Guarda un registro de defectos con soporte multiusuario."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                fotos_str = self._formatear_rango_fotos(fotos)
                
                # Valores para las columnas heredadas del esquema anterior
                inicio = fotos[0] if fotos else 0
                fin = fotos[-1] if fotos else 0

                cursor.execute('''
                    INSERT INTO registros_defectos
                    (fotos, modelo, linea, cantidad, responsable, descripcion, user_id, turno, departamento, numero_secuencia_inicio, numero_secuencia_fin)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (fotos_str, modelo, linea, cantidad, responsable, descripcion, user_id, turno, departamento, inicio, fin))

                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error al guardar registro: {e}")
            return False

    # Método legacy para compatibilidad temporal
    def guardar_registro_normal(self, fotos: List[int], modelo: str, linea: str,
                               cantidad: int, responsable: str, descripcion: str,
                               usuario_id: int) -> bool:
        """Compatibilidad temporal - delega a guardar_registro()."""
        usuario = self.obtener_usuario(usuario_id)
        turno = usuario.get('turno') if usuario else None
        departamento = usuario.get('departamento') if usuario else None
        return self.guardar_registro(fotos, modelo, linea, cantidad, responsable, descripcion, usuario_id, turno, departamento)

    def obtener_todos_registros(self, user_id: Optional[int] = None, turno: str = None, departamento: str = None) -> List[Dict]:
        """Obtiene registros filtrados por usuario, turno y departamento."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = 'SELECT * FROM registros_defectos WHERE 1=1'
                params = []

                if user_id is not None:
                    query += ' AND user_id = ?'
                    params.append(user_id)
                if turno is not None:
                    query += ' AND turno = ?'
                    params.append(turno)
                if departamento is not None:
                    query += ' AND departamento = ?'
                    params.append(departamento)

                query += ' ORDER BY fecha_registro DESC'
                cursor.execute(query, params)

                registros = []
                for row in cursor.fetchall():
                    registro = dict(row)
                    linea_formateada = f"{registro['fotos']} Modelo: {registro['modelo']}; Línea: {registro['linea']}; Cantidad: {registro['cantidad']}; Responsable: {registro['responsable']}; Descripción: {registro['descripcion']}"
                    registro['lineas_formateadas'] = [linea_formateada]
                    registros.append(registro)

                return registros
        except Exception as e:
            print(f"❌ Error al obtener registros: {e}")
            return []

    def obtener_registros_por_turno_depto(self, turno: str, departamento: str, user_id: int = None) -> List[Dict]:
        """Obtiene registros del turno/depto + propios del usuario."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM registros_defectos
                    WHERE (turno = ? AND departamento = ?) OR (user_id = ?)
                    ORDER BY fecha_registro DESC
                ''', (turno, departamento, user_id))

                registros = []
                for row in cursor.fetchall():
                    registro = dict(row)
                    linea_formateada = f"{registro['fotos']} Modelo: {registro['modelo']}; Línea: {registro['linea']}; Cantidad: {registro['cantidad']}; Responsable: {registro['responsable']}; Descripción: {registro['descripcion']}"
                    registro['lineas_formateadas'] = [linea_formateada]
                    registros.append(registro)

                return registros
        except Exception as e:
            print(f"❌ Error al obtener registros por turno/depto: {e}")
            return []

    def limpiar_registros(self) -> bool:
        """Limpia todos los registros (global - usar con precaución)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM registros_defectos')
                cursor.execute('DELETE FROM sqlite_sequence WHERE name = "registros_defectos"')
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error al limpiar registros: {e}")
            return False

    def limpiar_registros_usuario(self, user_id: int) -> bool:
        """Limpia solo los registros de un usuario específico."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM registros_defectos WHERE user_id = ?', (user_id,))
                conn.commit()
                print(f"🗑️ Registros del usuario {user_id} eliminados")
                return True
        except Exception as e:
            print(f"❌ Error al limpiar registros del usuario {user_id}: {e}")
            return False

    # ================================
    # 📊 ESTADÍSTICAS
    # ================================

    def obtener_estadisticas(self, user_id: int = None, turno: str = None, departamento: str = None) -> Dict:
        """Obtiene estadísticas filtradas."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                where_clauses = []
                params = []

                if user_id is not None:
                    where_clauses.append('user_id = ?')
                    params.append(user_id)
                if turno is not None:
                    where_clauses.append('turno = ?')
                    params.append(turno)
                if departamento is not None:
                    where_clauses.append('departamento = ?')
                    params.append(departamento)

                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

                cursor.execute(f'SELECT COUNT(*) FROM registros_defectos {where_sql}', params)
                total_registros = cursor.fetchone()[0]

                cursor.execute(f'''
                    SELECT modelo, linea, responsable, fecha_registro
                    FROM registros_defectos {where_sql}
                    ORDER BY fecha_registro DESC LIMIT 1
                ''', params)
                ultimo_registro = cursor.fetchone()

                return {
                    'total_registros': total_registros,
                    'ultimo_registro': f"{ultimo_registro[0]} - {ultimo_registro[1]} - {ultimo_registro[2]}" if ultimo_registro else None
                }
        except Exception as e:
            print(f"❌ Error al obtener estadísticas: {e}")
            return {}

    # ================================
    # 🔢 CONTADORES UNIFICADOS (Por Turno y Depto)
    # ================================

    def _obtener_turno_depto(self, user_id: int) -> Tuple[str, str]:
        usuario = self.obtener_usuario(user_id)
        if usuario:
            return usuario.get('turno', 'A'), usuario.get('departamento', 'IQA')
        return 'A', 'IQA'

    def obtener_y_avanzar_contador(self, user_id: int) -> int:
        """
        Obtiene el contador actual para el turno/depto del usuario y lo incrementa 
        automáticamente de forma atómica para evitar colisiones entre usuarios.
        """
        turno, depto = self._obtener_turno_depto(user_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Transacción exclusiva para evitar que dos usuarios obtengan el mismo número
                conn.execute('BEGIN EXCLUSIVE')
                cursor = conn.cursor()
                cursor.execute('SELECT contador_actual FROM contadores_grupo WHERE turno = ? AND departamento = ?', (turno, depto))
                result = cursor.fetchone()

                if result:
                    contador = result[0]
                    cursor.execute('UPDATE contadores_grupo SET contador_actual = contador_actual + 1 WHERE turno = ? AND departamento = ?', (turno, depto))
                else:
                    contador = 1
                    cursor.execute('''
                        INSERT INTO contadores_grupo (turno, departamento, contador_actual)
                        VALUES (?, ?, 2)
                    ''', (turno, depto))
                conn.commit()
                return contador
        except Exception as e:
            print(f"❌ Error al obtener contador de grupo: {e}")
            return 1

    def obtener_contador_usuario(self, user_id: int) -> int:
        """Obtiene el contador actual sin avanzarlo (útil para consultas de estado)."""
        turno, depto = self._obtener_turno_depto(user_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT contador_actual FROM contadores_grupo WHERE turno = ? AND departamento = ?', (turno, depto))
                result = cursor.fetchone()
                return result[0] if result else 1
        except:
            return 1

    def actualizar_contador_usuario(self, user_id: int, nuevo_contador: int):
        """LEGACY: Ya no se debe usar para incrementar manualmente porque causa Race Conditions."""
        pass

    def reiniciar_contador_usuario(self, user_id: int):
        """
        Reinicia el contador REAL del sistema (contadores_grupo) a 1
        según el turno y departamento del usuario.
        """
        self.establecer_contador_usuario(user_id, 1)

    def establecer_contador_usuario(self, user_id: int, valor: int):
        """
        Establece el contador del grupo (turno/depto) a un valor específico.
        Usado por /cancelar para hacer rollback al estado previo a la sesión.

        Args:
            user_id: ID de Telegram del usuario (para obtener turno/depto)
            valor:   Valor al que se quiere establecer (mínimo 1)
        """
        valor = max(1, valor)  # Nunca por debajo de 1
        turno, depto = self._obtener_turno_depto(user_id)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO contadores_grupo (turno, departamento, contador_actual)
                    VALUES (?, ?, ?)
                    ON CONFLICT(turno, departamento) DO UPDATE SET contador_actual = excluded.contador_actual
                    """,
                    (turno, depto, valor)
                )
                conn.commit()
        except Exception as e:
            print(f"[ERROR establecer_contador_usuario] {e}")

    def obtener_ultimo_numero_confirmado(self, user_id: int = None) -> int:
        """LEGACY: Ya no se usa. Retorna 0."""
        return 0

    def actualizar_ultimo_numero_confirmado(self, numero: int, user_id: int = None):
        """LEGACY: Ya no se usa. No hace nada."""
        pass

    # ================================
    # 🗑️ MÉTODOS LEGACY OBSOLETOS
    # ================================
    # Estos métodos se mantienen temporalmente para compatibilidad
    # pero serán eliminados en futuras versiones.

    def obtener_contador_actual(self) -> int:
        """⚠️ LEGACY: Usar obtener_contador_usuario(user_id) en su lugar."""
        print("⚠️ AVISO: obtener_contador_actual() está obsoleto. Use obtener_contador_usuario(user_id).")
        return 1

    def actualizar_contador(self, nuevo_contador: int):
        """⚠️ LEGACY: Usar actualizar_contador_usuario(user_id, contador) en su lugar."""
        print("⚠️ AVISO: actualizar_contador() está obsoleto. Use actualizar_contador_usuario(user_id, contador).")

    def obtener_numeros_ocupados(self) -> set:
        """⚠️ LEGACY: Retorna conjunto vacío. Ya no se usa en versión multiusuario."""
        return set()

    def actualizar_numeros_ocupados(self, numeros: set):
        """⚠️ LEGACY: No hace nada. Ya no se usa en versión multiusuario."""
        pass

    # ================================
    # 🔧 UTILIDADES
    # ================================

    def _formatear_rango_fotos(self, fotos: List[int]) -> str:
        """Formatea una lista de fotos en rangos."""
        if not fotos:
            return ""

        fotos = sorted(fotos)
        rangos = []
        inicio = fin = fotos[0]

        for foto in fotos[1:]:
            if foto == fin + 1:
                fin = foto
            else:
                if inicio == fin:
                    rangos.append(f"{inicio:03}")
                else:
                    rangos.append(f"{inicio:03}-{fin:03}")
                inicio = fin = foto

        if inicio == fin:
            rangos.append(f"{inicio:03}")
        else:
            rangos.append(f"{inicio:03}-{fin:03}")

        return "".join([f"({rango})" for rango in rangos])

# ================================
# 🌐 INSTANCIA GLOBAL
# ================================
db = DatabaseManager()
