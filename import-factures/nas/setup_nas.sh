#!/bin/bash
# Installation (ou reparation) : cree l'environnement Python et installe les dependances.
# A lancer depuis le Planificateur de taches DSM (tache "script defini par l'utilisateur", utilisateur root).
# Peut etre relance sans risque : un environnement incomplet ou cree avec un autre Python est refait.
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/logs"
echo "[$(date '+%F %T')] setup_nas.sh demarre (utilisateur: $(whoami), dossier: $HERE)" >> "$HERE/logs/setup_nas.log"
source "$HERE/common.sh"
OUT="$APP_DIR/logs/setup_nas.log"
{
  echo "=== $(date '+%F %T') installation ==="
  echo "Python de base : $BASE_PY ($("$BASE_PY" --version 2>&1))"
  MODULES="import requests, pdfplumber, dotenv, docx"
  PYV() { "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null; }
  if [ -x "$APP_DIR/venv/bin/python" ]; then
    if [ "$(PYV "$APP_DIR/venv/bin/python")" != "$(PYV "$BASE_PY")" ] || ! "$APP_DIR/venv/bin/python" -c "$MODULES" 2>/dev/null; then
      echo "environnement existant incomplet ou d'une autre version de Python : il est refait"
      rm -rf "$APP_DIR/venv"
    fi
  fi
  if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    "$BASE_PY" -m venv "$APP_DIR/venv" || echo "venv indisponible - installation dans lib/"
  fi
  if [ -x "$APP_DIR/venv/bin/python" ]; then
    TEST="$APP_DIR/venv/bin/python"
    "$TEST" -m pip install --upgrade pip
    "$TEST" -m pip install --prefer-binary -r "$APP_DIR/requirements-nas.txt"
  else
    TEST="$BASE_PY"
    "$TEST" -m pip install --upgrade --target "$APP_DIR/lib" -r "$APP_DIR/requirements-nas.txt"
    export PYTHONPATH="$APP_DIR/lib:${PYTHONPATH:-}"
  fi
  echo "--- verification des modules (Python $(PYV "$TEST")) ---"
  if "$TEST" -c "$MODULES; print('modules OK')"; then
    RESULT="INSTALLATION REUSSIE"
  else
    RESULT="ECHEC : modules manquants - lire les messages de pip ci-dessus"
  fi
  echo "--- partages detectes ---"
  echo "Savadur : $NAS_SAVADUR_PATH"
  echo "Perso   : $NAS_PERSO_PATH"
  [ -f "$APP_DIR/.env" ] && echo ".env present" || echo "ATTENTION : fichier .env absent"
  echo "=== $RESULT ==="
} >> "$OUT" 2>&1
tail -30 "$OUT"
exit 0
