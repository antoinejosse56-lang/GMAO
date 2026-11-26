"""
Previent par email quand la sauvegarde nocturne n'est pas complete (appele par nas/run_backup.sh).

Usage : python alerte_sauvegarde.py <code backup_base> <code backup_to_nas>
        python alerte_sauvegarde.py --essai        envoie un email d'essai (pour verifier que l'alerte arrive)
        ajouter --simulation pour afficher le message sans rien envoyer

Rien n'est envoye si les deux codes valent 0. La cle Brevo est lue dans app_config (comme check_calendriers.py).
"""
import html
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

DESTINATAIRE = os.environ.get("ALERTE_SAUVEGARDE_EMAIL", "antoinejosse56@gmail.com")
SENS = {"1": "ECHEC", "2": "INCOMPLETE ou baisse anormale", "124": "INTERROMPUE (trop longue)"}
PARTIES = (("Tableaux de la base", "backup_base.log"), ("Fichiers", "backup_to_nas.log"))
MOTS = ("ERREUR", "ECHEC", "ATTENTION", "MANQUANT", "VERIFICATION", "Traceback", "Error")


def log(msg):
    print(f"[{datetime.now():%F %T}] [alerte-sauvegarde] {msg}", flush=True)


def extrait(nom, maximum=25):
    """Lignes importantes du dernier passage inscrit dans un journal."""
    try:
        with open(os.path.join(HERE, "logs", nom), encoding="utf-8", errors="replace") as f:
            lignes = f.read().splitlines()[-4000:]
    except OSError:
        return ["(journal introuvable)"]
    debuts = [i for i, x in enumerate(lignes) if x.startswith("===")]
    if debuts:
        lignes = lignes[debuts[-1]:]
    importantes = [x for x in lignes if any(m in x for m in MOTS)] or lignes
    return importantes[-maximum:]


def message(codes):
    blocs = []
    for (titre, journal), code in zip(PARTIES, codes):
        etat = "complete" if code == "0" else SENS.get(code, f"en erreur (code {code})")
        couleur = "#1D9E75" if code == "0" else "#C0392B"
        blocs.append(f"<h3 style='margin:16px 0 4px'>{titre} : <span style='color:{couleur}'>{etat}</span></h3>")
        if code != "0":
            texte = html.escape(chr(10).join(extrait(journal)))
            blocs.append(f"<pre style='background:#f4f4f4;padding:10px;font-size:11px;white-space:pre-wrap'>{texte}</pre>")
    return ("<div style='font-family:Arial,sans-serif;max-width:720px'>"
            "<h2 style='color:#C0392B'>GMAO : la sauvegarde de cette nuit n'est pas complete</h2>"
            + "".join(blocs) +
            "<p style='color:#888;font-size:12px'>Tant que le probleme n'est pas regle, aucune ancienne sauvegarde "
            "des tableaux n'est supprimee. Journaux complets : dossier gmao-imports/logs du NAS.</p></div>")


def envoyer(sujet, contenu):
    base = os.environ["SUPABASE_URL"].rstrip("/")
    cle_service = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.get(f"{base}/rest/v1/app_config", params={"select": "value", "key": "eq.brevo_api_key"},
                     headers={"apikey": cle_service, "Authorization": f"Bearer {cle_service}"}, timeout=20)
    r.raise_for_status()
    lignes = r.json()
    if not lignes or not lignes[0].get("value"):
        log("ERREUR : pas de cle Brevo, email non envoye")
        return 1
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": lignes[0]["value"], "Content-Type": "application/json"},
        json={"sender": {"name": "GMAO Pro", "email": DESTINATAIRE}, "to": [{"email": DESTINATAIRE}],
              "subject": sujet, "htmlContent": contenu},
        timeout=30,
    )
    log(f"email : HTTP {r.status_code}" + ("" if r.ok else f" - {r.text[:200]}"))
    return 0 if r.ok else 1


def main(argv):
    simulation = "--simulation" in argv
    args = [a for a in argv if a != "--simulation"]
    if args == ["--essai"]:
        sujet = "GMAO : essai de l'alerte de sauvegarde"
        contenu = "<p>Ceci est un essai : l'alerte de sauvegarde fonctionne.</p>"
    elif len(args) == 2:
        if args == ["0", "0"]:
            log("sauvegarde complete, rien a signaler")
            return 0
        sujet, contenu = "GMAO : sauvegarde INCOMPLETE", message(args)
    else:
        log("usage : alerte_sauvegarde.py <code base> <code fichiers> | --essai")
        return 1
    if simulation:
        print(sujet)
        print(contenu)
        return 0
    return envoyer(sujet, contenu)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        log(f"ERREUR : {type(exc).__name__} : {exc}")
        sys.exit(1)
