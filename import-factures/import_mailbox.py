"""
Scanne une ou plusieurs boites Gmail (IMAP) a la recherche des mails portant
un libelle dedie (ex: "A importer"), en extrait les pieces jointes
(factures/devis) et les depose dans WATCH_DIR ou DEVIS_WATCH_DIR - exactement
comme si elles y avaient ete glissees a la main. import_factures.py et
import_devis.py (deja en place, inchanges) prennent ensuite le relais au
prochain passage de leur propre tache planifiee.

Pourquoi un libelle plutot que "tous les mails avec piece jointe" : evite de
remonter les newsletters/pubs qui ont aussi des PDF en piece jointe. Le
libelle se retire automatiquement une fois le mail traite (queue visuelle
dans Gmail : le libelle se vide au fur et a mesure).

Idempotent meme si le retrait du libelle echoue (connexion coupee en cours de
route, etc.) : chaque Message-ID traite est aussi note dans un fichier local
(mailbox_seen.json) et ne sera plus jamais retraite.

Configuration (.env) :
    GMAIL_ACCOUNT_1=savadur56@gmail.com
    GMAIL_APP_PASSWORD_1=xxxx xxxx xxxx xxxx
    GMAIL_ACCOUNT_2=antoinejosse56@gmail.com
    GMAIL_APP_PASSWORD_2=xxxx xxxx xxxx xxxx
    GMAIL_LABEL=A importer
(rajouter GMAIL_ACCOUNT_3/GMAIL_APP_PASSWORD_3 etc. pour une 3e boite plus tard,
aucune modification de code necessaire)

Le mot de passe d'application se genere depuis https://myaccount.google.com/apppasswords
(necessite la validation en 2 etapes activee sur le compte Google).

Usage :
    pip install -r requirements.txt   (aucune dependance supplementaire requise)
    python import_mailbox.py
A lancer via le Planificateur de taches Windows, un peu avant les taches
"GMAO Import Factures" / "GMAO Import Devis" pour qu'elles trouvent les
fichiers fraichement deposes des le meme cycle.
"""
import email
import imaplib
import json
import os
import re
import sys
import unicodedata
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WATCH_DIR = os.environ.get("WATCH_DIR", "")
DEVIS_WATCH_DIR = os.environ.get("DEVIS_WATCH_DIR", "")
GMAIL_LABEL = os.environ.get("GMAIL_LABEL", "A importer")
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".odt"}
SEEN_PATH = Path(__file__).with_name("mailbox_seen.json")
IMAP_HOST = "imap.gmail.com"


def log(msg):
    print(f"[import-mailbox] {msg}")


def load_accounts():
    accounts = []
    i = 1
    while True:
        user = os.environ.get(f"GMAIL_ACCOUNT_{i}")
        pwd = os.environ.get(f"GMAIL_APP_PASSWORD_{i}")
        if not user or not pwd:
            break
        accounts.append((user, pwd))
        i += 1
    return accounts


def load_seen() -> set:
    if SEEN_PATH.exists():
        try:
            return set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def save_seen(seen: set):
    # Ne garde que les 5000 derniers pour ne pas grossir indefiniment.
    trimmed = list(seen)[-5000:]
    SEEN_PATH.write_text(json.dumps(trimmed), encoding="utf-8")


def slugify(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name)
    return ascii_name.strip("_") or "fichier"


def decode_mime_words(s: str) -> str:
    if not s:
        return ""
    parts = decode_header(s)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


def sender_parts(msg) -> tuple:
    """Renvoie (nom_affiche, domaine) pour construire le nom de fichier,
    meme convention que les pieces jointes deposees manuellement jusqu'ici
    (ex: 2024-06-03_noreply_booking.com_invoice-...pdf)."""
    from_header = decode_mime_words(msg.get("From", ""))
    m = re.match(r"^(.*?)<(.+?)>$", from_header)
    display = m.group(1).strip(' "') if m else ""
    addr = m.group(2).strip() if m else from_header.strip()
    local, _, domain = addr.partition("@")
    name = display or local
    return slugify(name), slugify(domain)


