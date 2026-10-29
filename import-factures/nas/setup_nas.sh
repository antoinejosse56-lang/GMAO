#!/bin/bash
# Installation unique : cree l'environnement Python et installe les dependances.
# A lancer UNE FOIS depuis le Planificateur de taches DSM (tache "script defini par l'utilisateur",
# utilisateur root, cocher "Envoyer les details de l'execution par e-mail" si vous voulez le resultat).
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/logs"
echo "[$(date '+%F %T')] setup_nas.sh demarre (utilisateur: $(whoami), dossier: $HERE)" >> "$HERE/logs/setup_nas.log"
source "$HERE/common.sh"
OUT="$APP_DIR/logs/setup_nas.log"
{
  echo "=== $(date '+%F %T') installation ==="
  echo "Python utilise : $PY"
  "$PY" --version
  if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    "$PY" -m venv "$APP_DIR/venv" || echo "venv indisponible - installation dans lib/"
  fi
  if [ -x "$APP_DIR/venv/bin/python" ]; then
    "$APP_DIR/venv/bin/python" -m pip install --upgrade pip
    "$APP_DIR/venv/bin/python" -m pip install -r "$APP_DIR/requirements-nas.txt"
    TEST="$APP_DIR/venv/bin/python"
  else
    "$PY" -m pip install --upgrade --target "$APP_DIR/lib" -r "$APP_DIR/requirements-nas.txt"
    export PYTHONPATH="$APP_DIR/lib:${PYTHONPATH:-}"
    TEST="$PY"
  fi
  echo "--- verification des modules ---"
  "$TEST" -c "import requests, pdfplumber, dotenv, docx; print('modules OK')"
  echo "--- partages detectes ---"
  echo "Savadur : $NAS_SAVADUR_PATH"
  echo "Perso   : $NAS_PERSO_PATH"
  echo "Factures a traiter : $WATCH_DIR"
  ls -ld "$NAS_SAVADUR_PATH" "$NAS_PERSO_PATH" "$WATCH_DIR"
  [ -f "$APP_DIR/.env" ] && echo ".env present" || echo "ATTENTION : fichier .env absent"
  echo "=== fin ==="
} >> "$OUT" 2>&1
tail -25 "$OUT"
exit 0
