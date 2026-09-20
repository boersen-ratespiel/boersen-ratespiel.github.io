#!/usr/bin/env python3
"""Holt aktuelle Wirtschaftsmeldungen aus frei nutzbaren Quellen (RSS) und schreibt news.json.

Quellen (Nutzungsbedingungen jeweils geprüft, siehe CLAUDE.md):
  - Statistisches Bundesamt (Destatis): "Vervielfältigung und Verbreitung, auch auszugsweise, mit Quellennachweis gestattet"
  - Europäische Zentralbank (EZB): freie Nutzung, wenn die EZB als Quelle genannt und der Inhalt korrekt wiedergegeben wird

Läuft regelmäßig per GitHub Action (.github/workflows/update-news.yml), damit die statische Seite ohne
Backend und ohne Fremd-Requests im Browser echte News zeigen kann.

Nur Standardbibliothek. news.json wird nur neu geschrieben, wenn sich die Meldungen geändert haben
(kein Commit-Rauschen). Schlägt jeder Abruf fehl, bleibt die alte Datei unverändert und das Skript
endet mit Fehlercode 1.
"""

import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

SOURCES = [
    {
        'name': 'Statistisches Bundesamt (Destatis)',
        'url': 'https://www.destatis.de/SiteGlobals/Functions/RSSFeed/DE/RSSNewsfeed/Aktuell.xml',
        'prefix': 'https://www.destatis.de/',
        'lang': 'de',
        'only_relevant': True,  # der Feed enthält auch Gesellschaftsthemen (Familien, Kinder ...), die hier nichts zu suchen haben
    },
    {
        'name': 'Europäische Zentralbank (EZB)',
        'url': 'https://www.ecb.europa.eu/rss/press.xml',
        'prefix': 'https://www.ecb.europa.eu/',
        'lang': 'en',
        'link_contains': '/press/pr/',  # nur Pressemitteilungen; Reden und Interviews tragen Autorennamen und haben strengere Regeln
        'only_relevant': False,
    },
]
MAX_ITEMS = 24
MAX_AGE_DAYS = 14
TEASER_MAX_CHARS = 190
OUT_FILE = Path(__file__).resolve().parent.parent / 'news.json'

DC_DATE = '{http://purl.org/dc/elements/1.1/}date'

# Themen, die für eine Börsen-Lern-App relevant sind (Teilstring-Treffer, Deutsch bei Destatis).
RELEVANT = [
    'preis', 'inflation', 'umsatz', 'auftrag', 'produktion', 'export', 'import', 'handel', 'arbeitsmarkt',
    'erwerbstät', 'arbeitslos', 'beschäftigt', 'insolvenz', 'inlandsprodukt', 'bip$', 'wirtschaft', 'konjunktur',
    'zins', 'steuer', 'schulden', 'finanz', 'lohn', 'verdienst', 'investition', 'bau', 'energie', 'unternehmen',
    'gewinn', 'kredit', 'einkommen', 'konsum', 'gastgewerbe', 'industrie', 'vermögen', 'miete', 'arbeitskosten',
]

# Thema: erste passende Regel gewinnt. Ein '$' am Ende verlangt ein ganzes Wort ('bip$' trifft "BIP", nicht "Bipolar").
CATEGORIES = [
    ('Geldpolitik', ['monetary policy', 'zins', 'ezb$', 'ecb$', 'notenbank', 'interest rate']),
    ('Preise', ['preis', 'inflation', 'teuerung', 'price', 'hicp']),
    ('Arbeit', ['arbeitsmarkt', 'erwerbstät', 'arbeitslos', 'beschäftigt', 'lohn', 'verdienst', 'wage', 'employment', 'arbeitskosten']),
    ('Konjunktur', ['inlandsprodukt', 'bip$', 'gdp$', 'konjunktur', 'auftrag', 'produktion', 'umsatz', 'industrie',
                    'export', 'import', 'handel', 'growth', 'wachstum', 'baugenehm', 'investition']),
]
DEFAULT_CATEGORY = 'Wirtschaft'

HIGH_IMPACT = ['monetary policy', 'leitzins', 'zinsentscheid', 'inflation', 'verbraucherpreis', 'inlandsprodukt',
               'bip$', 'gdp$', 'arbeitslos', 'interest rate']
MID_IMPACT = ['erzeugerpreis', 'großhandelspreis', 'auftragsbestand', 'auftragseingang', 'produktion', 'export',
              'import', 'umsatz', 'konjunktur', 'wage', 'euro area', 'insolvenz', 'industrie']

# Richtung der gemeldeten Zahl. Bewusst KEINE Marktbewertung: "Erzeugerpreise +4,6 %" ist weder gut noch schlecht
# für Anleger, sondern erst einmal nur "die Zahl steigt".
UP_WORDS = ['höher', 'gestiegen', 'steig', 'anstieg', 'zunahme', 'zugenommen', 'wächst', 'wachstum', 'zulegen', 'legt zu',
            'rise', 'rose', 'increase', 'uptick', 'higher', 'grow']
DOWN_WORDS = ['niedriger', 'gesunken', 'sink', 'rückgang', 'abnahme', 'abgenommen', 'geringer', 'schrumpf',
              'decline', 'decrease', 'lower', 'drop', 'fell', 'fall']
