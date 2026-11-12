"""
Controle de coherence des calendriers : compare GMAO (reservations a venir) et l'API Lodgify, et previent par
email (une seule fois par nouvelle liste d'anomalies) si quelque chose ne colle pas :

 1. DOUBLE RESERVATION : deux reservations actives (ou une reservation et une periode bloquee) se chevauchent
    pour la meme chambre (le depart et l'arrivee le meme jour ne comptent pas).
 2. MANQUANTE DANS GMAO : reservation 'Booked' chez Lodgify absente de GMAO (ou fermee a la main dans GMAO).
 3. DATES DIFFERENTES : reservation Lodgify dont les dates ne correspondent a aucune ligne GMAO mais en
    chevauchent une (changement de dates probable).
 4. FANTOME : reservation GMAO 'booking' confirmee que Lodgify ne connait pas du tout (mauvaise chambre,
    doublon ou erreur d'import).

Les demandes en attente ('Open') et les calendriers Airbnb synchronises (absents de l'API) ne declenchent rien.
Lecture seule sur Lodgify ; seule ecriture : la cle 'lodgify_check_hash' dans app_config (anti-doublon d'email).

  python check_calendriers.py            -> controle + email si nouvelles anomalies
  python check_calendriers.py --dry-run  -> affiche seulement, n'envoie rien
"""
import hashlib
import sys
from datetime import date

import requests

import lodgify_api as L

OWNER_EMAIL = "antoinejosse56@gmail.com"
INACTIF = ("annule", "ferme")


def log(msg):
    print(f"[check-calendriers] {msg}")


def chevauche(a, b):
    return a[0] < b[1] and b[0] < a[1]


def libelle(arr, dep, room, nom=""):
    return f"{nom + ' ' if nom else ''}{arr[8:10]}/{arr[5:7]}/{arr[:4]} -> {dep[8:10]}/{dep[5:7]}/{dep[:4]} ({room})"


def anomalies(bookings, rows):
    out = []
    actives = [r for r in rows if (r.get("statut") or "confirmed") not in INACTIF and r.get("date_depart")]
    # 1. doubles reservations
    for room in sorted({r.get("room") for r in actives}):
        rr = sorted([r for r in actives if r.get("room") == room], key=lambda r: r["date_arrivee"])
        for i, a in enumerate(rr):
            for b in rr[i + 1:]:
                if b["date_arrivee"] >= a["date_depart"]:
                    break
                if chevauche((a["date_arrivee"], a["date_depart"]), (b["date_arrivee"], b["date_depart"])):
                    out.append(("DOUBLE RESERVATION",
                                f"{libelle(a['date_arrivee'], a['date_depart'], room, a.get('guest_name', ''))}  <->  "
                                f"{libelle(b['date_arrivee'], b['date_depart'], room, b.get('guest_name', ''))}"))
    # index GMAO
    gmao_par_cle = {}
    for r in rows:
        gmao_par_cle.setdefault((r.get("date_arrivee"), r.get("date_depart"), r.get("room")), []).append(r)
    api_cles = {L.key_of(b) for b in bookings}
    today = date.today().isoformat()
    # 2 + 3. Booked chez Lodgify
    for b in bookings:
        if b.get("status") != L.STATUS_ACTIVE or not L.room_of(b) or (b.get("arrival") or "") < today:
            continue
        k = L.key_of(b)
        lignes = gmao_par_cle.get(k, [])
        txt = libelle(k[0], k[1], k[2], L.guest_name(b))
        if any((x.get("statut") or "confirmed") not in INACTIF for x in lignes):
            continue
        if lignes:  # presente mais fermee/annulee dans GMAO
            out.append(("MANQUANTE DANS GMAO", f"{txt} : confirmee chez Lodgify mais marquee '{lignes[0].get('statut')}' dans GMAO"))
            continue
        voisines = [x for x in actives if x.get("room") == k[2] and chevauche((k[0], k[1]), (x["date_arrivee"], x["date_depart"]))]
        if voisines:
            v = voisines[0]
            out.append(("DATES DIFFERENTES", f"Lodgify : {txt}  /  GMAO : {libelle(v['date_arrivee'], v['date_depart'], v.get('room'), v.get('guest_name', ''))}"))
        else:
            out.append(("MANQUANTE DANS GMAO", f"{txt} (source {L.canon_source(b)}) n'existe pas dans GMAO"))
    # 4. fantomes
    for r in actives:
        if r.get("source") != "booking" or L.est_bloque(r):
            continue
        k = (r.get("date_arrivee"), r.get("date_depart"), r.get("room"))
        if k not in api_cles:
            out.append(("FANTOME", f"{libelle(k[0], k[1], k[2], r.get('guest_name', '')[:40])} : reservation Booking inconnue de Lodgify"))
    return out


