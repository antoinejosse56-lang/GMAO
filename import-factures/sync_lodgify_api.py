"""
Synchronise les STATUTS des reservations GMAO avec l'API Lodgify (fiable, contrairement aux flux iCal) :

- reservation 'confirmed' dans GMAO dont TOUTES les reservations Lodgify correspondantes (memes dates, meme
  chambre) sont 'Declined' (annulee / refusee)  ->  statut 'annule' dans GMAO. Le rappel d'agenda "code de la
  porte" est ensuite retire par sync_reservations_calendar.py au passage suivant.
- reservation 'annule' dans GMAO redevenue 'Booked' chez Lodgify  ->  'confirmed' (jamais pour 'ferme', qui est
  une fermeture manuelle).
- source ('lodgify' par defaut) corrigee en 'booking' / 'airbnb' quand l'API connait le vrai canal.

Les reservations absentes de l'API (calendriers Airbnb synchronises, periodes bloquees) ne sont jamais touchees.
Garde-fous : rien n'est modifie si l'API echoue ou renvoie 0 reservation ; arret sans rien changer si plus de
8 annulations d'un coup.

Passe a chaque heure (nas/run_all.sh) ou a la main : python sync_lodgify_api.py
"""
import sys
from datetime import date

import lodgify_api as L

MAX_ANNULATIONS = 8


def log(msg):
    print(f"[sync-lodgify-api] {msg}")


def main():
    try:
        bookings = L.all_bookings()
    except Exception as e:  # cle absente, API en panne...
        log(f"API Lodgify indisponible ({type(e).__name__}) : aucune modification.")
        return 1
    if not bookings:
        log("API Lodgify : 0 reservation renvoyee (anormal) : aucune modification.")
        return 1

    par_cle = {}
    for b in bookings:
        if L.room_of(b) and b.get("arrival") and b.get("departure"):
            par_cle.setdefault(L.key_of(b), []).append(b)

    aujourdhui = date.today().isoformat()
    rows = L.gmao_reservations(aujourdhui)
    a_annuler, a_rouvrir, sources = [], [], []
    for r in rows:
        k = (r.get("date_arrivee"), r.get("date_depart"), r.get("room"))
        bs = par_cle.get(k)
        if not bs:
            continue
        statuts = {b.get("status") for b in bs}
        actif = L.STATUS_ACTIVE in statuts
        if r.get("statut") == "confirmed" and not actif and statuts == {L.STATUS_CANCELLED}:
            a_annuler.append((r, bs[0]))
        elif r.get("statut") == "annule" and actif:
            a_rouvrir.append((r, bs[0]))
        if actif and (r.get("source") or "lodgify") == "lodgify":
            vrai = L.canon_source(next(b for b in bs if b.get("status") == L.STATUS_ACTIVE))
            if vrai != "lodgify":
                sources.append((r, vrai))

    log(f"{len(bookings)} reservation(s) Lodgify, {len(rows)} reservation(s) GMAO a venir : "
        f"{len(a_annuler)} a annuler, {len(a_rouvrir)} a reactiver, {len(sources)} source(s) a corriger.")
    if len(a_annuler) > MAX_ANNULATIONS:
        log(f"Plus de {MAX_ANNULATIONS} annulations d'un coup : arret par precaution, rien modifie.")
        return 1

    for r, b in a_annuler:
        L.patch_reservation(r["id"], {"statut": "annule"})
        log(f"ANNULEE : {r.get('guest_name')} {r['date_arrivee']} -> {r['date_depart']} ({r.get('room')}) "
            f"[Lodgify : Declined le {(b.get('canceled_at') or '?')[:10]}]")
    for r, b in a_rouvrir:
        L.patch_reservation(r["id"], {"statut": "confirmed"})
        log(f"REACTIVEE : {r.get('guest_name')} {r['date_arrivee']} -> {r['date_depart']} ({r.get('room')}) [Lodgify : Booked]")
    for r, vrai in sources:
        L.patch_reservation(r["id"], {"source": vrai})
        log(f"SOURCE : {r.get('guest_name')} {r['date_arrivee']} -> {vrai}")
    log("Termine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
