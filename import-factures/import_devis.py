"""
Scan le dossier de devis (local ou reseau, distinct du dossier factures), tente
une extraction basique (entreprise/montant/date), uploade dans Supabase Storage
et enregistre dans `devis_a_valider` pour rattachement a un bon de travaux et
validation manuelle dans le GMAO. Pipeline jumeau de import_factures.py, mais
separe : dossier different, table et bucket dedies - un devis n'est pas une
piece comptable a transmettre au comptable, juste une reference interne.

Permet de comparer plusieurs devis pour un meme bon de travaux (plusieurs
artisans consultes) : chaque devis valide devient une ligne dans la table
`devis`, et un seul est marque "retenu" depuis le GMAO.

Idempotent : un fichier deja connu (meme chemin relatif au dossier surveille)
n'est jamais retraite, quel que soit son statut (en_attente / valide / rejete).

Usage :
    pip install -r requirements.txt
    copier .env.example en .env et remplir DEVIS_WATCH_DIR / DEVIS_ARCHIVE_DIR
    python import_devis.py

A lancer periodiquement via le Planificateur de taches Windows, en parallele
de import_factures.py (deux taches distinctes, memes dependances).
"""
import hashlib
import mimetypes
import os
import shutil
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from import_factures import (
    LazyWordConverter,
    extract_docx_text,
    extract_odt_text,
    extract_pdf_text,
    guess_date_facture,
    guess_entreprise,
    guess_montant_ttc,
    parse_filename_date,
    sanitize_folder_name,
    slugify_path,
)

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
WATCH_DIR = os.environ.get("DEVIS_WATCH_DIR", "")
# Optionnel : si renseigne, les fichiers dont le devis a ete valide dans le GMAO
# sont deplaces vers ARCHIVE_DIR/<savadur|perso>/<bien>/<zone>/<motif>/.
ARCHIVE_DIR = os.environ.get("DEVIS_ARCHIVE_DIR", "")

BUCKET = "devis-a-valider"
TABLE = "devis_a_valider"
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".odt"}

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
}


def log(msg):
    print(f"[import-devis] {msg}")


def fetch_known_rows() -> dict:
    """Pagine par lots de 1000 (meme plafond Supabase que dans import_factures)."""
    known = {}
    offset = 0
    page_size = 1000
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE}",
            params={"select": "chemin_relatif,statut,bien,motif,entreprise,montant_ttc,date_devis"},
            headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+page_size-1}"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        for row in page:
            known[row["chemin_relatif"]] = row
        if len(page) < page_size:
            break
        offset += page_size
    return known


def fetch_known_hashes() -> set:
    """Meme principe que dans import_factures.py : reperer un devis deja recu
    sous un autre nom de fichier (2 boites mail, depot manuel + re-scan Gmail)."""
    hashes = set()
    offset = 0
    page_size = 1000
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE}",
            params={"select": "content_hash"},
            headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+page_size-1}"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        for row in page:
            if row.get("content_hash"):
                hashes.add(row["content_hash"])
        if len(page) < page_size:
            break
        offset += page_size
    return hashes


def archive_path_for(bien: str, motif: str) -> Path:
    """Meme logique que archive_path_for dans import_factures.py, dupliquee ici
    pour utiliser DEVIS_ARCHIVE_DIR au lieu de ARCHIVE_DIR (constante differente,
    pas reutilisable telle quelle par import). Racine commune avec les factures
    (meme arborescence <compte>/<type>/... sous D:/Antoine/GMAO)."""
    parts = [p.strip() for p in (bien or "").split(" - ") if p.strip()]
    compte = "PERSO" if parts and "dubail" not in parts[0].lower() else "SAVADUR"
    folder = Path(ARCHIVE_DIR) / compte / "Devis"
    if parts:
        for p in parts:
            folder = folder / sanitize_folder_name(p)
    else:
        folder = folder / "Non classe"
    if motif:
        folder = folder / sanitize_folder_name(motif)
    return folder


def archive_filename_for(original_ext: str, entreprise: str, date_devis: str, description: str) -> str:
    parts = [
        sanitize_folder_name(entreprise) if entreprise else "Devis",
        date_devis or "date-inconnue",
        sanitize_folder_name(description) if description else "Devis",
    ]
    return ".".join(parts) + original_ext


def generate_pdf_preview(path: Path, storage_path: str, word_converter: LazyWordConverter):
    pdf_local = path.with_suffix(path.suffix + ".apercu.pdf")
    try:
        word_converter.convert(path, pdf_local)
        pdf_bytes = pdf_local.read_bytes()
    finally:
        if pdf_local.exists():
            pdf_local.unlink()
    pdf_storage_path = storage_path.rsplit(".", 1)[0] + "_apercu.pdf"
    upload_to_storage(pdf_storage_path, pdf_bytes, "application/pdf")
    return pdf_storage_path


def upload_to_storage(storage_path: str, content: bytes, content_type: str):
    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}",
        headers={**HEADERS, "Content-Type": content_type, "x-upsert": "true"},
        data=content,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"upload storage echoue ({resp.status_code}) : {resp.text[:300]}")


def insert_row(row: dict):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
        json=row,
        timeout=30,
    )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"insert {TABLE} echoue ({resp.status_code}) : {resp.text[:300]}")


