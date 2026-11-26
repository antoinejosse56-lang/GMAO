"""
Sauvegarde de TOUTES les tables Supabase (loyers, locataires, reservations, releves, saisies...) vers le NAS.
Complete backup_to_nas.py, qui ne copie que les fichiers (buckets Storage).

LECTURE SEULE sur la base : uniquement des requetes GET, aucune donnee n'est modifiee.

Un fichier par passage : <partage Perso>/_Sauvegarde base GMAO/gmao_base_AAAA-MM-JJ_HHMM.zip, contenant un
fichier JSON par table + _inventaire.json. Les anciennes sauvegardes ne sont JAMAIS ecrasees ni supprimees
(quelques centaines de Ko par jour). Les cles secretes de app_config sont masquees.

Controles : nombre de lignes compare a celui annonce par la base, relecture de l'archive, et message
ATTENTION si une table a perdu plus de 10 % de ses lignes depuis la sauvegarde precedente.

Codes de sortie : 0 = complet ; 2 = incomplet ou baisse anormale (voir le journal) ; 1 = echec.

Tourne chaque nuit sur le NAS (nas/run_backup.sh) ou a la main : python backup_base.py
"""
import json
import os
import sys
import zipfile
from datetime import datetime

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
DOSSIER = "_Sauvegarde base GMAO"
PAGE = 1000
SECRETS = ("api_key", "secret", "token", "password")


def log(msg):
    print(f"[{datetime.now():%F %T}] [backup-base] {msg}", flush=True)


def lire_table(nom, colonnes):
    """Toutes les lignes d'une table, par pages, dans un ordre stable. Renvoie (lignes, total annonce)."""
    ordre = "id" if "id" in colonnes else ("key" if "key" in colonnes else next(iter(colonnes), None))
    lignes, total = [], None
    while True:
        params = {"select": "*"}
        if ordre:
            params["order"] = f"{ordre}.asc"
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{nom}",
            params=params,
            headers={**HEADERS, "Prefer": "count=exact", "Range-Unit": "items",
                     "Range": f"{len(lignes)}-{len(lignes) + PAGE - 1}"},
            timeout=120,
        )
        r.raise_for_status()
        page = r.json()
        annonce = r.headers.get("Content-Range", "/").split("/")[-1]
        total = int(annonce) if annonce.isdigit() else total
        lignes += page
        if not page or (total is not None and len(lignes) >= total) or (total is None and len(page) < PAGE):
            return lignes, total


def masquer_secrets(lignes):
    for ligne in lignes:
        if any(s in str(ligne.get("key", "")).lower() for s in SECRETS):
            ligne["value"] = "(masque dans la sauvegarde)"


def inventaire_precedent(dossier):
    """Nombre de lignes par table dans la derniere sauvegarde complete."""
    archives = sorted(n for n in os.listdir(dossier)
                      if n.startswith("gmao_base_") and n.endswith(".zip") and "INCOMPLETE" not in n)
    for nom in reversed(archives):
        try:
            with zipfile.ZipFile(os.path.join(dossier, nom)) as z:
                return nom, json.loads(z.read("_inventaire.json"))["tables"]
        except Exception as e:
            log(f"archive precedente illisible ({nom}) : {e}")
    return None, {}


def main():
    racine = os.environ.get("NAS_PERSO_PATH", "")
    if not racine or not os.path.isdir(racine):
        log(f"ERREUR : partage NAS introuvable (NAS_PERSO_PATH='{racine}')")
        return 1
    dossier = os.path.join(racine, DOSSIER)
    os.makedirs(dossier, exist_ok=True)

    spec = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=HEADERS, timeout=60)
    spec.raise_for_status()
    definitions = spec.json()["definitions"]
    if not definitions:
        log("ERREUR : aucune table annoncee par la base")
        return 1

    contenus, inventaire, erreurs = {}, {}, []
    for nom in sorted(definitions):
        try:
            lignes, total = lire_table(nom, definitions[nom].get("properties", {}))
        except Exception as e:
            erreurs.append(f"{nom} : {e}")
            continue
        if nom == "app_config":
            masquer_secrets(lignes)
        if total is not None and len(lignes) != total:
            erreurs.append(f"{nom} : {len(lignes)} lignes lues sur {total} annoncees")
        inventaire[nom] = len(lignes)
        contenus[nom] = json.dumps(lignes, ensure_ascii=False, indent=1)

    nom_prec, precedent = inventaire_precedent(dossier)
    alertes = []
    for table, avant in precedent.items():
        apres = inventaire.get(table)
        if apres is None:
            alertes.append(f"table {table} absente ({avant} lignes dans {nom_prec})")
        elif avant - apres >= max(1, avant * 0.10):
            alertes.append(f"table {table} : {avant} -> {apres} lignes depuis {nom_prec}")

    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffixe = "_INCOMPLETE" if erreurs else ""
    final = os.path.join(dossier, f"gmao_base_{horodatage}{suffixe}.zip")
    partiel = final + ".part"
    with zipfile.ZipFile(partiel, "x", zipfile.ZIP_DEFLATED) as z:
        for table, texte in contenus.items():
            z.writestr(f"{table}.json", texte)
        z.writestr("_inventaire.json", json.dumps(
            {"date": horodatage, "tables": inventaire, "erreurs": erreurs, "alertes": alertes},
            ensure_ascii=False, indent=1))
    with zipfile.ZipFile(partiel) as z:  # relecture de controle
        if z.testzip() is not None or any(len(json.loads(z.read(f"{t}.json"))) != n for t, n in inventaire.items()):
            log("ERREUR : l'archive relue ne correspond pas aux donnees lues")
            return 1
    os.rename(partiel, final)

    log(f"{len(inventaire)} tables, {sum(inventaire.values())} lignes -> {final} "
        f"({os.path.getsize(final) // 1024} Ko)")
    for e in erreurs:
        log(f"ERREUR table : {e}")
    for a in alertes:
        log(f"ATTENTION baisse de donnees : {a}")
    return 2 if erreurs or alertes else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # le journal doit toujours dire pourquoi
        log(f"ERREUR : {type(exc).__name__} : {exc}")
        sys.exit(1)
