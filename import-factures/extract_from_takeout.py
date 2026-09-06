"""
Extrait les pieces jointes de factures d'un export Google Takeout Gmail (.mbox),
pour reconstituer l'historique des factures recues depuis une certaine date.

Ne modifie jamais le fichier .mbox source (lecture seule) ni ton compte Gmail -
tout se passe en local sur le fichier deja telecharge.

Usage :
    python extract_from_takeout.py "D:\\Antoine\\Export Gmail\\Mail\\All mail Including Spam and Trash.mbox" "D:\\Antoine\\Export Gmail\\extrait" --depuis 2019-01-01

Le dossier de sortie peut ensuite etre traite par le pipeline habituel :
    python import_factures.py --source-dir "D:\\Antoine\\Export Gmail\\extrait"
"""
import argparse
import mailbox
import re
import unicodedata
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".odt"}

# Mots-cles facture en plusieurs langues (memes que l'automatisation mail existante)
KEYWORD_RE = re.compile(
    r"facture|quittance|invoice|rechnung|fattura|factura|faktura|factuur",
    re.IGNORECASE,
)


def log(msg):
    print(f"[extract-takeout] {msg}")


def sanitize(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name)
    return ascii_name.strip("_") or "inconnu"


def decode_filename(raw):
    """part.get_filename() ne decode PAS les noms de pieces jointes encodes
    RFC 2047 (ex: '=?iso-8859-1?Q?facture_n=B0628.odt?=') - il renvoie la
    chaine brute telle quelle. Sans ce decodage, l'extension se retrouve
    corrompue (".odt?=" au lieu de ".odt") et le fichier est silencieusement
    ignore par le filtre ALLOWED_EXTENSIONS, meme si l'extension est autorisee."""
    if not raw:
        return raw
    try:
        parts = decode_header(raw)
        return "".join(
            p.decode(enc or "utf-8", errors="ignore") if isinstance(p, bytes) else p
            for p, enc in parts
        )
    except Exception:
        return raw


def get_text_parts(message):
    """Concatene le texte (plain + html brut) du message pour la recherche de mots-cles."""
    parts = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "text":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
                except Exception:
                    continue
    else:
        try:
            payload = message.get_payload(decode=True)
            if payload:
                parts.append(payload.decode(message.get_content_charset() or "utf-8", errors="ignore"))
        except Exception:
            pass
    return "\n".join(parts)


def message_date(message):
    date_hdr = message.get("Date")
    if not date_hdr:
        return None
    try:
        dt = parsedate_to_datetime(str(date_hdr))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def extract(mbox_path: Path, output_dir: Path, depuis: datetime):
    output_dir.mkdir(parents=True, exist_ok=True)
    mbox = mailbox.mbox(str(mbox_path), factory=None)

    total_messages = 0
    matched_messages = 0
    saved_files = 0
    skipped_existing = 0

    for message in mbox:
        total_messages += 1
        if total_messages % 2000 == 0:
            log(f"... {total_messages} messages parcourus, {saved_files} fichier(s) extrait(s) jusqu'ici")

        dt = message_date(message)
        if dt and dt < depuis:
            continue

        subject = str(message.get("Subject", "") or "")
        body_text = get_text_parts(message)
        if not KEYWORD_RE.search(subject) and not KEYWORD_RE.search(body_text):
            continue

        sender = str(message.get("From", "inconnu"))
        date_prefix = dt.strftime("%Y-%m-%d") if dt else "0000-00-00"

        has_attachment_match = False
        for part in message.walk():
            filename = decode_filename(part.get_filename())
            if not filename:
                continue
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            out_name = f"{date_prefix}_{sanitize(sender)}_{sanitize(Path(filename).stem)}{ext}"
            out_path = output_dir / out_name
            if out_path.exists():
                skipped_existing += 1
                continue
            out_path.write_bytes(payload)
            saved_files += 1
            has_attachment_match = True

        if has_attachment_match:
            matched_messages += 1

    log(f"Termine. {total_messages} message(s) parcouru(s), {matched_messages} facture(s) detectee(s), "
        f"{saved_files} fichier(s) extrait(s) vers {output_dir} "
        f"({skipped_existing} deja present(s), ignores).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mbox_path", help="Chemin vers le fichier .mbox exporte par Google Takeout")
    parser.add_argument("output_dir", help="Dossier ou ecrire les pieces jointes extraites")
    parser.add_argument("--depuis", default="2019-01-01", help="Date minimale (AAAA-MM-JJ), defaut 2019-01-01")
    args = parser.parse_args()

    mbox_path = Path(args.mbox_path)
    if not mbox_path.is_file():
        parser.error(f"Fichier introuvable : {mbox_path}")

    depuis = datetime.strptime(args.depuis, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    extract(mbox_path, Path(args.output_dir), depuis)


if __name__ == "__main__":
    main()