def process_file(path: Path, chemin_relatif: str, word_converter: LazyWordConverter = None, known_hashes: set = None):
    log(f"Nouveau fichier : {chemin_relatif}")
    ext = path.suffix.lower()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    storage_path = slugify_path(chemin_relatif)

    row = {
        "fichier_nom": path.name,
        "fichier_date": parse_filename_date(path.name).isoformat() if parse_filename_date(path.name) else None,
        "chemin_relatif": chemin_relatif,
        "storage_path": None,
        "apercu_pdf_path": None,
        "entreprise": None,
        "montant_ttc": None,
        "date_devis": None,
        "erreur_extraction": None,
        "content_hash": None,
    }

    try:
        content = path.read_bytes()
    except OSError as e:
        row["erreur_extraction"] = f"Fichier illisible sur le disque : {e}"
        insert_row(row)
        return

    content_hash = hashlib.sha256(content).hexdigest()
    row["content_hash"] = content_hash
    is_duplicate = known_hashes is not None and content_hash in known_hashes
    if known_hashes is not None:
        known_hashes.add(content_hash)

    if is_duplicate:
        row["erreur_extraction"] = (
            "Doublon detecte automatiquement (meme contenu qu'un fichier deja recu, "
            "probablement recu sur les 2 boites mail ou deja depose a la main)"
        )
        row["statut"] = "rejete"
        try:
            upload_to_storage(storage_path, content, content_type)
            row["storage_path"] = storage_path
        except Exception as e:
            row["erreur_extraction"] += f" (upload echoue : {e})"
        insert_row(row)
        log(f"  -> doublon detecte, rejete automatiquement (hash {content_hash[:8]}...)")
        return

    try:
        upload_to_storage(storage_path, content, content_type)
        row["storage_path"] = storage_path
    except Exception as e:
        row["erreur_extraction"] = f"Echec upload vers Supabase Storage : {e}"
        insert_row(row)
        return

    text = None
    try:
        if ext == ".pdf":
            text = extract_pdf_text(path)
        elif ext == ".docx":
            text = extract_docx_text(path)
        elif ext == ".odt":
            text = extract_odt_text(path)
        elif ext == ".doc":
            row["erreur_extraction"] = (
                "Format .doc (Word 97-2003) non pris en charge pour l'extraction automatique — "
                "saisie manuelle necessaire."
            )
        if text is not None:
            row["montant_ttc"] = guess_montant_ttc(text)
            row["entreprise"] = guess_entreprise(text)
            row["date_devis"] = guess_date_facture(text)
            if not text.strip():
                row["erreur_extraction"] = "Aucun texte extrait — saisie manuelle necessaire."
    except Exception as e:
        row["erreur_extraction"] = f"Extraction du texte echouee (fichier peut-etre corrompu) : {e}"
    # Pour les images (.jpg/.jpeg/.png) : pas d'extraction (comme pour les factures),
    # entreprise/montant restent vides pour saisie manuelle - ce n'est pas une erreur.

    if ext in (".doc", ".docx", ".odt") and word_converter is not None:
        try:
            row["apercu_pdf_path"] = generate_pdf_preview(path, storage_path, word_converter)
        except Exception as e:
            log(f"  ATTENTION : conversion PDF echouee pour {chemin_relatif} : {e}")

    insert_row(row)
    log(f"  -> importe (entreprise={row['entreprise']!r}, montant_ttc={row['montant_ttc']!r}, date_devis={row['date_devis']!r})")


def archive_validated_files(watch_path: Path, known_rows: dict):
    """Deplace vers ARCHIVE_DIR les fichiers dont le devis correspondant a ete
    valide dans le GMAO (statut == 'valide' sur devis_a_valider). Renomme au
    format 'NOM_ENTREPRISE.DATE.motif.ext'."""
    if not ARCHIVE_DIR:
        return
    moved = 0
    for p in sorted(watch_path.iterdir()):
        if not p.is_file() or p.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        info = known_rows.get(p.name)
        if not info or info.get("statut") != "valide":
            continue
        dest_dir = archive_path_for(info.get("bien"), info.get("motif"))
        dest_dir.mkdir(parents=True, exist_ok=True)
        new_name = archive_filename_for(p.suffix, info.get("entreprise"), info.get("date_devis"), info.get("motif"))
        dest = dest_dir / new_name
        if dest.exists():
            log(f"  ARCHIVAGE ignore (deja present a destination) : {p.name} -> {new_name}")
            continue
        try:
            shutil.move(str(p), str(dest))
            moved += 1
            log(f"Archive : {p.name} -> {dest}")
        except OSError as e:
            log(f"  ERREUR archivage {p.name} : {e}")
    if moved:
        log(f"{moved} fichier(s) archive(s).")


def main():
    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans .env")
    if not WATCH_DIR:
        sys.exit("DEVIS_WATCH_DIR manquant dans .env")

    watch_path = Path(WATCH_DIR)
    if not watch_path.is_dir():
        sys.exit(f"Dossier introuvable ou inaccessible : {WATCH_DIR}")

    known_rows = fetch_known_rows()
    known_hashes = fetch_known_hashes()
    log(f"{len(known_rows)} fichier(s) deja connu(s) en base ({len(known_hashes)} empreinte(s) de contenu).")

    candidates = [
        p for p in sorted(watch_path.iterdir())
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    log(f"{len(candidates)} fichier(s) eligible(s) trouve(s) dans {WATCH_DIR}")

    word_converter = LazyWordConverter()
    nouveaux = 0
    try:
        for p in candidates:
            chemin_relatif = p.name
            if chemin_relatif in known_rows:
                continue
            nouveaux += 1
            try:
                process_file(p, chemin_relatif, word_converter, known_hashes)
            except Exception as e:
                log(f"  ERREUR inattendue sur {p.name} : {e}")
    finally:
        word_converter.close()

    log(f"Termine. {nouveaux} nouveau(x) fichier(s) traite(s).")

    if ARCHIVE_DIR:
        archive_validated_files(watch_path, known_rows)


if __name__ == "__main__":
    main()
