#!/bin/bash
# Lance tous les imports horaires dans le meme ordre que les taches planifiees Windows :
# courrier -> factures -> devis -> releves -> documents -> synchro calendrier.
# A programmer toutes les heures dans le Planificateur de taches DSM (script defini par l'utilisateur).
source "$(dirname "$0")/common.sh"

# Verrou : si un passage precedent tourne encore, on n'en lance pas un second (verrou perime apres 3 h)
LOCK="$APP_DIR/.lock_run_all.d"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then
    rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" 2>/dev/null || exit 0
  else
    echo "[$(date '+%F %T')] passage precedent encore en cours - abandon" >> "$APP_DIR/logs/run_all.log"; exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

echo "[$(date '+%F %T')] debut du passage" >> "$APP_DIR/logs/run_all.log"
for job in import_mailbox import_factures import_devis import_releve import_documents sync_gamme_calendar; do
  echo "=== $(date '+%F %T') ===" >> "$APP_DIR/logs/$job.log"
  timeout 1500 "$PY" "$APP_DIR/$job.py" >> "$APP_DIR/logs/$job.log" 2>&1
  code=$?
  echo "[$(date '+%F %T')] $job -> code $code" >> "$APP_DIR/logs/run_all.log"
done
echo "[$(date '+%F %T')] fin du passage" >> "$APP_DIR/logs/run_all.log"

# Evite que les journaux grossissent indefiniment (garde les 3000 dernieres lignes de chacun)
for f in "$APP_DIR"/logs/*.log; do
  [ "$(wc -l < "$f")" -gt 6000 ] && tail -n 3000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done
exit 0
