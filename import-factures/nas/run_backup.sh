#!/bin/bash
# Sauvegarde nocturne : copie vers le NAS les fichiers stockes dans Supabase (meme travail que la tache
# Windows "GMAO - Backup NAS"). A programmer une fois par jour (ex. 02h00) dans le Planificateur de taches DSM.
source "$(dirname "$0")/common.sh"
# 1) les tables de la base (loyers, locataires, saisies...) : en premier, c'est rapide et le plus precieux
timeout 1800 "$PY" "$APP_DIR/backup_base.py" >> "$APP_DIR/logs/backup_base.log" 2>&1
code=$?
echo "[$(date '+%F %T')] backup_base -> code $code" >> "$APP_DIR/logs/run_all.log"
# 2) les fichiers (documents, factures, photos)
echo "=== $(date '+%F %T') ===" >> "$APP_DIR/logs/backup_to_nas.log"
timeout 14000 "$PY" "$APP_DIR/backup_to_nas.py" >> "$APP_DIR/logs/backup_to_nas.log" 2>&1
code=$?
echo "[$(date '+%F %T')] backup_to_nas -> code $code" >> "$APP_DIR/logs/run_all.log"
exit 0
