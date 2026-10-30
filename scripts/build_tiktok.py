#!/usr/bin/env python3
"""Erzeugt den TikTok-Beitrag des Tages: 3 Bilder (1080×1920 JPEG) plus Titel/Beschreibung.

Täglich wechselt das Format: "Rauf oder runter?" (simulierter Kurs mit Auflösung), eine Frage aus dem Quiz
(QUIZ_DATA in script.js) oder ein Begriff aus dem Lexikon (index.html). Inhalte werden nur an ihren bisherigen Stellen
gepflegt; dieses Skript liest sie von dort. Gezeichnet wird per Canvas in scripts/tiktok/render.html, ausgeführt in
Headless-Chrome (auf den GitHub-Runnern vorinstalliert) — so braucht es weder Pillow noch npm-Pakete.

Ausgabe: tiktok/<JJJJ-MM-TT>/1.jpg … 3.jpg und post.json ({title, description, kind, images}). Läuft in
deploy-pages.yml vor dem Upload, damit die Bilder unter https://boersen-ratespiel.github.io/tiktok/… erreichbar sind —
TikTok holt Fotos nur per URL ab (PULL_FROM_URL). Der Inhalt hängt nur vom Datum ab, jeder Deploy des Tages erzeugt also
dieselben Bilder. tiktok/ ist nicht eingecheckt (.gitignore).

Lokal testen: python3 scripts/build_tiktok.py [JJJJ-MM-TT] [chart|quiz|lexikon]
Chrome-Pfad notfalls über die Umgebungsvariable CHROME setzen.
"""

import base64
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_lexikon import parse_entries, plain_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / 'scripts' / 'tiktok' / 'render.html'
OUT_DIR = ROOT / 'tiktok'
KINDS = ['chart', 'quiz', 'lexikon']
FIRST_DAY = datetime.date(2026, 10, 30)  # Tag 0 der Rotation; nur für die Reihenfolge wichtig
HASHTAGS = '#börse #aktien #geldanlage #finanzen #etf #lernenmittiktok #finanztok'
KEEP_DAYS = 3  # ältere Ordner werden gelöscht (TikTok holt die Bilder innerhalb von Minuten ab)
CHROME_CANDIDATES = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser',
                     '/opt/pw-browsers/chromium/chrome-linux64/chrome',
                     '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome']


def berlin_today():
    return datetime.datetime.now(ZoneInfo('Europe/Berlin')).date()


def find_chrome():
    for name in [os.environ.get('CHROME')] + CHROME_CANDIDATES:
        if name and (shutil.which(name) or Path(name).is_file()):
            return shutil.which(name) or name
    sys.exit('Kein Chrome/Chromium gefunden — Pfad über die Umgebungsvariable CHROME angeben.')


def quiz_data_js(script_js):
    m = re.search(r'^const QUIZ_DATA = \{.*?^\};', script_js, re.S | re.M)
    if not m:
        sys.exit('QUIZ_DATA nicht in script.js gefunden — hat sich der Code geändert?')
    return m.group(0)


def build_job(day, kind=None):
    n = (day - FIRST_DAY).days
    entries = parse_entries((ROOT / 'index.html').read_text(encoding='utf-8'))
    kind = kind or KINDS[n % len(KINDS)]
    # Jedes Format kommt jeden dritten Tag dran; der Zähler läuft also pro Format durch alle Einträge, ohne Wiederholung,
    # bis alle einmal dran waren. Beim Quiz springt ein Primzahl-Schritt zwischen den Schwierigkeitsgraden hin und her.
    turn = n // len(KINDS)
    entry = entries[turn % len(entries)]
    return {
        'date': day.isoformat(),
        'kind': kind,
        'pick': turn * 7,
        'lexikonCount': len(entries),
        'lexikon': {'id': entry['id'], 'title': plain_text(entry['title']), 'text': plain_text(entry['body'])},
    }


def render(job):
    page = TEMPLATE.read_text(encoding='utf-8')
    page = page.replace('__FONT_URL__', (ROOT / 'fonts' / 'outfit-variable.woff2').as_uri())
    page = page.replace('__JOB__', json.dumps(job, ensure_ascii=False).replace('</', '<\\/'))
    page = page.replace('__QUIZ_DATA__', quiz_data_js((ROOT / 'script.js').read_text(encoding='utf-8')))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'render.html'
        path.write_text(page, encoding='utf-8')
        # Kein eigenes --user-data-dir: damit lädt Chrome beim ersten Start Komponenten nach und --dump-dom hängt.
        result = subprocess.run(
            [find_chrome(), '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
             '--allow-file-access-from-files', '--virtual-time-budget=15000', '--dump-dom', path.as_uri()],
            capture_output=True, text=True, timeout=90,
        )
    m = re.search(r'<pre id="out">(.*?)</pre>', result.stdout, re.S)
    if not m or not m.group(1).strip():
        sys.exit(f'Chrome hat keine Bilder geliefert.\n{result.stderr[-2000:]}')
    data = json.loads(html.unescape(m.group(1)))
    if 'error' in data:
        sys.exit(f'Fehler beim Zeichnen: {data["error"]}')
    return data


def main():
    day = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else berlin_today()
    kind = sys.argv[2] if len(sys.argv) > 2 else None
    if kind and kind not in KINDS:
        sys.exit(f'Unbekanntes Format {kind!r}, erlaubt: {", ".join(KINDS)}')
    job = build_job(day, kind)
    data = render(job)

    target = OUT_DIR / day.isoformat()
    target.mkdir(parents=True, exist_ok=True)
    names = []
    for i, b64 in enumerate(data['images'], start=1):
        name = f'{i}.jpg'
        (target / name).write_bytes(base64.b64decode(b64))
        names.append(name)
    post = {'date': day.isoformat(), 'kind': job['kind'], 'title': data['title'],
            'description': f"{data['description']}\n\n{HASHTAGS}", 'images': names}
    (target / 'post.json').write_text(json.dumps(post, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    for old in OUT_DIR.iterdir():
        try:
            too_old = (day - datetime.date.fromisoformat(old.name)).days >= KEEP_DAYS
        except ValueError:
            continue
        if too_old:
            shutil.rmtree(old)
    print(f'{target.relative_to(ROOT)}: {job["kind"]}, {len(names)} Bilder — {data["title"]}')


if __name__ == '__main__':
    main()
