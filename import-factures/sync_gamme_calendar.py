"""
Synchronise les BT issus d'une gamme (work_orders.gamme_id renseigne) vers
Google Calendar, et envoie une alerte email a l'intervenant assigne (qui
recoit deja une notification sur son telephone via l'appli Gmail - plus
simple et plus fiable qu'une vraie notification push).

Pour chaque BT ouvert issu d'une gamme :
- Un evenement (journee entiere, a la date d'echeance) est cree/maintenu
  dans l'agenda Google dedie de l'intervenant assigne ("GMAO - <nom>",
  partage automatiquement avec lui a sa premiere creation).
- Le meme evenement est aussi cree dans l'agenda dedie de chaque admin
  (qui doit voir tous les BT, pas seulement les siens).
- Un email est envoye a l'intervenant assigne, une seule fois (memorise via
  work_orders.gcal_event_ids pour ne pas relancer a chaque execution).
- Quand un BT passe a l'etat 'done', l'evenement correspondant est retire
  de tous les agendas ou il avait ete cree.

A executer periodiquement via une tache planifiee Windows, independamment de
l'ouverture de GMAO Pro dans un navigateur (voir le message de conversation
pour la commande Register-ScheduledTask).
"""
import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

IMPORT_FACTURES_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(IMPORT_FACTURES_DIR, ".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
HEADERS_W = {**HEADERS, "Content-Type": "application/json", "Prefer": "return=representation"}

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CALENDAR_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CALENDAR_CLIENT_SECRET"]
GOOGLE_REFRESH_TOKEN = os.environ["GOOGLE_CALENDAR_REFRESH_TOKEN"]

# Compte Google proprietaire du token (celui qui a fait l'autorisation) - ses
# propres agendas n'ont pas besoin d'etre partages avec lui-meme.
OWNER_EMAIL = "antoinejosse56@gmail.com"
# Domaines d'e-mail internes a l'appli (identifiants de connexion, pas de
# vraie boite mail) - jamais de creation/partage d'agenda pour ceux-la.
FAKE_EMAIL_DOMAINS = {"gmao.fr"}


def log(msg):
    print(f"[sync-gamme-calendar] {msg}")


def get_access_token():
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def gcal_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def fetch_all(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def patch_row(table, row_id, data):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params={"id": f"eq.{row_id}"},
        headers=HEADERS_W,
        json=data,
        timeout=15,
    )


def ensure_user_calendar(token, user):
    """Cree l'agenda Google dedie de cet utilisateur s'il n'existe pas encore
    (memorise dans users.gcal_id), et le partage avec lui en lecture."""
    if user.get("gcal_id"):
        return user["gcal_id"]
    email = (user.get("email") or "").strip()
    domain = email.split("@")[-1].lower() if "@" in email else ""
    if not email or domain in FAKE_EMAIL_DOMAINS:
        return None
    summary = f"GMAO - {user['name']}"
    resp = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars",
        headers=gcal_headers(token),
        json={"summary": summary, "description": "Bons de travaux GMAO Pro issus des gammes d'entretien"},
        timeout=30,
    )
    resp.raise_for_status()
    calendar_id = resp.json()["id"]
    log(f"Agenda cree pour {user['name']} ({email}) : {calendar_id}")

    if email.lower() != OWNER_EMAIL.lower():
        acl_resp = requests.post(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/acl",
            headers=gcal_headers(token),
            json={"role": "reader", "scope": {"type": "user", "value": email}},
            timeout=30,
        )
        if not acl_resp.ok:
            log(f"  ATTENTION partage echoue pour {email} : {acl_resp.text[:200]}")

    patch_row("users", user["id"], {"gcal_id": calendar_id})
    user["gcal_id"] = calendar_id
    return calendar_id


