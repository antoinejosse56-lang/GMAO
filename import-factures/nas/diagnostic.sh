#!/bin/bash
# Diagnostic : affiche quel Python est utilise par les imports et si les modules y sont visibles.
# A lancer depuis le Planificateur de taches DSM (ou en changeant temporairement le script de la tache
# "GMAO - installation"), puis lire logs/diagnostic.log.
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HERE/logs"
OUT="$HERE/logs/diagnostic.log"
{
  echo "=== $(date '+%F %T') diagnostic ==="
  echo "utilisateur : $(whoami) | dossier : $HERE"
  echo "PATH=$PATH"
  echo "--- contenu du dossier"; ls -la "$HERE" 2>&1 | head -30
  echo "--- venv/"; ls -la "$HERE/venv/bin" 2>&1 | head -15; cat "$HERE/venv/pyvenv.cfg" 2>&1
  echo "--- lib/ (debut)"; ls "$HERE/lib" 2>&1 | head -15
  echo "--- interpreteurs trouves"
  for c in python3 python3.9 python3.10 python3.11 python3.12 python; do echo "$c -> $(command -v $c 2>&1)"; done
  ls -d /var/packages/Python3*/target/bin/python3* 2>&1 | head
  echo "--- environnement tel que le verront les imports"
  (
    source "$HERE/common.sh"
    echo "PY=$PY"
    echo "PYTHONPATH=$PYTHONPATH"
    "$PY" -c "import sys; print(sys.executable); print(sys.version); print(sys.path)" 2>&1
    for m in requests dotenv pdfplumber docx; do
      "$PY" -c "import $m; print('$m OK ->', getattr($m,'__file__','?'))" 2>&1 | tail -1
    done
    echo "--- pip list (extrait)"
    "$PY" -m pip list 2>&1 | head -30
  )
  echo "--- fichier .env : $( [ -f "$HERE/.env" ] && echo present || echo ABSENT ) ($(wc -c < "$HERE/.env" 2>/dev/null) octets)"
  echo "=== fin ==="
} > "$OUT" 2>&1
cat "$OUT"
exit 0