SIGNED_UP = re.compile(r'(?<!\w)\+\s?\d')
SIGNED_DOWN = re.compile(r'(?<!\w)[-–−]\s?\d')


def contains(text, words):
    """Teilstring-Treffer (deutsche Komposita: 'preis' trifft "Erzeugerpreise"); '$' am Ende verlangt ein ganzes Wort."""
    for w in words:
        if w.endswith('$'):
            if re.search(r'\b' + re.escape(w[:-1]) + r'\b', text):
                return True
        elif w in text:
            return True
    return False


def word_starts(text, stems):
    """Zählt Stämme, die am Wortanfang stehen ('fall' trifft "Fall", aber nicht "Ausfall")."""
    return sum(1 for s in stems if re.search(r'\b' + re.escape(s), text))


def clean_text(raw):
    text = re.sub(r'<[^>]+>', ' ', raw or '')
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def make_teaser(desc):
    if len(desc) <= TEASER_MAX_CHARS:
        return desc
    cut = desc[:TEASER_MAX_CHARS].rsplit(' ', 1)[0].rstrip(' ,;:-–')
    return cut + ' …'


def detect_trend(headline, desc):
    """'up' / 'down' / 'flat' — Richtung der berichteten Zahl, aus Vorzeichen und Signalwörtern der Überschrift,
    ersatzweise des ersten Satzes im Kurztext. Im Zweifel 'flat': lieber nichts behaupten."""
    title = headline.lower()
    first_sentence = re.split(r'(?<=[.!?])\s', desc.lower(), maxsplit=1)[0]

    up, down = bool(SIGNED_UP.search(headline)), bool(SIGNED_DOWN.search(headline))
    if up != down:
        return 'up' if up else 'down'
    if up and down:
        return 'flat'
    for text in (title, first_sentence):
        u, d = word_starts(text, UP_WORDS), word_starts(text, DOWN_WORDS)
        if u != d:
            return 'up' if u > d else 'down'
        if u:  # gleich viele Treffer -> widersprüchlich
            break
    return 'flat'


def classify(headline, desc):
    title = headline.lower()
    both = title + ' ' + desc.lower()

    category = DEFAULT_CATEGORY
    for name, words in CATEGORIES:
        if contains(title, words):
            category = name
            break

    if contains(title, HIGH_IMPACT):
        impact = 3
    elif contains(both, MID_IMPACT):
        impact = 2
    else:
        impact = 1
    return category, detect_trend(headline, desc), impact


def normalize_link(link):
    # Die EZB liefert Links wie https://www.ecb.europa.eu//press/... — doppelte Schrägstriche im Pfad entfernen.
    return re.sub(r'(?<!:)/{2,}', '/', link.strip())


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'boersen-ratespiel-newsbot/1.0 (+https://boersen-ratespiel.github.io/)'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_items(xml_bytes, source):
    channel = ET.fromstring(xml_bytes).find('channel')
    for item in channel.findall('item'):
        link = normalize_link(item.findtext('link') or '')
        headline = clean_text(item.findtext('title'))
        desc = clean_text(item.findtext('description'))
        if not headline or not link.startswith(source['prefix']) or link.lower().endswith('.pdf'):
            continue
        if 'link_contains' in source and source['link_contains'] not in link:
            continue
        if source['only_relevant'] and not contains((headline + ' ' + desc).lower(), RELEVANT):
            continue
        try:
            iso = item.findtext(DC_DATE)
            published = datetime.fromisoformat(iso.replace('Z', '+00:00')) if iso else parsedate_to_datetime(item.findtext('pubDate'))
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        yield link, headline, desc, published.astimezone(timezone.utc)


def build_items():
    now = datetime.now(timezone.utc)
    by_link = {}
    failures = 0
    for source in SOURCES:
        try:
            for link, headline, desc, published in parse_items(fetch(source['url']), source):
                if (now - published).days > MAX_AGE_DAYS:
                    continue
                by_link[link] = (source, headline, desc, published)
        except Exception as exc:  # eine kaputte Quelle soll die andere nicht mitreißen
            failures += 1
            print(f"Quelle fehlgeschlagen: {source['name']}: {exc}", file=sys.stderr)
    if failures == len(SOURCES):
        return None

    items = []
    for link, (source, headline, desc, published) in sorted(by_link.items(), key=lambda kv: kv[1][3], reverse=True)[:MAX_ITEMS]:
        category, trend, impact = classify(headline, desc)
        items.append({
            'headline': headline,
            'desc': make_teaser(desc),
            'source': source['name'],
            'lang': source['lang'],
            'category': category,
            'trend': trend,
            'impact': impact,
            'url': link,
            'published': published.strftime('%Y-%m-%dT%H:%M:%SZ'),
        })
    return items


def main():
    items = build_items()
    if not items:
        print('Keine Meldungen erhalten — news.json bleibt unverändert.', file=sys.stderr)
        return 1

    if OUT_FILE.exists():
        try:
            if json.loads(OUT_FILE.read_text(encoding='utf-8')).get('items') == items:
                print('Keine neuen Meldungen.')
                return 0
        except (ValueError, OSError):
            pass

    payload = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'items': items,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(items)} Meldungen geschrieben.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
