"""
Sauvegarde tous les fichiers des 3 buckets Supabase Storage (documents-
locataires, factures-a-valider, devis-a-valider) vers le NAS, repartis dans
2 partages reseau distincts selon qu'un fichier concerne SAVADUR/Dubail ou
tout le reste (perso) - Supabase reste le stockage principal/en ligne de
l'application, ce script ne fait qu'une copie de sauvegarde en plus.

Idempotent : un fichier deja present a destination (meme chemin) n'est
jamais retelecharge - a relancer periodiquement (Planificateur de taches
Windows), comme les autres scripts de ce dossier. Les fichiers ne sont
jamais modifies une fois uploades cote appli, donc pas besoin de comparer
les tailles/dates pour detecter un changement.

La repartition SAVADUR/Dubail vs Perso est deduite des memes regles que
l'application (champ `compte` quand il existe, sinon nom du bien/logement
contenant "dubail") :
  - documents-locataires/identite/<tenant_id>/...   -> locataire (logement)
  - documents-locataires/assurance/<tenant_id>/...  -> locataire (logement)
  - documents-locataires/edl/<edl_id>/...           -> etat des lieux (bien)
  - documents-locataires/bt/<wo_id>/...             -> bon de travaux (asset/topo)
  - documents-locataires/vehicules/<asset_id>/...   -> vehicule (compte/nom)
  - documents-locataires/factures/<owner_id>/...    -> facture liee (drive_url matche)
  - documents-locataires/biens/<slug>/...           -> nom du bien (slug)
  - factures-a-valider/<...>                        -> ligne factures_a_valider.bien
  - devis-a-valider/<...>                           -> ligne devis_a_valider.bien
Un fichier dont l'origine ne peut pas etre determinee part par defaut cote
Perso (categorie residuelle - seul SAVADUR/Dubail est un cas identifie).

Usage :
    pip install -r requirements.txt
    copier .env.example en .env et remplir les valeurs NAS_* (voir commentaire)
    python backup_to_nas.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
NAS_SAVADUR_PATH = os.environ.get("NAS_SAVADUR_PATH", "")
NAS_PERSO_PATH = os.environ.get("NAS_PERSO_PATH", "")
NAS_USER = os.environ.get("NAS_USER", "")
NAS_PASSWORD = os.environ.get("NAS_PASSWORD", "")

HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
BUCKETS = ["documents-locataires", "factures-a-valider", "devis-a-valider"]

# Execution non surveillee (tache planifiee) : les blips reseau passagers (DNS,
# Wi-Fi, NAS qui repond avec un temps de retard) ne doivent jamais faire
# planter tout le script - seule une vraie panne durable doit remonter en
# erreur. Retries automatiques sur toute requete HTTP (Supabase), + reprise
# manuelle sur l'ecriture NAS (voir write_with_retry).
SESSION = requests.Session()
_retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
SESSION.mount("https://", HTTPAdapter(max_retries=_retry))
SESSION.mount("http://", HTTPAdapter(max_retries=_retry))
requests = SESSION  # tous les appels requests.get/post ci-dessous passent par la session avec retries


def log(msg):
    print(f"[backup-nas] {msg}")


def dubail_filter(s):
    return "dubail" in (s or "").lower()


def sanitize_filename(name):
    """Nettoie un nom pour un fichier/dossier Windows valide, en gardant la
    lisibilite (accents/espaces conserves, seuls les caracteres interdits sautent) -
    meme convention que sanitize_folder_name() dans import_factures.py."""
    import re as _re
    cleaned = _re.sub(r'[<>:"/\\|?*]', "_", name or "").strip().rstrip(". ")
    return cleaned or "Non classe"


def validated_dest_folder(root, kind, bien):
    """<root>/<bien decompose en sous-dossiers>/<Factures|Devis|Documents> - le
    bien/la zone d'abord puis la categorie en dernier niveau, pour retrouver
    facilement tout ce qui concerne un logement (factures, devis, documents
    confondus) sans avoir a fouiller 3 arborescences separees."""
    folder = Path(root)
    parts = [p.strip() for p in (bien or "").split(" - ") if p.strip()]
    if parts:
        for p in parts:
            folder = folder / sanitize_filename(p)
    else:
        folder = folder / "Non classe"
    return folder / kind


def year_month(date_str):
    return date_str[:4] + "." + date_str[5:7] if date_str and len(date_str) >= 7 else "date-inconnue"


def validated_dest_filename(ext, bien, date_str, entreprise, description):
    """'<BIEN>.<annee>.<mois>.<Entreprise>.<Description><ext>' - le bien complet
    est repete dans le nom (en plus du dossier) pour rester identifiable si le
    fichier est deplace/partage hors de son dossier."""
    parts = [
        sanitize_filename(bien) if bien else "Non classe",
        year_month(date_str),
        sanitize_filename(entreprise) if entreprise else "Facture",
        sanitize_filename(description) if description else "Facture",
    ]
    return ".".join(parts) + ext


def bien_document_dest(root, doc):
    """'<root>/Documents/<bien>/<BIEN>.<annee>.<mois>.<notes ou type><ext>' pour
    une ligne bien_documents (DPE, amiante, etc.) - `notes` est en general plus
    precis que `type` (ex: "DPE" / "Etat Parasitaire") quand il est renseigne."""
    bien = doc.get("bien")
    label = doc.get("notes") or doc.get("type") or "Document"
    ext = Path(parse_storage_url(doc.get("document_url") or "")[1]).suffix if parse_storage_url(doc.get("document_url") or "") else ".pdf"
    name = ".".join([
        sanitize_filename(bien) if bien else "Non classe",
        year_month(doc.get("date")),
        sanitize_filename(label),
    ]) + ext
    return validated_dest_folder(root, "Documents", bien) / name


def edl_dest(root, edl, tenants):
    """'<root>/Documents/<bien>/<BIEN>.<annee>.<mois>.EDL <Entree|Sortie>.<Locataire><ext>'."""
    bien = edl.get("bien")
    parsed = parse_storage_url(edl.get("pdf_url") or "")
    ext = Path(parsed[1]).suffix if parsed else ".pdf"
    type_label = "Entree" if edl.get("type") == "entree" else "Sortie"
    tenant = tenants.get(edl.get("tenant_id")) or {}
    name = ".".join([
        sanitize_filename(bien) if bien else "Non classe",
        year_month(edl.get("date")),
        f"EDL {type_label}",
        sanitize_filename(tenant.get("nom")) if tenant.get("nom") else "Locataire",
    ]) + ext
    return validated_dest_folder(root, "Documents", bien) / name


def connect_nas_share(unc_path):
    """Authentifie la session Windows sur le partage reseau (net use) - sans
    ca, un chemin \\\\serveur\\partage protege par mot de passe n'est pas
    accessible en lecture/ecriture depuis Python. Tolere le cas "deja
    connecte" (relance du script)."""
    if not unc_path:
        return
    result = subprocess.run(
        ["net", "use", unc_path, NAS_PASSWORD, f"/user:{NAS_USER}"],
        capture_output=True, text=True,
    )
    combined = (result.stdout + result.stderr).lower()
    if result.returncode != 0 and "déjà" not in combined and "already" not in combined and "multiple" not in combined:
        log(f"  ATTENTION connexion NAS ({unc_path}) : {result.stdout.strip()} {result.stderr.strip()}")


