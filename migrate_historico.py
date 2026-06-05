#!/usr/bin/env python3
"""
migrate_historico.py
Migra fotos + registros de Alberto.Chona desde proyecto_completo.
Ejecutar desde: /home/danim/Escritorio/Labs/Python/Bot_calidad/

Modos:
  python migrate_historico.py --dry-run   # Solo muestra lo que haría
  python migrate_historico.py             # Ejecuta migración real
"""
import sqlite3
import shutil
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── Config ─────────────────────────────────────────────────────────────────
OLD_DB        = Path("proyecto_completo/bot_calidad.db")
NEW_DB        = Path("bot_calidad.db")
OLD_FOTOS     = Path("proyecto_completo/fotos/8659391667")
NEW_FOTOS     = Path("media_files/fotos/8659391667")
ALBERTO_ID    = 8659391667
DRY_RUN       = "--dry-run" in sys.argv

# ─── Helpers ────────────────────────────────────────────────────────────────
def ts():
    return datetime.now().strftime("%H:%M:%S")

def log(msg, indent=0):
    prefix = "  " * indent
    print(f"[{ts()}] {prefix}{msg}")

# ─── Main ────────────────────────────────────────────────────────────────────
def run():
    mode = "DRY-RUN" if DRY_RUN else "MIGRACIÓN REAL"
    log(f"=== {mode} - Alberto.Chona (8659391667) ===")

    # ── Verificar backup ─────────────────────────────────────────────────────
    if not DRY_RUN:
        backups = sorted(Path("backups").glob("**/bot_calidad_pre_migration.db")) if Path("backups").exists() else []
        if not backups:
            log("ERROR: No hay backup. Ejecuta: bash backup_before_migration.sh")
            sys.exit(1)
        log(f"Backup verificado: {backups[-1]}")

    # ── Conectar ─────────────────────────────────────────────────────────────
    old_conn = sqlite3.connect(OLD_DB)
    old_conn.row_factory = sqlite3.Row
    new_conn = sqlite3.connect(NEW_DB)
    new_conn.row_factory = sqlite3.Row

    old_cur = old_conn.cursor()
    new_cur = new_conn.cursor()

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 1: Analizar registros a migrar
    # ──────────────────────────────────────────────────────────────────────────
    old_cur.execute("""
        SELECT id, fotos, numero_secuencia_inicio, numero_secuencia_fin,
               user_id, modelo, linea, cantidad, responsable,
               descripcion, turno, departamento, fecha_registro
        FROM registros_defectos
        WHERE user_id = ?
        ORDER BY numero_secuencia_inicio
    """, (ALBERTO_ID,))
    old_records = old_cur.fetchall()

    log(f"")
    log(f"══════════════════════════════════════════════")
    log(f"  REGISTROS A MIGRAR: {len(old_records)}")
    log(f"══════════════════════════════════════════════")
    for r in old_records:
        log(f"  [{r['id']:3d}] fotos={r['fotos']:15s} | {r['descripcion']:20s} | {r['fecha_registro']}", indent=1)

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 2: Analizar fotos a migrar
    # ──────────────────────────────────────────────────────────────────────────
    old_fotos_list = sorted(OLD_FOTOS.iterdir()) if OLD_FOTOS.exists() else []
    old_fotos_files = [f for f in old_fotos_list if f.is_file()]

    log(f"")
    log(f"══════════════════════════════════════════════")
    log(f"  FOTOGRAFÍAS A MIGRAR: {len(old_fotos_files)}")
    log(f"══════════════════════════════════════════════")

    # Verificar qué fotos ya existen en destino
    NEW_FOTOS.mkdir(parents=True, exist_ok=True)
    ya_existen = sum(1 for f in old_fotos_files if (NEW_FOTOS / f.name).exists())
    nuevas = len(old_fotos_files) - ya_existen
    log(f"  Ya existen en destino: {ya_existen}")
    log(f"  Nuevas a copiar:       {nuevas}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 3: Verificar asociaciones foto ↔ registro
    # ──────────────────────────────────────────────────────────────────────────
    log(f"")
    log(f"══════════════════════════════════════════════")
    log(f"  VERIFICACIÓN ASOCIACIÓN FOTO ↔ REGISTRO")
    log(f"══════════════════════════════════════════════")

    # Construir mapa: seq_num → registro
    seq_to_registro = {}
    for r in old_records:
        for seq in range(r['numero_secuencia_inicio'], r['numero_secuencia_fin'] + 1):
            seq_to_registro[seq] = r

    fotos_sin_registro = []
    for f in old_fotos_files:
        m = re.match(r'^(\d+)_', f.name)
        if m:
            seq = int(m.group(1))
            if seq not in seq_to_registro:
                fotos_sin_registro.append(f.name)

    if fotos_sin_registro:
        log(f"  ⚠️  Fotos sin registro (cancelaciones): {len(fotos_sin_registro)}")
        for fn in fotos_sin_registro[:5]:
            log(f"     {fn}", indent=2)
        if len(fotos_sin_registro) > 5:
            log(f"     ... y {len(fotos_sin_registro)-5} más", indent=2)
    else:
        log(f"  ✅ Todas las fotos tienen registro asociado")

    covered_seqs = set(seq_to_registro.keys())
    all_seqs = {int(re.match(r'^(\d+)_', f.name).group(1))
                for f in old_fotos_files
                if re.match(r'^(\d+)_', f.name)}
    covered = all_seqs & covered_seqs
    log(f"  Secuencias únicas en fotos: {len(all_seqs)}")
    log(f"  Cubiertas por registro:     {len(covered)} ({100*len(covered)//len(all_seqs) if all_seqs else 0}%)")

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 4: Verificar duplicados con DB actual
    # ──────────────────────────────────────────────────────────────────────────
    log(f"")
    log(f"══════════════════════════════════════════════")
    log(f"  DETECCIÓN DE DUPLICADOS EN DB ACTUAL")
    log(f"══════════════════════════════════════════════")

    duplicados = []
    a_insertar = []
    for rec in old_records:
        new_cur.execute("""
            SELECT id FROM registros_defectos
            WHERE user_id=? AND fotos=? AND fecha_registro=?
        """, (rec['user_id'], rec['fotos'], rec['fecha_registro']))
        if new_cur.fetchone():
            duplicados.append(rec)
        else:
            a_insertar.append(rec)

    log(f"  Ya en DB actual (skip):   {len(duplicados)}")
    log(f"  Nuevos a insertar:        {len(a_insertar)}")

    # ──────────────────────────────────────────────────────────────────────────
    # RESUMEN
    # ──────────────────────────────────────────────────────────────────────────
    log(f"")
    log(f"══════════════════════════════════════════════")
    log(f"  RESUMEN FINAL")
    log(f"══════════════════════════════════════════════")
    log(f"  Registros:   {len(old_records)} encontrados → {len(a_insertar)} nuevos a insertar")
    log(f"  Fotografías: {len(old_fotos_files)} encontradas → {nuevas} nuevas a copiar")
    log(f"  Usuario:     8659391667 (Alberto.Chona) — se crea si no existe")
    log(f"  Fechas:      preservadas del original")
    log(f"  IDs:         NO preservados (evitar colisión)")
    log(f"")

    if DRY_RUN:
        log("=== FIN DRY-RUN. Sin cambios. Ejecuta sin --dry-run para migrar. ===")
        old_conn.close()
        new_conn.close()
        return

    # ══════════════════════════════════════════════════════════════════════════
    # EJECUCIÓN REAL
    # ══════════════════════════════════════════════════════════════════════════

    # ── PASO A: Crear usuario Alberto si no existe ───────────────────────────
    new_cur.execute(
        "SELECT id FROM calidad_perfilusuario WHERE telegram_user_id=?",
        (ALBERTO_ID,)
    )
    if not new_cur.fetchone():
        log("→ Creando usuario Alberto.Chona en auth_user...")
        new_cur.execute("""
            INSERT INTO auth_user
              (password, last_login, is_superuser, username, last_name,
               email, is_staff, is_active, date_joined, first_name)
            VALUES ('!migrated', NULL, 0, 'Alberto.Chona', 'Chona',
                    '', 0, 1, CURRENT_TIMESTAMP, 'Alberto')
        """)
        django_user_id = new_cur.lastrowid
        log(f"  auth_user.id = {django_user_id}")

        log("→ Creando perfil (turno=C, depto=IQA)...")
        new_cur.execute("""
            INSERT INTO calidad_perfilusuario
              (turno, telegram_user_id, usuario_id, departamento, rol)
            VALUES ('C', ?, ?, 'IQA', 'operador')
        """, (ALBERTO_ID, django_user_id))
        new_conn.commit()
        log("  ✅ Usuario creado")
    else:
        log("→ Usuario 8659391667 ya existe. Skip creación.")

    # ── PASO B: Insertar registros ───────────────────────────────────────────
    log(f"→ Insertando {len(a_insertar)} registros...")
    for rec in a_insertar:
        new_cur.execute("""
            INSERT INTO registros_defectos
              (fotos, modelo, linea, cantidad, responsable, descripcion,
               fecha_registro, user_id, turno, departamento,
               numero_secuencia_inicio, numero_secuencia_fin)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            rec['fotos'], rec['modelo'], rec['linea'],
            rec['cantidad'], rec['responsable'], rec['descripcion'],
            rec['fecha_registro'], rec['user_id'],
            rec['turno'], rec['departamento'],
            rec['numero_secuencia_inicio'], rec['numero_secuencia_fin']
        ))
        log(f"  ✅ Insertado: {rec['fotos']} | {rec['descripcion']} | {rec['fecha_registro']}", indent=1)
    new_conn.commit()

    # ── PASO C: Copiar fotos ─────────────────────────────────────────────────
    log(f"→ Copiando {nuevas} fotos nuevas...")
    copiadas = 0
    errores = 0
    for foto in old_fotos_files:
        dest = NEW_FOTOS / foto.name
        if dest.exists():
            continue
        try:
            shutil.copy2(foto, dest)
            copiadas += 1
        except Exception as e:
            log(f"  ERROR: {foto.name}: {e}")
            errores += 1

    log(f"  ✅ Copiadas: {copiadas} | Errores: {errores}")

    # ── PASO D: Verificación rápida post ────────────────────────────────────
    log("")
    log("→ Verificación post-migración...")
    new_cur.execute(
        "SELECT COUNT(*) FROM registros_defectos WHERE user_id=?", (ALBERTO_ID,)
    )
    total_reg = new_cur.fetchone()[0]
    total_fotos = sum(1 for f in NEW_FOTOS.iterdir() if f.is_file())

    new_cur.execute(
        "SELECT id FROM calidad_perfilusuario WHERE telegram_user_id=?", (ALBERTO_ID,)
    )
    perfil_ok = new_cur.fetchone() is not None

    log(f"  Perfil usuario:  {'✅' if perfil_ok else '❌'}")
    log(f"  Registros en DB: {total_reg} (esperado: ≥{len(old_records)})")
    log(f"  Fotos en disco:  {total_fotos} (esperado: ≥{len(old_fotos_files)})")

    ok = perfil_ok and total_reg >= len(old_records) and total_fotos >= len(old_fotos_files)
    log("")
    log(f"═══ {'✅ MIGRACIÓN EXITOSA' if ok else '❌ MIGRACIÓN CON ERRORES — REVISAR LOG'} ═══")

    old_conn.close()
    new_conn.close()


if __name__ == "__main__":
    run()
