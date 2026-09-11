"""
Scan le dossier de factures (local ou reseau), detecte les nouveaux fichiers
(PDF ou photos de tickets), les upload dans Supabase Storage, tente une
extraction basique (texte natif PDF uniquement - pas d'OCR en v1), et les
enregistre dans la table `factures_a_valider` pour validation manuelle dans
le GMAO.

Idempotent : un fichier deja connu (meme chemin relatif au dossier surveille)
n'est jamais retraite, quel que soit son statut (en_attente / valide / rejete).

Detection de doublons par contenu (pas juste par nom de fichier) : la meme
facture recue sur les 2 boites mail (import_mailbox.py), ou deposee a la main
dans le dossier puis re-recuperee par le scan Gmail, arrive sous 2 noms de
fichier differents mais avec un contenu binaire identique. Chaque fichier est
donc aussi identifie par une empreinte SHA256 (content_hash) ; si elle
correspond a une empreinte deja connue (n'importe quel statut), la nouvelle
ligne est inseree directement en statut 'rejete' avec le motif explique dans
erreur_extraction, plutot que de re-encombrer la file a valider.

Usage :
    pip install -r requirements.txt
    copier .env.example en .env et remplir les valeurs
    python import_factures.py

A lancer periodiquement via le Planificateur de taches Windows (pas de
processus en tache de fond requis - un passage = un scan complet).
"""
import hashlib
import mimetypes
import os
import re
import shutil
import sys
import unicodedata
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import docx as docx_lib
except ImportError:
    docx_lib = None

try:
    import win32com.client as win32
    import pythoncom
except ImportError:
    win32 = None
    pythoncom = None

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
WATCH_DIR = os.environ.get("WATCH_DIR", "")
# Optionnel : si renseigne, les fichiers dont la facture a ete validee dans le GMAO
# sont deplaces du dossier de transit vers ARCHIVE_DIR/<savadur|perso>/<bien>/<zone>/.
# Laisser vide pour desactiver l'archivage automatique.
ARCHIVE_DIR = os.environ.get("ARCHIVE_DIR", "")

BUCKET = "factures-a-valider"
TABLE = "factures_a_valider"
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".odt"}

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
}

FILENAME_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_")

# Date d'emission INDIQUEE SUR LA FACTURE, distincte de la date du nom de fichier (qui
# reflete la reception du mail, pas forcement le meme jour que l'emission). Plusieurs
# libelles possibles selon le logiciel de facturation du fournisseur, testes en ordre :
# 1) "Date : Le 11/11/2025" / "Date de facture : ..." / "Date d'emission : ..."
# 2) "Facture [d'acompte] n° F-250048 du 12/11/2025" (le "du" peut etre suivi d'un saut
#    de ligne avant la date, selon comment le PDF segmente le texte a l'extraction).
#    Ancre sur "facture" (pas juste "n°... du...") pour ne pas confondre avec la date
#    d'un devis reference sur le meme document ("Devis n° D-250031 du 29/09/2025").
# 3) Repli plus risque : "Le 05-08-2026" tout seul en tete de document (aucun libelle
#    "date"/"facture...du"), courant chez les auto-entrepreneurs. Restreint aux 150
#    premiers caracteres pour eviter de choper une autre date "Le ..." plus loin dans
#    le corps du document (ex: une echeance de paiement).
# Le separateur accepte / . ou - (les 3 formats se rencontrent).
INVOICE_DATE_PATTERNS = [
    re.compile(
        r"date\s*(?:de\s*facture|d['’]émission|d['’]emission)?\s*:?\s*(?:le\s*)?"
        r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"facture[^\n]{0,40}\bdu\s*\n?\s*(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})",
        re.IGNORECASE,
    ),
]
INVOICE_DATE_HEADER_RE = re.compile(
    r"\ble\s+(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})", re.IGNORECASE
)


def guess_date_facture(text: str):
    """Cherche la date d'emission sur la facture elle-meme. Retourne None si rien
    de fiable n'est trouve (mieux vaut vide qu'une date fausse)."""
    if not text:
        return None
    for pattern in INVOICE_DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        day_s, month_s, year_s = m.groups()
        try:
            day, month, year = int(day_s), int(month_s), int(year_s)
            if year < 100:
                year += 2000
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    m = INVOICE_DATE_HEADER_RE.search(text[:150])
    if m:
        day_s, month_s, year_s = m.groups()
        try:
            day, month, year = int(day_s), int(month_s), int(year_s)
            if year < 100:
                year += 2000
            return date(year, month, day).isoformat()
        except ValueError:
            pass
    return None

