"""
Chiffre (AES-256-GCM) et upsert dans Supabase (table fiches_paie_chiffrees)
les fiches de salaire deja transcrites en JSON sur le NAS
(Famille/Salaire/<annee>/salaire_<annee>.json et
Famille/Salaire/compte_recuperation.json).

Meme schema de chiffrement que index.html (voir SALAIRE_PBKDF2_SALT_B64 et
deriveSalaireKey/salaireEncrypt) : cle derivee UNE FOIS via PBKDF2-HMAC-
SHA256 (210000 iterations) a partir de la passphrase + un sel global fixe
(pas secret), puis un IV aleatoire de 12 octets par enregistrement pour
AES-GCM. La passphrase n'est jamais stockee ici en dur - elle est lue
depuis NAS_SALAIRE_PASSPHRASE dans .env (meme fichier _cle_dechiffrement.txt
que celui pose sur le NAS pour Antoine).

Usage :
    pip install -r requirements.txt
    python import_salaire_chiffre.py
"""
import base64
import json
import os
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

IMPORT_FACTURES_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(IMPORT_FACTURES_DIR, ".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}

NAS_PERSO_PATH = os.environ.get("NAS_PERSO_PATH", "")
SALAIRE_DIR = Path(NAS_PERSO_PATH) / "Famille" / "Salaire"

# Doit correspondre EXACTEMENT a SALAIRE_PBKDF2_SALT_B64 dans index.html -
# ce n'est pas un secret (juste un sel PBKDF2), mais il doit etre identique
# des deux cotes pour que le navigateur puisse dechiffrer ce qu'on chiffre ici.
PBKDF2_SALT_B64 = "amAgAqvi/ZBhfhgN/4PeDw=="
PBKDF2_ITERATIONS = 210_000
PASSPHRASE = os.environ["NAS_SALAIRE_PASSPHRASE"]


def log(msg):
    print(f"[import-salaire] {msg}")


def derive_key(passphrase: str, salt_b64: str) -> bytes:
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERATIONS)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_json(key: bytes, obj) -> dict:
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    ct = aesgcm.encrypt(iv, data, None)
    return {"iv": base64.b64encode(iv).decode(), "ciphertext": base64.b64encode(ct).decode()}


def upsert_row(periode, type_, key):
    """Supprime l'ancienne ligne (meme periode+type) puis insere la nouvelle -
    pas de contrainte unique en base, on gere le remplacement ici."""
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/fiches_paie_chiffrees",
        params={"periode": f"eq.{periode}", "type": f"eq.{type_}"},
        headers=HEADERS, timeout=30,
    )
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/fiches_paie_chiffrees",
        headers={**HEADERS, "Prefer": "return=representation"},
        json={"periode": periode, "type": type_, **key},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        log(f"  ERREUR {periode}/{type_} : {resp.status_code} {resp.text}")
        return False
    return True


def main():
    key = derive_key(PASSPHRASE, PBKDF2_SALT_B64)
    log(f"Dossier source : {SALAIRE_DIR}")

    n = 0
    for year_dir in sorted(SALAIRE_DIR.glob("*")):
        if not year_dir.is_dir():
            continue
        salaire_file = year_dir / f"salaire_{year_dir.name}.json"
        if not salaire_file.exists():
            continue
        data = json.loads(salaire_file.read_text(encoding="utf-8"))
        for fiche in data.get("fiches", []):
            periode = fiche["periode"]
            enc = encrypt_json(key, fiche)
            if upsert_row(periode, "bulletin", enc):
                log(f"  OK bulletin {periode}")
                n += 1

    recup_file = SALAIRE_DIR / "compte_recuperation.json"
    if recup_file.exists():
        recup_data = json.loads(recup_file.read_text(encoding="utf-8"))
        enc = encrypt_json(key, recup_data)
        if upsert_row("cumul", "compte_recup", enc):
            log("  OK compte_recup")
            n += 1

    log(f"Terminé : {n} ligne(s) chiffrée(s) et envoyée(s).")


if __name__ == "__main__":
    main()
