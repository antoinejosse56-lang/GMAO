#!/bin/bash
# Variables communes aux scripts NAS (source par run_all.sh, run_backup.sh, setup_nas.sh).
# Les chemins des partages sont detectes automatiquement (volume1, volume2...) : les variables
# exportees ici ont priorite sur celles du fichier .env (python-dotenv ne les ecrase pas).

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR" || exit 1
mkdir -p "$APP_DIR/logs"

find_share() {
  local v
  for v in ${NAS_VOLUMES:-/volume1 /volume2 /volume3 /volume4 /volumeUSB1/usbshare}; do
    if [ -d "$v/$1" ]; then echo "$v/$1"; return 0; fi
  done
  return 1
}

# Python du paquet "Python 3.x" de Synology (venv cree par setup_nas.sh en priorite)
if [ -x "$APP_DIR/venv/bin/python" ]; then
  PY="$APP_DIR/venv/bin/python"
else
  PY=""
  for c in python3 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; break; fi
  done
  if [ -z "$PY" ]; then
    PY="$(ls /var/packages/Python3*/target/bin/python3 2>/dev/null | tail -1)"
  fi
  # installation "sans venv" (dossier lib/) si le venv n'a pas pu etre cree
  [ -d "$APP_DIR/lib" ] && export PYTHONPATH="$APP_DIR/lib:${PYTHONPATH:-}"
fi

export NAS_SAVADUR_PATH="$(find_share 'Documents GMAO Savadur')"
export NAS_PERSO_PATH="$(find_share 'Documents GMAO Perso')"
if [ -z "$NAS_SAVADUR_PATH" ] || [ -z "$NAS_PERSO_PATH" ]; then
  echo "[nas] ERREUR : partages 'Documents GMAO Savadur' / 'Documents GMAO Perso' introuvables sous /volumeN" >&2
  exit 1
fi
# Dossiers de depot surveilles (les factures recues par mail arrivent dans "Factures a traiter")
export WATCH_DIR="$NAS_PERSO_PATH/_En_cours/Factures a traiter"
export DEVIS_WATCH_DIR="$NAS_PERSO_PATH/_En_cours/Devis a traiter"
export DOCUMENTS_WATCH_DIR="$NAS_PERSO_PATH/_En_cours/Documents a importer"
mkdir -p "$WATCH_DIR" "$DEVIS_WATCH_DIR" "$DOCUMENTS_WATCH_DIR"
export PYTHONIOENCODING=utf-8
export TZ="${TZ:-Europe/Paris}"
