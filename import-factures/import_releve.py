"""
Scan le dossier "Relevé de compte" sur le NAS (NAS_SAVADUR_PATH/Relevé de
compte/<Année>/<fichier>.ofx, ex: "01.26.Relevé CMB.ofx" pour janvier 2026,
depose a la main par l'utilisateur chaque debut de mois) et rapproche
automatiquement chaque operation avec la table `factures` (compte=savadur) :
pas d'etape de validation manuelle comme les autres pipelines (factures/
devis/documents) - une operation debit qui correspond exactement (au
centime) au montant TTC d'une facture non encore rapprochee est rapprochee
directement (rapproche=true, date_paiement completee si vide). Seules les
anomalies (aucune facture au bon montant, ou plusieurs candidates ambigues)
sont remontees pour un coup d'oeil humain, dans la table `releve_imports`
(affichee dans le GMAO, onglet Factures > SAVADUR).

Les operations credit (loyers, CAF...) ne sont PAS modifiees automatiquement
(rent_payments.paye a des effets de bord ailleurs dans l'appli - quittances,
dette locataire) : seule une verification informative est faite (le nom du
payeur correspond-il a un locataire SAVADUR actif ?), remontee elle aussi
comme anomalie legere si aucun nom ne correspond.

Idempotent par nom de fichier : un fichier deja prefixe "Importée " (marque
apres traitement, directement dans son dossier final - pas de dossier de
transit separe ici, contrairement aux autres pipelines) n'est jamais
retraite.

Usage :
    pip install -r requirements.txt
    python import_releve.py

A lancer periodiquement via le Planificateur de taches Windows, en parallele
des autres pipelines (meme dependances : SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY/
NAS_SAVADUR_PATH/NAS_USER/NAS_PASSWORD, deja dans .env).
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from nas_naming import dubail_filter

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
NAS_SAVADUR_PATH = os.environ.get("NAS_SAVADUR_PATH", "")
NAS_USER = os.environ.get("NAS_USER", "")
NAS_PASSWORD = os.environ.get("NAS_PASSWORD", "")

TABLE = "releve_imports"
IMPORT_MARKER = "Importée "

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}


def log(msg):
    print(f"[import-releve] {msg}")


def connect_nas_share(unc_path):
    """Meme mecanisme que les autres scripts de ce dossier (duplique,
    scripts independants) : authentifie la session Windows sur le partage
    NAS avant tout acces fichier."""
    if not unc_path:
        return
    result = subprocess.run(
        ["net", "use", unc_path, NAS_PASSWORD, f"/user:{NAS_USER}"],
        capture_output=True, text=True,
    )
    combined = (result.stdout + result.stderr).lower()
    if result.returncode != 0 and "déjà" not in combined and "already" not in combined and "multiple" not in combined:
        log(f"  ATTENTION connexion NAS ({unc_path}) : {result.stdout.strip()} {result.stderr.strip()}")


def parse_ofx(path: Path):
    """Parseur minimaliste pour l'OFX 1.x/SGML (tags non fermes, une valeur
    par ligne) tel qu'exporte par CMB en ligne - pas de dependance externe,
    la structure est reguliere et simple a extraire par regex."""
    text = path.read_text(encoding="cp1252", errors="replace")
    period_start = _tag(text, "DTSTART")
    period_end = _tag(text, "DTEND")
    txns = []
    for block in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, re.S):
        date_str = _tag(block, "DTPOSTED")
        amount_str = _tag(block, "TRNAMT")
        if not date_str or not amount_str:
            continue
        txns.append({
            "type": _tag(block, "TRNTYPE"),
            "date": datetime.strptime(date_str[:8], "%Y%m%d").date(),
            "amount": float(amount_str),
            "name": (_tag(block, "NAME") or "").strip(),
            "fitid": _tag(block, "FITID"),
        })
    period_start = datetime.strptime(period_start[:8], "%Y%m%d").date() if period_start else None
    period_end = datetime.strptime(period_end[:8], "%Y%m%d").date() if period_end else None
    return period_start, period_end, txns


def _tag(text, tag):
    m = re.search(rf"<{tag}>([^\r\n<]*)", text)
    return m.group(1).strip() if m else None


def fetch_savadur_factures():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/factures",
        params={"compte": "eq.savadur", "select": "id,date,fournisseur,montant_ttc,rapproche,date_paiement"},
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_savadur_tenant_names():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/tenants",
        params={"select": "nom,logement,actif"},
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return [
        t["nom"] for t in resp.json()
        if t.get("actif", True) is not False and dubail_filter(t.get("logement") or "")
        and t.get("nom")
    ]


def fetch_recurring_expenses() -> dict:
    """Prelevements recurrents deja reconnus (voir add_recurring_expenses.sql) -
    cle (libelle bancaire exact, montant) pour un lookup direct par operation."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/recurring_expenses",
        params={"compte": "eq.savadur", "actif": "eq.true", "select": "*"},
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return {(r["libelle"].strip(), round(float(r["montant"]), 2)): r for r in resp.json()}


