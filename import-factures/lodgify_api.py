"""
Acces LECTURE SEULE a l'API publique Lodgify (cle dans .env : LODGIFY_API_KEY) et petits utilitaires
partages par sync_lodgify_api.py (statuts / annulations) et check_calendriers.py (controle de coherence).

Ne modifie jamais rien chez Lodgify.
"""
import os

import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, ".env"))

BASE = "https://api.lodgify.com"
# Identifiant de logement Lodgify -> nom de la chambre dans GMAO (colonne reservations.room)
ROOMS = {785556: "Studio", 785857: "T2"}
# Statuts Lodgify : Booked = reservation ferme ; Open = demande / option en attente ; Declined = annulee ou refusee
STATUS_ACTIVE = "Booked"
STATUS_PENDING = "Open"
STATUS_CANCELLED = "Declined"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SB = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
SB_W = {**SB, "Content-Type": "application/json", "Prefer": "return=representation"}


def api_key():
    k = os.environ.get("LODGIFY_API_KEY", "").strip()
    if not k:
        raise RuntimeError("LODGIFY_API_KEY absente du .env")
    return k


def all_bookings():
    """Toutes les reservations (hors passees anciennes selon l'API) ; leve une exception si l'API repond mal."""
    h = {"X-ApiKey": api_key(), "Accept": "application/json"}
    out, page = [], 1
    while True:
        r = requests.get(
            f"{BASE}/v2/reservations/bookings",
            headers=h,
            params={"page": page, "size": 50, "includeCount": "true", "stayFilter": "Upcoming"},
            timeout=30,
        )
        r.raise_for_status()
        j = r.json()
        items = j.get("items") or []
        out += items
        if not items or len(out) >= (j.get("count") or 0):
            return out
        page += 1


def room_of(b):
    return ROOMS.get(b.get("property_id"))


def key_of(b):
    """Cle de rapprochement avec GMAO : (arrivee, depart, chambre)."""
    return (b.get("arrival"), b.get("departure"), room_of(b))


def canon_source(b):
    """Source Lodgify -> valeur de reservations.source dans GMAO (booking / airbnb / lodgify)."""
    s = (b.get("source") or "").lower()
    if "booking" in s:
        return "booking"
    if "airbnb" in s:
        return "airbnb"
    return "lodgify"


def guest_name(b):
    return ((b.get("guest") or {}).get("name") or "").strip()


def gmao_reservations(from_date):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/reservations",
        params={"select": "*", "date_arrivee": f"gte.{from_date}", "order": "date_arrivee"},
        headers=SB,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def patch_reservation(rid, data):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/reservations", params={"id": f"eq.{rid}"}, headers=SB_W, json=data, timeout=15)
    r.raise_for_status()


def est_bloque(r):
    """Periode bloquee (pas un voyageur) : Lodgify 'Closed Period', etc."""
    nom = (r.get("guest_name") or "").strip().lower()
    return not nom or any(k in nom for k in ("closed period", "blocked", "bloqu", "unavailable", "indisponible", "not available"))
