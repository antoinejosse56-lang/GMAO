"""
Rappel d'agenda Google quand un menage Turno n'est TOUJOURS PAS ASSIGNE a l'approche d'un depart
(table menage_missions, alimentee chaque dimanche depuis Turno).

Pour chaque mission 'non_assignee' (ni doublon, ni annulee) dont la date est dans les JOURS_AVANT prochains
jours, un evenement est cree dans l'agenda principal : "Menage non assigne ..." a 09h00 (immediatement si
l'heure est deja passee), avec notification popup. Si la mission est ensuite assignee / annulee / passee,
l'evenement est supprime au passage suivant. Idempotent (cle = numero de mission Turno).

Les donnees Turno sont relues une fois par semaine (dimanche) : le rappel peut donc rester affiche
jusqu'a 7 jours apres une assignation faite entre-temps ; la description le precise.

Tourne a chaque passage horaire (nas/run_all.sh) ou a la main : python sync_menage_calendar.py
"""
from datetime import date, datetime, timedelta

import requests

import sync_reservations_calendar as C

KIND = "menage_non_assigne"
JOURS_AVANT = 3          # rappel a partir de J-3 avant la mission


def log(msg):
    print(f"[sync-menage-calendar] {msg}")


def missions_non_assignees():
    today = date.today()
    r = requests.get(
        f"{C.SUPABASE_URL}/rest/v1/menage_missions",
        params={"select": "*", "statut": "eq.non_assignee", "doublon_de": "is.null",
                "date_mission": f"gte.{today.isoformat()}", "order": "date_mission"},
        headers=C.HEADERS, timeout=30)
    r.raise_for_status()
    limite = (today + timedelta(days=JOURS_AVANT)).isoformat()
    return [m for m in r.json() if m["date_mission"] <= limite]


def corps(m):
    d = m["date_mission"]
    vue = (m.get("vue_le") or "")[:10]
    titre = f"🧹 Ménage NON assigné — {m.get('room') or '?'} le {C.fr(d)}" + (f" à {m['heure_debut']}" if m.get("heure_debut") else "")
    desc = [
        "Aucun agent n'est assigné à cette mission de ménage dans Turno.",
        "À assigner (ou à faire soi-même) avant le départ du voyageur.",
        "",
        f"Mission Turno : #{m['turno_id']}",
        f"Logement : {m.get('room') or '?'}",
        f"Date : {C.fr_long(d)}" + (f" à {m['heure_debut']}" if m.get("heure_debut") else ""),
        "",
        f"Dernière lecture de Turno : {C.fr(vue) if vue else '?'} (mise à jour chaque dimanche) — si c'est déjà assigné depuis, ignorer.",
        "Rappel automatique GMAO Pro.",
    ]
    neuf = datetime.combine(date.today(), datetime.min.time()).replace(hour=C.RAPPEL_HEURE)
    debut = neuf if datetime.now() < neuf else datetime.now() + timedelta(minutes=2)
    fin = debut + timedelta(minutes=15)
    return {
        "summary": titre, "description": "\n".join(desc),
        "start": {"dateTime": debut.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/Paris"},
        "end": {"dateTime": fin.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/Paris"},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 0}]},
        "extendedProperties": {"private": {"gmao_kind": KIND, "gmao_turno_id": m["turno_id"], "gmao_date": d}},
    }


def existants(h):
    out, token = {}, None
    while True:
        params = {"privateExtendedProperty": f"gmao_kind={KIND}", "maxResults": 250, "singleEvents": "true",
                  "timeMin": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")}
        if token:
            params["pageToken"] = token
        r = requests.get(f"https://www.googleapis.com/calendar/v3/calendars/{C.CAL}/events", headers=h, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        for e in j.get("items", []):
            tid = (e.get("extendedProperties", {}).get("private") or {}).get("gmao_turno_id")
            if tid:
                out[tid] = e
        token = j.get("nextPageToken")
        if not token:
            return out


def main():
    h = {"Authorization": f"Bearer {C.access_token()}", "Content-Type": "application/json"}
    ms = missions_non_assignees()
    ex = existants(h)
    log(f"{len(ms)} menage(s) non assigne(s) a J-{JOURS_AVANT} ou moins, {len(ex)} rappel(s) deja dans l'agenda.")
    voulus, cree, supprime = set(), 0, 0
    for m in ms:
        voulus.add(m["turno_id"])
        if m["turno_id"] in ex:
            continue  # un seul rappel par mission (pas de re-notification a chaque heure)
        requests.post(f"https://www.googleapis.com/calendar/v3/calendars/{C.CAL}/events", headers=h, json=corps(m), timeout=30).raise_for_status()
        cree += 1
        log(f"cree : {m.get('room')} {m['date_mission']} (#{m['turno_id']})")
    for tid, ev in ex.items():
        if tid in voulus:
            continue
        pdate = (ev.get("extendedProperties", {}).get("private") or {}).get("gmao_date", "")
        if pdate and pdate < date.today().isoformat():
            continue  # passee : on ne touche pas
        requests.delete(f"https://www.googleapis.com/calendar/v3/calendars/{C.CAL}/events/{ev['id']}", headers=h, timeout=30)
        supprime += 1
        log(f"supprime (assigne / annule / doublon) : {ev.get('summary', '')}")
    log(f"Termine : {cree} cree(s), {supprime} supprime(s).")


if __name__ == "__main__":
    main()