def fetch_all(table, select):
    """Pagine {table}?select={select} par lots de 1000 (meme convention que
    import_factures.py - PostgREST plafonne chaque requete a 1000 lignes)."""
    rows = []
    offset = 0
    page_size = 1000
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            params={"select": select},
            headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset + page_size - 1}"},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def parse_storage_url(url):
    """Extrait (bucket, path) d'une URL publique Supabase Storage, ou None si
    l'URL ne correspond pas au format attendu (.../object/public/<bucket>/<path>?...)."""
    marker = "/object/public/"
    idx = (url or "").find(marker)
    if idx == -1:
        return None
    rest = url[idx + len(marker):].split("?", 1)[0]
    bucket, _, path = rest.partition("/")
    return (bucket, path) if bucket and path else None


def build_classification():
    """Precharge les tables necessaires pour deduire SAVADUR/Dubail (True) ou
    Perso (False/inconnu) a partir d'un id ou d'un fragment de chemin, et pour
    renommer lisiblement les documents/EDL deja rattaches a un bien (au lieu
    du nom brut horodate issu de l'upload)."""
    tenants = {t["id"]: t for t in fetch_all("tenants", "id,logement,nom")}
    assets = {a["id"]: a for a in fetch_all("assets", "id,name,compte")}
    work_orders = {w["id"]: w for w in fetch_all("work_orders", "id,asset_id,topo_ref")}
    edls = {e["id"]: e for e in fetch_all("logement_edl", "id,bien,tenant_id,type,date,pdf_url")}
    factures = [f for f in fetch_all("factures", "drive_url,compte") if f.get("drive_url")]
    factures_av = {f["storage_path"]: f for f in fetch_all("factures_a_valider", "storage_path,bien,statut,entreprise,description,date_facture") if f.get("storage_path")}
    devis_av = {d["storage_path"]: d for d in fetch_all("devis_a_valider", "storage_path,bien,statut,entreprise,motif,date_devis") if d.get("storage_path")}

    # Cle "<bucket>/<path>" -> ligne, pour renommer un document/EDL quel que
    # soit le bucket physique ou il a fini par atterrir (certains anciens
    # bien_documents pointent encore vers factures-a-valider, herites du
    # pipeline mail avant leur reclassement manuel en diagnostic).
    bien_docs_by_key = {}
    for d in fetch_all("bien_documents", "bien,type,date,notes,document_url"):
        parsed = parse_storage_url(d.get("document_url") or "")
        if parsed:
            bien_docs_by_key["/".join(parsed)] = d
    edl_by_key = {}
    for e in edls.values():
        parsed = parse_storage_url(e.get("pdf_url") or "")
        if parsed:
            edl_by_key["/".join(parsed)] = e

    def tenant_is_savadur(tenant_id):
        t = tenants.get(tenant_id)
        return dubail_filter(t.get("logement")) if t else None

    def asset_is_savadur(asset_id):
        a = assets.get(asset_id)
        if not a:
            return None
        if a.get("compte"):
            return a["compte"] == "savadur"
        return dubail_filter(a.get("name"))

    def wo_is_savadur(wo_id):
        w = work_orders.get(wo_id)
        if not w:
            return None
        if w.get("asset_id"):
            r = asset_is_savadur(w["asset_id"])
            if r is not None:
                return r
        return dubail_filter((w.get("topo_ref") or {}).get("propName"))

    def edl_is_savadur(edl_id):
        e = edls.get(edl_id)
        return dubail_filter(e.get("bien")) if e else None

    def facture_photo_is_savadur(owner_id):
        for f in factures:
            if owner_id in f["drive_url"]:
                return f.get("compte") == "savadur"
        return None

    return {
        "tenant": tenant_is_savadur,
        "asset": asset_is_savadur,
        "wo": wo_is_savadur,
        "edl": edl_is_savadur,
        "facture_photo": facture_photo_is_savadur,
        "factures_av": factures_av,
        "devis_av": devis_av,
        "bien_docs_by_key": bien_docs_by_key,
        "edl_by_key": edl_by_key,
        "tenants": tenants,
    }


