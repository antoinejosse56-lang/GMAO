"""
Rappel "envoyer le code de la porte d'entree" dans l'agenda Google, la veille de chaque arrivee
(reservations courte duree).

Pour chaque reservation confirmee dont l'arrivee est aujourd'hui ou plus tard, un evenement de
15 minutes est cree dans l'agenda principal du proprietaire a 09h00 la VEILLE de l'arrivee, avec une
notification (popup, a l'heure de l'evenement) sur le telephone / l'appli Google Agenda.
Le titre et la description contiennent la date d'arrivee et la date de depart.

- Idempotent : chaque evenement porte l'id de la reservation (propriete privee Google). Un passage
  repete ne cree pas de doublon.
- Si les dates / le voyageur / le logement changent, l'evenement est mis a jour ; si la reservation
  disparait ou n'est plus confirmee, il est supprime. Les evenements passes ne sont jamais touches.
- Reservation prise tardivement (la veille a 09h00 est deja passee mais l'arrivee n'est pas passee) :
  rappel immediat (dans 2 minutes) au lieu d'un evenement dans le passe.
- Les periodes bloquees (Lodgify "Closed Period"...) sont ignorees.

Tourne a chaque passage horaire (nas/run_all.sh, ou a la main : python sync_reservations_calendar.py).
"""
import hashlib
import os
from datetime import date, datetime, timedelta

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
CAL = "primary"                 # agenda principal du compte Google autorise (antoinejosse56@gmail.com)
KIND = "code_porte"             # marqueur des evenements geres par ce script
RAPPEL_HEURE = 9                # heure du rappel, la veille de l'arrivee
BLOQUE = ("closed period", "blocked", "bloqu", "unavailable", "indisponible", "not available")


def log(msg):
    print(f"[sync-resa-calendar] {msg}")


def access_token():
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": os.environ["GOOGLE_CALENDAR_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CALENDAR_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_CALENDAR_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def fr(d):
    return date.fromisoformat(d).strftime("%d/%m/%Y")


JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def fr_long(d):
    dd = date.fromisoformat(d)
    return f"{JOURS[dd.weekday()]} {dd.strftime('%d/%m/%Y')}"


def nom_voyageur(r):
    """Nom nettoye : certains imports collent 'Telephone : ... Email ...' a la suite du nom."""
    import re
    n = re.split(r"\s+(?:t[ée]l[ée]phone|phone|e-?mail)\s*:?", r.get("guest_name") or "", maxsplit=1, flags=re.I)[0]
    return n.strip() or (r.get("guest_name") or "").strip()


def est_bloque(r):
    nom = (r.get("guest_name") or "").strip().lower()
    return not nom or any(b in nom for b in BLOQUE)


def reservations_a_rappeler():
    today = date.today().isoformat()
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/reservations",
        params={"select": "*", "date_arrivee": f"gte.{today}", "order": "date_arrivee"},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for x in r.json():
        if (x.get("statut") or "confirmed").lower() in ("cancelled", "canceled", "annule", "annulee"):
            continue
        if est_bloque(x) or not x.get("date_depart"):
            continue
        out.append(x)
    return out


