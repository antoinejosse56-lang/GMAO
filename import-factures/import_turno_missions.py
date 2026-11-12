"""
Importe dans GMAO (table menage_missions) les missions de menage relevees dans Turno.

Turno n'a pas d'API ni d'email : la liste est lue dans l'interface web (https://app.turno.com/view/projects,
onglets "Missions en attente et acceptees" et "Missions annulees") par Claude via le navigateur integre,
qui produit un fichier JSON {"actifs": [...], "annulees": [...]} (voir README en bas). Ce script fait le reste :

 - statut : 'non_assignee' (aucun agent), 'assignee' (agent nomme), 'annulee' (onglet des annulees) ;
 - rapprochement avec la reservation GMAO du meme depart (meme chambre, date de la mission = date de depart) ;
 - DOUBLONS : plusieurs missions actives pour le meme depart -> on en garde une (celle qui a un agent, sinon la
   plus ancienne) et les autres recoivent doublon_de = numero de la mission gardee ;
 - rapport : missions non assignees proches, doublons, departs sans mission.

    python import_turno_missions.py missions.json            -> ecrit en base et affiche le rapport
    python import_turno_missions.py missions.json --dry-run  -> rapport seulement

Format d'une entree : {"id": "39945197", "d": "13 novembre 2026", "t": "11:00", "prop": "Studio Ind...", "agent": "Non-Assignée"}
Ne modifie jamais Turno.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
HW = {**H, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}

MOIS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "août": 8,
        "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
ALERTE_JOURS = 7  # missions non assignees a moins de 7 jours : mises en avant


def log(m):
    print(m)


def iso(d):
    j, mois, a = d.split()
    return date(int(a), MOIS[mois.lower().rstrip(".")], int(j)).isoformat()


def room_of(prop):
    p = (prop or "").lower()
    if "studio" in p:
        return "Studio"
    if "appartement" in p or "t2" in p:
        return "T2"
    return None


def get(table, params):
    r = requests.get(f"{URL}/rest/v1/{table}", params=params, headers=H, timeout=30)
    r.raise_for_status()
    return r.json()


def est_bloque(r):
    n = (r.get("guest_name") or "").lower()
    return not n or any(k in n for k in ("closed period", "blocked", "bloqu", "unavailable", "indisponible", "not available"))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    dry = "--dry-run" in sys.argv
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    today = date.today().isoformat()

    missions = []
    for src, cancelled in ((data.get("actifs", []), False), (data.get("annulees", []), True)):
        for m in src:
            ag = (m.get("agent") or "").strip()
            non_assignee = (not ag) or ag.lower().startswith("non-assign") or ag.lower().startswith("non assign")
            missions.append({
                "turno_id": m["id"], "room": room_of(m.get("prop")), "date_mission": iso(m["d"]),
                "heure_debut": m.get("t"), "heure_fin": None,
                "agent": None if (cancelled or non_assignee) else ag,
                "statut": "annulee" if cancelled else ("non_assignee" if non_assignee else "assignee"),
            })

    rows = [r for r in get("reservations", {"select": "id,guest_name,room,date_arrivee,date_depart,statut",
                                            "date_depart": f"gte.{(date.today() - timedelta(days=7)).isoformat()}"})
            if (r.get("statut") or "confirmed") not in ("annule", "ferme")]
    par_depart = {}
    for r in rows:
        par_depart.setdefault((r["date_depart"], r["room"]), []).append(r)

    # rapprochement
    for m in missions:
        cands = par_depart.get((m["date_mission"], m["room"]), [])
        cands = sorted(cands, key=lambda r: est_bloque(r))
        m["reservation_id"] = cands[0]["id"] if cands else None
        m["_resa"] = cands[0]["guest_name"] if cands else None
        m["doublon_de"] = None

    # doublons parmi les missions actives d'un meme depart
    groupes = {}
    for m in missions:
        if m["statut"] != "annulee":
            groupes.setdefault((m["date_mission"], m["room"]), []).append(m)
    for g in groupes.values():
        if len(g) > 1:
            g.sort(key=lambda m: (m["statut"] != "assignee", int(m["turno_id"])))
            for autre in g[1:]:
                autre["doublon_de"] = g[0]["turno_id"]

    maintenant = datetime.now().isoformat()
    if not dry:
        payload = [{k: v for k, v in m.items() if not k.startswith("_")} | {"vue_le": maintenant} for m in missions]
        r = requests.post(f"{URL}/rest/v1/menage_missions?on_conflict=turno_id", headers=HW, json=payload, timeout=30)
        r.raise_for_status()
        log(f"{len(payload)} mission(s) enregistree(s) dans menage_missions.")

    actives = [m for m in missions if m["statut"] != "annulee"]
    log(f"\n{len(actives)} mission(s) active(s), {len(missions) - len(actives)} annulee(s).")
    limite = (date.today() + timedelta(days=ALERTE_JOURS)).isoformat()
    log(f"\n== NON ASSIGNEES a moins de {ALERTE_JOURS} jours (hors doublons) ==")
    for m in sorted(actives, key=lambda m: m["date_mission"]):
        if m["statut"] == "non_assignee" and not m["doublon_de"] and today <= m["date_mission"] <= limite:
            log(f"  {m['date_mission']} {m['room']} #{m['turno_id']}  (depart de {m['_resa']})")
    log("\n== DOUBLONS ==")
    for m in sorted(actives, key=lambda m: m["date_mission"]):
        if m["doublon_de"]:
            log(f"  {m['date_mission']} {m['room']} #{m['turno_id']} doublon de #{m['doublon_de']}  [{m['agent'] or 'non assignee'}]")
    log("\n== DEPARTS GMAO SANS MISSION TURNO (hors periodes bloquees) ==")
    avec = {(m["date_mission"], m["room"]) for m in actives}
    for (d, rm), lst in sorted(par_depart.items()):
        if d >= today and (d, rm) not in avec:
            for r in lst:
                if not est_bloque(r):
                    log(f"  {d} {rm} {r['guest_name'][:30]}")
    log("\n== NON ASSIGNEES (toutes dates, hors doublons) ==")
    log("  " + ", ".join(f"{m['date_mission'][5:]} {m['room']}" for m in sorted(actives, key=lambda m: m['date_mission'])
                         if m["statut"] == "non_assignee" and not m["doublon_de"]))


if __name__ == "__main__":
    main()
