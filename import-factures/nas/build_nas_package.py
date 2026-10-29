"""
Prepare le dossier "gmao-imports" a deposer sur le NAS Synology (voir LISEZMOI_NAS.md).

    python nas/build_nas_package.py

Cree nas/dist/gmao-imports/ avec : les scripts Python d'import, les scripts shell (fins de ligne Linux),
requirements-nas.txt, mailbox_seen.json (pour ne pas retraiter les mails deja importes) et un fichier .env
construit a partir du .env du PC SANS les variables inutiles sur le NAS : mot de passe du NAS, chemins
Windows et phrase secrete du chiffrement des salaires (qui ne doit jamais quitter le PC).

Le dossier dist/ contient des secrets (cle Supabase, mots de passe d'application Gmail) : il est ignore par git
et ne doit etre depose que dans un emplacement prive du NAS (ex. dossier personnel de l'administrateur).
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent
DIST = HERE / "dist" / "gmao-imports"

PY_FILES = [
    "import_mailbox.py", "import_factures.py", "import_devis.py", "import_documents.py",
    "import_releve.py", "backup_to_nas.py", "sync_gamme_calendar.py", "nas_naming.py",
]
SH_FILES = ["common.sh", "run_all.sh", "run_backup.sh", "setup_nas.sh"]
DROP_ENV = {"NAS_USER", "NAS_PASSWORD", "NAS_SALAIRE_PASSPHRASE", "WATCH_DIR", "DEVIS_WATCH_DIR",
            "DOCUMENTS_WATCH_DIR", "NAS_SAVADUR_PATH", "NAS_PERSO_PATH"}


def write_lf(src: Path, dst: Path):
    dst.write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    for name in PY_FILES:
        write_lf(SRC / name, DIST / name)
    for name in SH_FILES:
        write_lf(HERE / name, DIST / name)
    write_lf(HERE / "requirements-nas.txt", DIST / "requirements-nas.txt")
    seen = SRC / "mailbox_seen.json"
    if seen.exists():
        shutil.copyfile(seen, DIST / "mailbox_seen.json")

    env_src = SRC / ".env"
    if not env_src.exists():
        sys.exit(".env introuvable dans import-factures/")
    kept, dropped = [], []
    for line in env_src.read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0].strip()
        if line.strip() and not line.lstrip().startswith("#") and key in DROP_ENV:
            dropped.append(key)
            continue
        kept.append(line)
    (DIST / ".env").write_bytes(("\n".join(kept) + "\n").encode("utf-8"))
    (DIST / "logs").mkdir()
    print(f"Paquet pret : {DIST}")
    print("  scripts Python :", len(PY_FILES), "| scripts shell :", len(SH_FILES))
    print("  variables .env retirees :", ", ".join(sorted(set(dropped))))


if __name__ == "__main__":
    main()