def classify_documents_locataires(path, cls):
    """True = SAVADUR/Dubail, False = Perso (par defaut si non determinable)."""
    parts = path.split("/")
    if len(parts) < 2:
        return False
    kind, ident = parts[0], parts[1]
    if kind in ("identite", "assurance"):
        result = cls["tenant"](ident)
    elif kind == "edl":
        result = cls["edl"](ident)
    elif kind == "bt":
        result = cls["wo"](ident)
    elif kind == "vehicules":
        result = cls["asset"](ident)
    elif kind == "factures":
        result = cls["facture_photo"](ident)
    elif kind == "biens":
        result = dubail_filter(ident)
    else:
        result = None
    return bool(result)


def list_all_objects(bucket, prefix=""):
    """Liste recursivement tous les fichiers d'un bucket : l'API Supabase Storage
    ne liste qu'un niveau a la fois, un "dossier" apparait comme une entree sans
    id/metadata et doit etre explore separement."""
    objects = []
    offset = 0
    limit = 100
    while True:
        resp = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/list/{bucket}",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"prefix": prefix, "limit": limit, "offset": offset, "sortBy": {"column": "name", "order": "asc"}},
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        for item in page:
            full_path = f"{prefix}{item['name']}" if not prefix or prefix.endswith("/") else f"{prefix}/{item['name']}"
            if item.get("id") is None and item.get("metadata") is None:
                objects.extend(list_all_objects(bucket, full_path + "/"))
            else:
                objects.append(full_path)
        if len(page) < limit:
            break
        offset += limit
    return objects


