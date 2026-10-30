#!/usr/bin/env python3
"""Veröffentlicht den TikTok-Beitrag des Tages (Foto-Karussell) über die TikTok Content Posting API.

Die Bilder erzeugt scripts/build_tiktok.py beim Deploy; sie liegen dann unter
https://boersen-ratespiel.github.io/tiktok/<JJJJ-MM-TT>/. TikTok lädt Fotos nur selbst per URL herunter
(PULL_FROM_URL), und nur von einer im TikTok-Entwicklerportal bestätigten Domain bzw. URL-Präfix.

Umgebungsvariablen (in GitHub: Settings -> Secrets and variables -> Actions):
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET  aus dem TikTok-Entwicklerportal (Secrets)
  TIKTOK_REFRESH_TOKEN                     einmalig mit scripts/tiktok_auth.py holen, gilt 365 Tage (Secret)
  TIKTOK_POST_MODE   MEDIA_UPLOAD (Standard): landet als Entwurf im TikTok-Postfach, Musik + Veröffentlichen in der App.
                     DIRECT_POST: wird sofort veröffentlicht (braucht den Scope video.publish).
  TIKTOK_PRIVACY     nur bei DIRECT_POST, Standard PUBLIC_TO_EVERYONE. Solange die App nicht von TikTok geprüft ist,
                     erlaubt TikTok nur SELF_ONLY — dann wird automatisch darauf ausgewichen (mit Warnung).
Fehlen die Zugangsdaten, endet das Skript ohne Fehler (TikTok ist optional).

Aufruf: python3 scripts/tiktok_post.py [JJJJ-MM-TT]   — nur Python-Standardbibliothek.
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

SITE = 'https://boersen-ratespiel.github.io/'
API = 'https://open.tiktokapis.com/v2/'
TITLE_MAX = 90
DESCRIPTION_MAX = 4000
WAIT_FOR_IMAGES_S = 600
STATUS_POLLS = 30
STATUS_POLL_S = 10


def notice(kind, msg):
    # GitHub Actions zeigt ::warning::/::notice:: in der Zusammenfassung des Laufs an.
    print(f'::{kind}::{msg}' if os.environ.get('GITHUB_ACTIONS') else f'[{kind}] {msg}', flush=True)


def request(url, data=None, token=None, form=False):
    headers = {'User-Agent': 'boersen-ratespiel-tiktok/1.0'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json; charset=UTF-8'
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers, err.read()


def api(path, data, token):
    status, _, raw = request(API + path, data, token)
    try:
        payload = json.loads(raw)
    except ValueError:
        sys.exit(f'{path}: HTTP {status}, keine JSON-Antwort: {raw[:300]!r}')
    error = payload.get('error') or {}
    if status != 200 or error.get('code', 'ok') != 'ok':
        sys.exit(f'{path}: HTTP {status}, {error.get("code")}: {error.get("message")} (log_id {error.get("log_id")})')
    return payload.get('data') or {}


def access_token(client_key, client_secret, refresh_token):
    status, _, raw = request(API + 'oauth/token/', {
        'client_key': client_key,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    }, form=True)
    payload = json.loads(raw or b'{}')
    if status != 200 or 'access_token' not in payload:
        sys.exit(f'Token-Erneuerung fehlgeschlagen (HTTP {status}): {payload.get("error")} {payload.get("error_description")}'
                 ' — Refresh-Token mit scripts/tiktok_auth.py neu holen.')
    new_refresh = payload.get('refresh_token')
    if new_refresh and new_refresh != refresh_token:
        notice('warning', 'TikTok hat einen neuen Refresh-Token ausgegeben. Bitte das Secret TIKTOK_REFRESH_TOKEN '
                          'aktualisieren (scripts/tiktok_auth.py), sonst läuft der alte irgendwann ab.')
    days = int(payload.get('refresh_expires_in', 0)) // 86400
    if days and days < 30:
        notice('warning', f'Der TikTok-Refresh-Token läuft in {days} Tagen ab — scripts/tiktok_auth.py erneut ausführen.')
    return payload['access_token']


def wait_until_live(urls):
    """Die Bilder kommen mit dem Deploy direkt davor; GitHub Pages braucht danach manchmal noch einen Moment."""
    deadline = time.time() + WAIT_FOR_IMAGES_S
    pending = list(urls)
    while pending:
        status, headers, _ = request(pending[0] + f'?check={int(time.time())}')
        if status == 200 and headers.get('Content-Type', '').startswith('image/jpeg'):
            pending.pop(0)
            continue
        if time.time() > deadline:
            sys.exit(f'Bild nicht erreichbar: {pending[0]} (HTTP {status})')
        time.sleep(15)


def main():
    client_key = os.environ.get('TIKTOK_CLIENT_KEY', '').strip()
    client_secret = os.environ.get('TIKTOK_CLIENT_SECRET', '').strip()
    refresh_token = os.environ.get('TIKTOK_REFRESH_TOKEN', '').strip()
    if not (client_key and client_secret and refresh_token):
        notice('notice', 'TikTok-Zugangsdaten fehlen (TIKTOK_CLIENT_KEY/TIKTOK_CLIENT_SECRET/TIKTOK_REFRESH_TOKEN) '
                         '— nichts gepostet.')
        return
    mode = os.environ.get('TIKTOK_POST_MODE', '').strip() or 'MEDIA_UPLOAD'
    if mode not in ('MEDIA_UPLOAD', 'DIRECT_POST'):
        sys.exit(f'TIKTOK_POST_MODE muss MEDIA_UPLOAD oder DIRECT_POST sein, nicht {mode!r}')

    day = sys.argv[1] if len(sys.argv) > 1 else datetime.datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat()
    base = f'{SITE}tiktok/{day}/'
    status, _, raw = request(base + f'post.json?check={int(time.time())}')
    if status != 200:
        sys.exit(f'{base}post.json nicht gefunden (HTTP {status}) — lief der Deploy mit build_tiktok.py?')
    post = json.loads(raw)
    image_urls = [base + name for name in post['images']]
    wait_until_live(image_urls)

    token = access_token(client_key, client_secret, refresh_token)
    post_info = {'title': post['title'][:TITLE_MAX], 'description': post['description'][:DESCRIPTION_MAX]}

    if mode == 'DIRECT_POST':
        creator = api('post/publish/creator_info/query/', {}, token)
        options = creator.get('privacy_level_options') or []
        privacy = os.environ.get('TIKTOK_PRIVACY', '').strip() or 'PUBLIC_TO_EVERYONE'
        if privacy not in options:
            fallback = 'SELF_ONLY' if 'SELF_ONLY' in options else (options[0] if options else privacy)
            notice('warning', f'Sichtbarkeit {privacy} ist für dieses Konto nicht erlaubt (erlaubt: {", ".join(options)}). '
                              f'Poste als {fallback}. Öffentlich geht erst nach dem App-Audit durch TikTok.')
            privacy = fallback
        post_info.update({
            'privacy_level': privacy,
            'disable_comment': bool(creator.get('comment_disabled')),
            'auto_add_music': True,
        })

    data = api('post/publish/content/init/', {
        'post_info': post_info,
        'source_info': {'source': 'PULL_FROM_URL', 'photo_cover_index': 0, 'photo_images': image_urls},
        'post_mode': mode,
        'media_type': 'PHOTO',
    }, token)
    publish_id = data.get('publish_id')
    print(f'Beitrag {day} ({post["kind"]}) an TikTok übergeben: {publish_id}', flush=True)

    done = {'PUBLISH_COMPLETE', 'SEND_TO_USER_INBOX'}
    for _ in range(STATUS_POLLS):
        time.sleep(STATUS_POLL_S)
        result = api('post/publish/status/fetch/', {'publish_id': publish_id}, token)
        state = result.get('status')
        print(f'Status: {state}', flush=True)
        if state in done:
            where = 'im TikTok-Postfach (Entwurf)' if state == 'SEND_TO_USER_INBOX' else 'veröffentlicht'
            notice('notice', f'TikTok-Beitrag {day}: {post["title"]} — {where}.')
            return
        if state == 'FAILED':
            sys.exit(f'TikTok meldet FAILED: {result.get("fail_reason")}')
    notice('warning', f'TikTok hat nach {STATUS_POLLS * STATUS_POLL_S} s noch nicht fertig gemeldet (publish_id {publish_id}).')


if __name__ == '__main__':
    main()
