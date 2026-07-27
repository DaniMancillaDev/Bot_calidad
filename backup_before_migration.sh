#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/danim/Escritorio/Labs/Python/Bot_calidad/backups/${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

echo "→ Backup DB..."
cp /home/danim/Escritorio/Labs/Python/Bot_calidad/bot_calidad.db \
   "${BACKUP_DIR}/bot_calidad_pre_migration.db"

echo "→ Backup fotos (hardlinks)..."
cp -al /home/danim/Escritorio/Labs/Python/Bot_calidad/media_files/fotos \
   "${BACKUP_DIR}/fotos_actuales" 2>/dev/null || \
cp -r /home/danim/Escritorio/Labs/Python/Bot_calidad/media_files/fotos \
   "${BACKUP_DIR}/fotos_actuales"

echo ""
echo "✅ Backup completo en: ${BACKUP_DIR}"
echo "   DB:    $(du -sh ${BACKUP_DIR}/bot_calidad_pre_migration.db | cut -f1)"
echo "   Fotos: $(find ${BACKUP_DIR}/fotos_actuales -type f | wc -l) archivos"
echo ""
echo "BACKUP_PATH=${BACKUP_DIR}" > /tmp/migration_backup_path.env
