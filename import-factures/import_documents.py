"""
Scan un dossier de documents generiques (DPE, attestation d'assurance,
diagnostic, annexe de bail, photo de compteur...) partage sur le NAS avec
Pauline (accessible aussi depuis un smartphone via SMB), uploade dans
Supabase Storage et enregistre dans `documents_a_valider` pour classification
manuelle (bien + type) dans le GMAO. Pipeline jumeau de import_devis.py, mais
sans extraction automatique : un document generique n'a pas de structure
"montant/entreprise" a deviner comme une facture ou un devis.

Idempotent : un fichier deja connu (meme chemin relatif au dossier surveille)
n'est jamais retraite, quel que soit son statut (en_attente / valide / rejete).

Une fois un document classe (bien + type choisis dans le GMAO, statut passe a
'valide'), ce script deplace l'original du dossier surveille vers le NAS
(SAVADUR ou Perso selon le bien) au prochain passage.

Usage :
    pip install -r requirements.txt
    copier .env.example en .env et remplir DOCUMENTS_WATCH_DIR / NAS_SAVADUR_PATH / NAS_PERSO_PATH
    python import_documents.py

A lancer periodiquement via le Planificateur de taches Windows, en parallele
de import_factures.py / import_devis.py (taches distinctes, memes dependances).
"""
import hashlib
import mimetypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from import_factures import LazyWordConverter, parse_filename_date, slugify_path
from nas_naming import dest_folder, dest_filename, is_savadur_for, unique_dest_path

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
WATCH_DIR = os.environ.get("DOCUMENTS_WATCH_DIR", "")
# Racines NAS (2 partages reseau distincts, partagees avec import_factures.py/
# import_devis.py/backup_to_nas.py) : une fois un document classe dans le
# GMAO, le fichier est deplace vers <NAS_SAVADUR_PATH ou NAS_PERSO_PATH>/
# <bien>/Documents/<motif>/ selon le bien concerne. Laisser les 2 vides pour
# desactiver l'archivage.
NAS_SAVADUR_PATH = os.environ.get("NAS_SAVADUR_PATH", "")
NAS_PERSO_PATH = os.environ.get("NAS_PERSO_PATH", "")
NAS_USER = os.environ.get("NAS_USER", "")
NAS_PASSWORD = os.environ.get("NAS_PASSWORD", "")

BUCKET = "documents-a-valider"
TABLE = "documents_a_valider"
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".odt"}

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
}


def log(msg):
    print(f"[import-documents] {msg}")


def connect_nas_share(unc_path):
    """Meme mecanisme que dans import_factures.py/import_devis.py/
    backup_to_nas.py (duplique, scripts independants) : authentifie la
    session Windows sur le partage NAS avant tout acces fichier."""
    if not unc_path:
        return
    result = subprocess.run(
        ["net", "use", unc_path, NAS_PASSWORD, f"/user:{NAS_USER}"],
        capture_output=True, text=True,
    )
    combined = (result.stdout + result.stderr).lower()
    if result.returncode != 0 and "déjà" not in combined and "already" not in combined and "multiple" not in combined:
        log(f"  ATTENTION connexion NAS ({unc_path}) : {result.stdout.strip()} {result.stderr.strip()}")


def fetch_known_rows() -> dict:
    """Pagine par lots de 1000 (meme plafond Supabase que dans import_factures)."""
    known = {}
    offset = 0
    page_size = 1000
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE}",
            params={"select": "chemin_relatif,statut,bien,asset_id,famille_id,type,date_document"},
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
    """Meme principe que import_factures.py/import_devis.py : reperer un
    document deja recu sous un autre nom (redepose par erreur, ou depose par
    Antoine ET Pauline separement)."""
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


