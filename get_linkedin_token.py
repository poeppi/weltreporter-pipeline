#!/usr/bin/env python3
"""
LinkedIn OAuth-Helfer — einmalig ausführen, um Access Token + Org-ID zu holen.

Voraussetzungen:
  1. LinkedIn Developer App angelegt (https://developer.linkedin.com/)
  2. Produkt "Marketing Developer Platform" genehmigt
  3. Redirect URI in der App eingetragen: http://localhost:8080/callback
  4. CLIENT_ID und CLIENT_SECRET in .env eingetragen

Ausführen:
  venv/bin/python3 get_linkedin_token.py

Das Skript öffnet den Browser, du loggst dich ein und autorisierst die App.
Am Ende gibt es Access Token und Org-ID aus — beides als GitHub Secret speichern.
"""

import json
import os
import requests
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse


REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "w_member_social"

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>Autorisierung erfolgreich. Du kannst dieses Fenster schliessen.</h2>")
        else:
            error = params.get("error_description", ["Unbekannter Fehler"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h2>Fehler: {error}</h2>".encode())

    def log_message(self, *args):
        pass  # suppress request logs


def load_env(path=".env"):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def main():
    env = load_env()
    client_id = env.get("LINKEDIN_CLIENT_ID") or os.environ.get("LINKEDIN_CLIENT_ID")
    client_secret = env.get("LINKEDIN_CLIENT_SECRET") or os.environ.get("LINKEDIN_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Bitte LINKEDIN_CLIENT_ID und LINKEDIN_CLIENT_SECRET in .env eintragen.")
        print("Beides findest du in deiner LinkedIn Developer App unter 'Auth'.")
        raise SystemExit(1)

    # Step 1: Authorization URL öffnen
    auth_url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    })

    print("Browser öffnet sich zur LinkedIn-Autorisierung ...")
    print(f"Falls kein Browser öffnet, URL manuell aufrufen:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Step 2: Lokalen Server starten und auf Callback warten
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    print("Warte auf Autorisierung (localhost:8080) ...")
    server.handle_request()

    if not auth_code:
        raise SystemExit("Kein Authorization Code erhalten.")

    print(f"Authorization Code erhalten.")

    # Step 3: Code gegen Access Token tauschen
    resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 0)
    print(f"Access Token erhalten (gültig {expires_in // 86400} Tage).")

    # Step 4: Weltreporter Org-ID abrufen
    org_resp = requests.get(
        "https://api.linkedin.com/v2/organizations",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"q": "vanityName", "vanityName": "weltreporter"},
        timeout=15,
    )
    org_id = None
    if org_resp.ok:
        elements = org_resp.json().get("elements", [])
        if elements:
            urn = elements[0].get("$URN", "")
            org_id = urn.split(":")[-1] if urn else None

    print()
    print("=" * 50)
    print("Als GitHub Secrets speichern:")
    print()
    print(f"  LINKEDIN_ACCESS_TOKEN  =  {access_token}")
    if org_id:
        print(f"  LINKEDIN_ORG_ID        =  {org_id}")
    else:
        print("  LINKEDIN_ORG_ID        =  [OPEN: Org-ID nicht gefunden — manuell prüfen]")
    print()
    print("Token-Ablauf: in .env speichern und in ~60 Tagen erneuern.")
    print("=" * 50)


if __name__ == "__main__":
    main()
