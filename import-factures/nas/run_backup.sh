#!/bin/bash
# Sauvegarde nocturne : tables de la base puis fichiers stockes dans Supabase, copies verifiees sur le NAS,
# email d'alerte si quelque chose manque. A programmer une fois par jour (ex. 02h00) dans le Planificateur DSM.

# Si le script s'arrete avant la fin (partages introuvables...), prevenir quand meme
FINI=""
trap '[ -z "$FINI" ] && [ -n "$PY" ] && "$PY" "$APP_DIR/alerte_sauvegarde.py" 1 1 >> "$APP_DIR/logs/alerte_sauvegarde.log" 2>&1' EXIT

source "$(dirname "$0")/common.sh"
# 1) les tables de la base (loyers, locataires, saisies...) : en premier, c'est rapide et le plus precieux
echo "=== $(date '+%F %T') ===" >> "$APP_DIR/logs/backup_base.log"
timeout 1800 "$PY" "$APP_DIR/backup_base.py" >> "$APP_DIR/logs/backup_base.log" 2>&1
code_base=$?
echo "[$(date '+%F %T')] backup_base -> code $code_base" >> "$APP_DIR/logs/run_all.log"
# 2) les fichiers (documents, factures, photos)
echo "=== $(date '+%F %T') ===" >> "$APP_DIR/logs/backup_to_nas.log"
timeout 14000 "$PY" "$APP_DIR/backup_to_nas.py" >> "$APP_DIR/logs/backup_to_nas.log" 2>&1
code_fichiers=$?
echo "[$(date '+%F %T')] backup_to_nas -> code $code_fichiers" >> "$APP_DIR/logs/run_all.log"
# 3) email seulement si l'une des deux n'est pas complete
"$PY" "$APP_DIR/alerte_sauvegarde.py" "$code_base" "$code_fichiers" >> "$APP_DIR/logs/alerte_sauvegarde.log" 2>&1
echo "[$(date '+%F %T')] alerte_sauvegarde -> code $?" >> "$APP_DIR/logs/run_all.log"
FINI=1
exit 0