# Libelles usuels de montant TTC, par ordre de priorite (le premier libelle qui matche
# quelque part dans le texte l'emporte - les autres ne sont meme pas essayes).
# Les factures avec acompte/solde (courant chez les artisans) contiennent souvent PLUSIEURS
# lignes "Total TTC" (une par section/lot) : le vrai montant a payer est sur un libelle plus
# specifique ("Total solde TTC", "Solde a payer"...) qui doit donc etre teste EN PREMIER,
# sinon on risque de choper le total d'une section au lieu du solde final.
MONTANT_LABELS = [
    r"total\s*solde\s*ttc",
    r"total\s*prix\s*vente\s*g[ée]n[ée]ral\s*ttc",
    r"solde\s*[aà]\s*payer",
    r"reste\s*[aà]\s*payer",
    r"net\s*[aà]\s*payer",
    r"total\s*ttc",
    r"montant\s*ttc",
    r"ttc\s*[aà]\s*payer",
    r"total\s*[aà]\s*payer",
    r"total\s*g[ée]n[ée]ral",
]
# Montant : 1 234,56€ / 1234.56 € / 123,45€ / 1234,56€ (sans separateur de milliers)...
# \d+ (pas \d{1,3}) : certains fournisseurs ecrivent les montants a 4 chiffres sans
# separateur ("1641,11" au lieu de "1 641,11") - \d{1,3} echouait purement et simplement
# sur ce cas, renvoyant aucun match plutot qu'un mauvais montant.
AMOUNT_RE = r"(\d+(?:[ .]\d{3})*(?:[,.]\d{2}))\s*€?"

SIRET_RE = re.compile(r"siret\s*:?\s*((?:\d[ .]?){14})", re.IGNORECASE)
SIREN_RE = re.compile(r"siren\s*:?\s*((?:\d[ .]?){9})", re.IGNORECASE)


def log(msg):
    print(f"[import-factures] {msg}")


def slugify_path(name: str) -> str:
    """Rend un nom de fichier sur pour une cle de storage (garde lisibilite)."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name)
    return ascii_name.strip("_") or "fichier"


def parse_filename_date(filename: str):
    m = FILENAME_DATE_RE.match(filename)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def fetch_known_rows() -> dict:
    """Renvoie {chemin_relatif: {statut, bien}} pour toutes les lignes connues -
    sert a la fois a la detection de doublons et a l'archivage post-validation.
    Pagine par lots de 1000 : PostgREST plafonne chaque requete a son "Max Rows"
    (1000 par defaut cote Supabase) quel que soit le Range demande - au-dela de
    1000 lignes en base, un seul GET n'en ramenait qu'une partie, ce qui faisait
    reessayer d'importer des fichiers deja connus (rejetes ensuite par la
    contrainte d'unicite - pas de perte de donnees, juste du travail inutile)."""
    known = {}
    offset = 0
    page_size = 1000
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE}",
            params={"select": "chemin_relatif,statut,bien,motif,entreprise,description,date_facture"},
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
    """Renvoie l'ensemble des empreintes SHA256 deja en base, tous statuts
    confondus - sert a reperer un contenu deja recu sous un autre nom de
    fichier (2 boites mail, depot manuel puis re-scan Gmail...)."""
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


