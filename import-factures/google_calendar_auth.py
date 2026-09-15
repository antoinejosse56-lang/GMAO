"""
A executer UNE SEULE FOIS pour autoriser GMAO Pro a creer des evenements dans
Google Calendar au nom du compte que vous choisissez de connecter (celui qui
possedera et partagera les agendas dedies GMAO).

Ouvre un navigateur pour l'ecran de consentement Google, recupere le code
d'autorisation via un petit serveur local, puis l'echange contre un refresh
token - a coller ensuite dans .env sous GOOGLE_CALENDAR_REFRESH_TOKEN.

Prerequis : GOOGLE_CALENDAR_CLIENT_ID / GOOGLE_CALENDAR_CLIENT_SECRET deja
remplis dans .env (client OAuth "Application de bureau"), et l'adresse Gmail
utilisee ici ajoutee comme "utilisateur de test" sur l'ecran de consentement
OAuth du projet Google Cloud (sinon Google refuse l'autorisation).
"""
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from dotenv import load_dotenv

load_dotenv(".env")
CLIENT_ID = os.environ["GOOGLE_CALENDAR_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CALENDAR_CLIENT_SECRET"]
PORT = 8734
REDIRECT_URI = f"http://localhost:{PORT}/callback"
SCOPE = "https://www.googleapis.com/auth/calendar"

auth_code = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if "code" in params:
            auth_code["value"] = params["code"][0]
            self.wfile.write(
                "<html><body><h2>Autorisation recue, vous pouvez fermer cet onglet.</h2></body></html>".encode(
                    "utf-8"
                )
            )
        else:
            self.wfile.write(
                ("<html><body><h2>Erreur : " + str(params.get("error")) + "</h2></body></html>").encode(
                    "utf-8"
                )
            )

    def log_message(self, format, *args):
        pass


def main():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    print("Ouverture du navigateur pour l'autorisation Google...")
    print("Si rien ne s'ouvre, copiez cette URL dans votre navigateur :")
    print(auth_url)
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", PORT), CallbackHandler)
    print(f"\nEn attente de l'autorisation sur {REDIRECT_URI} ...")
    while "value" not in auth_code:
        server.handle_request()

    print("Code recu, echange contre un refresh token...")
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": auth_code["value"],
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("\nATTENTION : pas de refresh_token retourne (le compte a peut-etre deja")
        print("autorise cette appli avant). Revoquez l'acces sur")
        print("https://myaccount.google.com/permissions puis relancez ce script.")
        return
    print("\n=== Refresh token obtenu ===")
    print(refresh_token)
    print("\nCollez cette valeur dans .env sous GOOGLE_CALENDAR_REFRESH_TOKEN=")


if __name__ == "__main__":
    main()
