#!/usr/bin/env python3
"""
migrate_sqlite_to_postgres.py
Lee registros de Alberto desde SQLite → inserta en Postgres via Django ORM.
Ejecutar desde: /home/danim/Escritorio/Labs/Python/Bot_calidad/
Con .env.local cargado (DATABASE_URL apunta a Postgres).
"""
import os
import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Tijuana')

def make_aware(dt_str):
    """Parse naive datetime string from SQLite → TZ-aware."""
    if dt_str is None:
        return None
    if isinstance(dt_str, str):
        dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    else:
        dt = dt_str
    return dt.replace(tzinfo=TZ)

# Setup Django con Postgres
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, str(Path(__file__).parent / 'web'))

import django
django.setup()

from django.contrib.auth.models import User
from calidad.models import RegistroDefecto, PerfilUsuario

SQLITE_DB  = Path("bot_calidad.db")
OLD_FOTOS  = Path("proyecto_completo/fotos/8659391667")
NEW_FOTOS  = Path("media_files/fotos/8659391667")
ALBERTO_ID = 8659391667

def ts():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

def log(msg, indent=0):
    print(f"[{ts()}] {'  '*indent}{msg}")

def run():
    log("=== MIGRACIÓN SQLite → Postgres (Alberto.Chona) ===")

    # ── PASO 1: Leer desde SQLite ─────────────────────────────────────────────
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT fotos, modelo, linea, cantidad, responsable, descripcion,
               fecha_registro, user_id, turno, departamento,
               numero_secuencia_inicio, numero_secuencia_fin
        FROM registros_defectos
        WHERE user_id = ?
        ORDER BY numero_secuencia_inicio
    """, (ALBERTO_ID,))
    sqlite_records = cur.fetchall()
    conn.close()
    log(f"Registros leídos de SQLite: {len(sqlite_records)}")

    # ── PASO 2: Crear usuario en Postgres si no existe ────────────────────────
    perfil_exists = PerfilUsuario.objects.filter(telegram_user_id=ALBERTO_ID).exists()
    if perfil_exists:
        log("Usuario Alberto.Chona ya existe en Postgres. Skip creación.")
    else:
        log("Creando auth_user Alberto.Chona en Postgres...")
        django_user = User.objects.create(
            username='Alberto.Chona',
            first_name='Alberto',
            last_name='Chona',
            email='',
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        django_user.set_unusable_password()
        django_user.save()
        log(f"  User.id = {django_user.id}")

        PerfilUsuario.objects.create(
            usuario=django_user,
            turno='C',
            departamento='IQA',
            rol='operador',
            telegram_user_id=ALBERTO_ID,
        )
        log("  Perfil creado: turno=C, depto=IQA, rol=operador ✅")

    # ── PASO 3: Insertar registros en Postgres (dedup por fotos+fecha) ────────
    migrados = 0
    omitidos = 0
    errores  = 0

    for rec in sqlite_records:
        # Dedup: mismo fotos + fecha_registro
        exists = RegistroDefecto.objects.filter(
            user_id=rec['user_id'],
            fotos=rec['fotos'],
            fecha_registro=rec['fecha_registro'],
        ).exists()

        if exists:
            log(f"  SKIP (duplicado): {rec['fotos']} {rec['fecha_registro']}", indent=1)
            omitidos += 1
            continue

        try:
            RegistroDefecto.objects.create(
                fotos=rec['fotos'],
                fotos_nums=[],          # backfill puede correr después
                modelo=rec['modelo'],
                linea=rec['linea'],
                cantidad=rec['cantidad'],
                responsable=rec['responsable'],
                descripcion=rec['descripcion'],
                fecha_registro=make_aware(rec['fecha_registro']),
                user_id=rec['user_id'],
                turno=rec['turno'],
                departamento=rec['departamento'],
            )
            log(f"  ✅ {rec['fotos']:15s} | {rec['descripcion']:20s} | {rec['fecha_registro']}", indent=1)
            migrados += 1
        except Exception as e:
            log(f"  ❌ ERROR {rec['fotos']}: {e}", indent=1)
            errores += 1

    log(f"Registros: {migrados} migrados, {omitidos} skip, {errores} errores")

    # ── PASO 4: Fotos (ya copiadas en paso anterior, verificar) ──────────────
    NEW_FOTOS.mkdir(parents=True, exist_ok=True)
    fotos_ok = sum(1 for f in NEW_FOTOS.iterdir() if f.is_file())
    old_total = sum(1 for f in OLD_FOTOS.iterdir() if f.is_file()) if OLD_FOTOS.exists() else 0

    if fotos_ok < old_total:
        log(f"Copiando fotos faltantes ({fotos_ok}/{old_total})...")
        copiadas = 0
        for foto in OLD_FOTOS.iterdir():
            if not foto.is_file():
                continue
            dest = NEW_FOTOS / foto.name
            if not dest.exists():
                shutil.copy2(foto, dest)
                copiadas += 1
        log(f"  Copiadas: {copiadas}")
    else:
        log(f"Fotos ya en disco: {fotos_ok} ✅")

    # ── PASO 5: Validación final ───────────────────────────────────────────────
    log("")
    log("═══ VALIDACIÓN POST ═══")
    pg_count    = RegistroDefecto.objects.filter(user_id=ALBERTO_ID).count()
    perfil_ok   = PerfilUsuario.objects.filter(telegram_user_id=ALBERTO_ID).exists()
    fotos_final = sum(1 for f in NEW_FOTOS.iterdir() if f.is_file())

    log(f"  Perfil en Postgres:    {'✅' if perfil_ok else '❌'}")
    log(f"  Registros en Postgres: {pg_count} (esperado: ≥{len(sqlite_records)})")
    log(f"  Fotos en disco:        {fotos_final} (esperado: ≥{old_total})")

    ok = perfil_ok and pg_count >= len(sqlite_records) and fotos_final >= old_total
    log("")
    log(f"═══ {'✅ ÉXITO — Datos visibles en web ahora' if ok else '❌ REVISAR ERRORES'} ═══")

if __name__ == "__main__":
    run()