def fetch_assets() -> dict:
    """Vehicules/bateaux notamment (assets.compte determine SAVADUR/Perso, cf.
    is_savadur_for) - necessaire quand un document est classe sur un vehicule
    plutot que sur un bien."""
    a = requests.get(f"{SUPABASE_URL}/rest/v1/assets", params={"select": "id,name,compte", "limit": 1000}, headers=HEADERS, timeout=30)
    a.raise_for_status()
    return {x["id"]: x for x in a.json()}


def fetch_famille() -> dict:
    """Membres de la famille - un document personnel (passeport, carte
    vitale...) n'a pas de notion SAVADUR/Perso, toujours archive cote Perso."""
    f = requests.get(f"{SUPABASE_URL}/rest/v1/famille", params={"select": "id,prenom,nom", "limit": 1000}, headers=HEADERS, timeout=30)
    f.raise_for_status()
    return {x["id"]: x for x in f.json()}


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
            "probablement depose 2 fois ou par Antoine et Pauline separement)"
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

    if ext in (".doc", ".docx", ".odt") and word_converter is not None:
        try:
            row["apercu_pdf_path"] = generate_pdf_preview(path, storage_path, word_converter)
        except Exception as e:
            log(f"  ATTENTION : conversion PDF echouee pour {chemin_relatif} : {e}")

    insert_row(row)
    log(f"  -> importe, en attente de classification (bien + type) dans le GMAO")


def archive_validated_files(watch_path: Path, known_rows: dict, assets: dict, famille: dict):
    """Deplace vers le NAS les fichiers dont le document correspondant a ete
    classe dans le GMAO (statut == 'valide' sur documents_a_valider). 3 cibles
    possibles, exactement une renseignee par ligne (bien / asset_id / famille_id) :
    - bien -> <NAS_SAVADUR_PATH ou NAS_PERSO_PATH>/<bien>/Documents/...
    - asset_id (vehicule/bateau) -> .../Véhicules/<nom>/Documents/... (compte
      SAVADUR/Perso de l'equipement, cf. assets.compte / is_savadur_for)
    - famille_id -> toujours cote Perso, .../Famille/<prenom nom>/Documents/...
    Meme convention de nommage que backup_to_nas.py/import_devis.py
    (nas_naming.py) : <annee>.<mois>.<Type>.<nom original>.ext."""
    if not NAS_SAVADUR_PATH or not NAS_PERSO_PATH:
        return
    moved = 0
    for p in sorted(watch_path.iterdir()):
        if not p.is_file() or p.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        info = known_rows.get(p.name)
        if not info or info.get("statut") != "valide":
            continue
        bien = info.get("bien")
        asset_id = info.get("asset_id")
        famille_id = info.get("famille_id")
        if bien:
            root = NAS_SAVADUR_PATH if is_savadur_for(bien) else NAS_PERSO_PATH
            dest_dir = dest_folder(root, "Documents", bien=bien)
        elif asset_id and assets.get(asset_id):
            asset = assets[asset_id]
            root = NAS_SAVADUR_PATH if is_savadur_for(None, asset_id, assets) else NAS_PERSO_PATH
            dest_dir = dest_folder(root, "Documents", equipment=asset["name"])
        elif famille_id and famille.get(famille_id):
            membre = famille[famille_id]
            nom_complet = f"{membre.get('prenom') or ''} {membre.get('nom') or ''}".strip() or "Sans nom"
            dest_dir = dest_folder(NAS_PERSO_PATH, "Documents", equipment=nom_complet, equipment_kind="Famille")
        else:
            continue
        new_name = dest_filename(p.suffix, info.get("date_document"), info.get("type"), p.stem, fallback="Document")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = unique_dest_path(dest_dir, new_name)
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
        sys.exit("DOCUMENTS_WATCH_DIR manquant dans .env")

    connect_nas_share(NAS_SAVADUR_PATH)
    connect_nas_share(NAS_PERSO_PATH)

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

    if NAS_SAVADUR_PATH and NAS_PERSO_PATH:
        assets = fetch_assets()
        famille = fetch_famille()
        archive_validated_files(watch_path, known_rows, assets, famille)


if __name__ == "__main__":
    main()