def update_facture(facture_id, patch):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/factures?id=eq.{facture_id}",
        headers=HEADERS, json=patch, timeout=30,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"update facture {facture_id} echoue ({resp.status_code}) : {resp.text[:300]}")


def insert_report(row):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers={**HEADERS, "Prefer": "return=minimal"},
        json=row, timeout=30,
    )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"insert {TABLE} echoue ({resp.status_code}) : {resp.text[:300]}")


def match_debit(txn, unrapprochees):
    """Renvoie (facture_matchee_ou_None, candidats_ambigus). Le montant TTC
    d'une facture est toujours positif, TRNAMT d'un debit est negatif.

    Rapprochement automatique UNIQUEMENT si un seul candidat a ce montant :
    des lors qu'il y en a plusieurs (charge recurrente a montant fixe, ex.
    contrat d'entretien mensuel identique) on ne devine pas lequel via la
    date - une facture est datee a la discretion du fournisseur (souvent fin
    de mois pour un service en cours), pas forcement le jour le plus proche
    du prelevement reel ; deviner par ecart de jours a deja produit un faux
    rapprochement sur le mauvais mois. Mieux vaut remonter tous les candidats
    et laisser un humain choisir en 1 clic dans le GMAO."""
    amount = abs(txn["amount"])
    candidates = [f for f in unrapprochees if f.get("montant_ttc") is not None and abs(float(f["montant_ttc"]) - amount) < 0.01]
    if not candidates:
        return None, []
    if len(candidates) == 1:
        return candidates[0], []
    return None, candidates


def apply_recurring(txn, rule, factures_by_id):
    """Applique une regle deja reconnue (recurring_expenses) a une operation :
    renvoie True si l'operation est bien prise en compte (echeancier sans
    facture, ou facture liee avec encore du solde disponible), False si la
    regle existe mais ne peut pas s'appliquer ce mois-ci (facture liee deja
    soldee - probablement une nouvelle annee sans facture encore attachee) et
    que l'operation doit donc repasser par le rapprochement normal."""
    if rule["mode"] == "echeancier":
        return True
    facture = factures_by_id.get(rule.get("facture_id"))
    if not facture:
        return False
    rapprochements = list(facture.get("rapprochements") or [])
    deja = sum(float(x.get("montant") or 0) for x in rapprochements)
    montant_ttc = float(facture.get("montant_ttc") or 0)
    if deja >= montant_ttc - 0.01:
        return False  # facture deja soldee, la regle doit etre mise a jour cote GMAO
    rapprochements.append({"montant": abs(txn["amount"]), "date": txn["date"].isoformat(), "recurring_expense_id": rule["id"]})
    total = sum(float(x.get("montant") or 0) for x in rapprochements)
    patch = {"rapprochements": rapprochements, "rapproche": total >= montant_ttc - 0.01}
    if not facture.get("date_paiement"):
        patch["date_paiement"] = txn["date"].isoformat()
    update_facture(facture["id"], patch)
    facture.update(patch)
    return True


