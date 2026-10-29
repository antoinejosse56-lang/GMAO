#!/bin/bash
# Sauvegarde nocturne : copie vers le NAS les fichiers stockes dans Supabase (meme travail que la tache
# Windows "GMAO - Backup NAS"). A programmer une fois par jour (ex. 02h00) dans le Planificateur de taches DSM.
source "$(dirname "$0")/common.sh"
echo "=== $(date '+%F %T') ===" >> "$APP_DIR/logs/backup_to_nas.log"
timeout 14000 "$PY" "$APP_DIR/backup_to_nas.py" >> "$APP_DIR/logs/backup_to_nas.log" 2>&1
echo "[$(date '+%F %T')] backup_to_nas -> code $?" >> "$APP_DIR/logs/run_all.log"
exit 0