def unique_dest(folder: Path, filename: str) -> Path:
    dest = folder / filename
    if not dest.exists():
        return dest
    stem, ext = os.path.splitext(filename)
    n = 2
    while (folder / f"{stem}_{n}{ext}").exists():
        n += 1
    return folder / f"{stem}_{n}{ext}"


def process_account(user: str, password: str, seen: set) -> int:
    log(f"Connexion a {user}...")
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        mail.login(user, password)
    except imaplib.IMAP4.error as e:
        log(f"  ERREUR connexion {user} : {e}")
        return 0

    # Le dossier "Tous les messages" change de nom selon la langue du compte
    # ("[Gmail]/All Mail" en anglais, "[Gmail]/Tous les messages" en francais,
    # etc.) - on le repere via son attribut IMAP standard \All plutot que par
    # un nom fige, pour marcher quelle que soit la langue de l'interface.
    status, folders = mail.list()
    all_mail_folder = None
    if status == "OK":
        for f in folders:
            decoded = f.decode(errors="ignore")
            if "\\All" in decoded:
                all_mail_folder = decoded.rsplit('"/"', 1)[-1].strip().strip('"')
                break
    if not all_mail_folder:
        log(f"  ERREUR : dossier 'Tous les messages' introuvable pour {user}")
        mail.logout()
        return 0
    status, _ = mail.select(f'"{all_mail_folder}"')
    if status != "OK":
        log(f"  ERREUR selection du dossier {all_mail_folder} pour {user}")
        mail.logout()
        return 0

    query = f'(X-GM-RAW "label:\\"{GMAIL_LABEL}\\"")'
    status, data = mail.uid("search", None, query)
    if status != "OK":
        log(f"  ERREUR recherche label sur {user}")
        mail.logout()
        return 0
    uids = data[0].split()
    log(f"  {len(uids)} mail(s) avec le libelle \"{GMAIL_LABEL}\"")

    imported = 0
    for uid in uids:
        status, msg_data = mail.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        message_id = msg.get("Message-ID", uid.decode())
        if message_id in seen:
            continue

        subject = decode_mime_words(msg.get("Subject", ""))
        try:
            recv_date = parsedate_to_datetime(msg.get("Date")).date().isoformat()
        except (TypeError, ValueError):
            recv_date = ""
        name_part, domain_part = sender_parts(msg)
        is_devis = "devis" in subject.lower()

        saved_any = False
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename = part.get_filename()
            if not filename:
                continue
            filename = decode_mime_words(filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            if "devis" in filename.lower():
                is_devis = True
            target_dir = DEVIS_WATCH_DIR if is_devis else WATCH_DIR
            if not target_dir:
                log(f"  ATTENTION : dossier cible non configure (devis={is_devis}), piece jointe ignoree : {filename}")
                continue
            folder = Path(target_dir)
            if not folder.is_dir():
                log(f"  ERREUR dossier introuvable : {folder}")
                continue
            safe_name = slugify(os.path.splitext(filename)[0]) + ext
            new_name = "_".join(filter(None, [recv_date, name_part, domain_part, safe_name]))
            dest = unique_dest(folder, new_name)
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            dest.write_bytes(payload)
            log(f"  -> {dest.name} ({'devis' if is_devis else 'facture'})")
            saved_any = True
            imported += 1

        if saved_any:
            try:
                mail.uid("store", uid, "-X-GM-LABELS", f'("{GMAIL_LABEL}")')
            except imaplib.IMAP4.error as e:
                log(f"  ATTENTION : retrait du libelle echoue pour {message_id} : {e}")
        seen.add(message_id)

    mail.logout()
    return imported


def main():
    accounts = load_accounts()
    if not accounts:
        sys.exit("Aucun compte configure - remplir GMAIL_ACCOUNT_1 / GMAIL_APP_PASSWORD_1 dans .env")
    if not WATCH_DIR and not DEVIS_WATCH_DIR:
        sys.exit("WATCH_DIR et DEVIS_WATCH_DIR manquants dans .env")

    seen = load_seen()
    total = 0
    for user, password in accounts:
        total += process_account(user, password, seen)
    save_seen(seen)
    log(f"Termine. {total} piece(s) jointe(s) importee(s).")


if __name__ == "__main__":
    main()