def sanitize_folder_name(name: str) -> str:
    """Nettoie un nom pour en faire un dossier Windows valide, en gardant la
    lisibilite (accents/espaces conserves, seuls les caracteres interdits sautent)."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(". ")
    return cleaned or "Non classe"


def archive_path_for(bien: str, motif: str) -> Path:
    """Calcule le sous-dossier d'archive ARCHIVE_DIR/<SAVADUR|PERSO>/Factures/...
    a partir de la valeur `bien` stockee et du motif. `bien` est un chemin
    "A - B - C" dont chaque segment devient un niveau de dossier (nombre
    variable) :
    - cas normal : "Prop - Zone - SousZone" (jusqu'a 3 niveaux) + motif en
      dernier niveau si renseigne (Entretien, Renovation, Travaux, Etudes,
      Medicale, Diagnostiques ou texte libre) ;
    - facture/devis lie a un chantier : "Prop - Chantier - TitreDuBT" (motif
      alors vide - le chantier et le BT categorisent deja suffisamment).
    Racine commune ARCHIVE_DIR partagee avec import_devis.py (meme
    arborescence <compte>/<type>/...)."""
    parts = [p.strip() for p in (bien or "").split(" - ") if p.strip()]
    compte = "PERSO" if parts and "dubail" not in parts[0].lower() else "SAVADUR"
    folder = Path(ARCHIVE_DIR) / compte / "Factures"
    if parts:
        for p in parts:
            folder = folder / sanitize_folder_name(p)
    else:
        folder = folder / "Non classe"
    if motif:
        folder = folder / sanitize_folder_name(motif)
    return folder


def archive_filename_for(original_ext: str, entreprise: str, date_facture: str, description: str) -> str:
    """Nom lisible 'NOM ENTREPRISE.DATE.Description.ext' pour le fichier archive
    (au lieu du nom brut issu de l'extraction mail) - facilite la recherche
    manuelle dans l'explorateur de fichiers."""
    parts = [
        sanitize_folder_name(entreprise) if entreprise else "Facture",
        date_facture or "date-inconnue",
        sanitize_folder_name(description) if description else "Facture",
    ]
    return ".".join(parts) + original_ext


def archive_validated_files(watch_path: Path, known_rows: dict):
    """Deplace vers ARCHIVE_DIR les fichiers encore presents dans le dossier de
    transit dont la facture correspondante a ete validee dans le GMAO. Ne touche
    pas aux fichiers en_attente ou rejetes - uniquement statut == 'valide'.
    Renomme au passage au format 'NOM ENTREPRISE.DATE.Description.ext'."""
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
        new_name = archive_filename_for(p.suffix, info.get("entreprise"), info.get("date_facture"), info.get("description"))
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


class LazyWordConverter:
    """Convertit .doc/.docx/.odt en PDF via Microsoft Word (automatisation COM),
    pour permettre de visualiser ces formats dans le navigateur (pas de lecteur
    natif). Une seule instance Word est lancee, reutilisee pour tous les
    fichiers du lot, et fermee explicitement a la fin (close()) - la lancer une
    fois par fichier serait beaucoup trop lent sur des dizaines de documents.

    Lancee "au besoin" (au premier appel a convert()) plutot qu'au demarrage,
    pour ne pas ouvrir Word du tout quand le lot ne contient aucun doc/docx/odt.

    Fragile en execution non-interactive (tache planifiee sans session ouverte) :
    Word peut se bloquer sur un fichier corrompu ou une boite de dialogue - pas
    de timeout cote COM. Une erreur sur un fichier ne bloque pas les suivants,
    mais un blocage complet de Word, si, necessitant de tuer le processus."""

    def __init__(self):
        self._word = None

    def _ensure(self):
        if self._word is not None:
            return
        if win32 is None:
            raise RuntimeError("pywin32 non installe (pip install -r requirements.txt) — Windows + Word requis")
        pythoncom.CoInitialize()
        self._word = win32.gencache.EnsureDispatch("Word.Application")
        self._word.Visible = False
        self._word.DisplayAlerts = 0

    def convert(self, src_path: Path, dst_path: Path):
        self._ensure()
        doc = self._word.Documents.Open(str(src_path), ReadOnly=True, ConfirmConversions=False)
        try:
            doc.SaveAs(str(dst_path), FileFormat=17)  # wdFormatPDF
        finally:
            doc.Close(False)

    def close(self):
        if self._word is not None:
            try:
                self._word.Quit()
            except Exception:
                pass
            self._word = None


def extract_pdf_text(path: Path) -> str:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber non installe (pip install -r requirements.txt)")
    text_parts = []
    with pdfplumber.open(str(path)) as pdf:
        for pg in pdf.pages:
            t = pg.extract_text() or ""
            text_parts.append(t)
    return "\n".join(text_parts)


def extract_odt_text(path: Path) -> str:
    """Texte natif d'un .odt (OpenDocument, format zip/XML comme .docx) - pas de
    dependance supplementaire, content.xml se parse avec la lib standard."""
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(str(path)) as z:
        with z.open("content.xml") as f:
            tree = ET.parse(f)
    p_tag = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"
    parts = ["".join(el.itertext()) for el in tree.iter(p_tag)]
    return "\n".join(parts)


def extract_docx_text(path: Path) -> str:
    """Texte natif d'un .docx (Word 2007+, format zip/XML). Le vieux format
    binaire .doc (Word 97-2003) n'est pas lisible par python-docx - trop rare
    et trop complexe a parser pour la v1, traite comme les images (saisie
    manuelle) plutot que d'ajouter une dependance lourde pour ce cas."""
    if docx_lib is None:
        raise RuntimeError("python-docx non installe (pip install -r requirements.txt)")
    doc = docx_lib.Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def guess_montant_ttc(text: str):
    """Cherche un libelle connu suivi d'un montant en euros a proximite.
    Retourne None si rien de fiable n'est trouve (mieux vaut vide qu'errone)."""
    if not text:
        return None
    lowered = text
    for label in MONTANT_LABELS:
        # Le montant peut etre sur la meme ligne ou juste apres (jusqu'a ~40 caracteres)
        pattern = re.compile(label + r"[^\d€\n]{0,40}" + AMOUNT_RE, re.IGNORECASE)
        matches = pattern.findall(lowered)
        if matches:
            raw = matches[-1]  # dernier = souvent le total final du document
            normalized = raw.replace(" ", "").replace(".", "").replace(",", ".") \
                if "," in raw else raw.replace(" ", "")
            try:
                return round(float(normalized), 2)
            except ValueError:
                continue
    return None


# Marqueurs qui indiquent que la ligne N'EST PAS un nom d'entreprise (mentions legales,
# coordonnees, TVA...) - une ligne qui en contient un est rejetee entierement.
# Mots entiers (\b) pour eviter de rejeter a tort un nom contenant la sous-chaine
# (ex: "tel" ne doit pas rejeter "HOTEL DE FRANCE").
BAD_LINE_WORD_RE = re.compile(
    r"\b(tel|tél|email|iban|bic|rcs|loi|décret|decret|indemnité|indemnite|"
    r"recouvrement|pénalité|penalite)\b",
    re.IGNORECASE,
)
BAD_LINE_SUBSTR_MARKERS = ["e-mail", "@", "www.", "http", "tva", "t.v.a"]
# Marqueurs a partir desquels on tronque une ligne par ailleurs correcte (le nom est avant,
# le reste est du bruit accroche a la meme ligne : coordonnees, capital social...).
TRUNCATE_MARKERS = [" au capital de", " - tel", " – tel", " tel :", " tel:", " - email", " email"]
# Separateurs de segments (tiret/virgule) : sert de repli quand une ligne entiere echoue
# (ex: "FG Studio – 39, Rue Capitaine..." -> le nom seul tient dans le 1er segment).
SEGMENT_SPLIT_RE = re.compile(r"\s[–—-]\s|,")


def _try_clean_segment(segment: str):
    segment = segment.strip()
    low = segment.lower()
    if len(segment) < 3 or len(segment) > 70:
        return None
    if re.match(r"^\d", segment):
        return None
    if re.search(r"\d{5}\s+\S", segment):  # code postal + ville
        return None
    if BAD_LINE_WORD_RE.search(segment) or any(marker in low for marker in BAD_LINE_SUBSTR_MARKERS):
        return None
    # Une ligne majoritairement numerique n'est pas un nom d'entreprise
    digits = sum(c.isdigit() for c in segment)
    if digits > len(segment) * 0.3:
        return None
    return segment


def _clean_entreprise_candidate(candidate: str):
    """Valide/nettoie une ligne candidate. Retourne None si elle n'est pas fiable."""
    low = candidate.lower()
    for marker in TRUNCATE_MARKERS:
        pos = low.find(marker)
        if pos > 0:
            candidate = candidate[:pos].strip()
            low = candidate.lower()
    cleaned = _try_clean_segment(candidate)
    if cleaned:
        return cleaned
    # Repli : la ligne entiere echoue (trop longue / mot interdit) mais son premier
    # segment avant un tiret ou une virgule peut etre le vrai nom (adresse/tel accroches
    # a la suite sur la meme ligne).
    first_segment = SEGMENT_SPLIT_RE.split(candidate, maxsplit=1)[0]
    if first_segment != candidate:
        return _try_clean_segment(first_segment)
    return None


AUTO_ENTREPRENEUR_RE = re.compile(r"auto[\s-]?entrepreneur\b", re.IGNORECASE)


def guess_entreprise(text: str):
    """Cherche une raison sociale a proximite d'un SIRET/SIREN.
    Retourne None si aucune ancre fiable n'est trouvee (mieux vaut vide qu'une
    phrase de mentions legales ou une ligne de coordonnees prise pour un nom)."""
    if not text:
        return None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if SIRET_RE.search(line) or SIREN_RE.search(line):
            # Le nom de l'entreprise est generalement 1 a 3 lignes au-dessus
            for back in range(1, 4):
                idx = i - back
                if idx < 0:
                    break
                cleaned = _clean_entreprise_candidate(lines[idx])
                if cleaned:
                    return cleaned
    # Repli specifique aux auto-entrepreneurs : mise en page a 2 colonnes qui melange
    # souvent adresse/contact fournisseur et client a l'extraction, rendant le nom trop
    # eloigne du SIRET pour le repli ci-dessus. "Auto entrepreneur" est une ancre peu
    # ambigue - le nom suit generalement (meme ligne apres un tiret, ou ligne suivante).
    for i, line in enumerate(lines):
        m = AUTO_ENTREPRENEUR_RE.search(line)
        if not m:
            continue
        after = line[m.end():].strip(" -:–—\t")
        cleaned = _clean_entreprise_candidate(after) if after else None
        if cleaned:
            return cleaned
        if i + 1 < len(lines):
            cleaned = _clean_entreprise_candidate(lines[i + 1])
            if cleaned:
                return cleaned
    return None


def upload_to_storage(storage_path: str, content: bytes, content_type: str):
    resp = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}",
        # x-upsert : ecrase un objet deja present au meme chemin au lieu d'echouer.
        # Utile si le script est relance apres un echec partiel (upload ok, insert DB rate).
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


def generate_pdf_preview(path: Path, storage_path: str, word_converter: "LazyWordConverter"):
    """Convertit un .doc/.docx/.odt en PDF via Word et l'uploade a cote de
    l'original, pour permettre de le visualiser dans le navigateur (pas de
    lecteur natif pour ces formats). Retourne le storage_path du PDF genere,
    ou leve une exception si la conversion/upload echoue."""
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


def process_file(path: Path, chemin_relatif: str, word_converter: "LazyWordConverter" = None, known_hashes: set = None):
    log(f"Nouveau fichier : {chemin_relatif}")
    ext = path.suffix.lower()
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    # Slugifie le nom complet (pas juste le stem) : chemin_relatif est deja garanti
    # unique en base, donc ca minimise le risque de collision de cle de storage.
    storage_path = slugify_path(chemin_relatif)

    row = {
        "fichier_nom": path.name,
        "fichier_date": parse_filename_date(path.name).isoformat() if parse_filename_date(path.name) else None,
        "chemin_relatif": chemin_relatif,
        "storage_path": None,
        "apercu_pdf_path": None,
        "entreprise": None,
        "montant_ttc": None,
        "date_facture": None,
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

    if ext == ".pdf":
        try:
            text = extract_pdf_text(path)
            row["montant_ttc"] = guess_montant_ttc(text)
            row["entreprise"] = guess_entreprise(text)
            row["date_facture"] = guess_date_facture(text)
            if not text.strip():
                row["erreur_extraction"] = (
                    "Aucun texte extrait (probablement un PDF scanne / image) — "
                    "OCR non disponible en v1, saisie manuelle necessaire."
                )
        except Exception as e:
            row["erreur_extraction"] = f"Extraction du texte PDF echouee (fichier peut-etre corrompu) : {e}"
    elif ext == ".docx":
        try:
            text = extract_docx_text(path)
            row["montant_ttc"] = guess_montant_ttc(text)
            row["entreprise"] = guess_entreprise(text)
            row["date_facture"] = guess_date_facture(text)
            if not text.strip():
                row["erreur_extraction"] = "Document Word vide — saisie manuelle necessaire."
        except Exception as e:
            row["erreur_extraction"] = f"Extraction du texte Word echouee (fichier peut-etre corrompu) : {e}"
    elif ext == ".odt":
        try:
            text = extract_odt_text(path)
            row["montant_ttc"] = guess_montant_ttc(text)
            row["entreprise"] = guess_entreprise(text)
            row["date_facture"] = guess_date_facture(text)
            if not text.strip():
                row["erreur_extraction"] = "Document ODT vide — saisie manuelle necessaire."
        except Exception as e:
            row["erreur_extraction"] = f"Extraction du texte ODT echouee (fichier peut-etre corrompu) : {e}"
    elif ext == ".doc":
        row["erreur_extraction"] = (
            "Format .doc (Word 97-2003) non pris en charge pour l'extraction automatique — "
            "saisie manuelle necessaire."
        )
    # Pour les images (.jpg/.jpeg/.png) : pas d'extraction en v1 (OCR reporte a la v2),
    # entreprise/montant_ttc restent vides pour saisie manuelle - ce n'est pas une erreur.

    if ext in (".doc", ".docx", ".odt") and word_converter is not None:
        try:
            row["apercu_pdf_path"] = generate_pdf_preview(path, storage_path, word_converter)
        except Exception as e:
            log(f"  ATTENTION : conversion PDF echouee pour {chemin_relatif} : {e}")

    insert_row(row)
    log(f"  -> importee (entreprise={row['entreprise']!r}, montant_ttc={row['montant_ttc']!r}, date_facture={row['date_facture']!r})")


def inspect_file(filename: str):
    """Mode debug : affiche le texte extrait et ce que les heuristiques y trouvent,
    sans toucher a Supabase (ni upload, ni insert). Usage :
        python import_factures.py --inspect "nom_du_fichier.pdf"
    """
    watch_path = Path(WATCH_DIR)
    path = watch_path / filename
    if not path.is_file():
        sys.exit(f"Fichier introuvable : {path}")
    ext = path.suffix.lower()
    if ext not in (".pdf", ".docx", ".odt"):
        sys.exit("--inspect ne fonctionne que sur des PDF, .docx ou .odt (pas d'extraction pour les images/.doc en v1)")
    if ext == ".pdf":
        text = extract_pdf_text(path)
    elif ext == ".docx":
        text = extract_docx_text(path)
    else:
        text = extract_odt_text(path)
    print("=" * 70)
    print("TEXTE EXTRAIT :")
    print("=" * 70)
    print(text)
    print("=" * 70)
    print(f"RESULTAT guess_montant_ttc : {guess_montant_ttc(text)!r}")
    print(f"RESULTAT guess_entreprise  : {guess_entreprise(text)!r}")
    print(f"RESULTAT guess_date_facture: {guess_date_facture(text)!r}")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--inspect":
        if not WATCH_DIR:
            sys.exit("WATCH_DIR manquant dans .env")
        inspect_file(sys.argv[2])
        return

    # --source-dir : traite un dossier different de WATCH_DIR pour cette execution
    # (backfill historique par ex.), sans toucher a la config habituelle du scan
    # periodique. L'archivage post-validation reste desactive pendant un backfill
    # (les fichiers viennent d'etre crees, aucun n'est encore valide de toute facon).
    source_dir = WATCH_DIR
    if len(sys.argv) >= 3 and sys.argv[1] == "--source-dir":
        source_dir = sys.argv[2]

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans .env")
    if not source_dir:
        sys.exit("WATCH_DIR manquant dans .env (ou fournir --source-dir <dossier>)")

    watch_path = Path(source_dir)
    if not watch_path.is_dir():
        sys.exit(f"Dossier introuvable ou inaccessible : {source_dir}")

    known_rows = fetch_known_rows()
    known_hashes = fetch_known_hashes()
    log(f"{len(known_rows)} fichier(s) deja connu(s) en base ({len(known_hashes)} empreinte(s) de contenu).")

    candidates = [
        p for p in sorted(watch_path.iterdir())
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    ]
    log(f"{len(candidates)} fichier(s) eligible(s) trouve(s) dans {source_dir}")

    word_converter = LazyWordConverter()
    nouveaux = 0
    try:
        for p in candidates:
            chemin_relatif = p.name  # dossier scanne a plat (pas de sous-dossiers)
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
