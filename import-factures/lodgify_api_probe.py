"""
Exploration LECTURE SEULE de l'API publique Lodgify : verifie que la cle fonctionne et montre ce qu'on peut
recuperer (logements, reservations avec statut, tarifs, disponibilites). Ne modifie rien chez Lodgify.

Cle : variable LODGIFY_API_KEY dans import-factures/.env (jamais dans le chat, jamais dans git).
    python lodgify_api_probe.py

Les reponses brutes sont ecrites dans lodgify_probe_out/ (ignore par git) pour analyse ; la console
n'affiche qu'un resume (jamais la cle).
"""
import json
import os
import sys
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))
KEY = os.environ.get("LODGIFY_API_KEY", "").strip()
if not KEY:
    sys.exit("LODGIFY_API_KEY absente de import-factures/.env (ajouter une ligne LODGIFY_API_KEY=...)")

BASE = "https://api.lodgify.com"
H = {"X-ApiKey": KEY, "Accept": "application/json"}
OUT = os.path.join(HERE, "lodgify_probe_out")
os.makedirs(OUT, exist_ok=True)


def call(name, path, params=None):
    r = requests.get(BASE + path, headers=H, params=params, timeout=30)
    ok = r.status_code == 200
    print(f"[{name}] GET {path} -> HTTP {r.status_code}")
    if not ok:
        print("   ", r.text[:200].replace(KEY, "***"))
        return None
    try:
        data = r.json()
    except ValueError:
        print("    reponse non JSON")
        return None
    with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


def items(d):
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in ("items", "results", "data"):
            if isinstance(d.get(k), list):
                return d[k]
    return []


props = call("properties", "/v2/properties", {"includeInOut": "false"})
plist = items(props)
print(f"    {len(plist)} logement(s) :")
for p in plist:
    print("     -", p.get("id"), p.get("name"), "| chambres:", [r.get("id") for r in (p.get("rooms") or [])])

bk = call("bookings", "/v2/reservations/bookings", {"page": 1, "size": 50, "includeCount": "true", "stayFilter": "Upcoming"})
blist = items(bk)
print(f"    {len(blist)} reservation(s) a venir (1ere page)")
statuts = {}
for b in blist:
    statuts[b.get("status")] = statuts.get(b.get("status"), 0) + 1
print("    statuts :", statuts)
for b in blist[:5]:
    g = (b.get("guest") or {}).get("name")
    print("     -", b.get("id"), b.get("status"), b.get("arrival"), "->", b.get("departure"), "|", g, "|", b.get("source"))

# Tarifs : calendrier de tarifs du 1er logement sur 60 jours
if plist:
    p = plist[0]
    rooms = p.get("rooms") or []
    params = {"HouseId": p.get("id"), "StartDate": date.today().isoformat(), "EndDate": (date.today() + timedelta(days=60)).isoformat()}
    if rooms:
        params["RoomTypeId"] = rooms[0].get("id")
    call("rates", "/v2/rates/calendar", params)
    call("availability", f"/v2/availability/{p.get('id')}", {"start": params["StartDate"], "end": params["EndDate"]})

print(f"\nReponses brutes dans {OUT}")