def download_object(bucket, path):
    resp = requests.get(f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}", headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.content


def write_with_retry(dest: Path, content: bytes, root: str, attempts=3):
    """Ecrit sur le NAS avec quelques tentatives : une coupure Wi-Fi/SMB
    passagere ne doit pas faire echouer definitivement un fichier alors que le
    reste du lot se deroule normalement. Retente une reconnexion (net use)
    entre chaque tentative, au cas ou la session NAS ait ete coupee."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            return
        except OSError as e:
            last_error = e
            if attempt < attempts:
                connect_nas_share(root)
                time.sleep(3)
    raise last_error


def backup_bucket(bucket, cls):
    log(f"Listage de {bucket}...")
    paths = list_all_objects(bucket)
    log(f"  {len(paths)} fichier(s) trouve(s) dans {bucket}.")
    copied = skipped = errors = 0
    for path in paths:
        row = None
        if bucket == "documents-locataires":
            is_savadur = classify_documents_locataires(path, cls)
        elif bucket == "factures-a-valider":
            row = cls["factures_av"].get(path)
            is_savadur = dubail_filter(row.get("bien")) if row else False
        else:  # devis-a-valider
            row = cls["devis_av"].get(path)
            is_savadur = dubail_filter(row.get("bien")) if row else False

        # Document (diagnostic, EDL...) deja rattache a un bien dans le GMAO :
        # verifie en priorite, quel que soit le bucket physique - certains
        # bien_documents anciens pointent encore vers factures-a-valider
        # (heritage du pipeline mail avant leur reclassement manuel).
        key = f"{bucket}/{path}"
        bien_doc = cls["bien_docs_by_key"].get(key)
        edl_row = cls["edl_by_key"].get(key)
        if edl_row:
            is_savadur = dubail_filter(edl_row.get("bien"))
            root = NAS_SAVADUR_PATH if is_savadur else NAS_PERSO_PATH
            dest = edl_dest(root, edl_row, cls["tenants"])
        elif bien_doc:
            is_savadur = dubail_filter(bien_doc.get("bien"))
            root = NAS_SAVADUR_PATH if is_savadur else NAS_PERSO_PATH
            dest = bien_document_dest(root, bien_doc)
        else:
            root = NAS_SAVADUR_PATH if is_savadur else NAS_PERSO_PATH
            # Facture/devis deja validee dans le GMAO : rangee et renommee
            # lisiblement (Factures ou Devis /<bien>/<BIEN.annee.mois.Entreprise.
            # Description>.ext) au lieu du mirroir brut du bucket - une fois
            # validee, le nom d'origine issu du mail n'a plus d'interet et la
            # noyer avec les centaines d'autres fichiers "a valider" la rendait
            # introuvable.
            if row and row.get("statut") == "valide" and bucket in ("factures-a-valider", "devis-a-valider"):
                kind = "Factures" if bucket == "factures-a-valider" else "Devis"
                date_str = row.get("date_facture") if bucket == "factures-a-valider" else row.get("date_devis")
                description = row.get("description") if bucket == "factures-a-valider" else row.get("motif")
                dest = validated_dest_folder(root, kind, row.get("bien")) / validated_dest_filename(
                    Path(path).suffix, row.get("bien"), date_str, row.get("entreprise"), description
                )
            else:
                dest = Path(root) / bucket / Path(path)
        if dest.exists():
            skipped += 1
            continue
        try:
            write_with_retry(dest, download_object(bucket, path), root)
            copied += 1
        except Exception as e:
            errors += 1
            log(f"  ERREUR {path} : {e}")
    log(f"  {bucket} : {copied} copie(s), {skipped} deja present(s), {errors} erreur(s).")


def main():
    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans .env")
    if not NAS_SAVADUR_PATH or not NAS_PERSO_PATH:
        sys.exit("NAS_SAVADUR_PATH / NAS_PERSO_PATH manquants dans .env")

    connect_nas_share(NAS_SAVADUR_PATH)
    connect_nas_share(NAS_PERSO_PATH)

    log("Chargement des tables de classification (tenants, assets, BT, EDL, factures)...")
    cls = build_classification()

    for bucket in BUCKETS:
        try:
            backup_bucket(bucket, cls)
        except Exception as e:
            log(f"  ECHEC complet sur {bucket} (sera retente au prochain lancement) : {e}")

    log("Termine.")


if __name__ == "__main__":
    main()