def sb_get_config(key):
    r = requests.get(f"{L.SUPABASE_URL}/rest/v1/app_config", params={"select": "value", "key": f"eq.{key}"}, headers=L.SB, timeout=15)
    r.raise_for_status()
    j = r.json()
    return j[0]["value"] if j else None


def sb_set_config(key, value):
    if sb_get_config(key) is None:
        requests.post(f"{L.SUPABASE_URL}/rest/v1/app_config", headers=L.SB_W, json={"key": key, "value": value}, timeout=15).raise_for_status()
    else:
        requests.patch(f"{L.SUPABASE_URL}/rest/v1/app_config", params={"key": f"eq.{key}"}, headers=L.SB_W, json={"value": value}, timeout=15).raise_for_status()


def envoyer_mail(items):
    key = sb_get_config("brevo_api_key")
    if not key:
        log("Pas de cle Brevo : email non envoye.")
        return
    lignes = "".join(f"<tr><td style='padding:6px 10px;font-weight:600;white-space:nowrap'>{t}</td><td style='padding:6px 10px'>{d}</td></tr>" for t, d in items)
    html = (
        "<div style='font-family:Arial,sans-serif;max-width:700px'>"
        "<h2 style='color:#BA7517'>GMAO Pro : anomalies dans les calendriers de reservation</h2>"
        "<p>Le controle automatique (GMAO &harr; Lodgify) a releve :</p>"
        f"<table style='border-collapse:collapse;font-size:13px'>{lignes}</table>"
        "<p style='color:#888;font-size:12px'>Ce message n'est envoye qu'une fois par liste d'anomalies.</p></div>"
    )
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": key, "Content-Type": "application/json"},
        json={"sender": {"name": "GMAO Pro", "email": OWNER_EMAIL}, "to": [{"email": OWNER_EMAIL}],
              "subject": f"GMAO : {len(items)} anomalie(s) dans les calendriers de reservation", "htmlContent": html},
        timeout=20,
    )
    log(f"Email envoye (HTTP {r.status_code}).")


def main():
    dry = "--dry-run" in sys.argv
    try:
        bookings = L.all_bookings()
    except Exception as e:
        log(f"API Lodgify indisponible ({type(e).__name__}) : controle annule.")
        return 1
    if not bookings:
        log("API Lodgify : 0 reservation (anormal) : controle annule.")
        return 1
    rows = L.gmao_reservations(date.today().isoformat())
    items = anomalies(bookings, rows)
    log(f"{len(bookings)} reservation(s) Lodgify, {len(rows)} GMAO a venir : {len(items)} anomalie(s).")
    for t, d in items:
        log(f"  [{t}] {d}")
    if dry:
        return 0
    h = hashlib.sha1("\n".join(f"{t}|{d}" for t, d in sorted(items)).encode()).hexdigest()[:16] if items else ""
    if h and h != sb_get_config("lodgify_check_hash"):
        envoyer_mail(items)
    if h != (sb_get_config("lodgify_check_hash") or ""):
        sb_set_config("lodgify_check_hash", h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
