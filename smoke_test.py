import os
import sys

def run_tests():
    print("Iniciando pruebas de humo (Smoke Tests)...\n")
    
    # 1. Test .env reading for Django
    print("[1/4] Probando config Django...")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.config.settings')
    try:
        from web.config import settings
        print("  OK: Settings cargado.")
        print(f"  OK: DEBUG = {settings.DEBUG}")
        print(f"  OK: DB path = {settings.DATABASES['default']['NAME']}")
    except Exception as e:
        print(f"  ERROR: No se pudo cargar settings de Django: {e}")
        return False

    # 2. Test Logging
    print("\n[2/4] Probando Logging...")
    try:
        from shared.config.logging_config import setup_logging
        import logging
        setup_logging()
        logger = logging.getLogger('test')
        logger.info("Test de log OK.")
        if os.path.exists('bot.log'):
            print("  OK: bot.log creado/accesible.")
        else:
            print("  ERROR: bot.log no fue creado.")
            return False
    except Exception as e:
        print(f"  ERROR: Fallo en el modulo de logging: {e}")
        return False

    # 3. Test Database
    print("\n[3/4] Probando Base de Datos e indices...")
    try:
        from database import DatabaseManager
        db = DatabaseManager('bot_calidad.db')
        db.init_database()
        
        # Verificar indices
        import sqlite3
        conn = sqlite3.connect('bot_calidad.db')
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
        indexes = [row[0] for row in c.fetchall()]
        conn.close()
        
        if 'idx_registros_turno_depto' in indexes and 'idx_calidad_perfil_telegram' in indexes:
            print("  OK: Base de datos inicializada y nuevos indices detectados.")
        else:
            print("  ERROR: Faltan los indices de rendimiento.")
            return False
    except Exception as e:
        print(f"  ERROR: Base de datos fallo: {e}")
        return False

    # 4. Test Bot Imports
    print("\n[4/4] Probando imports del bot...")
    try:
        from bot.handlers.registro_handler import create_start, create_guardar_foto, create_procesar_respuesta
        from bot.handlers.consulta_handler import create_reporte
        print("  OK: Handlers factory importados correctamente.")
    except Exception as e:
        print(f"  ERROR: Imports del bot fallaron: {e}")
        return False
        
    print("\n[OK] TODAS LAS PRUEBAS PASARON. SISTEMA LISTO PARA PRODUCCION.")
    return True

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
