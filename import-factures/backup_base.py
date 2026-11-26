"""
Sauvegarde de TOUTES les tables Supabase (loyers, locataires, reservations, releves, saisies...) vers le NAS.
Complete backup_to_nas.py, qui ne copie que les fichiers (buckets Storage).

LECTURE SEULE sur la base : uniquement des requetes GET, aucune donnee n'est modifiee.

Un fichier par passage : <partage Perso>/_Sauvegarde base GMAO/gmao_base_AAAA-MM-JJ_HHMMSS.zip, contenant un
fichier JSON par table + _inventaire.json. Les cles secretes de app_config sont masquees.

Conservation : les 3 dernieres sauvegardes saines. Une plus ancienne n'est supprimee qu'APRES la reussite d'une
nouvelle sauvegarde saine. Sauvegarde incomplete (_INCOMPLETE) ou baisse anormale (_ALERTE) : RIEN n'est
supprime, et ces archives ne sont jamais effacees automatiquement. Seuls les fichiers gmao_base_*.zip de ce
dossier sont concernes.

Verification a chaque passage : chaque table est lue deux fois de suite jusqu'a obtenir deux lectures
identiques, le nombre de lignes est compare a celui annonce par la base, puis l'archive est relue et comparee
VALEUR PAR VALEUR a ce qui a ete lu.

Controles : alerte si, depuis
la derniere sauvegarde saine, une table a disparu, s'est videe ou a perdu au moins 5 lignes et 10 %.
L'alerte persiste (comparaison avec la derniere sauvegarde saine) tant qu'elle n'a pas ete examinee.

Codes de sortie : 0 = complet ; 2 = incomplet ou baisse anormale (voir le journal) ; 1 = echec.

Tourne chaque nuit sur le NAS (nas/run_backup.sh) ou a la main : python backup_base.py
"""
import json
import os
import re
import sys
import time
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
CONSERVER = 3  # nombre de sauvegardes saines gardees
ARCHIVE_SAINE = re.compile(r"^gmao_base_\d{4}-\d{2}-\d{2}_\d{6}\.zip$")
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


def lire_table_stable(nom, colonnes, essais=4):
    """Lit la table jusqu'a obtenir deux lectures successives identiques (base modifiee pendant la lecture)."""
    precedente = None
    for essai in range(essais):
        lignes, total = lire_table(nom, colonnes)
        contenu = sorted(json.dumps(x, sort_keys=True) for x in lignes)
        if contenu == precedente:
            return lignes, total
        precedente = contenu
        if essai:
            time.sleep(5)
    raise RuntimeError(f"contenu different a chaque lecture ({essais} essais)")


def masquer_secrets(lignes):
    for ligne in lignes:
        if any(s in str(ligne.get("key", "")).lower() for s in SECRETS):
            ligne["value"] = "(masque dans la sauvegarde)"


def inventaire_precedent(dossier):
    """Nombre de lignes par table dans la derniere sauvegarde saine."""
    archives = sorted(n for n in os.listdir(dossier) if ARCHIVE_SAINE.match(n))
    for nom in reversed(archives):
        try:
            with zipfile.ZipFile(os.path.join(dossier, nom)) as z:
                return nom, json.loads(z.read("_inventaire.json"))["tables"]
        except Exception as e:
            log(f"archive precedente illisible ({nom}) : {e}")
    return None, {}


def supprimer_anciennes(dossier):
    """Ne garde que les CONSERVER dernieres sauvegardes saines (appele seulement apres un passage sain)."""
    saines = sorted(n for n in os.listdir(dossier) if ARCHIVE_SAINE.match(n))
    for nom in saines[:-CONSERVER]:
        os.remove(os.path.join(dossier, nom))
        log(f"ancienne sauvegarde supprimee : {nom}")


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

    donnees, inventaire, erreurs = {}, {}, []
    for nom in sorted(definitions):
        try:
            lignes, total = lire_table_stable(nom, definitions[nom].get("properties", {}))
        except Exception as e:
            erreurs.append(f"{nom} : {e}")
            continue
        if nom == "app_config":
            masquer_secrets(lignes)
        if total is not None and len(lignes) != total:
            erreurs.append(f"{nom} : {len(lignes)} lignes lues sur {total} annoncees")
        inventaire[nom] = len(lignes)
        donnees[nom] = lignes

    nom_prec, precedent = inventaire_precedent(dossier)
    alertes = []
    for table, avant in precedent.items():
        apres = inventaire.get(table)
        if apres is None:
            alertes.append(f"table {table} absente ({avant} lignes dans {nom_prec})")
        elif (apres == 0 and avant >= 3) or (avant - apres >= 5 and avant - apres >= avant * 0.10):
            alertes.append(f"table {table} : {avant} -> {apres} lignes depuis {nom_prec}")

    horodatage = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffixe = "_INCOMPLETE" if erreurs else ("_ALERTE" if alertes else "")
    final = os.path.join(dossier, f"gmao_base_{horodatage}{suffixe}.zip")
    partiel = final + ".part"
    with zipfile.ZipFile(partiel, "x", zipfile.ZIP_DEFLATED) as z:
        for table, lignes in donnees.items():
            z.writestr(f"{table}.json", json.dumps(lignes, ensure_ascii=False, indent=1))
        z.writestr("_inventaire.json", json.dumps(
            {"date": horodatage, "tables": inventaire, "erreurs": erreurs, "alertes": alertes},
            ensure_ascii=False, indent=1))
    with zipfile.ZipFile(partiel) as z:  # relecture de controle, valeur par valeur
        differentes = [t for t, lignes in donnees.items() if json.loads(z.read(f"{t}.json")) != lignes]
        if z.testzip() is not None or differentes:
            log(f"ERREUR : l'archive relue ne correspond pas aux donnees lues {differentes}")
            return 1
    os.rename(partiel, final)

    log(f"{len(inventaire)} tables, {sum(inventaire.values())} lignes -> {final} "
        f"({os.path.getsize(final) // 1024} Ko)")
    valeurs = sum(len(x) for lignes in donnees.values() for x in lignes)
    log(f"VERIFICATION : {len(donnees)}/{len(definitions)} tables confirmees par double lecture, {valeurs} valeurs "
        "relues a l'identique dans l'archive")
    for e in erreurs:
        log(f"ERREUR table : {e}")
    for a in alertes:
        log(f"ATTENTION baisse de donnees : {a}")
    if erreurs or alertes:
        log("aucune ancienne sauvegarde supprimee (a examiner)")
        return 2
    supprimer_anciennes(dossier)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # le journal doit toujours dire pourquoi
        log(f"ERREUR : {type(exc).__name__} : {exc}")
        sys.exit(1)