def signature(r):
    raw = "|".join([nom_voyageur(r)] + [str(r.get(k) or "") for k in ("property", "room", "date_arrivee", "date_depart")])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def corps(r, nouveau_tardif):
    veille = date.fromisoformat(r["date_arrivee"]) - timedelta(days=1)
    logement = " — ".join(x for x in (r.get("property"), r.get("room")) if x)
    nuits = r.get("nb_nuits") or (date.fromisoformat(r["date_depart"]) - date.fromisoformat(r["date_arrivee"])).days
    titre = f"🔑 Envoyer le code d'entrée — {nom_voyageur(r)} (arrivée {fr(r['date_arrivee'])}, départ {fr(r['date_depart'])})"
    desc = [
        "Envoyer le code de la porte d'entrée au voyageur.",
        "",
        f"Voyageur : {nom_voyageur(r)}",
        f"Logement : {logement}",
        f"Arrivée : {fr_long(r['date_arrivee'])}",
        f"Départ : {fr_long(r['date_depart'])} ({nuits} nuit{'s' if nuits > 1 else ''})",
    ]
    if r.get("guest_email") and "guest.booking.com" not in r["guest_email"]:
        desc.append(f"Email : {r['guest_email']}")
    if r.get("source"):
        desc.append(f"Source : {r['source']}")
    desc += ["", "Rappel automatique GMAO Pro (réservations courte durée)."]
    if nouveau_tardif:
        debut = datetime.now() + timedelta(minutes=2)
    else:
        debut = datetime(veille.year, veille.month, veille.day, RAPPEL_HEURE, 0)
    fin = debut + timedelta(minutes=15)
    return {
        "summary": titre,
        "description": "\n".join(desc),
        "start": {"dateTime": debut.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/Paris"},
        "end": {"dateTime": fin.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/Paris"},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 0}]},
        "extendedProperties": {"private": {"gmao_kind": KIND, "gmao_resa_id": r["id"], "gmao_sig": signature(r)}},
    }


def evenements_existants(h):
    """Evenements geres par ce script, de hier a +2 ans : {id_reservation: evenement}."""
    out, token = {}, None
    t_min = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    while True:
        params = {
            "privateExtendedProperty": f"gmao_kind={KIND}",
            "timeMin": t_min,
            "maxResults": 250,
            "singleEvents": "true",
            "showDeleted": "false",
        }
        if token:
            params["pageToken"] = token
        r = requests.get(f"https://www.googleapis.com/calendar/v3/calendars/{CAL}/events", headers=h, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        for e in j.get("items", []):
            rid = (e.get("extendedProperties", {}).get("private") or {}).get("gmao_resa_id")
            if rid:
                out[rid] = e
        token = j.get("nextPageToken")
        if not token:
            return out


def main():
    h = {"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"}
    resas = reservations_a_rappeler()
    existants = evenements_existants(h)
    log(f"{len(resas)} reservation(s) a venir, {len(existants)} evenement(s) deja dans l'agenda.")
    maintenant = datetime.now()
    voulus = set()
    cree = maj = supprime = 0
    for r in resas:
        voulus.add(r["id"])
        ev = existants.get(r["id"])
        veille_9h = datetime.combine(date.fromisoformat(r["date_arrivee"]) - timedelta(days=1), datetime.min.time()).replace(hour=RAPPEL_HEURE)
        if ev is None:
            tardif = veille_9h < maintenant
            requests.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{CAL}/events", headers=h, json=corps(r, tardif), timeout=30
            ).raise_for_status()
            cree += 1
            log(f"cree : {nom_voyageur(r)} arrivee {r['date_arrivee']}{' (rappel immediat, reservation tardive)' if tardif else ''}")
        elif (ev.get("extendedProperties", {}).get("private") or {}).get("gmao_sig") != signature(r):
            tardif = veille_9h < maintenant
            requests.put(
                f"https://www.googleapis.com/calendar/v3/calendars/{CAL}/events/{ev['id']}", headers=h, json=corps(r, tardif), timeout=30
            ).raise_for_status()
            maj += 1
            log(f"mis a jour : {nom_voyageur(r)} arrivee {r['date_arrivee']}")
    # reservations annulees / supprimees / devenues passees -> retire seulement les rappels a venir
    for rid, ev in existants.items():
        if rid in voulus:
            continue
        debut = (ev.get("start") or {}).get("dateTime", "")[:19]
        if debut and datetime.fromisoformat(debut) < maintenant - timedelta(hours=1):
            continue  # evenement passe : on ne touche pas
        requests.delete(f"https://www.googleapis.com/calendar/v3/calendars/{CAL}/events/{ev['id']}", headers=h, timeout=30)
        supprime += 1
        log(f"supprime (reservation disparue) : {ev.get('summary', '')}")
    log(f"Termine : {cree} cree(s), {maj} mis a jour, {supprime} supprime(s).")


if __name__ == "__main__":
    main()
