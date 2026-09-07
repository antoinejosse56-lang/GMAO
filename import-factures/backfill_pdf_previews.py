"""
Genere un apercu PDF pour les factures deja importees au format .doc/.docx/.odt
qui n'en ont pas encore (colonne apercu_pdf_path vide) - ajoute apres coup,
l'import initial ne le faisait pas pour ces fichiers-la. Necessite Microsoft
Word installe (conversion via COM, meme mecanisme que import_factures.py).

Va chercher les fichiers originaux en local (pas de re-telechargement depuis
Supabase Storage) : donne le meme dossier source que celui utilise au moment
de l'import (extraction mbox ou WATCH_DIR).

Usage :
    python backfill_pdf_previews.py "D:\\Antoine\\import-factures-mbox\\perso"
    python backfill_pdf_previews.py "D:\\Antoine\\import-factures-mbox\\savadur"
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from import_factures import LazyWordConverter, generate_pdf_preview

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "factures_a_valider"
WORD_EXTS = (".doc", ".docx", ".odt")

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
}


def log(msg):
    print(f"[backfill-pdf] {msg}")


def fetch_rows_sans_apercu():
    """Pagine par lots de 1000 (meme plafond Supabase que fetch_known_rows)."""
    rows = []
    offset = 0
    page_size = 1000
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE}",
            params={"select": "id,chemin_relatif,storage_path", "apercu_pdf_path": "is.null"},
            headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+page_size-1}"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return [r for r in rows if r["chemin_relatif"].lower().endswith(WORD_EXTS)]


def update_apercu_pdf_path(row_id: str, pdf_storage_path: str):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        params={"id": f"eq.{row_id}"},
        headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json={"apercu_pdf_path": pdf_storage_path},
        timeout=30,
    )
    resp.raise_for_status()


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage : python backfill_pdf_previews.py "<dossier_source>"')
    source_dir = Path(sys.argv[1])
    if not source_dir.is_dir():
        sys.exit(f"Dossier introuvable : {source_dir}")
    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans .env")

    rows = fetch_rows_sans_apercu()
    log(f"{len(rows)} fichier(s) Word/ODT sans apercu PDF (toutes sources confondues).")

    converter = LazyWordConverter()
    done, absent, erreurs = 0, 0, 0
    try:
        for row in rows:
            local_path = source_dir / row["chemin_relatif"]
            if not local_path.is_file():
                absent += 1
                continue
            storage_path = row["storage_path"] or row["chemin_relatif"]
            try:
                pdf_storage_path = generate_pdf_preview(local_path, storage_path, converter)
                update_apercu_pdf_path(row["id"], pdf_storage_path)
                done += 1
                log(f"  OK : {row['chemin_relatif']}")
            except Exception as e:
                erreurs += 1
                log(f"  ERREUR sur {row['chemin_relatif']} : {e}")
    finally:
        converter.close()

    log(f"Termine. {done} apercu(s) genere(s), {absent} introuvable(s) dans {source_dir}, {erreurs} erreur(s).")


if __name__ == "__main__":
    main()