def wo_event_body(wo, asset_name, is_new):
    tr = wo.get("topo_ref") or {}
    location = " › ".join(tr[k] for k in ("propName", "zoneName", "subName") if tr.get(k))
    original_due = wo.get("due_date") or wo.get("date")
    description_lines = [wo.get("description") or ""]
    if location:
        description_lines.append(f"Localisation : {location}")
    if asset_name:
        description_lines.append(f"Équipement : {asset_name}")
    if original_due:
        description_lines.append(f"Échéance d'origine : {original_due}")
    description_lines.append("Généré depuis une gamme d'entretien GMAO Pro.")
    # Les vraies Google Tasks ne peuvent pas etre partagees entre comptes
    # (contrairement a un agenda Calendar), donc on simule leur comportement
    # avec un evenement horaire que le script redate sur AUJOURD'HUI a chaque
    # execution tant que le BT reste ouvert : il ne disparait jamais avant
    # d'etre marque termine dans GMAO Pro, comme une tache en retard.
    # Une seule notification est envoyee, a la creation (quelques minutes
    # apres, pour un rappel quasi immediat). Les jours suivants, l'evenement
    # est simplement redate a 11h sans reminder - il reste visible dans
    # l'agenda mais ne redeclenche plus d'alerte.
    now = datetime.now()
    if is_new:
        start_time = now + timedelta(minutes=2)
        reminders = {"useDefault": False, "overrides": [{"method": "popup", "minutes": 0}]}
    else:
        start_time = now.replace(hour=11, minute=0, second=0, microsecond=0)
        reminders = {"useDefault": False, "overrides": []}
    end_time = start_time + timedelta(minutes=15)
    return {
        "summary": f"🔧 {wo['title']}",
        "description": "\n".join(l for l in description_lines if l),
        "start": {"dateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/Paris"},
        "end": {"dateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "Europe/Paris"},
        "reminders": reminders,
    }


def upsert_event(token, calendar_id, wo, asset_name, existing_ids, is_new):
    body = wo_event_body(wo, asset_name, is_new)
    event_id = existing_ids.get(calendar_id)
    if event_id:
        resp = requests.put(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
            headers=gcal_headers(token), json=body, timeout=30,
        )
        if resp.status_code != 404:
            resp.raise_for_status()
            return event_id
    resp = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        headers=gcal_headers(token), json=body, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def delete_event(token, calendar_id, event_id):
    resp = requests.delete(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
        headers=gcal_headers(token), timeout=30,
    )
    if resp.status_code not in (200, 204, 404, 410):
        log(f"  ATTENTION suppression evenement echouee ({resp.status_code}) : {resp.text[:200]}")


def get_brevo_key():
    rows = fetch_all("app_config", {"select": "value", "key": "eq.brevo_api_key"})
    return rows[0]["value"] if rows else None


def send_alert_email(brevo_key, to_email, to_name, wo, asset_name):
    if not brevo_key or not to_email:
        return
    due = wo.get("due_date") or wo.get("date") or ""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
      <div style="background:#1D9E75;padding:18px 24px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0;font-size:17px">🔧 GMAO Pro — Bon de travaux à réaliser</h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e5e5e0;border-top:none;border-radius:0 0 8px 8px">
        <p style="color:#444">Bonjour <b>{to_name}</b>,</p>
        <p style="color:#444">Une gamme d'entretien a généré un nouveau bon de travaux à réaliser :</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px;margin:12px 0">
          <tr style="background:#f5f5f3"><td style="padding:8px 12px;font-weight:500;width:35%">Titre</td><td style="padding:8px 12px"><b>{wo['title']}</b></td></tr>
          <tr><td style="padding:8px 12px;font-weight:500">Équipement</td><td style="padding:8px 12px">{asset_name or '—'}</td></tr>
          <tr style="background:#f5f5f3"><td style="padding:8px 12px;font-weight:500">Échéance</td><td style="padding:8px 12px">{due}</td></tr>
        </table>
        <p style="color:#888;font-size:12px">Il a aussi été ajouté à votre agenda Google "GMAO - {to_name}". Connectez-vous à GMAO Pro pour le marquer réalisé.</p>
      </div>
    </div>"""
    requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": brevo_key, "Content-Type": "application/json"},
        json={
            "sender": {"name": "GMAO Pro", "email": OWNER_EMAIL},
            "to": [{"email": to_email, "name": to_name}],
            "subject": f"🔧 GMAO — BT à réaliser : {wo['title']}",
            "htmlContent": html,
        },
        timeout=15,
    )


def main():
    token = get_access_token()
    brevo_key = get_brevo_key()

    users = fetch_all("users", {"select": "*"})
    assets = {a["id"]: a["name"] for a in fetch_all("assets", {"select": "id,name"})}
    work_orders = fetch_all("work_orders", {"select": "*", "gamme_id": "not.is.null"})
    open_wos = [w for w in work_orders if w.get("status") != "done"]
    closed_wos = [w for w in work_orders if w.get("status") == "done" and w.get("gcal_event_ids")]

    log(f"{len(open_wos)} BT ouvert(s) issu(s) d'une gamme, {len(closed_wos)} termine(s) avec evenement(s) a retirer.")

    admins = [u for u in users if u.get("role") == "admin"]
    by_email = {(u.get("email") or "").lower(): u for u in users if u.get("email")}

    # 1. Nettoyage des BT desormais termines : on retire l'evenement de tous
    # les agendas ou il avait ete cree.
    for wo in closed_wos:
        for calendar_id, event_id in (wo.get("gcal_event_ids") or {}).items():
            delete_event(token, calendar_id, event_id)
        patch_row("work_orders", wo["id"], {"gcal_event_ids": {}})
        log(f"BT termine, evenement(s) retire(s) : {wo['title']}")

    # 2. Creation/mise a jour des BT ouverts.
    for wo in open_wos:
        existing_ids = dict(wo.get("gcal_event_ids") or {})
        is_new = not existing_ids
        asset_name = assets.get(wo.get("asset_id"))

        target_users = list(admins)
        assignee = by_email.get((wo.get("by_email") or "").lower())
        if assignee and assignee.get("role") != "admin":
            target_users.append(assignee)

        updated_ids = dict(existing_ids)
        for user in target_users:
            calendar_id = ensure_user_calendar(token, user)
            if not calendar_id:
                continue
            event_id = upsert_event(token, calendar_id, wo, asset_name, existing_ids, is_new)
            updated_ids[calendar_id] = event_id

        if updated_ids != existing_ids:
            patch_row("work_orders", wo["id"], {"gcal_event_ids": updated_ids})
            log(f"{'Cree' if is_new else 'Mis a jour'} : {wo['title']} -> {len(updated_ids)} agenda(s)")

        if is_new and assignee and assignee.get("email"):
            send_alert_email(brevo_key, assignee["email"], assignee["name"], wo, asset_name)

    log("Termine.")


if __name__ == "__main__":
    main()