def process_file(path: Path, tenant_names: list):
    log(f"Traitement : {path.name}")
    period_start, period_end, txns = parse_ofx(path)
    factures = fetch_savadur_factures()
    factures_by_id = {f["id"]: f for f in factures}
    recurring = fetch_recurring_expenses()
    # Le rapprochement bancaire n'a demarre qu'en 2026 : une facture plus
    # ancienne que ~12 mois n'a plus de raison d'etre proposee comme
    # candidate (evite aussi qu'une vieille facture ne soit retenue par
    # coincidence de montant comme seul candidat "sur - donc auto-rapprochee
    # a tort).
    date_cutoff = datetime.now().date() - timedelta(days=365)
    unrapprochees = [
        f for f in factures
        if not f.get("rapproche") and (not f.get("date") or datetime.strptime(f["date"][:10], "%Y-%m-%d").date() >= date_cutoff)
    ]

    anomalies = []
    nb_rapproches = 0
    nb_sans_facture = 0
    nb_ambigus = 0
    nb_credits_non_identifies = 0
    nb_recurrents_connus = 0
    tenant_names_lower = [n.lower() for n in tenant_names]

    for txn in txns:
        if txn["type"] == "DEBIT":
            rule = recurring.get((txn["name"].strip(), round(abs(txn["amount"]), 2)))
            if rule and apply_recurring(txn, rule, factures_by_id):
                nb_recurrents_connus += 1
                continue
            match, ambigus = match_debit(txn, unrapprochees)
            if match:
                rapprochements = list(match.get("rapprochements") or []) + [{"montant": abs(txn["amount"]), "date": txn["date"].isoformat()}]
                patch = {"rapproche": True, "rapprochements": rapprochements}
                if not match.get("date_paiement"):
                    patch["date_paiement"] = txn["date"].isoformat()
                update_facture(match["id"], patch)
                match.update(patch)  # ne plus le proposer a un autre txn du meme releve
                nb_rapproches += 1
            elif ambigus:
                nb_ambigus += 1
                anomalies.append({
                    "type": "ambigu",
                    "date": txn["date"].isoformat(),
                    "montant": txn["amount"],
                    "libelle": txn["name"],
                    "candidats": [{"id": c["id"], "fournisseur": c.get("fournisseur"), "date": c.get("date")} for c in ambigus[:5]],
                })
            else:
                nb_sans_facture += 1
                anomalies.append({
                    "type": "debit_sans_facture",
                    "date": txn["date"].isoformat(),
                    "montant": txn["amount"],
                    "libelle": txn["name"],
                })
        elif txn["type"] == "CREDIT":
            name_lower = txn["name"].lower()
            if not any(tn in name_lower or name_lower in tn for tn in tenant_names_lower if tn):
                nb_credits_non_identifies += 1
                anomalies.append({
                    "type": "credit_non_identifie",
                    "date": txn["date"].isoformat(),
                    "montant": txn["amount"],
                    "libelle": txn["name"],
                })

    insert_report({
        "compte": "savadur",
        "fichier_nom": path.name,
        "chemin_relatif": str(path.relative_to(Path(NAS_SAVADUR_PATH))),
        "periode_debut": period_start.isoformat() if period_start else None,
        "periode_fin": period_end.isoformat() if period_end else None,
        "nb_operations": len(txns),
        "nb_debits_rapproches": nb_rapproches,
        "nb_debits_sans_facture": nb_sans_facture,
        "nb_ambigus": nb_ambigus,
        "nb_credits_non_identifies": nb_credits_non_identifies,
        "nb_recurrents_connus": nb_recurrents_connus,
        "anomalies": anomalies,
    })
    log(f"  -> {nb_rapproches} rapprochee(s), {nb_recurrents_connus} recurrent(s) reconnu(s), {nb_sans_facture} sans facture, {nb_ambigus} ambigu(s), {nb_credits_non_identifies} credit(s) non identifie(s)")

    marked = path.with_name(IMPORT_MARKER + path.name)
    path.rename(marked)
    log(f"  Renomme : {marked.name}")


def main():
    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans .env")
    if not NAS_SAVADUR_PATH:
        sys.exit("NAS_SAVADUR_PATH manquant dans .env")

    connect_nas_share(NAS_SAVADUR_PATH)
    releves_root = Path(NAS_SAVADUR_PATH) / "Relevé de compte"
    if not releves_root.is_dir():
        sys.exit(f"Dossier introuvable ou inaccessible : {releves_root}")

    candidates = [
        p for p in sorted(releves_root.glob("*/*.ofx"))
        if p.is_file() and not p.name.startswith(IMPORT_MARKER)
    ]
    log(f"{len(candidates)} releve(s) a traiter dans {releves_root}")
    if not candidates:
        return

    tenant_names = fetch_savadur_tenant_names()
    for p in candidates:
        try:
            process_file(p, tenant_names)
        except Exception as e:
            log(f"  ERREUR inattendue sur {p.name} : {e}")


if __name__ == "__main__":
    main()
