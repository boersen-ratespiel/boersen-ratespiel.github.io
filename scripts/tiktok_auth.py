#!/usr/bin/env python3
"""Holt einmalig den TikTok-Refresh-Token für scripts/tiktok_post.py (gilt 365 Tage).

Ablauf (lokal ausführen, nicht in GitHub Actions):
  1. TIKTOK_CLIENT_KEY=… TIKTOK_CLIENT_SECRET=… python3 scripts/tiktok_auth.py
  2. Den ausgegebenen Link öffnen, mit dem TikTok-Konto anmelden und zustimmen.
  3. TikTok leitet auf REDIRECT_URI weiter (die Seite zeigt "404" — das ist egal). Die komplette Adresse aus der
     Adressleiste kopieren und hier einfügen.
  4. Den ausgegebenen Refresh-Token als GitHub-Secret TIKTOK_REFRESH_TOKEN speichern.

REDIRECT_URI muss im TikTok-Entwicklerportal unter "Login Kit -> Redirect URI" genau so eingetragen sein.
Nur Python-Standardbibliothek.
"""

import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

REDIRECT_URI = 'https://boersen-ratespiel.github.io/tiktok/'
SCOPES = 'user.info.basic,video.upload,video.publish'


def main():
    client_key = os.environ.get('TIKTOK_CLIENT_KEY', '').strip()
    client_secret = os.environ.get('TIKTOK_CLIENT_SECRET', '').strip()
    if not (client_key and client_secret):
        sys.exit('Bitte TIKTOK_CLIENT_KEY und TIKTOK_CLIENT_SECRET als Umgebungsvariablen setzen.')

    state = secrets.token_urlsafe(16)
    url = 'https://www.tiktok.com/v2/auth/authorize/?' + urllib.parse.urlencode({
        'client_key': client_key,
        'scope': SCOPES,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'state': state,
    })
    print('1. Diesen Link öffnen und zustimmen:\n\n' + url + '\n')
    back = input('2. Adresse nach der Weiterleitung hier einfügen: ').strip()
    query = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
    if query.get('state', [''])[0] != state:
        sys.exit('state passt nicht — bitte den Ablauf neu starten.')
    if 'code' not in query:
        sys.exit(f'Kein code in der Adresse: {query.get("error_description") or query}')

    req = urllib.request.Request(
        'https://open.tiktokapis.com/v2/oauth/token/',
        data=urllib.parse.urlencode({
            'client_key': client_key,
            'client_secret': client_secret,
            'code': query['code'][0],
            'grant_type': 'authorization_code',
            'redirect_uri': REDIRECT_URI,
        }).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read())
    if 'refresh_token' not in payload:
        sys.exit(f'Fehler: {payload}')
    print(f'\nGewährte Rechte: {payload.get("scope")}')
    print(f'Gültig für {int(payload.get("refresh_expires_in", 0)) // 86400} Tage.')
    print('\nAls GitHub-Secret TIKTOK_REFRESH_TOKEN speichern:\n\n' + payload['refresh_token'])


if __name__ == '__main__':
    main()
