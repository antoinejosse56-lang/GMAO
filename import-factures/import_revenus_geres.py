"""
Importe un export CSV de compte-rendu de gestion (CRG) d'une agence
(Foncia...) pour un bien entierement gere par un tiers - dans revenus_geres.

Format attendu (export "Comptabilite" du portail proprietaire Foncia) :
    DATE;LABEL;DEBIT;CREDIT
    23/09/2026;CRG SOLDE COMPTE A.S.L JEAN MARTIN;;568,79
    23/09/2026;PAIEMENT CRG JOSSE;568,79;
Chaque virement reellement recu par le proprietaire apparait dans la colonne
DEBIT (l'agence "debite" son compte de gestion pour payer le proprietaire) ;
la colonne CREDIT en face n'est que la contrepartie comptable interne de
l'agence (loyer encaisse pour le compte du proprietaire) et ne doit pas etre
comptee en plus. Regle retenue : pour chaque DATE, le montant net recu par
le proprietaire = somme des montants en colonne DEBIT ce jour-la (couvre a
la fois les mois simples a une seule ligne DEBIT, et les mois avec plusieurs
lignes DEBIT le meme jour, ex. acompte + solde).

Idempotent : upsert PostgREST sur (bien, date, montant), donc reimporter le
meme export (ou un export plus recent qui recouvre les mois deja connus) ne
duplique rien.

Usage :
    pip install -r requirements.txt
    python import_revenus_geres.py <fichier.csv> --bien "Rue Jean Martin" --gestionnaire Foncia
"""
import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
             "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def log(msg):
    print(f"[import-revenus-geres] {msg}")


def parse_amount(raw):
    raw = (raw or "").strip().replace(" ", "").replace(" ", "")
    if not raw:
        return None
    return float(raw.replace(",", "."))


def parse_csv(path):
    """Regroupe les montants DEBIT par date, avec les libelles associes."""
    by_date = defaultdict(lambda: {"montant": 0.0, "labels": []})
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            date_str, label = row[0].strip(), row[1].strip()
            debit = parse_amount(row[2]) if len(row) > 2 else None
            if not date_str or debit is None:
                continue
            try:
                d = datetime.strptime(date_str, "%d/%m/%Y").date()
            except ValueError:
                log(f"  Date illisible ignorée : {date_str!r}")
                continue
            by_date[d]["montant"] += debit
            by_date[d]["labels"].append(label)
    return by_date


def upsert_rows(rows):
    if not rows:
        log("Aucune ligne à importer.")
        return
    url = f"{SUPABASE_URL}/rest/v1/revenus_geres?on_conflict=bien,date,montant"
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    resp = requests.post(url, headers=headers, json=rows, timeout=30)
    if resp.status_code not in (200, 201):
        log(f"  ERREUR insertion : {resp.status_code} {resp.text}")
        sys.exit(1)
    log(f"{len(rows)} ligne(s) upsertées (déduplication sur bien+date+montant).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--bien", required=True)
    ap.add_argument("--gestionnaire", default="Foncia")
    args = ap.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        log("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants dans .env")
        sys.exit(1)

    by_date = parse_csv(args.csv_path)
    rows = []
    for d, info in sorted(by_date.items()):
        if info["montant"] <= 0:
            continue
        rows.append({
            "bien": args.bien,
            "gestionnaire": args.gestionnaire,
            "date": d.isoformat(),
            "mois": MONTHS_FR[d.month - 1],
            "annee": d.year,
            "montant": round(info["montant"], 2),
            "libelle": " + ".join(dict.fromkeys(info["labels"])),
        })
        log(f"  {d.isoformat()} : {round(info['montant'],2)} € ({rows[-1]['libelle']})")

    upsert_rows(rows)


if __name__ == "__main__":
    main()
